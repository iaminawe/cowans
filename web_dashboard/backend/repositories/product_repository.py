"""
Product Repository for managing product database operations.
"""

import logging
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func

from models import Product, ProductStatus, Category
from .base import BaseRepository

logger = logging.getLogger(__name__)

class ProductRepository(BaseRepository):
    """Repository for Product model operations."""
    
    def __init__(self, session: Session):
        super().__init__(Product, session)
    
    def search(self, query: str, limit: int = 50) -> List[Product]:
        """Search products by SKU, name, brand, or manufacturer."""
        search_term = f"%{query}%"
        return self.session.query(Product).filter(
            or_(
                Product.sku.ilike(search_term),
                Product.name.ilike(search_term),
                Product.brand.ilike(search_term),
                Product.manufacturer.ilike(search_term),
                Product.manufacturer_part_number.ilike(search_term)
            )
        ).limit(limit).all()
    
    def get_by_sku(self, sku: str) -> Optional[Product]:
        """Get product by SKU."""
        return self.get_by(sku=sku.upper())
    
    def get_by_mpn(self, mpn: str) -> Optional[Product]:
        """Get product by manufacturer part number."""
        return self.get_by(manufacturer_part_number=mpn)
    
    def get_by_shopify_id(self, shopify_id: str) -> Optional[Product]:
        """Get product by Shopify product ID."""
        return self.get_by(shopify_product_id=shopify_id)
    
    def get_by_category(self, category_id: int, status: Optional[str] = None, 
                       limit: Optional[int] = None, offset: Optional[int] = None) -> List[Product]:
        """Get products by category with optional status filter."""
        query = self.session.query(Product).filter(Product.category_id == category_id)
        
        if status:
            query = query.filter(Product.status == status)
        
        if offset:
            query = query.offset(offset)
        if limit:
            query = query.limit(limit)
        
        return query.all()
    
    def get_by_brand(self, brand: str, limit: Optional[int] = None) -> List[Product]:
        """Get products by brand."""
        query = self.session.query(Product).filter(Product.brand == brand)
        if limit:
            query = query.limit(limit)
        return query.all()
    
    def get_by_product_type(self, product_type: str, limit: int = 10) -> List[Product]:
        """Get products by product type."""
        return self.session.query(Product)\
            .filter(Product.product_type == product_type)\
            .limit(limit)\
            .all()
    
    def get_unsynced(self, limit: Optional[int] = None) -> List[Product]:
        """Get products that haven't been synced to Shopify."""
        query = self.session.query(Product).filter(
            or_(
                Product.shopify_product_id.is_(None),
                Product.shopify_sync_status != 'success'
            )
        )
        if limit:
            query = query.limit(limit)
        return query.all()
    
    def get_active(self, limit: Optional[int] = None, offset: Optional[int] = None) -> List[Product]:
        """Get active products."""
        return self.filter({'status': ProductStatus.ACTIVE.value, 'is_active': True}, limit=limit, offset=offset)
    
    def update_sync_status(self, product_id: int, shopify_product_id: str, 
                          shopify_variant_id: Optional[str] = None,
                          shopify_handle: Optional[str] = None) -> Optional[Product]:
        """Update product sync status after successful Shopify sync."""
        from datetime import datetime
        
        return self.update(
            product_id,
            shopify_product_id=shopify_product_id,
            shopify_variant_id=shopify_variant_id,
            shopify_handle=shopify_handle,
            shopify_synced_at=datetime.utcnow(),
            shopify_sync_status='success'
        )
    
    def bulk_update_category(self, product_ids: List[int], category_id: int) -> int:
        """Bulk update category for multiple products."""
        updated = self.session.query(Product).filter(
            Product.id.in_(product_ids)
        ).update(
            {'category_id': category_id},
            synchronize_session=False
        )
        self.session.flush()
        return updated
    
    def get_with_category(self, product_id: int) -> Optional[Product]:
        """Get product with category eagerly loaded."""
        return self.session.query(Product).options(
            joinedload(Product.category)
        ).filter(Product.id == product_id).first()
    
    def get_duplicate_skus(self) -> List[Dict[str, Any]]:
        """Find duplicate SKUs in the database."""
        duplicates = self.session.query(
            Product.sku,
            func.count(Product.id).label('count')
        ).group_by(Product.sku).having(func.count(Product.id) > 1).all()
        
        return [{'sku': sku, 'count': count} for sku, count in duplicates]
    
    def get_products_missing_images(self, limit: Optional[int] = None) -> List[Product]:
        """Get products without featured images."""
        query = self.session.query(Product).filter(
            or_(
                Product.featured_image_url.is_(None),
                Product.featured_image_url == ''
            )
        )
        if limit:
            query = query.limit(limit)
        return query.all()
    
    def get_inventory_alerts(self, threshold: int = 10) -> List[Product]:
        """Get products with low inventory."""
        return self.session.query(Product).filter(
            and_(
                Product.track_inventory == True,
                Product.inventory_quantity < threshold,
                Product.status == ProductStatus.ACTIVE.value
            )
        ).all()
    
    def get_category_product_counts(self) -> Dict[int, int]:
        """Get product count for each category."""
        counts = self.session.query(
            Product.category_id,
            func.count(Product.id).label('count')
        ).group_by(Product.category_id).all()
        
        return {category_id: count for category_id, count in counts}
    
    def search_advanced(self, filters: Dict[str, Any], sort_by: Optional[str] = None, 
                       sort_order: str = 'asc', page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        """Advanced search with multiple filters and sorting."""
        query = self.session.query(Product)
        
        # Apply filters
        if filters.get('query'):
            search_term = f"%{filters['query']}%"
            query = query.filter(
                or_(
                    Product.sku.ilike(search_term),
                    Product.name.ilike(search_term),
                    Product.description.ilike(search_term)
                )
            )
        
        if filters.get('category_id'):
            query = query.filter(Product.category_id == filters['category_id'])
        
        if filters.get('brand'):
            query = query.filter(Product.brand == filters['brand'])
        
        if filters.get('status'):
            query = query.filter(Product.status == filters['status'])
        
        if filters.get('min_price') is not None:
            query = query.filter(Product.price >= filters['min_price'])
        
        if filters.get('max_price') is not None:
            query = query.filter(Product.price <= filters['max_price'])
        
        if filters.get('in_stock') is not None:
            if filters['in_stock']:
                query = query.filter(Product.inventory_quantity > 0)
            else:
                query = query.filter(Product.inventory_quantity == 0)
        
        if filters.get('synced') is not None:
            if filters['synced']:
                query = query.filter(Product.shopify_product_id.isnot(None))
            else:
                query = query.filter(Product.shopify_product_id.is_(None))
        
        # Apply sorting
        if sort_by and hasattr(Product, sort_by):
            order_func = getattr(getattr(Product, sort_by), 'desc' if sort_order == 'desc' else 'asc')
            query = query.order_by(order_func())
        
        # Get total count before pagination
        total = query.count()
        
        # Apply pagination
        offset = (page - 1) * per_page
        items = query.offset(offset).limit(per_page).all()
        
        # Calculate pagination metadata
        total_pages = (total + per_page - 1) // per_page
        
        return {
            'items': items,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': total_pages,
            'has_prev': page > 1,
            'has_next': page < total_pages
        }
    
    def create_product(self, product_data: Dict[str, Any]) -> Optional[Product]:
        """Create a new product."""
        try:
            product = Product(**product_data)
            self.session.add(product)
            self.session.commit()
            self.session.refresh(product)
            return product
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error creating product: {e}")
            return None
    
    def update_product(self, product_id: int, update_data: Dict[str, Any]) -> Optional[Product]:
        """Update an existing product."""
        try:
            product = self.session.query(Product).filter(Product.id == product_id).first()
            if not product:
                return None
            
            for key, value in update_data.items():
                if hasattr(product, key):
                    setattr(product, key, value)
            
            self.session.commit()
            self.session.refresh(product)
            return product
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error updating product {product_id}: {e}")
            return None
    
    def count_all(self) -> int:
        """Count all products."""
        return self.session.query(Product).count()
    
    def count_by_sync_status(self, sync_status: str) -> int:
        """Count products by sync status."""
        return self.session.query(Product).filter(
            Product.shopify_sync_status == sync_status
        ).count()
    
    def get_recently_synced(self, limit: int = 10) -> List[Product]:
        """Get recently synced products."""
        return self.session.query(Product).filter(
            Product.shopify_synced_at.isnot(None)
        ).order_by(Product.shopify_synced_at.desc()).limit(limit).all()