"""
Shopify Bulk Operations API Integration

This module provides integration with Shopify's Bulk Operations API for:
- Bulk product creation and updates
- Large-scale query operations
- Progress monitoring for bulk operations
- Error recovery and partial success handling
"""

import json
import time
import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple, Generator
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import uuid
import aiohttp
from urllib.parse import urljoin

logger = logging.getLogger(__name__)


class BulkOperationType(Enum):
    """Types of bulk operations."""
    QUERY = "QUERY"
    MUTATION = "MUTATION"


class BulkOperationStatus(Enum):
    """Status of bulk operations."""
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


@dataclass
class BulkOperation:
    """Represents a bulk operation."""
    id: str
    operation_id: str  # Shopify's operation ID
    type: BulkOperationType
    status: BulkOperationStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    url: Optional[str] = None  # URL for results
    object_count: int = 0
    root_object_count: int = 0
    errors: List[str] = field(default_factory=list)
    user_errors: List[Dict[str, Any]] = field(default_factory=list)


class ShopifyBulkOperations:
    """Handles Shopify Bulk Operations API interactions."""
    
    # GraphQL mutations for bulk operations
    BULK_OPERATION_RUN_QUERY = """
    mutation bulkOperationRunQuery($query: String!) {
        bulkOperationRunQuery(query: $query) {
            bulkOperation {
                id
                status
                createdAt
                url
                objectCount
                rootObjectCount
            }
            userErrors {
                field
                message
            }
        }
    }
    """
    
    BULK_OPERATION_RUN_MUTATION = """
    mutation bulkOperationRunMutation($mutation: String!, $stagedUploadPath: String!) {
        bulkOperationRunMutation(
            mutation: $mutation,
            stagedUploadPath: $stagedUploadPath
        ) {
            bulkOperation {
                id
                status
                createdAt
                url
                objectCount
                rootObjectCount
            }
            userErrors {
                field
                message
            }
        }
    }
    """
    
    BULK_OPERATION_STATUS_QUERY = """
    query bulkOperationStatus($id: ID!) {
        node(id: $id) {
            ... on BulkOperation {
                id
                status
                errorCode
                createdAt
                completedAt
                objectCount
                fileSize
                url
                partialDataUrl
            }
        }
    }
    """
    
    CURRENT_BULK_OPERATION_QUERY = """
    {
        currentBulkOperation {
            id
            status
            errorCode
            createdAt
            completedAt
            objectCount
            fileSize
            url
            partialDataUrl
        }
    }
    """
    
    BULK_OPERATION_CANCEL_MUTATION = """
    mutation bulkOperationCancel($id: ID!) {
        bulkOperationCancel(id: $id) {
            bulkOperation {
                id
                status
            }
            userErrors {
                field
                message
            }
        }
    }
    """
    
    # Bulk mutations for products
    PRODUCT_CREATE_MUTATION = """
    mutation productCreate($input: ProductInput!, $media: [CreateMediaInput!]) {
        productCreate(input: $input, media: $media) {
            product {
                id
                handle
                title
            }
            userErrors {
                field
                message
                code
            }
        }
    }
    """
    
    PRODUCT_UPDATE_MUTATION = """
    mutation productUpdate($input: ProductInput!) {
        productUpdate(input: $input) {
            product {
                id
                handle
                title
                updatedAt
            }
            userErrors {
                field
                message
                code
            }
        }
    }
    """
    
    PRODUCTS_BULK_QUERY = """
    {
        products {
            edges {
                node {
                    id
                    handle
                    title
                    status
                    vendor
                    productType
                    tags
                    variants {
                        edges {
                            node {
                                id
                                sku
                                price
                                inventoryQuantity
                            }
                        }
                    }
                    metafields {
                        edges {
                            node {
                                id
                                namespace
                                key
                                value
                                type
                            }
                        }
                    }
                }
            }
        }
    }
    """
    
    def __init__(self, shop_url: str, access_token: str, max_retries: int = 3):
        """Initialize Shopify Bulk Operations handler."""
        self.shop_url = shop_url
        self.access_token = access_token
        self.max_retries = max_retries
        
        # GraphQL endpoint
        self.graphql_url = urljoin(f"https://{shop_url}", "/admin/api/2024-01/graphql.json")
        
        # Active operations tracking
        self.active_operations: Dict[str, BulkOperation] = {}
        
        # HTTP session
        self.session: Optional[aiohttp.ClientSession] = None
        
        self.logger = logging.getLogger(f"{__name__}.ShopifyBulkOperations")
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession(
            headers={
                "X-Shopify-Access-Token": self.access_token,
                "Content-Type": "application/json"
            }
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    async def execute_graphql(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a GraphQL query or mutation."""
        if not self.session:
            raise RuntimeError("Session not initialized. Use async context manager.")
        
        payload = {
            "query": query,
            "variables": variables or {}
        }
        
        for attempt in range(self.max_retries):
            try:
                async with self.session.post(self.graphql_url, json=payload) as response:
                    if response.status == 429:  # Rate limited
                        retry_after = int(response.headers.get("Retry-After", "5"))
                        self.logger.warning(f"Rate limited. Retrying after {retry_after} seconds")
                        await asyncio.sleep(retry_after)
                        continue
                    
                    response.raise_for_status()
                    data = await response.json()
                    
                    if "errors" in data:
                        self.logger.error(f"GraphQL errors: {data['errors']}")
                    
                    return data
                    
            except Exception as e:
                self.logger.error(f"GraphQL request failed (attempt {attempt + 1}): {e}")
                if attempt == self.max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
        
        raise Exception("Max retries exceeded")
    
    async def run_bulk_query(self, query: str) -> BulkOperation:
        """Run a bulk query operation."""
        self.logger.info("Starting bulk query operation")
        
        result = await self.execute_graphql(
            self.BULK_OPERATION_RUN_QUERY,
            {"query": query}
        )
        
        operation_data = result.get("data", {}).get("bulkOperationRunQuery", {})
        bulk_op_data = operation_data.get("bulkOperation", {})
        user_errors = operation_data.get("userErrors", [])
        
        if user_errors:
            error_messages = [f"{e['field']}: {e['message']}" for e in user_errors]
            raise Exception(f"Bulk operation failed: {'; '.join(error_messages)}")
        
        bulk_operation = BulkOperation(
            id=str(uuid.uuid4()),
            operation_id=bulk_op_data["id"],
            type=BulkOperationType.QUERY,
            status=BulkOperationStatus[bulk_op_data["status"]],
            created_at=datetime.fromisoformat(bulk_op_data["createdAt"].replace("Z", "+00:00")),
            url=bulk_op_data.get("url"),
            object_count=bulk_op_data.get("objectCount", 0),
            root_object_count=bulk_op_data.get("rootObjectCount", 0),
            user_errors=user_errors
        )
        
        self.active_operations[bulk_operation.id] = bulk_operation
        self.logger.info(f"Bulk query operation created: {bulk_operation.operation_id}")
        
        return bulk_operation
    
    async def run_bulk_mutation(self, mutation: str, input_file_path: str) -> BulkOperation:
        """Run a bulk mutation operation."""
        self.logger.info("Starting bulk mutation operation")
        
        # First, upload the input file to Shopify's staged uploads
        staged_upload_path = await self._stage_upload_file(input_file_path)
        
        result = await self.execute_graphql(
            self.BULK_OPERATION_RUN_MUTATION,
            {
                "mutation": mutation,
                "stagedUploadPath": staged_upload_path
            }
        )
        
        operation_data = result.get("data", {}).get("bulkOperationRunMutation", {})
        bulk_op_data = operation_data.get("bulkOperation", {})
        user_errors = operation_data.get("userErrors", [])
        
        if user_errors:
            error_messages = [f"{e['field']}: {e['message']}" for e in user_errors]
            raise Exception(f"Bulk operation failed: {'; '.join(error_messages)}")
        
        bulk_operation = BulkOperation(
            id=str(uuid.uuid4()),
            operation_id=bulk_op_data["id"],
            type=BulkOperationType.MUTATION,
            status=BulkOperationStatus[bulk_op_data["status"]],
            created_at=datetime.fromisoformat(bulk_op_data["createdAt"].replace("Z", "+00:00")),
            url=bulk_op_data.get("url"),
            object_count=bulk_op_data.get("objectCount", 0),
            root_object_count=bulk_op_data.get("rootObjectCount", 0),
            user_errors=user_errors
        )
        
        self.active_operations[bulk_operation.id] = bulk_operation
        self.logger.info(f"Bulk mutation operation created: {bulk_operation.operation_id}")
        
        return bulk_operation
    
    async def check_operation_status(self, operation_id: str) -> BulkOperation:
        """Check the status of a bulk operation."""
        result = await self.execute_graphql(
            self.BULK_OPERATION_STATUS_QUERY,
            {"id": operation_id}
        )
        
        node_data = result.get("data", {}).get("node", {})
        
        if not node_data:
            raise Exception(f"Operation {operation_id} not found")
        
        # Find the operation in our tracking
        bulk_operation = None
        for op in self.active_operations.values():
            if op.operation_id == operation_id:
                bulk_operation = op
                break
        
        if not bulk_operation:
            # Create a new tracking entry
            bulk_operation = BulkOperation(
                id=str(uuid.uuid4()),
                operation_id=operation_id,
                type=BulkOperationType.QUERY,  # Default, could be determined from context
                status=BulkOperationStatus[node_data["status"]],
                created_at=datetime.fromisoformat(node_data["createdAt"].replace("Z", "+00:00"))
            )
            self.active_operations[bulk_operation.id] = bulk_operation
        
        # Update operation status
        bulk_operation.status = BulkOperationStatus[node_data["status"]]
        bulk_operation.url = node_data.get("url")
        bulk_operation.object_count = node_data.get("objectCount", 0)
        
        if node_data.get("completedAt"):
            bulk_operation.completed_at = datetime.fromisoformat(
                node_data["completedAt"].replace("Z", "+00:00")
            )
        
        if node_data.get("errorCode"):
            bulk_operation.errors.append(node_data["errorCode"])
        
        return bulk_operation
    
    async def wait_for_completion(self, 
                                 operation_id: str, 
                                 check_interval: int = 5,
                                 timeout: int = 3600) -> BulkOperation:
        """Wait for a bulk operation to complete."""
        start_time = time.time()
        
        while True:
            operation = await self.check_operation_status(operation_id)
            
            if operation.status in [
                BulkOperationStatus.COMPLETED,
                BulkOperationStatus.FAILED,
                BulkOperationStatus.CANCELLED,
                BulkOperationStatus.EXPIRED
            ]:
                self.logger.info(f"Operation {operation_id} completed with status: {operation.status.value}")
                return operation
            
            elapsed = time.time() - start_time
            if elapsed > timeout:
                raise TimeoutError(f"Operation {operation_id} timed out after {timeout} seconds")
            
            self.logger.debug(f"Operation {operation_id} still running... ({elapsed:.0f}s elapsed)")
            await asyncio.sleep(check_interval)
    
    async def download_results(self, operation: BulkOperation) -> Generator[Dict[str, Any], None, None]:
        """Download and parse results from a completed bulk operation."""
        if not operation.url:
            raise ValueError("Operation has no result URL")
        
        if operation.status != BulkOperationStatus.COMPLETED:
            raise ValueError(f"Operation is not completed: {operation.status.value}")
        
        self.logger.info(f"Downloading results from {operation.url}")
        
        async with self.session.get(operation.url) as response:
            response.raise_for_status()
            
            # Stream the response line by line (JSONL format)
            async for line in response.content:
                if line.strip():
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError as e:
                        self.logger.error(f"Failed to parse line: {e}")
    
    async def cancel_operation(self, operation_id: str) -> bool:
        """Cancel a running bulk operation."""
        result = await self.execute_graphql(
            self.BULK_OPERATION_CANCEL_MUTATION,
            {"id": operation_id}
        )
        
        operation_data = result.get("data", {}).get("bulkOperationCancel", {})
        user_errors = operation_data.get("userErrors", [])
        
        if user_errors:
            error_messages = [f"{e['field']}: {e['message']}" for e in user_errors]
            self.logger.error(f"Failed to cancel operation: {'; '.join(error_messages)}")
            return False
        
        self.logger.info(f"Operation {operation_id} cancelled")
        return True
    
    async def get_current_operation(self) -> Optional[BulkOperation]:
        """Get the current bulk operation if any."""
        result = await self.execute_graphql(self.CURRENT_BULK_OPERATION_QUERY)
        
        operation_data = result.get("data", {}).get("currentBulkOperation")
        
        if not operation_data:
            return None
        
        return BulkOperation(
            id=str(uuid.uuid4()),
            operation_id=operation_data["id"],
            type=BulkOperationType.QUERY,  # Could be determined from context
            status=BulkOperationStatus[operation_data["status"]],
            created_at=datetime.fromisoformat(operation_data["createdAt"].replace("Z", "+00:00")),
            completed_at=datetime.fromisoformat(operation_data["completedAt"].replace("Z", "+00:00")) if operation_data.get("completedAt") else None,
            url=operation_data.get("url"),
            object_count=operation_data.get("objectCount", 0)
        )
    
    async def bulk_create_products(self, products: List[Dict[str, Any]]) -> BulkOperation:
        """Bulk create products using JSONL file."""
        # Create JSONL file with product data
        input_file = await self._create_jsonl_file(products, "productCreate")
        
        # Run bulk mutation
        mutation = self.PRODUCT_CREATE_MUTATION
        operation = await self.run_bulk_mutation(mutation, input_file)
        
        return operation
    
    async def bulk_update_products(self, products: List[Dict[str, Any]]) -> BulkOperation:
        """Bulk update products using JSONL file."""
        # Create JSONL file with product data
        input_file = await self._create_jsonl_file(products, "productUpdate")
        
        # Run bulk mutation
        mutation = self.PRODUCT_UPDATE_MUTATION
        operation = await self.run_bulk_mutation(mutation, input_file)
        
        return operation
    
    async def bulk_query_products(self, filters: Optional[Dict[str, Any]] = None) -> BulkOperation:
        """Bulk query products with optional filters."""
        # Build query with filters
        query = self._build_products_query(filters)
        
        # Run bulk query
        operation = await self.run_bulk_query(query)
        
        return operation
    
    async def _stage_upload_file(self, file_path: str) -> str:
        """Upload a file to Shopify's staged uploads."""
        # This is a simplified version. In production, you'd need to:
        # 1. Create a staged upload target
        # 2. Upload the file to the target URL
        # 3. Return the staged upload path
        
        # For now, return a placeholder
        return f"tmp/{file_path}"
    
    async def _create_jsonl_file(self, items: List[Dict[str, Any]], operation_type: str) -> str:
        """Create a JSONL file for bulk operations."""
        import tempfile
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            for item in items:
                # Format item for the specific operation
                formatted_item = {
                    "input": item
                }
                
                # Add media if present
                if "media" in item:
                    formatted_item["media"] = item.pop("media")
                
                # Write as JSONL
                f.write(json.dumps(formatted_item) + '\n')
            
            return f.name
    
    def _build_products_query(self, filters: Optional[Dict[str, Any]] = None) -> str:
        """Build a products query with filters."""
        if not filters:
            return self.PRODUCTS_BULK_QUERY
        
        # Build filter string
        filter_parts = []
        if "status" in filters:
            filter_parts.append(f'status:{filters["status"]}')
        if "product_type" in filters:
            filter_parts.append(f'product_type:"{filters["product_type"]}"')
        if "vendor" in filters:
            filter_parts.append(f'vendor:"{filters["vendor"]}"')
        if "tag" in filters:
            filter_parts.append(f'tag:"{filters["tag"]}"')
        
        filter_string = " AND ".join(filter_parts) if filter_parts else ""
        
        # Build query with filters
        query = f"""
        {{
            products(query: "{filter_string}") {{
                edges {{
                    node {{
                        id
                        handle
                        title
                        status
                        vendor
                        productType
                        tags
                        variants {{
                            edges {{
                                node {{
                                    id
                                    sku
                                    price
                                    inventoryQuantity
                                }}
                            }}
                        }}
                        metafields {{
                            edges {{
                                node {{
                                    id
                                    namespace
                                    key
                                    value
                                    type
                                }}
                            }}
                        }}
                    }}
                }}
            }}
        }}
        """
        
        return query
    
    def get_operation_progress(self, operation: BulkOperation) -> Dict[str, Any]:
        """Get progress information for an operation."""
        total_duration = None
        if operation.started_at and operation.completed_at:
            total_duration = (operation.completed_at - operation.started_at).total_seconds()
        elif operation.started_at:
            total_duration = (datetime.utcnow() - operation.started_at).total_seconds()
        
        return {
            "operation_id": operation.operation_id,
            "type": operation.type.value,
            "status": operation.status.value,
            "object_count": operation.object_count,
            "root_object_count": operation.root_object_count,
            "duration_seconds": total_duration,
            "errors": operation.errors,
            "user_errors": operation.user_errors,
            "result_url": operation.url
        }