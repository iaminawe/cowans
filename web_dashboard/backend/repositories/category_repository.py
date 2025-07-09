"""
Category Repository for managing category database operations.
"""

import logging
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func

from models import Category, Product
from .base import BaseRepository

logger = logging.getLogger(__name__)

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
    
    def get_category_tree(self, include_inactive: bool = False, search: str = "") -> List[Dict[str, Any]]:
        """Get hierarchical category tree."""
        # Get all categories
        query = self.session.query(Category)
        
        if not include_inactive:
            query = query.filter(Category.is_active == True)
        
        if search:
            query = query.filter(Category.name.ilike(f"%{search}%"))
        
        query = query.order_by(Category.level, Category.sort_order, Category.name)
        categories = query.all()
        
        # Build tree structure
        category_dict = {}
        root_categories = []
        
        for cat in categories:
            cat_data = self.to_dict_with_counts(cat)
            cat_data['children'] = []
            category_dict[cat.id] = cat_data
            
            if cat.parent_id is None:
                root_categories.append(cat_data)
            elif cat.parent_id in category_dict:
                category_dict[cat.parent_id]['children'].append(cat_data)
        
        return root_categories
    
    def get_all_with_counts(self, include_inactive: bool = False, search: str = "") -> List[Dict[str, Any]]:
        """Get all categories with product counts."""
        query = self.session.query(Category)
        
        if not include_inactive:
            query = query.filter(Category.is_active == True)
        
        if search:
            query = query.filter(Category.name.ilike(f"%{search}%"))
        
        query = query.order_by(Category.level, Category.sort_order, Category.name)
        categories = query.all()
        
        return [self.to_dict_with_counts(cat) for cat in categories]
    
    def to_dict_with_counts(self, category: Category) -> Dict[str, Any]:
        """Convert category to dict with product counts."""
        product_count = self.count_products_in_category(category.id)
        
        return {
            'id': category.id,
            'name': category.name,
            'description': category.description,
            'slug': category.slug,
            'parent_id': category.parent_id,
            'level': category.level,
            'path': category.path,
            'sort_order': category.sort_order,
            'is_active': category.is_active,
            'shopify_collection_id': category.shopify_collection_id,
            'shopify_handle': category.shopify_handle,
            'shopify_synced_at': category.shopify_synced_at.isoformat() if category.shopify_synced_at else None,
            'meta_data': category.meta_data,
            'created_at': category.created_at.isoformat(),
            'updated_at': category.updated_at.isoformat(),
            'product_count': product_count
        }
    
    def count(self) -> int:
        """Count total categories."""
        return self.session.query(func.count(Category.id)).scalar() or 0
    
    def count_active(self) -> int:
        """Count active categories."""
        return self.session.query(func.count(Category.id)).filter(
            Category.is_active == True
        ).scalar() or 0
    
    def count_with_products(self) -> int:
        """Count categories that have products."""
        return self.session.query(func.count(func.distinct(Product.category_id))).filter(
            Product.category_id.isnot(None)
        ).scalar() or 0
    
    def count_empty(self) -> int:
        """Count categories with no products."""
        subquery = self.session.query(func.distinct(Product.category_id)).subquery()
        return self.session.query(func.count(Category.id)).filter(
            Category.id.notin_(subquery)
        ).scalar() or 0
    
    def get_max_depth(self) -> int:
        """Get maximum category depth/level."""
        return self.session.query(func.max(Category.level)).scalar() or 0
    
    def get_avg_products_per_category(self) -> float:
        """Get average number of products per category."""
        total_categories = self.count_active()
        if total_categories == 0:
            return 0.0
        
        total_products = self.session.query(func.count(Product.id)).filter(
            Product.category_id.isnot(None)
        ).scalar() or 0
        
        return round(total_products / total_categories, 2)
    
    def count_products_in_category(self, category_id: int) -> int:
        """Count products in a specific category."""
        return self.session.query(func.count(Product.id)).filter(
            Product.category_id == category_id
        ).scalar() or 0
    
    def would_create_cycle(self, category_id: int, new_parent_id: int) -> bool:
        """Check if moving category would create a circular reference."""
        if category_id == new_parent_id:
            return True
        
        # Check if new_parent_id is a descendant of category_id
        category = self.get(category_id)
        if not category or not category.path:
            return False
        
        descendants = self.get_descendants(category_id)
        return any(desc.id == new_parent_id for desc in descendants)
    
    def update_descendant_paths(self, category_id: int):
        """Update paths for all descendants after moving a category."""
        category = self.get(category_id)
        if not category:
            return
        
        # Get all descendants
        descendants = self.session.query(Category).filter(
            Category.path.like(f"%/{category_id}/%")
        ).all()
        
        for desc in descendants:
            # Recalculate path based on new hierarchy
            path_parts = []
            current = desc
            
            while current and current.parent_id:
                current = self.get(current.parent_id)
                if current:
                    path_parts.append(str(current.id))
            
            desc.path = "/".join(reversed(path_parts)) if path_parts else None
            desc.level = len(path_parts)
    
    def move_category(self, category_id: int, new_parent_id: Optional[int], position: int = 0) -> bool:
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
    
    def get_by_name(self, name: str) -> Optional[Category]:
        """Get category by name."""
        return self.session.query(Category).filter(
            Category.name.ilike(f'%{name}%')
        ).first()
    
    def create_category(self, category_data: Dict[str, Any]) -> Optional[Category]:
        """Create a new category."""
        try:
            category = Category(**category_data)
            self.session.add(category)
            self.session.commit()
            self.session.refresh(category)
            return category
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error creating category: {e}")
            return None
    
    def update_category(self, category_id: int, update_data: Dict[str, Any]) -> Optional[Category]:
        """Update an existing category."""
        try:
            category = self.session.query(Category).filter(Category.id == category_id).first()
            if not category:
                return None
            
            for key, value in update_data.items():
                if hasattr(category, key):
                    setattr(category, key, value)
            
            self.session.commit()
            self.session.refresh(category)
            return category
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error updating category {category_id}: {e}")
            return None
    
    def count_with_shopify_mapping(self) -> int:
        """Count categories that have Shopify collection mapping."""
        return self.session.query(Category).filter(
            Category.shopify_collection_id.isnot(None)
        ).count()