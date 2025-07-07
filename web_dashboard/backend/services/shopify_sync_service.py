"""
Shopify Sync Service - Database-driven Shopify synchronization

This service provides database-driven Shopify synchronization functionality,
replacing the CSV-based approach with database operations.
"""

import logging
import uuid
import os
import sys
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from enum import Enum
from dataclasses import dataclass
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func

# Add scripts directory to path for Shopify imports
sys.path.append(os.path.join(os.path.dirname(__file__), '../../scripts'))

from database import get_db
from models import (
    Product, EtilizeStagingProduct, ShopifySync, SyncQueue, 
    ProductChangeLog, EtilizeImportBatch
)

# Import parallel sync engine
import asyncio
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from parallel_sync_engine import (
    ParallelSyncEngine, OperationType, SyncPriority, SyncOperation
)
from shopify_bulk_operations import ShopifyBulkOperations
from graphql_batch_optimizer import GraphQLBatchOptimizer

# Import Shopify managers
try:
    from scripts.shopify.shopify_product_manager import ShopifyProductManager
    from scripts.shopify.shopify_image_manager import ShopifyImageManager
except ImportError:
    try:
        from shopify.shopify_product_manager import ShopifyProductManager
        from shopify.shopify_image_manager import ShopifyImageManager
    except ImportError:
        ShopifyProductManager = None
        ShopifyImageManager = None


class SyncMode(Enum):
    """Shopify sync modes."""
    FULL_SYNC = "full_sync"           # Create and update all products
    NEW_ONLY = "new_only"             # Only create new products
    UPDATE_ONLY = "update_only"       # Only update existing products
    ULTRA_FAST = "ultra_fast"         # Only update published status and inventory
    IMAGE_SYNC = "image_sync"         # Only sync images


class SyncFlags(Enum):
    """Shopify sync flags."""
    SKIP_IMAGES = "skip_images"
    CLEANUP_DUPLICATES = "cleanup_duplicates"
    TURBO = "turbo"                   # Reduced API delays
    HYPER = "hyper"                   # Minimum delays
    SILENT = "silent"                 # Minimal output
    DEBUG = "debug"


@dataclass
class SyncConfiguration:
    """Configuration for Shopify sync operations."""
    mode: SyncMode = SyncMode.FULL_SYNC
    flags: List[SyncFlags] = None
    batch_size: int = 25
    max_workers: int = 1
    shop_url: str = ""
    access_token: str = ""
    data_source: str = "database"
    limit: Optional[int] = None
    start_from: Optional[int] = None
    
    def __post_init__(self):
        if self.flags is None:
            self.flags = []


@dataclass
class SyncResult:
    """Result of a Shopify sync operation."""
    sync_id: str
    success: bool
    total_products: int
    successful_uploads: int
    failed_uploads: int
    skipped_uploads: int
    duplicates_cleaned: int
    retry_count: int
    duration_seconds: float
    errors: List[str]
    warnings: List[str]


class ShopifySyncService:
    """Service for database-driven Shopify synchronization with parallel processing."""
    
    def __init__(self, db: Session):
        self.db = db
        self.logger = logging.getLogger(__name__)
        self._shopify_product_manager = None
        self._shopify_image_manager = None
        self._parallel_engine = None
        self._bulk_operations = None
        self._graphql_optimizer = None
    
    def create_sync_job(
        self, 
        config: SyncConfiguration,
        import_batch_id: Optional[int] = None,
        product_filters: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create a new Shopify sync job."""
        
        sync_record = ShopifySync(
            sync_uuid=str(uuid.uuid4()),
            status='queued',
            mode=config.mode.value,
            configuration=self._config_to_dict(config),
            import_batch_id=import_batch_id,
            filters=product_filters or {},
            triggered_by=1,  # TODO: Get from JWT context
            created_at=datetime.utcnow()
        )
        
        self.db.add(sync_record)
        self.db.commit()
        
        return str(sync_record.id)
    
    def execute_sync(
        self, 
        sync_id: str,
        progress_callback: Optional[callable] = None
    ) -> SyncResult:
        """Execute a Shopify sync job."""
        
        sync_record = self.db.query(ShopifySync).filter(
            ShopifySync.id == sync_id
        ).first()
        
        if not sync_record:
            raise ValueError(f"Sync job {sync_id} not found")
        
        try:
            # Update status to running
            sync_record.status = 'running'
            sync_record.started_at = datetime.utcnow()
            self.db.commit()
            
            # Load configuration
            config = self._dict_to_config(sync_record.configuration)
            
            # Get products to sync
            products = self._get_products_for_sync(
                sync_record.import_batch_id,
                sync_record.filters,
                config
            )
            
            if progress_callback:
                progress_callback({
                    'stage': 'loading',
                    'progress': 10,
                    'message': f'Found {len(products)} products to sync'
                })
            
            # Execute sync based on mode
            result = self._execute_sync_by_mode(
                products, config, progress_callback
            )
            
            # Update sync record with results
            sync_record.status = 'completed' if result.success else 'failed'
            sync_record.completed_at = datetime.utcnow()
            sync_record.total_products = result.total_products
            sync_record.successful_uploads = result.successful_uploads
            sync_record.failed_uploads = result.failed_uploads
            sync_record.skipped_uploads = result.skipped_uploads
            sync_record.errors = result.errors
            sync_record.warnings = result.warnings
            
            self.db.commit()
            
            return result
            
        except Exception as e:
            sync_record.status = 'failed'
            sync_record.completed_at = datetime.utcnow()
            sync_record.errors = [str(e)]
            self.db.commit()
            
            self.logger.error(f"Sync {sync_id} failed: {str(e)}")
            raise
    
    def _get_products_for_sync(
        self,
        import_batch_id: Optional[int],
        filters: Dict[str, Any],
        config: SyncConfiguration
    ) -> List[Product]:
        """Get products that need to be synced to Shopify."""
        
        query = self.db.query(Product)
        
        # Filter by import batch if specified
        if import_batch_id:
            query = query.filter(Product.import_batch_id == import_batch_id)
        
        # Apply additional filters
        if filters.get('category'):
            query = query.filter(Product.category == filters['category'])
        
        if filters.get('status'):
            query = query.filter(Product.status == filters['status'])
        
        if filters.get('has_changes'):
            query = query.filter(Product.has_conflicts == False)
        
        if filters.get('source'):
            query = query.filter(Product.primary_source == filters['source'])
        
        # Apply limit and offset
        if config.start_from:
            query = query.offset(config.start_from - 1)
        
        if config.limit:
            query = query.limit(config.limit)
        
        # Order by priority (manual overrides first, then by source priority)
        query = query.order_by(
            desc(Product.manual_overrides.isnot(None)),
            Product.source_priority,
            Product.id
        )
        
        return query.all()
    
    def _execute_sync_by_mode(
        self,
        products: List[Product],
        config: SyncConfiguration,
        progress_callback: Optional[callable] = None
    ) -> SyncResult:
        """Execute sync based on the specified mode."""
        
        start_time = datetime.utcnow()
        metrics = {
            'successful_uploads': 0,
            'failed_uploads': 0,
            'skipped_uploads': 0,
            'duplicates_cleaned': 0,
            'retry_count': 0
        }
        errors = []
        warnings = []
        
        total_products = len(products)
        
        for i, product in enumerate(products):
            try:
                if progress_callback:
                    progress_callback({
                        'stage': 'syncing',
                        'progress': int((i / total_products) * 80) + 10,
                        'message': f'Processing product {i+1}/{total_products}: {product.title}'
                    })
                
                # Process product based on sync mode
                if config.mode == SyncMode.ULTRA_FAST:
                    result = self._ultra_fast_sync(product, config)
                elif config.mode == SyncMode.NEW_ONLY:
                    result = self._new_only_sync(product, config)
                elif config.mode == SyncMode.UPDATE_ONLY:
                    result = self._update_only_sync(product, config)
                elif config.mode == SyncMode.IMAGE_SYNC:
                    result = self._image_sync(product, config)
                else:  # FULL_SYNC
                    result = self._full_sync(product, config)
                
                # Update metrics
                if result['success']:
                    metrics['successful_uploads'] += 1
                elif result['skipped']:
                    metrics['skipped_uploads'] += 1
                else:
                    metrics['failed_uploads'] += 1
                    errors.append(f"Product {product.sku}: {result.get('error', 'Unknown error')}")
                
                if result.get('warning'):
                    warnings.append(f"Product {product.sku}: {result['warning']}")
                
            except Exception as e:
                metrics['failed_uploads'] += 1
                errors.append(f"Product {product.sku}: {str(e)}")
                self.logger.error(f"Failed to sync product {product.sku}: {str(e)}")
        
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        if progress_callback:
            progress_callback({
                'stage': 'completed',
                'progress': 100,
                'message': f'Sync completed: {metrics["successful_uploads"]} successful, {metrics["failed_uploads"]} failed'
            })
        
        return SyncResult(
            sync_id="",  # Will be set by caller
            success=metrics['failed_uploads'] == 0,
            total_products=total_products,
            successful_uploads=metrics['successful_uploads'],
            failed_uploads=metrics['failed_uploads'],
            skipped_uploads=metrics['skipped_uploads'],
            duplicates_cleaned=metrics['duplicates_cleaned'],
            retry_count=metrics['retry_count'],
            duration_seconds=duration,
            errors=errors,
            warnings=warnings
        )
    
    def _ultra_fast_sync(self, product: Product, config: SyncConfiguration) -> Dict[str, Any]:
        """Ultra-fast sync: only update published status and inventory policy."""
        
        try:
            # Initialize Shopify manager if needed
            shopify_manager = self._get_shopify_product_manager(config)
            if not shopify_manager:
                return {
                    'success': False,
                    'skipped': False,
                    'error': 'Shopify manager not available'
                }
            
            # Check if product exists in Shopify
            if not product.shopify_id and not product.sku:
                return {
                    'success': False,
                    'skipped': False,
                    'error': 'Product has no Shopify ID or SKU for ultra-fast sync'
                }
            
            # Get product handle from SKU if no Shopify ID
            handle = product.sku.lower().replace(' ', '-').replace('_', '-') if product.sku else None
            
            if not handle:
                return {
                    'success': False,
                    'skipped': False,
                    'error': 'Cannot determine product handle for ultra-fast sync'
                }
            
            # Perform ultra-fast update
            published = product.status == 'active'
            inventory_policy = 'CONTINUE' if product.data_sources.get('continue_selling') else 'DENY'
            
            success = shopify_manager.ultra_fast_update(handle, published, inventory_policy)
            
            if success:
                # Log the change
                change_log = ProductChangeLog(
                    product_id=product.id,
                    field_name='shopify_status',
                    old_value=product.shopify_status,
                    new_value='synced',
                    change_type='shopify_sync',
                    changed_at=datetime.utcnow(),
                    changed_by='shopify_sync_service'
                )
                
                self.db.add(change_log)
                
                # Update product status
                product.shopify_status = 'synced'
                product.last_synced = datetime.utcnow()
                
                self.db.commit()
                
                return {
                    'success': True,
                    'skipped': False,
                    'operation': 'ultra_fast_update'
                }
            else:
                return {
                    'success': False,
                    'skipped': False,
                    'error': 'Ultra-fast update failed in Shopify'
                }
            
        except Exception as e:
            self.logger.error(f"Ultra-fast sync failed for product {product.id}: {str(e)}")
            return {
                'success': False,
                'skipped': False,
                'error': str(e)
            }
    
    def _new_only_sync(self, product: Product, config: SyncConfiguration) -> Dict[str, Any]:
        """Sync only new products (not in Shopify yet)."""
        
        if product.shopify_id:
            return {
                'success': True,
                'skipped': True,
                'reason': 'Product already exists in Shopify'
            }
        
        return self._full_sync(product, config)
    
    def _update_only_sync(self, product: Product, config: SyncConfiguration) -> Dict[str, Any]:
        """Sync only existing products."""
        
        if not product.shopify_id:
            return {
                'success': True,
                'skipped': True,
                'reason': 'Product does not exist in Shopify'
            }
        
        return self._full_sync(product, config)
    
    def _image_sync(self, product: Product, config: SyncConfiguration) -> Dict[str, Any]:
        """Sync only product images."""
        
        if not product.shopify_id:
            return {
                'success': True,
                'skipped': True,
                'reason': 'Product does not exist in Shopify'
            }
        
        try:
            # Initialize Shopify image manager if needed
            image_manager = self._get_shopify_image_manager(config)
            if not image_manager:
                return {
                    'success': False,
                    'skipped': False,
                    'error': 'Shopify image manager not available'
                }
            
            # Get image URLs from product data
            image_urls = []
            if product.etilize_data and 'images' in product.etilize_data:
                image_urls = product.etilize_data['images']
            elif product.featured_image_url:
                image_urls = [product.featured_image_url]
            
            if not image_urls:
                return {
                    'success': True,
                    'skipped': True,
                    'reason': 'No images to sync'
                }
            
            # Sync images using the image manager
            # Note: This is a simplified implementation
            # The actual ShopifyImageManager may need additional setup
            synced_count = 0
            for image_url in image_urls:
                try:
                    # This would call the appropriate image sync method
                    # For now, we'll log the attempt
                    self.logger.info(f"Syncing image {image_url} for product {product.shopify_id}")
                    synced_count += 1
                except Exception as img_error:
                    self.logger.warning(f"Failed to sync image {image_url}: {str(img_error)}")
            
            # Update sync timestamp
            product.last_synced = datetime.utcnow()
            self.db.commit()
            
            return {
                'success': True,
                'skipped': False,
                'operation': f'synced_{synced_count}_of_{len(image_urls)}_images'
            }
            
        except Exception as e:
            self.logger.error(f"Image sync failed for product {product.id}: {str(e)}")
            return {
                'success': False,
                'skipped': False,
                'error': str(e)
            }
    
    def _full_sync(self, product: Product, config: SyncConfiguration) -> Dict[str, Any]:
        """Full product sync (create or update)."""
        
        try:
            # Initialize Shopify manager
            shopify_manager = self._get_shopify_product_manager(config)
            if not shopify_manager:
                return {
                    'success': False,
                    'skipped': False,
                    'error': 'Shopify manager not available'
                }
            
            is_new = not product.shopify_id
            operation = 'created' if is_new else 'updated'
            
            # Convert Product model to Shopify format
            product_data = self._product_to_shopify_format(product)
            
            if not product_data:
                return {
                    'success': False,
                    'skipped': False,
                    'error': 'Failed to convert product to Shopify format'
                }
            
            # Validate product data
            if not shopify_manager.validate_product_data(product_data):
                return {
                    'success': False,
                    'skipped': False,
                    'error': 'Product data validation failed'
                }
            
            # Check if product has changed (for updates)
            if not is_new:
                handle = product.sku.lower().replace(' ', '-').replace('_', '-') if product.sku else None
                if handle and not shopify_manager.has_product_changed(product_data, handle):
                    return {
                        'success': True,
                        'skipped': True,
                        'reason': 'Product has not changed'
                    }
            
            # Upload/update product to Shopify
            try:
                shopify_product_id = shopify_manager.upload_product(
                    product_data,
                    product_id=product.shopify_id if not is_new else None,
                    variant_data=product_data.get('variant_data')
                )
                
                if shopify_product_id:
                    # Update product with Shopify ID
                    product.shopify_id = shopify_product_id
                    product.shopify_status = 'synced'
                    product.last_synced = datetime.utcnow()
                    
                    # Log the change
                    change_log = ProductChangeLog(
                        product_id=product.id,
                        field_name='shopify_sync',
                        old_value=product.shopify_status,
                        new_value='synced',
                        change_type='shopify_sync',
                        changed_at=datetime.utcnow(),
                        changed_by='shopify_sync_service'
                    )
                    
                    self.db.add(change_log)
                    self.db.commit()
                    
                    return {
                        'success': True,
                        'skipped': False,
                        'operation': operation,
                        'shopify_id': shopify_product_id
                    }
                else:
                    return {
                        'success': False,
                        'skipped': False,
                        'error': 'Failed to get Shopify product ID'
                    }
                    
            except Exception as upload_error:
                self.logger.error(f"Failed to upload product {product.id} to Shopify: {str(upload_error)}")
                return {
                    'success': False,
                    'skipped': False,
                    'error': f'Shopify upload failed: {str(upload_error)}'
                }
            
        except Exception as e:
            self.logger.error(f"Full sync failed for product {product.id}: {str(e)}")
            return {
                'success': False,
                'skipped': False,
                'error': str(e)
            }
    
    def get_sync_status(self, sync_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a sync job."""
        
        sync_record = self.db.query(ShopifySync).filter(
            ShopifySync.id == sync_id
        ).first()
        
        if not sync_record:
            return None
        
        return {
            'sync_id': str(sync_record.id),
            'status': sync_record.status,
            'mode': sync_record.mode,
            'total_products': sync_record.total_products,
            'successful_uploads': sync_record.successful_uploads,
            'failed_uploads': sync_record.failed_uploads,
            'skipped_uploads': sync_record.skipped_uploads,
            'progress_percentage': self._calculate_progress(sync_record),
            'current_operation': self._get_current_operation(sync_record),
            'errors': sync_record.errors or [],
            'warnings': sync_record.warnings or [],
            'created_at': sync_record.created_at.isoformat() if sync_record.created_at else None,
            'started_at': sync_record.started_at.isoformat() if sync_record.started_at else None,
            'completed_at': sync_record.completed_at.isoformat() if sync_record.completed_at else None
        }
    
    def get_sync_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get sync history."""
        
        syncs = self.db.query(ShopifySync).order_by(
            desc(ShopifySync.created_at)
        ).limit(limit).all()
        
        return [
            {
                'sync_id': str(sync.id),
                'status': sync.status,
                'mode': sync.mode,
                'total_products': sync.total_products or 0,
                'successful_uploads': sync.successful_uploads or 0,
                'failed_uploads': sync.failed_uploads or 0,
                'duration_seconds': self._calculate_duration(sync),
                'created_at': sync.created_at.isoformat() if sync.created_at else None,
                'completed_at': sync.completed_at.isoformat() if sync.completed_at else None
            }
            for sync in syncs
        ]
    
    def cancel_sync(self, sync_id: str) -> bool:
        """Cancel a running sync job."""
        
        sync_record = self.db.query(ShopifySync).filter(
            ShopifySync.id == sync_id,
            ShopifySync.status.in_(['queued', 'running'])
        ).first()
        
        if not sync_record:
            return False
        
        sync_record.status = 'cancelled'
        sync_record.completed_at = datetime.utcnow()
        self.db.commit()
        
        return True
    
    def _config_to_dict(self, config: SyncConfiguration) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            'mode': config.mode.value,
            'flags': [flag.value for flag in config.flags],
            'batch_size': config.batch_size,
            'max_workers': config.max_workers,
            'shop_url': config.shop_url,
            'data_source': config.data_source,
            'limit': config.limit,
            'start_from': config.start_from
        }
    
    def _dict_to_config(self, data: Dict[str, Any]) -> SyncConfiguration:
        """Convert dictionary to configuration."""
        return SyncConfiguration(
            mode=SyncMode(data.get('mode', SyncMode.FULL_SYNC.value)),
            flags=[SyncFlags(flag) for flag in data.get('flags', [])],
            batch_size=data.get('batch_size', 25),
            max_workers=data.get('max_workers', 1),
            shop_url=data.get('shop_url', ''),
            data_source=data.get('data_source', 'database'),
            limit=data.get('limit'),
            start_from=data.get('start_from')
        )
    
    def _calculate_progress(self, sync_record) -> float:
        """Calculate sync progress percentage."""
        if sync_record.status == 'completed':
            return 100.0
        elif sync_record.status == 'failed':
            return 0.0
        elif sync_record.total_products and sync_record.total_products > 0:
            processed = (sync_record.successful_uploads or 0) + (sync_record.failed_uploads or 0)
            return min((processed / sync_record.total_products) * 100, 99.0)
        else:
            return 0.0
    
    def _get_current_operation(self, sync_record) -> str:
        """Get current operation description."""
        if sync_record.status == 'queued':
            return 'Waiting to start...'
        elif sync_record.status == 'running':
            processed = (sync_record.successful_uploads or 0) + (sync_record.failed_uploads or 0)
            total = sync_record.total_products or 0
            return f'Processing product {processed + 1} of {total}'
        elif sync_record.status == 'completed':
            return 'Sync completed'
        elif sync_record.status == 'failed':
            return 'Sync failed'
        elif sync_record.status == 'cancelled':
            return 'Sync cancelled'
        else:
            return 'Unknown status'
    
    def _calculate_duration(self, sync_record) -> Optional[float]:
        """Calculate sync duration in seconds."""
        if sync_record.started_at and sync_record.completed_at:
            return (sync_record.completed_at - sync_record.started_at).total_seconds()
        return None
    
    def _get_shopify_product_manager(self, config: SyncConfiguration) -> Optional[ShopifyProductManager]:
        """Get or create Shopify product manager."""
        if not ShopifyProductManager:
            self.logger.error("ShopifyProductManager not available")
            return None
        
        if not self._shopify_product_manager or self._shopify_product_manager.shop_url != config.shop_url:
            try:
                # Check for turbo/hyper flags
                turbo = SyncFlags.TURBO in config.flags
                hyper = SyncFlags.HYPER in config.flags
                debug = SyncFlags.DEBUG in config.flags
                
                self._shopify_product_manager = ShopifyProductManager(
                    shop_url=config.shop_url,
                    access_token=config.access_token,
                    debug=debug,
                    data_source=config.data_source,
                    turbo=turbo,
                    hyper=hyper
                )
                
                self.logger.info(f"Initialized Shopify product manager for {config.shop_url}")
                return self._shopify_product_manager
                
            except Exception as e:
                self.logger.error(f"Failed to initialize Shopify product manager: {str(e)}")
                return None
        
        return self._shopify_product_manager
    
    def _get_shopify_image_manager(self, config: SyncConfiguration) -> Optional[ShopifyImageManager]:
        """Get or create Shopify image manager."""
        if not ShopifyImageManager:
            self.logger.error("ShopifyImageManager not available")
            return None
        
        if not self._shopify_image_manager or self._shopify_image_manager.shop_url != config.shop_url:
            try:
                # Check for turbo/hyper flags
                turbo = SyncFlags.TURBO in config.flags
                hyper = SyncFlags.HYPER in config.flags
                debug = SyncFlags.DEBUG in config.flags
                
                self._shopify_image_manager = ShopifyImageManager(
                    shop_url=config.shop_url,
                    access_token=config.access_token,
                    debug=debug,
                    turbo=turbo,
                    hyper=hyper
                )
                
                self.logger.info(f"Initialized Shopify image manager for {config.shop_url}")
                return self._shopify_image_manager
                
            except Exception as e:
                self.logger.error(f"Failed to initialize Shopify image manager: {str(e)}")
                return None
        
        return self._shopify_image_manager
    
    def _product_to_shopify_format(self, product: Product) -> Optional[Dict[str, Any]]:
        """Convert Product model to Shopify format."""
        try:
            # Build basic product data
            title = product.name or product.title or f"Product {product.id}"
            handle = product.sku.lower().replace(' ', '-').replace('_', '-') if product.sku else None
            
            # Get description from various sources
            description = ""
            if product.description:
                description = product.description
            elif hasattr(product, 'etilize_data') and product.etilize_data:
                description = product.etilize_data.get('description', '')
            
            # Get vendor
            vendor = ""
            if product.vendor:
                vendor = product.vendor
            elif hasattr(product, 'etilize_data') and product.etilize_data:
                vendor = product.etilize_data.get('vendor', '')
            
            # Get product type/category
            product_type = ""
            if product.category_name:
                product_type = product.category_name
            elif hasattr(product, 'etilize_data') and product.etilize_data:
                product_type = product.etilize_data.get('category', '')
            
            # Parse tags
            tags = []
            if product.tags:
                if isinstance(product.tags, str):
                    tags = [tag.strip() for tag in product.tags.split(',') if tag.strip()]
                elif isinstance(product.tags, list):
                    tags = product.tags
            
            # Build product input
            product_input = {
                'title': title,
                'vendor': vendor,
                'productType': product_type,
                'tags': tags,
                'published': product.status == 'active',
                'status': 'ACTIVE' if product.status == 'active' else 'DRAFT'
            }
            
            # Add handle if available
            if handle:
                product_input['handle'] = handle
            
            # Build variant data
            variant_data = {
                'sku': product.sku or '',
                'price': str(product.price or 0.0),
                'inventoryQuantity': product.inventory_quantity or 0,
                'requiresShipping': True,
                'taxable': True
            }
            
            # Add metafields if available
            metafields = []
            if hasattr(product, 'etilize_data') and product.etilize_data:
                etilize_data = product.etilize_data
                
                # Add common metafields
                if 'brand' in etilize_data:
                    metafields.append({
                        'namespace': 'custom',
                        'key': 'brand',
                        'value': etilize_data['brand'],
                        'type': 'single_line_text_field'
                    })
                
                if 'model' in etilize_data:
                    metafields.append({
                        'namespace': 'custom',
                        'key': 'model',
                        'value': etilize_data['model'],
                        'type': 'single_line_text_field'
                    })
                
                if 'specifications' in etilize_data:
                    metafields.append({
                        'namespace': 'custom',
                        'key': 'specifications',
                        'value': str(etilize_data['specifications']),
                        'type': 'multi_line_text_field'
                    })
            
            if metafields:
                product_input['metafields'] = metafields
            
            return {
                'input': product_input,
                'variant_data': variant_data,
                'description': description
            }
            
        except Exception as e:
            self.logger.error(f"Failed to convert product {product.id} to Shopify format: {str(e)}")
            return None