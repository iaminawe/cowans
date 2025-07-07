"""
Repository Classes for Database Operations

This module contains repository classes that provide a data access layer
for all database operations, supporting the sync engine and web dashboard.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy import and_, or_, func, desc, asc
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError

from models import (
    User, Product, Category, Icon, Job, SyncHistory, ProductImage,
    ProductMetafield, SystemLog, Configuration, ProductStatus, 
    SyncStatus, JobStatus, IconStatus
)


class BaseRepository:
    """Base repository with common operations."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def get_by_id(self, model_class, entity_id: int):
        """Get entity by ID."""
        return self.session.query(model_class).get(entity_id)
    
    def get_all(self, model_class, limit: int = None):
        """Get all entities with optional limit."""
        query = self.session.query(model_class)
        if limit:
            query = query.limit(limit)
        return query.all()
    
    def create(self, entity):
        """Create a new entity."""
        self.session.add(entity)
        self.session.flush()  # Get ID without committing
        return entity
    
    def update(self, entity):
        """Update an existing entity."""
        self.session.merge(entity)
        return entity
    
    def delete(self, entity):
        """Delete an entity."""
        self.session.delete(entity)
    
    def delete_by_id(self, model_class, entity_id: int):
        """Delete entity by ID."""
        entity = self.get_by_id(model_class, entity_id)
        if entity:
            self.delete(entity)
            return True
        return False


class UserRepository(BaseRepository):
    """Repository for User operations."""
    
    def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        return self.session.query(User).filter(User.email == email).first()
    
    def get_active_users(self) -> List[User]:
        """Get all active users."""
        return self.session.query(User).filter(User.is_active == True).all()
    
    def create(self, email: str, password_hash: str, first_name: str = None,
               last_name: str = None, is_admin: bool = False) -> User:
        """Create a new user."""
        user = User(
            email=email,
            password_hash=password_hash,
            first_name=first_name,
            last_name=last_name,
            is_admin=is_admin
        )
        return super().create(user)
    
    def update_last_login(self, user_id: int):
        """Update user's last login timestamp."""
        user = self.get_by_id(User, user_id)
        if user:
            user.last_login = datetime.utcnow()
            return user
        return None


class ProductRepository(BaseRepository):
    """Repository for Product operations with sync support."""
    
    def get_by_id(self, product_id: int) -> Optional[Product]:
        """Get product by ID with relationships."""
        return self.session.query(Product).options(
            joinedload(Product.category)
        ).get(product_id)
    
    def get_by_sku(self, sku: str) -> Optional[Product]:
        """Get product by SKU."""
        return self.session.query(Product).filter(Product.sku == sku).first()
    
    def get_by_shopify_id(self, shopify_id: str) -> Optional[Product]:
        """Get product by Shopify product ID."""
        return self.session.query(Product).filter(
            Product.shopify_product_id == shopify_id
        ).first()
    
    def get_by_manufacturer_part_number(self, mpn: str) -> Optional[Product]:
        """Get product by manufacturer part number."""
        return self.session.query(Product).filter(
            Product.manufacturer_part_number == mpn
        ).first()
    
    def get_active_products(self, limit: int = None) -> List[Product]:
        """Get all active products."""
        query = self.session.query(Product).filter(
            Product.is_active == True,
            Product.status == ProductStatus.ACTIVE.value
        ).options(joinedload(Product.category))
        
        if limit:
            query = query.limit(limit)
        
        return query.all()
    
    def get_products_by_category(self, category_id: int) -> List[Product]:
        """Get products by category."""
        return self.session.query(Product).filter(
            Product.category_id == category_id,
            Product.is_active == True
        ).options(joinedload(Product.category)).all()
    
    def get_products_by_brand(self, brand: str) -> List[Product]:
        """Get products by brand."""
        return self.session.query(Product).filter(
            Product.brand == brand,
            Product.is_active == True
        ).all()
    
    def get_modified_since(self, since: datetime) -> List[Product]:
        """Get products modified since a specific datetime."""
        return self.session.query(Product).filter(
            Product.updated_at >= since,
            Product.is_active == True
        ).options(joinedload(Product.category)).all()
    
    def get_pending_sync(self, limit: int = 100) -> List[Product]:
        """Get products pending Shopify sync."""
        return self.session.query(Product).filter(
            or_(
                Product.shopify_sync_status == SyncStatus.PENDING.value,
                Product.shopify_sync_status == SyncStatus.FAILED.value,
                Product.shopify_product_id.is_(None)
            ),
            Product.is_active == True
        ).limit(limit).all()
    
    def get_sync_conflicts(self) -> List[Product]:
        """Get products with sync conflicts."""
        return self.session.query(Product).filter(
            Product.shopify_sync_status == SyncStatus.PARTIAL.value
        ).all()
    
    def get_products_without_shopify_id(self) -> List[Product]:
        """Get products that haven't been synced to Shopify."""
        return self.session.query(Product).filter(
            Product.shopify_product_id.is_(None),
            Product.is_active == True
        ).all()
    
    def search_products(self, query: str, limit: int = 50) -> List[Product]:
        """Search products by name, SKU, or description."""
        search_filter = or_(
            Product.name.ilike(f"%{query}%"),
            Product.sku.ilike(f"%{query}%"),
            Product.description.ilike(f"%{query}%"),
            Product.manufacturer_part_number.ilike(f"%{query}%")
        )
        
        return self.session.query(Product).filter(
            search_filter,
            Product.is_active == True
        ).limit(limit).all()
    
    def get_products_by_sync_status(self, status: SyncStatus) -> List[Product]:
        """Get products by sync status."""
        return self.session.query(Product).filter(
            Product.shopify_sync_status == status.value
        ).all()
    
    def update_sync_status(self, product_id: int, status: SyncStatus,
                          shopify_id: str = None) -> bool:
        """Update product sync status."""
        product = self.get_by_id(product_id)
        if product:
            product.shopify_sync_status = status.value
            product.shopify_synced_at = datetime.utcnow()
            if shopify_id:
                product.shopify_product_id = shopify_id
            return True
        return False
    
    def bulk_update_sync_status(self, product_ids: List[int], 
                               status: SyncStatus) -> int:
        """Bulk update sync status for multiple products."""
        updated = self.session.query(Product).filter(
            Product.id.in_(product_ids)
        ).update({
            Product.shopify_sync_status: status.value,
            Product.shopify_synced_at: datetime.utcnow()
        }, synchronize_session=False)
        
        return updated
    
    def create(self, sku: str, name: str, price: float, category_id: int,
               description: str = None, **kwargs) -> Product:
        """Create a new product."""
        product = Product(
            sku=sku,
            name=name,
            price=price,
            category_id=category_id,
            description=description,
            **kwargs
        )
        return super().create(product)
    
    def get_product_stats(self) -> Dict[str, int]:
        """Get product statistics."""
        total = self.session.query(Product).count()
        active = self.session.query(Product).filter(
            Product.is_active == True
        ).count()
        synced = self.session.query(Product).filter(
            Product.shopify_product_id.isnot(None)
        ).count()
        pending_sync = self.session.query(Product).filter(
            Product.shopify_sync_status == SyncStatus.PENDING.value
        ).count()
        
        return {
            "total": total,
            "active": active,
            "synced": synced,
            "pending_sync": pending_sync,
            "sync_percentage": (synced / active * 100) if active > 0 else 0
        }
    
    def get_by_category(self, category_id: int) -> List[Product]:
        """Get products by category ID."""
        return self.session.query(Product).filter(
            Product.category_id == category_id
        ).all()


class CategoryRepository(BaseRepository):
    """Repository for Category operations."""
    
    def get_by_id(self, category_id: int) -> Optional[Category]:
        """Get category by ID with products."""
        return self.session.query(Category).options(
            joinedload(Category.products)
        ).get(category_id)
    
    def get_by_slug(self, slug: str) -> Optional[Category]:
        """Get category by slug."""
        return self.session.query(Category).filter(Category.slug == slug).first()
    
    def get_by_shopify_collection_id(self, collection_id: str) -> Optional[Category]:
        """Get category by Shopify collection ID."""
        return self.session.query(Category).filter(
            Category.shopify_collection_id == collection_id
        ).first()
    
    def get_root_categories(self) -> List[Category]:
        """Get root level categories (no parent)."""
        return self.session.query(Category).filter(
            Category.parent_id.is_(None),
            Category.is_active == True
        ).order_by(Category.sort_order, Category.name).all()
    
    def get_children(self, parent_id: int) -> List[Category]:
        """Get child categories of a parent."""
        return self.session.query(Category).filter(
            Category.parent_id == parent_id,
            Category.is_active == True
        ).order_by(Category.sort_order, Category.name).all()
    
    def get_category_tree(self) -> List[Category]:
        """Get the complete category tree."""
        return self.session.query(Category).filter(
            Category.is_active == True
        ).order_by(Category.level, Category.sort_order, Category.name).all()
    
    def get_categories_by_level(self, level: int) -> List[Category]:
        """Get categories at a specific level."""
        return self.session.query(Category).filter(
            Category.level == level,
            Category.is_active == True
        ).order_by(Category.sort_order, Category.name).all()
    
    def search_categories(self, query: str) -> List[Category]:
        """Search categories by name or description."""
        return self.session.query(Category).filter(
            or_(
                Category.name.ilike(f"%{query}%"),
                Category.description.ilike(f"%{query}%")
            ),
            Category.is_active == True
        ).all()
    
    def create(self, name: str, slug: str, parent_id: int = None,
               description: str = None, **kwargs) -> Category:
        """Create a new category."""
        # Calculate level
        level = 0
        if parent_id:
            parent = self.get_by_id(parent_id)
            if parent:
                level = parent.level + 1
        
        category = Category(
            name=name,
            slug=slug,
            parent_id=parent_id,
            level=level,
            description=description,
            **kwargs
        )
        return super().create(category)


class IconRepository(BaseRepository):
    """Repository for Icon operations."""
    
    def get_by_category(self, category_id: int) -> List[Icon]:
        """Get icons for a category."""
        return self.session.query(Icon).filter(
            Icon.category_id == category_id,
            Icon.is_active == True
        ).all()
    
    def get_active_icon(self, category_id: int) -> Optional[Icon]:
        """Get the active icon for a category."""
        return self.session.query(Icon).filter(
            Icon.category_id == category_id,
            Icon.status == IconStatus.ACTIVE.value,
            Icon.is_active == True
        ).first()
    
    def get_by_hash(self, file_hash: str) -> Optional[Icon]:
        """Get icon by file hash (for deduplication)."""
        return self.session.query(Icon).filter(Icon.file_hash == file_hash).first()
    
    def get_by_batch(self, batch_id: str) -> List[Icon]:
        """Get icons from a generation batch."""
        return self.session.query(Icon).filter(
            Icon.generation_batch_id == batch_id
        ).all()
    
    def get_pending_generation(self) -> List[Icon]:
        """Get icons pending generation."""
        return self.session.query(Icon).filter(
            Icon.status == IconStatus.GENERATING.value
        ).all()
    
    def get_failed_generation(self) -> List[Icon]:
        """Get icons with failed generation."""
        return self.session.query(Icon).filter(
            Icon.status == IconStatus.FAILED.value
        ).all()
    
    def create(self, category_id: int, filename: str, file_path: str,
               created_by: int, **kwargs) -> Icon:
        """Create a new icon."""
        icon = Icon(
            category_id=category_id,
            filename=filename,
            file_path=file_path,
            created_by=created_by,
            **kwargs
        )
        return super().create(icon)


class JobRepository(BaseRepository):
    """Repository for Job operations."""
    
    def get_by_uuid(self, job_uuid: str) -> Optional[Job]:
        """Get job by UUID."""
        return self.session.query(Job).filter(Job.job_uuid == job_uuid).first()
    
    def get_by_user(self, user_id: int, limit: int = 50) -> List[Job]:
        """Get jobs for a specific user."""
        return self.session.query(Job).filter(
            Job.user_id == user_id
        ).order_by(desc(Job.created_at)).limit(limit).all()
    
    def get_active_jobs(self) -> List[Job]:
        """Get currently running jobs."""
        return self.session.query(Job).filter(
            Job.status.in_([JobStatus.PENDING.value, JobStatus.RUNNING.value])
        ).all()
    
    def get_recent_jobs(self, limit: int = 100) -> List[Job]:
        """Get recent jobs."""
        return self.session.query(Job).order_by(
            desc(Job.created_at)
        ).limit(limit).all()
    
    def get_failed_jobs(self, since: datetime = None) -> List[Job]:
        """Get failed jobs since a specific time."""
        query = self.session.query(Job).filter(
            Job.status == JobStatus.FAILED.value
        )
        
        if since:
            query = query.filter(Job.created_at >= since)
        
        return query.order_by(desc(Job.created_at)).all()
    
    def get_jobs_by_script(self, script_name: str) -> List[Job]:
        """Get jobs by script name."""
        return self.session.query(Job).filter(
            Job.script_name == script_name
        ).order_by(desc(Job.created_at)).all()
    
    def get_job_stats(self) -> Dict[str, int]:
        """Get job statistics."""
        total = self.session.query(Job).count()
        pending = self.session.query(Job).filter(
            Job.status == JobStatus.PENDING.value
        ).count()
        running = self.session.query(Job).filter(
            Job.status == JobStatus.RUNNING.value
        ).count()
        completed = self.session.query(Job).filter(
            Job.status == JobStatus.COMPLETED.value
        ).count()
        failed = self.session.query(Job).filter(
            Job.status == JobStatus.FAILED.value
        ).count()
        
        return {
            "total": total,
            "pending": pending,
            "running": running,
            "completed": completed,
            "failed": failed
        }
    
    def create(self, job_uuid: str, script_name: str, user_id: int,
               display_name: str = None, description: str = None,
               parameters: Dict = None, **kwargs) -> Job:
        """Create a new job."""
        job = Job(
            job_uuid=job_uuid,
            script_name=script_name,
            user_id=user_id,
            display_name=display_name,
            description=description,
            parameters=parameters or {},
            **kwargs
        )
        return super().create(job)


class SyncHistoryRepository(BaseRepository):
    """Repository for SyncHistory operations."""
    
    def get_recent(self, limit: int = 100, sync_type: str = None) -> List[SyncHistory]:
        """Get recent sync history."""
        query = self.session.query(SyncHistory)
        
        if sync_type:
            query = query.filter(SyncHistory.sync_type == sync_type)
        
        return query.order_by(desc(SyncHistory.started_at)).limit(limit).all()
    
    def get_by_status(self, status: SyncStatus) -> List[SyncHistory]:
        """Get sync history by status."""
        return self.session.query(SyncHistory).filter(
            SyncHistory.status == status.value
        ).order_by(desc(SyncHistory.started_at)).all()
    
    def get_successful_syncs(self, since: datetime = None) -> List[SyncHistory]:
        """Get successful syncs since a specific time."""
        query = self.session.query(SyncHistory).filter(
            SyncHistory.status == SyncStatus.SUCCESS.value
        )
        
        if since:
            query = query.filter(SyncHistory.started_at >= since)
        
        return query.order_by(desc(SyncHistory.started_at)).all()
    
    def get_failed_syncs(self, since: datetime = None) -> List[SyncHistory]:
        """Get failed syncs since a specific time."""
        query = self.session.query(SyncHistory).filter(
            SyncHistory.status == SyncStatus.FAILED.value
        )
        
        if since:
            query = query.filter(SyncHistory.started_at >= since)
        
        return query.order_by(desc(SyncHistory.started_at)).all()
    
    def get_sync_stats(self) -> Dict[str, Any]:
        """Get sync statistics."""
        total = self.session.query(SyncHistory).count()
        
        # Count by status
        success_count = self.session.query(SyncHistory).filter(
            SyncHistory.status == SyncStatus.SUCCESS.value
        ).count()
        
        failed_count = self.session.query(SyncHistory).filter(
            SyncHistory.status == SyncStatus.FAILED.value
        ).count()
        
        # Recent stats (last 24 hours)
        since_24h = datetime.utcnow() - timedelta(hours=24)
        recent_total = self.session.query(SyncHistory).filter(
            SyncHistory.started_at >= since_24h
        ).count()
        
        # Average duration
        avg_duration = self.session.query(
            func.avg(SyncHistory.duration)
        ).filter(
            SyncHistory.duration.isnot(None)
        ).scalar() or 0
        
        return {
            "total": total,
            "success_count": success_count,
            "failed_count": failed_count,
            "success_rate": (success_count / total * 100) if total > 0 else 0,
            "recent_24h": recent_total,
            "average_duration_seconds": float(avg_duration)
        }
    
    def create(self, sync_type: str, user_id: int, sync_source: str = None,
               sync_target: str = None, **kwargs) -> SyncHistory:
        """Create a new sync history record."""
        sync_history = SyncHistory(
            sync_type=sync_type,
            user_id=user_id,
            sync_source=sync_source,
            sync_target=sync_target,
            **kwargs
        )
        return super().create(sync_history)


class ProductImageRepository(BaseRepository):
    """Repository for ProductImage operations."""
    
    def get_by_product(self, product_id: int) -> List[ProductImage]:
        """Get images for a product."""
        return self.session.query(ProductImage).filter(
            ProductImage.product_id == product_id,
            ProductImage.is_active == True
        ).order_by(ProductImage.sort_order).all()
    
    def get_featured_image(self, product_id: int) -> Optional[ProductImage]:
        """Get the featured image for a product."""
        return self.session.query(ProductImage).filter(
            ProductImage.product_id == product_id,
            ProductImage.is_featured == True,
            ProductImage.is_active == True
        ).first()
    
    def get_by_hash(self, file_hash: str) -> List[ProductImage]:
        """Get images by file hash (for deduplication)."""
        return self.session.query(ProductImage).filter(
            ProductImage.file_hash == file_hash
        ).all()


class ProductMetafieldRepository(BaseRepository):
    """Repository for ProductMetafield operations."""
    
    def get_by_product(self, product_id: int) -> List[ProductMetafield]:
        """Get metafields for a product."""
        return self.session.query(ProductMetafield).filter(
            ProductMetafield.product_id == product_id
        ).all()
    
    def get_by_namespace(self, namespace: str) -> List[ProductMetafield]:
        """Get metafields by namespace."""
        return self.session.query(ProductMetafield).filter(
            ProductMetafield.namespace == namespace
        ).all()
    
    def get_by_key(self, namespace: str, key: str) -> List[ProductMetafield]:
        """Get metafields by namespace and key."""
        return self.session.query(ProductMetafield).filter(
            ProductMetafield.namespace == namespace,
            ProductMetafield.key == key
        ).all()


class SystemLogRepository(BaseRepository):
    """Repository for SystemLog operations."""
    
    def get_recent_logs(self, limit: int = 1000, level: str = None) -> List[SystemLog]:
        """Get recent system logs."""
        query = self.session.query(SystemLog)
        
        if level:
            query = query.filter(SystemLog.level == level)
        
        return query.order_by(desc(SystemLog.created_at)).limit(limit).all()
    
    def get_error_logs(self, since: datetime = None) -> List[SystemLog]:
        """Get error logs since a specific time."""
        query = self.session.query(SystemLog).filter(
            SystemLog.level.in_(["ERROR", "CRITICAL"])
        )
        
        if since:
            query = query.filter(SystemLog.created_at >= since)
        
        return query.order_by(desc(SystemLog.created_at)).all()


class ConfigurationRepository(BaseRepository):
    """Repository for Configuration operations."""
    
    def get_by_key(self, key: str) -> Optional[Configuration]:
        """Get configuration by key."""
        return self.session.query(Configuration).filter(
            Configuration.key == key
        ).first()
    
    def get_by_category(self, category: str) -> List[Configuration]:
        """Get configurations by category."""
        return self.session.query(Configuration).filter(
            Configuration.category == category
        ).all()
    
    def get_all_config(self) -> Dict[str, str]:
        """Get all configuration as a dictionary."""
        configs = self.session.query(Configuration).all()
        return {config.key: config.value for config in configs}
    
    def set_config(self, key: str, value: str, category: str = None,
                   description: str = None) -> Configuration:
        """Set a configuration value."""
        config = self.get_by_key(key)
        
        if config:
            config.value = value
            config.updated_at = datetime.utcnow()
        else:
            config = Configuration(
                key=key,
                value=value,
                category=category,
                description=description
            )
            self.session.add(config)
        
        return config