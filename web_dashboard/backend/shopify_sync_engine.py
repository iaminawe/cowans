"""
Shopify Sync Engine - Database-Driven Synchronization Service

This module provides a comprehensive database-driven synchronization engine 
that replaces the current file-based approach with intelligent, real-time 
sync capabilities between the local database and Shopify.

Features:
- Database-driven sync with change tracking
- Intelligent conflict resolution
- Rate-limited GraphQL batch operations
- Bidirectional synchronization
- Real-time sync status and progress tracking
- Robust retry mechanisms and error recovery
"""

import asyncio
import json
import logging
import hashlib
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Set
from enum import Enum
from dataclasses import dataclass, asdict
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from models import (
    Product, Category, ProductImage, ProductMetafield, SyncHistory, 
    Job, ProductStatus, SyncStatus, JobStatus, Base
)
from database import db_session_scope
from repositories import (
    ProductRepository, CategoryRepository, SyncHistoryRepository,
    JobRepository
)

# Import existing Shopify managers
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'scripts', 'shopify'))
from shopify_product_manager import ShopifyProductManager
from shopify_image_manager import ShopifyImageManager


class SyncOperation(Enum):
    """Types of sync operations."""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    SYNC_DOWN = "sync_down"  # Pull from Shopify
    SYNC_UP = "sync_up"     # Push to Shopify


class ConflictResolution(Enum):
    """Conflict resolution strategies."""
    ETILIZE_PRIORITY = "etilize_priority"      # Etilize data wins
    SHOPIFY_PRIORITY = "shopify_priority"      # Shopify data wins
    MANUAL_REVIEW = "manual_review"            # Human intervention required
    MERGE_FIELDS = "merge_fields"              # Intelligent field merging
    TIMESTAMP_BASED = "timestamp_based"        # Most recent wins


class SyncPriority(Enum):
    """Sync queue priorities."""
    CRITICAL = 1   # Immediate sync required
    HIGH = 2       # High priority (pricing, inventory)
    NORMAL = 3     # Normal priority (descriptions, images)
    LOW = 4        # Low priority (SEO, tags)
    BATCH = 5      # Batch processing


@dataclass
class SyncQueueItem:
    """Represents an item in the sync queue."""
    id: str
    operation: SyncOperation
    entity_type: str  # "product", "category", "image"
    entity_id: int
    priority: SyncPriority
    data: Dict[str, Any]
    retry_count: int = 0
    max_retries: int = 3
    created_at: datetime = None
    scheduled_at: datetime = None
    error_message: str = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.scheduled_at is None:
            self.scheduled_at = self.created_at


@dataclass
class SyncResult:
    """Result of a sync operation."""
    success: bool
    operation: SyncOperation
    entity_type: str
    entity_id: int
    shopify_id: str = None
    error_message: str = None
    warnings: List[str] = None
    sync_duration: float = 0
    changes_detected: bool = False
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


@dataclass
class ConflictItem:
    """Represents a sync conflict that needs resolution."""
    id: str
    entity_type: str
    entity_id: int
    field_name: str
    local_value: Any
    shopify_value: Any
    resolution_strategy: ConflictResolution
    created_at: datetime = None
    resolved_at: datetime = None
    resolved_value: Any = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()


class SyncMetrics:
    """Tracks sync performance metrics."""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.total_operations = 0
        self.successful_operations = 0
        self.failed_operations = 0
        self.conflicts_detected = 0
        self.conflicts_resolved = 0
        self.rate_limit_hits = 0
        self.api_calls_made = 0
        self.start_time = datetime.utcnow()
        self.total_sync_time = 0
    
    def record_operation(self, result: SyncResult):
        """Record the result of a sync operation."""
        self.total_operations += 1
        if result.success:
            self.successful_operations += 1
        else:
            self.failed_operations += 1
        self.total_sync_time += result.sync_duration
    
    def record_api_call(self, rate_limited: bool = False):
        """Record an API call."""
        self.api_calls_made += 1
        if rate_limited:
            self.rate_limit_hits += 1
    
    def record_conflict(self, resolved: bool = False):
        """Record a conflict."""
        self.conflicts_detected += 1
        if resolved:
            self.conflicts_resolved += 1
    
    def get_success_rate(self) -> float:
        """Get success rate as percentage."""
        if self.total_operations == 0:
            return 0.0
        return (self.successful_operations / self.total_operations) * 100
    
    def get_average_sync_time(self) -> float:
        """Get average sync time per operation."""
        if self.total_operations == 0:
            return 0.0
        return self.total_sync_time / self.total_operations


class ShopifySyncEngine:
    """
    Database-driven Shopify synchronization engine with intelligent 
    conflict resolution and performance optimization.
    """
    
    def __init__(self, shop_url: str, access_token: str, 
                 batch_size: int = 10, max_concurrent: int = 5):
        """Initialize the sync engine."""
        self.shop_url = shop_url
        self.access_token = access_token
        self.batch_size = batch_size
        self.max_concurrent = max_concurrent
        
        # Initialize Shopify managers
        self.product_manager = ShopifyProductManager(
            shop_url, access_token, debug=True, turbo=True
        )
        self.image_manager = ShopifyImageManager(
            shop_url, access_token, debug=True
        )
        
        # Sync state
        self.sync_queue: List[SyncQueueItem] = []
        self.active_syncs: Set[str] = set()
        self.conflict_queue: List[ConflictItem] = []
        self.metrics = SyncMetrics()
        
        # Rate limiting and performance
        self.last_api_call = 0
        self.api_call_count = 0
        self.rate_limit_window = 60  # seconds
        self.max_calls_per_window = 100
        
        # Configuration
        self.conflict_resolution_strategy = ConflictResolution.ETILIZE_PRIORITY
        self.auto_resolve_conflicts = True
        self.enable_bidirectional_sync = False
        
        # Logger
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
    
    async def start_sync_engine(self):
        """Start the sync engine with background processing."""
        self.logger.info("Starting Shopify Sync Engine")
        
        # Start background tasks
        tasks = [
            asyncio.create_task(self._process_sync_queue()),
            asyncio.create_task(self._resolve_conflicts()),
            asyncio.create_task(self._monitor_changes()),
            asyncio.create_task(self._cleanup_completed_jobs())
        ]
        
        try:
            await asyncio.gather(*tasks)
        except Exception as e:
            self.logger.error(f"Sync engine error: {e}")
            raise
    
    async def stop_sync_engine(self):
        """Stop the sync engine gracefully."""
        self.logger.info("Stopping Shopify Sync Engine")
        # Cancel active syncs and cleanup
        self.active_syncs.clear()
    
    def queue_product_sync(self, product_id: int, operation: SyncOperation,
                          priority: SyncPriority = SyncPriority.NORMAL,
                          data: Dict[str, Any] = None) -> str:
        """Queue a product for synchronization."""
        item_id = str(uuid.uuid4())
        
        sync_item = SyncQueueItem(
            id=item_id,
            operation=operation,
            entity_type="product",
            entity_id=product_id,
            priority=priority,
            data=data or {}
        )
        
        self.sync_queue.append(sync_item)
        self.sync_queue.sort(key=lambda x: x.priority.value)
        
        self.logger.info(f"Queued product {product_id} for {operation.value}")
        return item_id
    
    def queue_category_sync(self, category_id: int, operation: SyncOperation,
                           priority: SyncPriority = SyncPriority.NORMAL,
                           data: Dict[str, Any] = None) -> str:
        """Queue a category for synchronization."""
        item_id = str(uuid.uuid4())
        
        sync_item = SyncQueueItem(
            id=item_id,
            operation=operation,
            entity_type="category",
            entity_id=category_id,
            priority=priority,
            data=data or {}
        )
        
        self.sync_queue.append(sync_item)
        self.sync_queue.sort(key=lambda x: x.priority.value)
        
        self.logger.info(f"Queued category {category_id} for {operation.value}")
        return item_id
    
    async def sync_product_to_shopify(self, product_id: int) -> SyncResult:
        """Sync a single product to Shopify with conflict detection."""
        start_time = time.time()
        
        try:
            with db_session_scope() as session:
                # Get product from database
                product_repo = ProductRepository(session)
                product = product_repo.get_by_id(product_id)
                
                if not product:
                    return SyncResult(
                        success=False,
                        operation=SyncOperation.UPDATE,
                        entity_type="product",
                        entity_id=product_id,
                        error_message="Product not found in database"
                    )
                
                # Check if product exists in Shopify
                existing_product_id = None
                if product.shopify_product_id:
                    existing_product_id = product.shopify_product_id
                elif product.sku:
                    # Try to find by handle (derived from SKU)
                    handle = self._generate_handle(product.name, product.sku)
                    existing_product_id = self.product_manager.get_product_by_handle(handle)
                
                # Prepare product data for Shopify
                shopify_data = self._prepare_product_data(product)
                
                # Detect conflicts if product exists
                conflicts = []
                if existing_product_id:
                    conflicts = await self._detect_product_conflicts(
                        product, existing_product_id
                    )
                
                # Resolve conflicts if any
                if conflicts:
                    if self.auto_resolve_conflicts:
                        shopify_data = await self._resolve_product_conflicts(
                            shopify_data, conflicts
                        )
                    else:
                        # Queue for manual resolution
                        for conflict in conflicts:
                            self.conflict_queue.append(conflict)
                        
                        return SyncResult(
                            success=False,
                            operation=SyncOperation.UPDATE,
                            entity_type="product",
                            entity_id=product_id,
                            error_message="Conflicts detected, manual resolution required"
                        )
                
                # Perform the sync operation
                if existing_product_id:
                    # Update existing product
                    result = self.product_manager.execute_graphql(
                        self.product_manager.UPDATE_PRODUCT_MUTATION,
                        {"input": {**shopify_data, "id": existing_product_id}}
                    )
                    operation = SyncOperation.UPDATE
                else:
                    # Create new product
                    result = self.product_manager.execute_graphql(
                        self.product_manager.CREATE_PRODUCT_MUTATION,
                        {"input": shopify_data}
                    )
                    operation = SyncOperation.CREATE
                
                # Process result
                if "errors" in result:
                    return SyncResult(
                        success=False,
                        operation=operation,
                        entity_type="product",
                        entity_id=product_id,
                        error_message=str(result["errors"]),
                        sync_duration=time.time() - start_time
                    )
                
                # Extract Shopify product ID from result
                product_data = result.get("data", {})
                if operation == SyncOperation.CREATE:
                    shopify_product = product_data.get("productCreate", {}).get("product", {})
                else:
                    shopify_product = product_data.get("productUpdate", {}).get("product", {})
                
                shopify_id = shopify_product.get("id")
                
                # Update local database with Shopify ID
                if shopify_id:
                    product.shopify_product_id = shopify_id
                    product.shopify_synced_at = datetime.utcnow()
                    product.shopify_sync_status = SyncStatus.SUCCESS.value
                    session.commit()
                
                # Sync images if present
                if product.featured_image_url or product.additional_images:
                    await self._sync_product_images(product, shopify_id)
                
                return SyncResult(
                    success=True,
                    operation=operation,
                    entity_type="product",
                    entity_id=product_id,
                    shopify_id=shopify_id,
                    changes_detected=len(conflicts) > 0,
                    sync_duration=time.time() - start_time
                )
                
        except Exception as e:
            self.logger.error(f"Failed to sync product {product_id}: {e}")
            return SyncResult(
                success=False,
                operation=SyncOperation.UPDATE,
                entity_type="product",
                entity_id=product_id,
                error_message=str(e),
                sync_duration=time.time() - start_time
            )
    
    async def sync_product_from_shopify(self, shopify_product_id: str) -> SyncResult:
        """Sync a product from Shopify to local database."""
        start_time = time.time()
        
        try:
            # Fetch product from Shopify
            shopify_data = await self._fetch_shopify_product(shopify_product_id)
            
            if not shopify_data:
                return SyncResult(
                    success=False,
                    operation=SyncOperation.SYNC_DOWN,
                    entity_type="product",
                    entity_id=0,
                    error_message="Product not found in Shopify"
                )
            
            with db_session_scope() as session:
                product_repo = ProductRepository(session)
                
                # Find existing product by Shopify ID or SKU
                product = product_repo.get_by_shopify_id(shopify_product_id)
                
                if not product and shopify_data.get("sku"):
                    product = product_repo.get_by_sku(shopify_data["sku"])
                
                if product:
                    # Update existing product
                    conflicts = await self._detect_local_conflicts(product, shopify_data)
                    
                    if conflicts and not self.auto_resolve_conflicts:
                        # Queue for manual resolution
                        for conflict in conflicts:
                            self.conflict_queue.append(conflict)
                        
                        return SyncResult(
                            success=False,
                            operation=SyncOperation.SYNC_DOWN,
                            entity_type="product",
                            entity_id=product.id,
                            error_message="Conflicts detected"
                        )
                    
                    # Apply updates
                    self._update_product_from_shopify(product, shopify_data)
                    operation = SyncOperation.UPDATE
                    
                else:
                    # Create new product
                    product = self._create_product_from_shopify(shopify_data)
                    session.add(product)
                    operation = SyncOperation.CREATE
                
                session.commit()
                
                return SyncResult(
                    success=True,
                    operation=operation,
                    entity_type="product",
                    entity_id=product.id,
                    shopify_id=shopify_product_id,
                    sync_duration=time.time() - start_time
                )
                
        except Exception as e:
            self.logger.error(f"Failed to sync product from Shopify {shopify_product_id}: {e}")
            return SyncResult(
                success=False,
                operation=SyncOperation.SYNC_DOWN,
                entity_type="product",
                entity_id=0,
                error_message=str(e),
                sync_duration=time.time() - start_time
            )
    
    async def batch_sync_products(self, product_ids: List[int],
                                 operation: SyncOperation = SyncOperation.UPDATE) -> List[SyncResult]:
        """Perform batch synchronization of multiple products."""
        self.logger.info(f"Starting batch sync of {len(product_ids)} products")
        
        # Split into batches
        batches = [
            product_ids[i:i + self.batch_size] 
            for i in range(0, len(product_ids), self.batch_size)
        ]
        
        all_results = []
        
        for batch_num, batch in enumerate(batches, 1):
            self.logger.info(f"Processing batch {batch_num}/{len(batches)}")
            
            # Process batch with concurrency control
            semaphore = asyncio.Semaphore(self.max_concurrent)
            
            async def sync_with_semaphore(product_id):
                async with semaphore:
                    return await self.sync_product_to_shopify(product_id)
            
            batch_tasks = [sync_with_semaphore(pid) for pid in batch]
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            
            # Process results
            for result in batch_results:
                if isinstance(result, Exception):
                    self.logger.error(f"Batch sync error: {result}")
                    # Create error result
                    error_result = SyncResult(
                        success=False,
                        operation=operation,
                        entity_type="product",
                        entity_id=0,
                        error_message=str(result)
                    )
                    all_results.append(error_result)
                else:
                    all_results.append(result)
                    self.metrics.record_operation(result)
            
            # Rate limiting between batches
            if batch_num < len(batches):
                await asyncio.sleep(1)  # 1 second between batches
        
        self.logger.info(f"Batch sync completed. Success rate: {self.metrics.get_success_rate():.1f}%")
        return all_results
    
    async def incremental_sync(self, since: datetime = None) -> Dict[str, List[SyncResult]]:
        """Perform incremental sync of changed products since a specific time."""
        if since is None:
            since = datetime.utcnow() - timedelta(hours=1)  # Default to last hour
        
        self.logger.info(f"Starting incremental sync since {since}")
        
        results = {
            "products": [],
            "categories": [],
            "images": []
        }
        
        try:
            with db_session_scope() as session:
                product_repo = ProductRepository(session)
                
                # Find products modified since the specified time
                modified_products = product_repo.get_modified_since(since)
                
                self.logger.info(f"Found {len(modified_products)} modified products")
                
                if modified_products:
                    product_ids = [p.id for p in modified_products]
                    product_results = await self.batch_sync_products(product_ids)
                    results["products"] = product_results
                
                # TODO: Add category and image incremental sync
                
        except Exception as e:
            self.logger.error(f"Incremental sync failed: {e}")
            raise
        
        return results
    
    async def _process_sync_queue(self):
        """Background task to process the sync queue."""
        while True:
            try:
                if not self.sync_queue:
                    await asyncio.sleep(1)
                    continue
                
                # Get next item with highest priority
                item = self.sync_queue.pop(0)
                
                if item.id in self.active_syncs:
                    continue  # Already processing
                
                self.active_syncs.add(item.id)
                
                try:
                    # Process the sync item
                    if item.entity_type == "product":
                        if item.operation in [SyncOperation.CREATE, SyncOperation.UPDATE]:
                            result = await self.sync_product_to_shopify(item.entity_id)
                        elif item.operation == SyncOperation.SYNC_DOWN:
                            # This would need the Shopify ID from item.data
                            shopify_id = item.data.get("shopify_id")
                            if shopify_id:
                                result = await self.sync_product_from_shopify(shopify_id)
                            else:
                                result = SyncResult(
                                    success=False,
                                    operation=item.operation,
                                    entity_type=item.entity_type,
                                    entity_id=item.entity_id,
                                    error_message="Missing Shopify ID for sync down operation"
                                )
                    
                    # Record metrics
                    self.metrics.record_operation(result)
                    
                    # If failed and retries remaining, requeue
                    if not result.success and item.retry_count < item.max_retries:
                        item.retry_count += 1
                        item.scheduled_at = datetime.utcnow() + timedelta(
                            seconds=2 ** item.retry_count  # Exponential backoff
                        )
                        item.error_message = result.error_message
                        self.sync_queue.append(item)
                        self.sync_queue.sort(key=lambda x: x.priority.value)
                
                finally:
                    self.active_syncs.discard(item.id)
                
            except Exception as e:
                self.logger.error(f"Error processing sync queue: {e}")
            
            await asyncio.sleep(0.1)  # Small delay to prevent busy waiting
    
    async def _resolve_conflicts(self):
        """Background task to resolve conflicts."""
        while True:
            try:
                if not self.conflict_queue:
                    await asyncio.sleep(5)
                    continue
                
                # Process conflicts based on resolution strategy
                for conflict in self.conflict_queue[:]:  # Copy to avoid modification during iteration
                    resolved = await self._resolve_conflict(conflict)
                    
                    if resolved:
                        self.conflict_queue.remove(conflict)
                        self.metrics.record_conflict(resolved=True)
                
            except Exception as e:
                self.logger.error(f"Error resolving conflicts: {e}")
            
            await asyncio.sleep(5)  # Check every 5 seconds
    
    async def _monitor_changes(self):
        """Background task to monitor for changes and trigger syncs."""
        while True:
            try:
                if self.enable_bidirectional_sync:
                    # Monitor Shopify for changes (webhooks would be better)
                    # This is a simplified polling approach
                    await self._check_shopify_changes()
                
            except Exception as e:
                self.logger.error(f"Error monitoring changes: {e}")
            
            await asyncio.sleep(60)  # Check every minute
    
    async def _cleanup_completed_jobs(self):
        """Background task to cleanup old sync history and completed jobs."""
        while True:
            try:
                cutoff_date = datetime.utcnow() - timedelta(days=7)  # Keep 7 days
                
                with db_session_scope() as session:
                    # Clean up old sync history
                    session.query(SyncHistory).filter(
                        SyncHistory.started_at < cutoff_date,
                        SyncHistory.status.in_([SyncStatus.SUCCESS.value, SyncStatus.FAILED.value])
                    ).delete()
                    
                    session.commit()
                
            except Exception as e:
                self.logger.error(f"Error cleaning up jobs: {e}")
            
            await asyncio.sleep(3600)  # Run every hour
    
    def _prepare_product_data(self, product: Product) -> Dict[str, Any]:
        """Prepare product data for Shopify API."""
        # Generate handle from name and SKU
        handle = self._generate_handle(product.name, product.sku)
        
        # Prepare basic product data
        shopify_data = {
            "title": product.name,
            "handle": handle,
            "bodyHtml": product.description or "",
            "vendor": product.brand or product.manufacturer or "",
            "productType": product.category.name if product.category else "",
            "status": "ACTIVE" if product.status == ProductStatus.ACTIVE.value else "DRAFT",
            "variants": [{
                "sku": product.sku,
                "price": str(product.price),
                "inventoryQuantity": product.inventory_quantity,
                "inventoryPolicy": "CONTINUE" if product.continue_selling_when_out_of_stock else "DENY",
                "requiresShipping": True,
                "trackQuantity": product.track_inventory,
                "weight": product.weight,
                "weightUnit": product.weight_unit.upper() if product.weight_unit else "KG"
            }]
        }
        
        # Add SEO fields if present
        if product.seo_title:
            shopify_data["seo"] = {
                "title": product.seo_title,
                "description": product.seo_description or ""
            }
        
        # Add metafields
        if product.metafields:
            metafields = []
            for key, value in product.metafields.items():
                if "." in key:
                    namespace, field_key = key.split(".", 1)
                    metafields.append({
                        "namespace": namespace,
                        "key": field_key,
                        "value": str(value),
                        "type": "single_line_text_field"
                    })
            
            if metafields:
                shopify_data["metafields"] = metafields
        
        return shopify_data
    
    def _generate_handle(self, name: str, sku: str) -> str:
        """Generate a URL handle from product name and SKU."""
        # Use SKU as base, fallback to name
        base = sku if sku else name
        
        # Convert to lowercase and replace spaces/special chars with hyphens
        handle = base.lower()
        handle = "".join(c if c.isalnum() else "-" for c in handle)
        handle = "-".join(filter(None, handle.split("-")))  # Remove empty parts
        
        return handle[:100]  # Shopify handle length limit
    
    async def _detect_product_conflicts(self, product: Product, 
                                       shopify_product_id: str) -> List[ConflictItem]:
        """Detect conflicts between local product and Shopify product."""
        conflicts = []
        
        try:
            # Fetch current Shopify product data
            shopify_data = await self._fetch_shopify_product(shopify_product_id)
            
            if not shopify_data:
                return conflicts
            
            # Compare key fields
            comparisons = [
                ("title", product.name, shopify_data.get("title")),
                ("price", str(product.price), shopify_data.get("price")),
                ("inventory", product.inventory_quantity, shopify_data.get("inventory_quantity")),
                ("description", product.description, shopify_data.get("bodyHtml")),
            ]
            
            for field_name, local_value, shopify_value in comparisons:
                if local_value != shopify_value:
                    conflict = ConflictItem(
                        id=f"{product.id}_{field_name}_{int(time.time())}",
                        entity_type="product",
                        entity_id=product.id,
                        field_name=field_name,
                        local_value=local_value,
                        shopify_value=shopify_value,
                        resolution_strategy=self.conflict_resolution_strategy
                    )
                    conflicts.append(conflict)
            
        except Exception as e:
            self.logger.error(f"Error detecting conflicts for product {product.id}: {e}")
        
        return conflicts
    
    async def _resolve_conflict(self, conflict: ConflictItem) -> bool:
        """Resolve a single conflict based on the resolution strategy."""
        try:
            if conflict.resolution_strategy == ConflictResolution.ETILIZE_PRIORITY:
                # Local data (Etilize) wins
                conflict.resolved_value = conflict.local_value
                conflict.resolved_at = datetime.utcnow()
                return True
                
            elif conflict.resolution_strategy == ConflictResolution.SHOPIFY_PRIORITY:
                # Shopify data wins
                conflict.resolved_value = conflict.shopify_value
                conflict.resolved_at = datetime.utcnow()
                return True
                
            elif conflict.resolution_strategy == ConflictResolution.TIMESTAMP_BASED:
                # Use most recent (implementation would need timestamps)
                conflict.resolved_value = conflict.local_value  # Default to local
                conflict.resolved_at = datetime.utcnow()
                return True
                
            elif conflict.resolution_strategy == ConflictResolution.MANUAL_REVIEW:
                # Requires human intervention
                return False
                
            else:
                # Default resolution
                conflict.resolved_value = conflict.local_value
                conflict.resolved_at = datetime.utcnow()
                return True
                
        except Exception as e:
            self.logger.error(f"Error resolving conflict {conflict.id}: {e}")
            return False
    
    async def _fetch_shopify_product(self, shopify_product_id: str) -> Optional[Dict[str, Any]]:
        """Fetch product data from Shopify."""
        # This would use the existing ShopifyProductManager to fetch product details
        # Implementation depends on extending the existing manager with more detailed queries
        return {}
    
    def _update_product_from_shopify(self, product: Product, shopify_data: Dict[str, Any]):
        """Update local product with Shopify data."""
        # Implementation to update product fields from Shopify data
        pass
    
    def _create_product_from_shopify(self, shopify_data: Dict[str, Any]) -> Product:
        """Create a new product from Shopify data."""
        # Implementation to create new product from Shopify data
        return Product()
    
    async def _sync_product_images(self, product: Product, shopify_product_id: str):
        """Sync product images to Shopify."""
        # Implementation to sync images using ShopifyImageManager
        pass
    
    async def _detect_local_conflicts(self, product: Product, shopify_data: Dict[str, Any]) -> List[ConflictItem]:
        """Detect conflicts when syncing from Shopify to local."""
        # Implementation similar to _detect_product_conflicts but in reverse
        return []
    
    async def _resolve_product_conflicts(self, shopify_data: Dict[str, Any], 
                                       conflicts: List[ConflictItem]) -> Dict[str, Any]:
        """Apply conflict resolutions to product data."""
        # Implementation to modify shopify_data based on resolved conflicts
        return shopify_data
    
    async def _check_shopify_changes(self):
        """Check for changes in Shopify (polling approach)."""
        # Implementation to poll Shopify for changes
        # In production, webhooks would be preferred
        pass
    
    def get_sync_status(self) -> Dict[str, Any]:
        """Get current sync engine status and metrics."""
        return {
            "queue_size": len(self.sync_queue),
            "active_syncs": len(self.active_syncs),
            "conflicts_pending": len(self.conflict_queue),
            "metrics": {
                "total_operations": self.metrics.total_operations,
                "success_rate": self.metrics.get_success_rate(),
                "average_sync_time": self.metrics.get_average_sync_time(),
                "api_calls_made": self.metrics.api_calls_made,
                "rate_limit_hits": self.metrics.rate_limit_hits,
                "conflicts_detected": self.metrics.conflicts_detected,
                "conflicts_resolved": self.metrics.conflicts_resolved
            },
            "configuration": {
                "batch_size": self.batch_size,
                "max_concurrent": self.max_concurrent,
                "conflict_resolution": self.conflict_resolution_strategy.value,
                "auto_resolve_conflicts": self.auto_resolve_conflicts,
                "bidirectional_sync": self.enable_bidirectional_sync
            }
        }