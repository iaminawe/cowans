"""
GraphQL Optimizer - Advanced GraphQL query optimization for Shopify API

This module provides advanced GraphQL query optimization, batching,
and performance monitoring for the Shopify sync engine.
"""

import json
import time
import logging
import hashlib
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
from datetime import datetime, timedelta

# Optimized GraphQL queries for batch operations
BATCH_PRODUCT_QUERY = """
query getBatchProducts($handles: [String!]!) {
  products: nodes(ids: $handles) {
    ... on Product {
      id
      handle
      title
      bodyHtml
      vendor
      productType
      tags
      variants(first: 5) {
        edges {
          node {
            id
            sku
            price
            inventoryQuantity
            inventoryItem {
              id
              tracked
            }
          }
        }
      }
      metafields(first: 20, namespace: "custom") {
        edges {
          node {
            namespace
            key
            value
            type
          }
        }
      }
      media(first: 10) {
        edges {
          node {
            ... on MediaImage {
              id
              image {
                originalSrc
                url
              }
            }
          }
        }
      }
    }
  }
}
"""

# Optimized batch product creation mutation
BATCH_PRODUCT_CREATE_MUTATION = """
mutation batchProductCreate($products: [ProductInput!]!) {
  results: productCreateMany(products: $products) {
    products {
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

# Optimized product update with minimal fields
MINIMAL_PRODUCT_UPDATE = """
mutation minimalProductUpdate($input: ProductInput!) {
  productUpdate(input: $input) {
    product {
      id
      updatedAt
    }
    userErrors {
      field
      message
    }
  }
}
"""

# Batch variant updates
BATCH_VARIANT_UPDATE_MUTATION = """
mutation batchVariantUpdate($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
  productVariantsBulkUpdate(productId: $productId, variants: $variants) {
    productVariants {
      id
      sku
      price
      inventoryQuantity
    }
    userErrors {
      field
      message
    }
  }
}
"""

# Query to check for existing products by SKU in batch
BATCH_PRODUCT_LOOKUP_BY_SKU = """
query batchProductLookup($skus: [String!]!) {
  products(first: 250, query: $skus) {
    edges {
      node {
        id
        handle
        variants(first: 1) {
          edges {
            node {
              id
              sku
            }
          }
        }
      }
    }
  }
}
"""


@dataclass
class QueryMetrics:
    """Metrics for GraphQL query performance."""
    query_hash: str
    query_type: str
    execution_time: float
    response_size: int
    api_cost: int = 0
    throttle_delay: float = 0
    retry_count: int = 0
    success: bool = True
    error_message: str = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class BatchOperation:
    """Represents a batched GraphQL operation."""
    operation_id: str
    query: str
    variables: Dict[str, Any]
    priority: int = 3  # 1=high, 3=normal, 5=low
    dependencies: List[str] = field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 3
    created_at: datetime = field(default_factory=datetime.utcnow)


class GraphQLBatchProcessor:
    """Processes GraphQL operations in optimized batches."""
    
    def __init__(self, shopify_client, max_batch_size: int = 10):
        self.client = shopify_client
        self.max_batch_size = max_batch_size
        self.pending_operations: List[BatchOperation] = []
        self.query_cache: Dict[str, Any] = {}
        self.metrics: List[QueryMetrics] = []
        self.logger = logging.getLogger(__name__)
    
    def add_operation(self, operation: BatchOperation):
        """Add an operation to the batch queue."""
        self.pending_operations.append(operation)
        
        # Sort by priority
        self.pending_operations.sort(key=lambda x: (x.priority, x.created_at))
    
    def process_batch(self) -> List[Dict[str, Any]]:
        """Process pending operations in optimized batches."""
        if not self.pending_operations:
            return []
        
        results = []
        
        # Group operations by type for optimization
        grouped_ops = self._group_operations_by_type()
        
        for op_type, operations in grouped_ops.items():
            if op_type == "product_lookup":
                batch_results = self._process_product_lookup_batch(operations)
            elif op_type == "product_create":
                batch_results = self._process_product_create_batch(operations)
            elif op_type == "product_update":
                batch_results = self._process_product_update_batch(operations)
            else:
                # Process individually
                batch_results = self._process_individual_operations(operations)
            
            results.extend(batch_results)
        
        # Clear processed operations
        self.pending_operations.clear()
        
        return results
    
    def _group_operations_by_type(self) -> Dict[str, List[BatchOperation]]:
        """Group operations by type for batch optimization."""
        groups = defaultdict(list)
        
        for op in self.pending_operations:
            # Determine operation type based on query content
            if "productByHandle" in op.query or "products(" in op.query:
                groups["product_lookup"].append(op)
            elif "productCreate" in op.query:
                groups["product_create"].append(op)
            elif "productUpdate" in op.query:
                groups["product_update"].append(op)
            else:
                groups["individual"].append(op)
        
        return groups
    
    def _process_product_lookup_batch(self, operations: List[BatchOperation]) -> List[Dict[str, Any]]:
        """Process product lookup operations in batch."""
        if not operations:
            return []
        
        # Extract SKUs from operations
        skus = []
        op_map = {}
        
        for op in operations:
            sku = self._extract_sku_from_variables(op.variables)
            if sku:
                skus.append(sku)
                op_map[sku] = op
        
        if not skus:
            return self._process_individual_operations(operations)
        
        # Build batch query
        sku_query = " OR ".join([f"sku:{sku}" for sku in skus])
        
        try:
            start_time = time.time()
            
            result = self.client.execute_graphql(
                BATCH_PRODUCT_LOOKUP_BY_SKU,
                {"skus": sku_query}
            )
            
            execution_time = time.time() - start_time
            
            # Record metrics
            self._record_query_metrics(
                query_type="batch_product_lookup",
                execution_time=execution_time,
                response_size=len(json.dumps(result)),
                success="errors" not in result
            )
            
            # Process results
            batch_results = []
            products = result.get("data", {}).get("products", {}).get("edges", [])
            
            for product_edge in products:
                product = product_edge["node"]
                variants = product.get("variants", {}).get("edges", [])
                
                if variants:
                    variant = variants[0]["node"]
                    sku = variant.get("sku")
                    
                    if sku in op_map:
                        batch_results.append({
                            "operation_id": op_map[sku].operation_id,
                            "success": True,
                            "data": product,
                            "execution_time": execution_time / len(skus)  # Distributed time
                        })
            
            return batch_results
            
        except Exception as e:
            self.logger.error(f"Batch product lookup failed: {e}")
            # Fallback to individual processing
            return self._process_individual_operations(operations)
    
    def _process_product_create_batch(self, operations: List[BatchOperation]) -> List[Dict[str, Any]]:
        """Process product creation operations in batch."""
        if not operations:
            return []
        
        # Check if batch creation is supported (Shopify Plus feature)
        if len(operations) > 1 and self._supports_batch_creation():
            return self._process_batch_product_creation(operations)
        else:
            return self._process_individual_operations(operations)
    
    def _process_product_update_batch(self, operations: List[BatchOperation]) -> List[Dict[str, Any]]:
        """Process product update operations in batch."""
        # Group updates by product ID for variant batch updates
        product_updates = defaultdict(list)
        individual_updates = []
        
        for op in operations:
            product_id = op.variables.get("input", {}).get("id")
            if product_id and "variants" in op.variables.get("input", {}):
                product_updates[product_id].append(op)
            else:
                individual_updates.append(op)
        
        results = []
        
        # Process variant batch updates
        for product_id, ops in product_updates.items():
            if len(ops) > 1:
                batch_result = self._process_variant_batch_update(product_id, ops)
                results.extend(batch_result)
            else:
                results.extend(self._process_individual_operations(ops))
        
        # Process individual updates
        if individual_updates:
            results.extend(self._process_individual_operations(individual_updates))
        
        return results
    
    def _process_individual_operations(self, operations: List[BatchOperation]) -> List[Dict[str, Any]]:
        """Process operations individually."""
        results = []
        
        for op in operations:
            try:
                start_time = time.time()
                
                result = self.client.execute_graphql(op.query, op.variables)
                
                execution_time = time.time() - start_time
                
                # Record metrics
                self._record_query_metrics(
                    query_type="individual",
                    execution_time=execution_time,
                    response_size=len(json.dumps(result)),
                    success="errors" not in result
                )
                
                results.append({
                    "operation_id": op.operation_id,
                    "success": "errors" not in result,
                    "data": result,
                    "execution_time": execution_time
                })
                
            except Exception as e:
                self.logger.error(f"Individual operation {op.operation_id} failed: {e}")
                results.append({
                    "operation_id": op.operation_id,
                    "success": False,
                    "error": str(e),
                    "execution_time": 0
                })
        
        return results
    
    def _extract_sku_from_variables(self, variables: Dict[str, Any]) -> Optional[str]:
        """Extract SKU from operation variables."""
        # Check various common patterns
        if "sku" in variables:
            return variables["sku"]
        
        input_data = variables.get("input", {})
        if "sku" in input_data:
            return input_data["sku"]
        
        variants = input_data.get("variants", [])
        if variants and isinstance(variants, list) and len(variants) > 0:
            return variants[0].get("sku")
        
        return None
    
    def _supports_batch_creation(self) -> bool:
        """Check if the shop supports batch product creation."""
        # This would typically check shop plan or capabilities
        # For now, assume it's supported
        return True
    
    def _process_batch_product_creation(self, operations: List[BatchOperation]) -> List[Dict[str, Any]]:
        """Process multiple product creations in a single batch."""
        product_inputs = []
        op_map = {}
        
        for i, op in enumerate(operations):
            product_input = op.variables.get("input", {})
            product_inputs.append(product_input)
            op_map[i] = op.operation_id
        
        try:
            start_time = time.time()
            
            result = self.client.execute_graphql(
                BATCH_PRODUCT_CREATE_MUTATION,
                {"products": product_inputs}
            )
            
            execution_time = time.time() - start_time
            
            # Record metrics
            self._record_query_metrics(
                query_type="batch_product_create",
                execution_time=execution_time,
                response_size=len(json.dumps(result)),
                success="errors" not in result
            )
            
            # Process results
            batch_results = []
            results_data = result.get("data", {}).get("results", {})
            products = results_data.get("products", [])
            user_errors = results_data.get("userErrors", [])
            
            for i, product in enumerate(products):
                batch_results.append({
                    "operation_id": op_map.get(i),
                    "success": True,
                    "data": {"productCreate": {"product": product}},
                    "execution_time": execution_time / len(operations)
                })
            
            # Handle errors
            for error in user_errors:
                # Map errors back to operations (simplified)
                batch_results.append({
                    "operation_id": "error",
                    "success": False,
                    "error": error.get("message"),
                    "execution_time": 0
                })
            
            return batch_results
            
        except Exception as e:
            self.logger.error(f"Batch product creation failed: {e}")
            return self._process_individual_operations(operations)
    
    def _process_variant_batch_update(self, product_id: str, operations: List[BatchOperation]) -> List[Dict[str, Any]]:
        """Process variant updates for a single product in batch."""
        variant_inputs = []
        
        for op in operations:
            variants = op.variables.get("input", {}).get("variants", [])
            variant_inputs.extend(variants)
        
        try:
            start_time = time.time()
            
            result = self.client.execute_graphql(
                BATCH_VARIANT_UPDATE_MUTATION,
                {
                    "productId": product_id,
                    "variants": variant_inputs
                }
            )
            
            execution_time = time.time() - start_time
            
            # Record metrics
            self._record_query_metrics(
                query_type="batch_variant_update",
                execution_time=execution_time,
                response_size=len(json.dumps(result)),
                success="errors" not in result
            )
            
            # Create results for each operation
            results = []
            for op in operations:
                results.append({
                    "operation_id": op.operation_id,
                    "success": "errors" not in result,
                    "data": result,
                    "execution_time": execution_time / len(operations)
                })
            
            return results
            
        except Exception as e:
            self.logger.error(f"Batch variant update failed: {e}")
            return self._process_individual_operations(operations)
    
    def _record_query_metrics(self, query_type: str, execution_time: float,
                             response_size: int, success: bool, error_message: str = None):
        """Record query performance metrics."""
        metrics = QueryMetrics(
            query_hash=hashlib.md5(query_type.encode()).hexdigest()[:8],
            query_type=query_type,
            execution_time=execution_time,
            response_size=response_size,
            success=success,
            error_message=error_message
        )
        
        self.metrics.append(metrics)
        
        # Keep only recent metrics (last 1000)
        if len(self.metrics) > 1000:
            self.metrics = self.metrics[-1000:]
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics for GraphQL operations."""
        if not self.metrics:
            return {}
        
        recent_metrics = [m for m in self.metrics if m.timestamp > datetime.utcnow() - timedelta(hours=1)]
        
        if not recent_metrics:
            return {}
        
        total_time = sum(m.execution_time for m in recent_metrics)
        success_count = sum(1 for m in recent_metrics if m.success)
        
        stats_by_type = defaultdict(list)
        for m in recent_metrics:
            stats_by_type[m.query_type].append(m.execution_time)
        
        return {
            "total_operations": len(recent_metrics),
            "success_rate": (success_count / len(recent_metrics)) * 100,
            "total_execution_time": total_time,
            "average_execution_time": total_time / len(recent_metrics),
            "operations_by_type": {
                query_type: {
                    "count": len(times),
                    "avg_time": sum(times) / len(times),
                    "total_time": sum(times)
                }
                for query_type, times in stats_by_type.items()
            }
        }


class QueryOptimizer:
    """Optimizes GraphQL queries for better performance."""
    
    def __init__(self):
        self.field_usage_stats = defaultdict(int)
        self.query_patterns = {}
        self.logger = logging.getLogger(__name__)
    
    def optimize_product_query(self, required_fields: List[str]) -> str:
        """Generate an optimized product query based on required fields."""
        base_fields = ["id", "handle"]
        
        field_mapping = {
            "title": "title",
            "description": "bodyHtml",
            "vendor": "vendor",
            "product_type": "productType",
            "tags": "tags",
            "price": "variants(first: 1) { edges { node { price } } }",
            "sku": "variants(first: 1) { edges { node { sku } } }",
            "inventory": "variants(first: 1) { edges { node { inventoryQuantity } } }",
            "images": "media(first: 5) { edges { node { ... on MediaImage { image { originalSrc } } } } }",
            "metafields": "metafields(first: 10) { edges { node { namespace key value } } }"
        }
        
        query_fields = base_fields.copy()
        
        for field in required_fields:
            if field in field_mapping:
                mapped_field = field_mapping[field]
                if mapped_field not in query_fields:
                    query_fields.append(mapped_field)
                    
                # Track field usage
                self.field_usage_stats[field] += 1
        
        # Build the query
        fields_str = "\n      ".join(query_fields)
        
        query = f"""
        query optimizedProductQuery($handle: String!) {{
          productByHandle(handle: $handle) {{
            {fields_str}
          }}
        }}
        """
        
        return query.strip()
    
    def get_minimal_update_fields(self, changes: Dict[str, Any]) -> Dict[str, Any]:
        """Extract only the fields that need to be updated."""
        # Map of change types to minimal required fields
        minimal_mappings = {
            "price": ["id", "variants"],
            "inventory": ["id", "variants"],
            "title": ["id", "title"],
            "description": ["id", "bodyHtml"],
            "tags": ["id", "tags"],
            "seo": ["id", "seo"],
            "status": ["id", "status"]
        }
        
        minimal_input = {"id": changes.get("id")}
        
        for change_type, fields in minimal_mappings.items():
            if any(field in changes for field in fields[1:]):  # Skip 'id'
                for field in fields[1:]:
                    if field in changes:
                        minimal_input[field] = changes[field]
        
        return minimal_input
    
    def suggest_batch_operations(self, operations: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """Suggest how to batch operations for optimal performance."""
        # Group operations by type and compatibility
        compatible_groups = []
        
        # Group by operation type
        creates = [op for op in operations if op.get("type") == "create"]
        updates = [op for op in operations if op.get("type") == "update"]
        deletes = [op for op in operations if op.get("type") == "delete"]
        
        # Batch creates (up to 10 per batch)
        for i in range(0, len(creates), 10):
            compatible_groups.append(creates[i:i+10])
        
        # Group updates by product (for variant batching)
        updates_by_product = defaultdict(list)
        for update in updates:
            product_id = update.get("product_id")
            if product_id:
                updates_by_product[product_id].append(update)
            else:
                compatible_groups.append([update])  # Individual update
        
        # Add grouped updates
        for product_updates in updates_by_product.values():
            if len(product_updates) > 1:
                compatible_groups.append(product_updates)
            else:
                compatible_groups.append(product_updates)
        
        # Process deletes individually (safer)
        for delete in deletes:
            compatible_groups.append([delete])
        
        return compatible_groups
    
    def get_field_usage_recommendations(self) -> Dict[str, Any]:
        """Get recommendations based on field usage patterns."""
        if not self.field_usage_stats:
            return {}
        
        total_queries = sum(self.field_usage_stats.values())
        
        recommendations = {
            "most_used_fields": sorted(
                self.field_usage_stats.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10],
            "usage_percentages": {
                field: (count / total_queries) * 100
                for field, count in self.field_usage_stats.items()
            },
            "optimization_suggestions": []
        }
        
        # Add specific recommendations
        for field, count in self.field_usage_stats.items():
            usage_percent = (count / total_queries) * 100
            
            if usage_percent < 5:
                recommendations["optimization_suggestions"].append(
                    f"Consider removing '{field}' from default queries (used only {usage_percent:.1f}% of the time)"
                )
            elif usage_percent > 80:
                recommendations["optimization_suggestions"].append(
                    f"'{field}' is used {usage_percent:.1f}% of the time - consider including in all queries"
                )
        
        return recommendations