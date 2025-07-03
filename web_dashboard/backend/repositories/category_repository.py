"""
Category Repository for managing category database operations.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func

from models import Category, Product
from .base import BaseRepository

class CategoryRepository(BaseRepository):
    """Repository for Category model operations."""
    
    def __init__(self, session: Session):
        super().__init__(Category, session)
    
    def get_by_slug(self, slug: str) -> Optional[Category]:
        """Get category by slug."""
        return self.get_by(slug=slug)
    
    def get_by_shopify_id(self, shopify_id: str) -> Optional[Category]:
        """Get category by Shopify collection ID."""
        return self.get_by(shopify_collection_id=shopify_id)
    
    def get_root_categories(self) -> List[Category]:
        """Get all root categories (no parent)."""
        return self.session.query(Category).filter(
            Category.parent_id.is_(None),
            Category.is_active == True
        ).order_by(Category.sort_order, Category.name).all()
    
    def get_children(self, parent_id: int) -> List[Category]:
        """Get direct children of a category."""
        return self.session.query(Category).filter(
            Category.parent_id == parent_id,
            Category.is_active == True
        ).order_by(Category.sort_order, Category.name).all()
    
    def get_descendants(self, category_id: int) -> List[Category]:
        """Get all descendants of a category (recursive)."""
        category = self.get(category_id)
        if not category or not category.path:
            return []
        
        return self.session.query(Category).filter(
            Category.path.like(f"{category.path}/%"),
            Category.is_active == True
        ).order_by(Category.level, Category.sort_order).all()
    
    def get_ancestors(self, category_id: int) -> List[Category]:
        """Get all ancestors of a category."""
        category = self.get(category_id)
        if not category or not category.path:
            return []
        
        # Parse path to get ancestor IDs
        ancestor_ids = [int(id_str) for id_str in category.path.split('/') if id_str and id_str != str(category_id)]
        
        if not ancestor_ids:
            return []
        
        return self.session.query(Category).filter(
            Category.id.in_(ancestor_ids)
        ).order_by(Category.level).all()
    
    def get_tree(self) -> List[Dict[str, Any]]:
        """Get complete category tree structure."""
        def build_tree(parent_id=None):
            categories = self.session.query(Category).filter(
                Category.parent_id == parent_id,
                Category.is_active == True
            ).order_by(Category.sort_order, Category.name).all()
            
            tree = []
            for category in categories:
                node = {
                    'id': category.id,
                    'name': category.name,
                    'slug': category.slug,
                    'description': category.description,
                    'level': category.level,
                    'product_count': self.get_product_count(category.id),
                    'children': build_tree(category.id)
                }
                tree.append(node)
            
            return tree
        
        return build_tree()
    
    def get_product_count(self, category_id: int, include_descendants: bool = False) -> int:
        """Get count of products in a category."""
        if include_descendants:
            category = self.get(category_id)
            if category and category.path:
                return self.session.query(func.count(Product.id)).join(Category).filter(
                    or_(
                        Category.id == category_id,
                        Category.path.like(f"{category.path}/%")
                    ),
                    Product.is_active == True
                ).scalar() or 0
        
        return self.session.query(func.count(Product.id)).filter(
            Product.category_id == category_id,
            Product.is_active == True
        ).scalar() or 0
    
    def create_with_path(self, name: str, slug: str, parent_id: Optional[int] = None, 
                        description: Optional[str] = None, **kwargs) -> Category:
        """Create category with automatic path calculation."""
        # Calculate level and path
        level = 0
        path = ""
        
        if parent_id:
            parent = self.get(parent_id)
            if parent:
                level = parent.level + 1
                path = f"{parent.path}/{parent.id}" if parent.path else str(parent.id)
        
        category = self.create(
            name=name,
            slug=slug,
            parent_id=parent_id,
            level=level,
            path=path,
            description=description,
            **kwargs
        )
        
        # Update path to include self
        if category.id:
            category.path = f"{path}/{category.id}" if path else str(category.id)
            self.session.flush()
        
        return category
    
    def move_category(self, category_id: int, new_parent_id: Optional[int]) -> bool:
        """Move category to a new parent."""
        category = self.get(category_id)
        if not category:
            return False
        
        # Prevent moving to self or descendants
        if new_parent_id:
            new_parent = self.get(new_parent_id)
            if not new_parent:
                return False
            
            # Check if new parent is a descendant
            if new_parent.path and str(category_id) in new_parent.path.split('/'):
                return False
        
        # Get old path for updating descendants
        old_path = category.path or str(category.id)
        
        # Calculate new level and path
        if new_parent_id:
            parent = self.get(new_parent_id)
            new_level = parent.level + 1
            new_path = f"{parent.path}/{category.id}" if parent.path else f"{parent.id}/{category.id}"
        else:
            new_level = 0
            new_path = str(category.id)
        
        # Update category
        category.parent_id = new_parent_id
        category.level = new_level
        category.path = new_path
        
        # Update all descendants
        descendants = self.get_descendants(category_id)
        for descendant in descendants:
            if descendant.path:
                descendant.path = descendant.path.replace(old_path, new_path, 1)
                descendant.level = len(descendant.path.split('/')) - 1
        
        self.session.flush()
        return True
    
    def get_with_products(self, category_id: int, limit: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Get category with its products."""
        category = self.session.query(Category).options(
            joinedload(Category.products)
        ).filter(Category.id == category_id).first()
        
        if not category:
            return None
        
        products = category.products
        if limit:
            products = products[:limit]
        
        return {
            'category': category,
            'products': products,
            'product_count': len(category.products)
        }
    
    def get_unsynced(self) -> List[Category]:
        """Get categories not synced to Shopify."""
        return self.session.query(Category).filter(
            Category.shopify_collection_id.is_(None),
            Category.is_active == True
        ).all()
    
    def update_shopify_sync(self, category_id: int, shopify_collection_id: str, 
                           shopify_handle: str) -> Optional[Category]:
        """Update category after Shopify sync."""
        from datetime import datetime
        
        return self.update(
            category_id,
            shopify_collection_id=shopify_collection_id,
            shopify_handle=shopify_handle,
            shopify_synced_at=datetime.utcnow()
        )
    
    def search(self, query: str, limit: int = 50) -> List[Category]:
        """Search categories by name or description."""
        search_term = f"%{query}%"
        return self.session.query(Category).filter(
            or_(
                Category.name.ilike(search_term),
                Category.description.ilike(search_term),
                Category.slug.ilike(search_term)
            ),
            Category.is_active == True
        ).limit(limit).all()
    
    def get_popular_categories(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get categories with most products."""
        results = self.session.query(
            Category,
            func.count(Product.id).label('product_count')
        ).join(Product).filter(
            Category.is_active == True,
            Product.is_active == True
        ).group_by(Category.id).order_by(
            func.count(Product.id).desc()
        ).limit(limit).all()
        
        return [
            {
                'category': category,
                'product_count': count
            }
            for category, count in results
        ]