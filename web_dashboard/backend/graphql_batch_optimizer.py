"""
Enhanced GraphQL Batch Optimizer for Shopify API

This module enhances the existing GraphQL optimizer with:
- Query fragments for common fields
- Dynamic field selection based on sync type
- Query cost prediction and optimization
- Batch mutation grouping
- Connection pooling for GraphQL requests
"""

import hashlib
import json
import time
import logging
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
import asyncio
import aiohttp
from urllib.parse import urljoin

logger = logging.getLogger(__name__)


# Common GraphQL fragments for reuse
PRODUCT_BASIC_FIELDS = """
fragment ProductBasicFields on Product {
    id
    handle
    title
    status
    vendor
    productType
    tags
    createdAt
    updatedAt
}
"""

PRODUCT_VARIANT_FIELDS = """
fragment ProductVariantFields on ProductVariant {
    id
    sku
    price
    compareAtPrice
    barcode
    weight
    weightUnit
    inventoryQuantity
    inventoryPolicy
    requiresShipping
    taxable
}
"""

PRODUCT_IMAGE_FIELDS = """
fragment ProductImageFields on MediaImage {
    id
    image {
        url
        altText
        width
        height
    }
}
"""

PRODUCT_METAFIELD_FIELDS = """
fragment ProductMetafieldFields on Metafield {
    id
    namespace
    key
    value
    type
}
"""

PRODUCT_SEO_FIELDS = """
fragment ProductSeoFields on SEO {
    title
    description
}
"""


@dataclass
class QueryCost:
    """Represents the cost of a GraphQL query."""
    requested_cost: int = 0
    actual_cost: int = 0
    throttle_status: str = "OK"
    currently_available: int = 1000
    restore_rate: int = 50
    
    @property
    def cost_ratio(self) -> float:
        """Calculate the ratio of actual to requested cost."""
        if self.requested_cost == 0:
            return 0
        return self.actual_cost / self.requested_cost


@dataclass
class BatchedMutation:
    """Represents a batched mutation operation."""
    id: str
    mutations: List[Dict[str, Any]]
    operation_type: str
    priority: int = 3
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def size(self) -> int:
        """Get the number of mutations in this batch."""
        return len(self.mutations)


class QueryFieldSelector:
    """Dynamically selects fields based on operation requirements."""
    
    # Field sets for different operations
    FIELD_SETS = {
        "minimal": ["id", "handle"],
        "basic": ["id", "handle", "title", "status", "vendor", "productType", "tags"],
        "inventory": ["id", "variants { edges { node { id sku inventoryQuantity } } }"],
        "pricing": ["id", "variants { edges { node { id sku price compareAtPrice } } }"],
        "full": ["id", "handle", "title", "bodyHtml", "status", "vendor", "productType", "tags",
                 "variants { edges { node { ...ProductVariantFields } } }",
                 "media { edges { node { ...ProductImageFields } } }",
                 "metafields { edges { node { ...ProductMetafieldFields } } }",
                 "seo { ...ProductSeoFields }"],
        "sync_check": ["id", "handle", "updatedAt", "variants { edges { node { id updatedAt } } }"]
    }
    
    @classmethod
    def select_fields(cls, operation_type: str, requirements: Optional[Set[str]] = None) -> List[str]:
        """Select appropriate fields for the operation."""
        if requirements:
            # Build custom field set based on requirements
            fields = set(["id", "handle"])  # Always include these
            
            for requirement in requirements:
                if requirement in cls.FIELD_SETS:
                    fields.update(cls.FIELD_SETS[requirement])
                else:
                    # Add individual field if not a predefined set
                    fields.add(requirement)
            
            return list(fields)
        
        # Use predefined field set
        return cls.FIELD_SETS.get(operation_type, cls.FIELD_SETS["basic"])


class QueryCostPredictor:
    """Predicts GraphQL query costs before execution."""
    
    # Base costs for different operations
    BASE_COSTS = {
        "product": 1,
        "variant": 1,
        "media": 1,
        "metafield": 1,
        "collection": 1
    }
    
    # Connection costs
    CONNECTION_COSTS = {
        "first": lambda n: n,  # Cost equals number of items requested
        "last": lambda n: n,
        "after": lambda n: n,
        "before": lambda n: n
    }
    
    @classmethod
    def predict_cost(cls, query: str, variables: Optional[Dict[str, Any]] = None) -> int:
        """Predict the cost of a GraphQL query."""
        cost = 0
        
        # Count entity queries
        for entity, base_cost in cls.BASE_COSTS.items():
            count = query.lower().count(entity)
            cost += count * base_cost
        
        # Account for connections
        if "first:" in query:
            # Extract connection sizes
            import re
            matches = re.findall(r'first:\s*(\d+)', query)
            for match in matches:
                cost += int(match)
        
        # Account for bulk operations
        if variables:
            if "ids" in variables and isinstance(variables["ids"], list):
                cost += len(variables["ids"])
            if "handles" in variables and isinstance(variables["handles"], list):
                cost += len(variables["handles"])
        
        # Add buffer for nested fields
        nested_depth = query.count("{")
        cost += nested_depth * 2
        
        return max(cost, 1)  # Minimum cost of 1


class GraphQLConnectionPool:
    """Manages a pool of connections for GraphQL requests."""
    
    def __init__(self, 
                 shop_url: str,
                 access_token: str,
                 pool_size: int = 10,
                 timeout: int = 30):
        """Initialize connection pool."""
        self.shop_url = shop_url
        self.access_token = access_token
        self.pool_size = pool_size
        self.timeout = timeout
        
        self.graphql_url = urljoin(f"https://{shop_url}", "/admin/api/2024-01/graphql.json")
        self.connector: Optional[aiohttp.TCPConnector] = None
        self.session: Optional[aiohttp.ClientSession] = None
        
        self.logger = logging.getLogger(f"{__name__}.GraphQLConnectionPool")
    
    async def __aenter__(self):
        """Enter async context."""
        self.connector = aiohttp.TCPConnector(
            limit=self.pool_size,
            limit_per_host=self.pool_size
        )
        
        self.session = aiohttp.ClientSession(
            connector=self.connector,
            headers={
                "X-Shopify-Access-Token": self.access_token,
                "Content-Type": "application/json"
            },
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        )
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context."""
        if self.session:
            await self.session.close()
        if self.connector:
            await self.connector.close()
    
    async def execute(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a GraphQL query using the connection pool."""
        if not self.session:
            raise RuntimeError("Session not initialized")
        
        payload = {
            "query": query,
            "variables": variables or {}
        }
        
        async with self.session.post(self.graphql_url, json=payload) as response:
            response.raise_for_status()
            return await response.json()


class GraphQLBatchOptimizer:
    """Enhanced GraphQL batch optimizer with advanced features."""
    
    def __init__(self,
                 shop_url: str,
                 access_token: str,
                 max_batch_size: int = 50,
                 max_query_cost: int = 1000):
        """Initialize the batch optimizer."""
        self.shop_url = shop_url
        self.access_token = access_token
        self.max_batch_size = max_batch_size
        self.max_query_cost = max_query_cost
        
        # Components
        self.field_selector = QueryFieldSelector()
        self.cost_predictor = QueryCostPredictor()
        self.connection_pool: Optional[GraphQLConnectionPool] = None
        
        # Query cache with TTL
        self.query_cache: Dict[str, Tuple[Any, datetime]] = {}
        self.cache_ttl = timedelta(minutes=5)
        
        # Metrics
        self.query_metrics: List[QueryCost] = []
        self.cache_hits = 0
        self.cache_misses = 0
        
        self.logger = logging.getLogger(__name__)
    
    async def __aenter__(self):
        """Enter async context."""
        self.connection_pool = await GraphQLConnectionPool(
            self.shop_url,
            self.access_token
        ).__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context."""
        if self.connection_pool:
            await self.connection_pool.__aexit__(exc_type, exc_val, exc_tb)
    
    def build_optimized_query(self,
                             operation: str,
                             requirements: Optional[Set[str]] = None,
                             include_fragments: bool = True) -> str:
        """Build an optimized GraphQL query."""
        # Select fields based on operation
        fields = self.field_selector.select_fields(operation, requirements)
        
        # Build fragments if needed
        fragments = ""
        if include_fragments:
            fragment_names = set()
            for field in fields:
                if "ProductVariantFields" in field:
                    fragment_names.add(PRODUCT_VARIANT_FIELDS)
                elif "ProductImageFields" in field:
                    fragment_names.add(PRODUCT_IMAGE_FIELDS)
                elif "ProductMetafieldFields" in field:
                    fragment_names.add(PRODUCT_METAFIELD_FIELDS)
                elif "ProductSeoFields" in field:
                    fragment_names.add(PRODUCT_SEO_FIELDS)
            
            fragments = "\n".join(fragment_names)
        
        # Build query structure
        field_string = "\n    ".join(fields)
        
        if operation == "products_by_ids":
            query = f"""
            {fragments}
            
            query GetProductsByIds($ids: [ID!]!) {{
                nodes(ids: $ids) {{
                    ... on Product {{
                        {field_string}
                    }}
                }}
            }}
            """
        elif operation == "products_by_handles":
            query = f"""
            {fragments}
            
            query GetProductsByHandles($handles: [String!]!) {{
                products(first: {min(len(requirements or []), 250)}, query: $handles) {{
                    edges {{
                        node {{
                            {field_string}
                        }}
                    }}
                }}
            }}
            """
        else:
            query = f"""
            {fragments}
            
            query GetProducts {{
                products(first: 10) {{
                    edges {{
                        node {{
                            {field_string}
                        }}
                    }}
                }}
            }}
            """
        
        return query.strip()
    
    def batch_mutations(self, mutations: List[Dict[str, Any]]) -> List[BatchedMutation]:
        """Group mutations into optimal batches."""
        # Group by mutation type
        grouped = defaultdict(list)
        for mutation in mutations:
            mutation_type = mutation.get("type", "unknown")
            grouped[mutation_type].append(mutation)
        
        # Create batches respecting size and cost limits
        batches = []
        
        for mutation_type, items in grouped.items():
            current_batch = []
            current_cost = 0
            
            for item in items:
                # Predict cost for this item
                item_cost = self.cost_predictor.predict_cost(
                    item.get("query", ""),
                    item.get("variables", {})
                )
                
                # Check if adding this item would exceed limits
                if (len(current_batch) >= self.max_batch_size or
                    current_cost + item_cost > self.max_query_cost):
                    # Save current batch and start new one
                    if current_batch:
                        batches.append(BatchedMutation(
                            id=f"{mutation_type}_{len(batches)}",
                            mutations=current_batch,
                            operation_type=mutation_type
                        ))
                    current_batch = [item]
                    current_cost = item_cost
                else:
                    current_batch.append(item)
                    current_cost += item_cost
            
            # Save final batch
            if current_batch:
                batches.append(BatchedMutation(
                    id=f"{mutation_type}_{len(batches)}",
                    mutations=current_batch,
                    operation_type=mutation_type
                ))
        
        # Sort by priority
        batches.sort(key=lambda b: b.priority)
        
        return batches
    
    async def execute_with_caching(self,
                                  query: str,
                                  variables: Optional[Dict[str, Any]] = None,
                                  cache_key: Optional[str] = None) -> Dict[str, Any]:
        """Execute a query with caching support."""
        # Generate cache key if not provided
        if not cache_key:
            key_data = f"{query}{json.dumps(variables or {}, sort_keys=True)}"
            cache_key = hashlib.md5(key_data.encode()).hexdigest()
        
        # Check cache
        if cache_key in self.query_cache:
            cached_result, cached_time = self.query_cache[cache_key]
            if datetime.utcnow() - cached_time < self.cache_ttl:
                self.cache_hits += 1
                self.logger.debug(f"Cache hit for key: {cache_key}")
                return cached_result
            else:
                # Remove expired entry
                del self.query_cache[cache_key]
        
        self.cache_misses += 1
        
        # Execute query
        if not self.connection_pool:
            raise RuntimeError("Connection pool not initialized")
        
        start_time = time.time()
        result = await self.connection_pool.execute(query, variables)
        execution_time = time.time() - start_time
        
        # Extract cost information from response
        extensions = result.get("extensions", {})
        cost_info = extensions.get("cost", {})
        
        query_cost = QueryCost(
            requested_cost=cost_info.get("requestedQueryCost", 0),
            actual_cost=cost_info.get("actualQueryCost", 0),
            throttle_status=cost_info.get("throttleStatus", {}).get("status", "OK"),
            currently_available=cost_info.get("throttleStatus", {}).get("currentlyAvailable", 1000),
            restore_rate=cost_info.get("throttleStatus", {}).get("restoreRate", 50)
        )
        
        self.query_metrics.append(query_cost)
        
        # Log if approaching rate limits
        if query_cost.currently_available < 200:
            self.logger.warning(
                f"Low rate limit availability: {query_cost.currently_available} "
                f"(restore rate: {query_cost.restore_rate}/s)"
            )
        
        # Cache successful results
        if "errors" not in result:
            self.query_cache[cache_key] = (result, datetime.utcnow())
            
            # Limit cache size
            if len(self.query_cache) > 1000:
                # Remove oldest entries
                sorted_cache = sorted(
                    self.query_cache.items(),
                    key=lambda x: x[1][1]
                )
                self.query_cache = dict(sorted_cache[-500:])
        
        return result
    
    async def execute_batch(self, batch: BatchedMutation) -> List[Dict[str, Any]]:
        """Execute a batch of mutations efficiently."""
        results = []
        
        # Execute mutations with rate limit awareness
        for mutation in batch.mutations:
            # Check current rate limit status
            if self.query_metrics:
                latest_cost = self.query_metrics[-1]
                if latest_cost.currently_available < 100:
                    # Wait for rate limit to recover
                    wait_time = 100 / latest_cost.restore_rate
                    self.logger.info(f"Waiting {wait_time:.1f}s for rate limit recovery")
                    await asyncio.sleep(wait_time)
            
            # Execute mutation
            result = await self.connection_pool.execute(
                mutation["query"],
                mutation.get("variables")
            )
            results.append(result)
        
        return results
    
    def optimize_query_for_sync(self,
                               sync_type: str,
                               entity_ids: List[str],
                               additional_fields: Optional[Set[str]] = None) -> Tuple[str, Dict[str, Any]]:
        """Optimize a query for a specific sync operation."""
        # Determine required fields based on sync type
        if sync_type == "inventory_only":
            requirements = {"inventory"}
        elif sync_type == "price_only":
            requirements = {"pricing"}
        elif sync_type == "status_only":
            requirements = {"minimal", "status"}
        elif sync_type == "full_sync":
            requirements = {"full"}
        else:
            requirements = {"basic"}
        
        # Add any additional fields
        if additional_fields:
            requirements.update(additional_fields)
        
        # Build optimized query
        query = self.build_optimized_query("products_by_ids", requirements)
        
        # Prepare variables
        variables = {"ids": entity_ids}
        
        # Predict cost
        predicted_cost = self.cost_predictor.predict_cost(query, variables)
        
        self.logger.debug(
            f"Optimized query for {sync_type} with {len(entity_ids)} entities. "
            f"Predicted cost: {predicted_cost}"
        )
        
        return query, variables
    
    def get_optimization_stats(self) -> Dict[str, Any]:
        """Get optimization statistics."""
        total_queries = len(self.query_metrics)
        
        if total_queries == 0:
            return {
                "total_queries": 0,
                "cache_hit_rate": 0,
                "average_cost_ratio": 0,
                "total_cost_saved": 0
            }
        
        # Calculate metrics
        total_requested = sum(m.requested_cost for m in self.query_metrics)
        total_actual = sum(m.actual_cost for m in self.query_metrics)
        cache_requests = self.cache_hits + self.cache_misses
        
        return {
            "total_queries": total_queries,
            "cache_hit_rate": (self.cache_hits / cache_requests * 100) if cache_requests > 0 else 0,
            "average_cost_ratio": total_actual / total_requested if total_requested > 0 else 0,
            "total_cost_saved": total_requested - total_actual,
            "cache_size": len(self.query_cache),
            "average_query_cost": total_actual / total_queries
        }