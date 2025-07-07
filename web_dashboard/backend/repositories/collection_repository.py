"""Repository for Collection data operations."""
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from sqlalchemy import func, and_, or_, distinct, case
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy.exc import IntegrityError

from models import Collection, Product, ProductCollection
from repositories.base_repository import BaseRepository


class CollectionRepository(BaseRepository[Collection]):
    """Repository for collection-related database operations."""
    
    def __init__(self, session: Session):
        super().__init__(Collection, session)
    
    def get_with_products(self, collection_id: int) -> Optional[Collection]:
        """Get a collection with its products loaded."""
        return self.session.query(Collection)\
            .options(selectinload(Collection.products))\
            .filter(Collection.id == collection_id)\
            .first()
    
    def get_by_handle(self, handle: str) -> Optional[Collection]:
        """Get a collection by its handle."""
        return self.session.query(Collection)\
            .filter(Collection.handle == handle)\
            .first()
    
    def get_by_shopify_id(self, shopify_id: str) -> Optional[Collection]:
        """Get a collection by its Shopify ID."""
        return self.session.query(Collection)\
            .filter(Collection.shopify_collection_id == shopify_id)\
            .first()
    
    def get_all_with_stats(self, 
                          status: Optional[str] = None,
                          include_archived: bool = False) -> List[Dict[str, Any]]:
        """Get all collections with product counts and sync status."""
        query = self.session.query(
            Collection,
            func.count(distinct(ProductCollection.product_id)).label('actual_product_count')
        ).outerjoin(ProductCollection)\
         .group_by(Collection.id)
        
        if status:
            query = query.filter(Collection.status == status)
        
        if not include_archived:
            query = query.filter(Collection.status != 'archived')
        
        results = []
        for collection, product_count in query.all():
            results.append({
                'id': collection.id,
                'name': collection.name,
                'handle': collection.handle,
                'description': collection.description,
                'status': collection.status,
                'rules_type': collection.rules_type,
                'products_count': product_count,
                'shopify_collection_id': collection.shopify_collection_id,
                'shopify_synced_at': collection.shopify_synced_at,
                'shopify_sync_status': collection.shopify_sync_status,
                'created_at': collection.created_at,
                'updated_at': collection.updated_at
            })
        
        return results
    
    def create_collection(self, 
                         name: str,
                         handle: str,
                         description: str,
                         created_by: int,
                         rules_type: str = 'manual',
                         rules_conditions: Optional[List[Dict]] = None,
                         **kwargs) -> Collection:
        """Create a new collection."""
        collection = Collection(
            name=name,
            handle=handle,
            description=description,
            created_by=created_by,
            rules_type=rules_type,
            rules_conditions=rules_conditions,
            **kwargs
        )
        
        self.session.add(collection)
        self.session.commit()
        return collection
    
    def update_collection(self, 
                         collection_id: int,
                         updated_by: int,
                         **updates) -> Optional[Collection]:
        """Update a collection."""
        collection = self.get(collection_id)
        if not collection:
            return None
        
        # Update fields
        for key, value in updates.items():
            if hasattr(collection, key):
                setattr(collection, key, value)
        
        collection.updated_by = updated_by
        collection.updated_at = datetime.utcnow()
        
        self.session.commit()
        return collection
    
    def add_products_to_collection(self, 
                                  collection_id: int,
                                  product_ids: List[int],
                                  position_start: int = 0) -> int:
        """Add products to a collection."""
        added_count = 0
        position = position_start
        
        for product_id in product_ids:
            # Check if product exists
            product_exists = self.session.query(Product).filter(Product.id == product_id).count() > 0
            if not product_exists:
                continue
            
            # Check if already in collection
            existing = self.session.query(ProductCollection)\
                .filter(and_(
                    ProductCollection.collection_id == collection_id,
                    ProductCollection.product_id == product_id
                )).first()
            
            if not existing:
                product_collection = ProductCollection(
                    collection_id=collection_id,
                    product_id=product_id,
                    position=position
                )
                self.session.add(product_collection)
                added_count += 1
                position += 1
        
        if added_count > 0:
            # Update product count
            self._update_product_count(collection_id)
            self.session.commit()
        
        return added_count
    
    def remove_products_from_collection(self, 
                                       collection_id: int,
                                       product_ids: List[int]) -> int:
        """Remove products from a collection."""
        removed_count = self.session.query(ProductCollection)\
            .filter(and_(
                ProductCollection.collection_id == collection_id,
                ProductCollection.product_id.in_(product_ids)
            )).delete(synchronize_session=False)
        
        if removed_count > 0:
            self._update_product_count(collection_id)
            self.session.commit()
        
        return removed_count
    
    def update_product_positions(self, 
                                collection_id: int,
                                positions: Dict[int, int]) -> bool:
        """Update product positions within a collection."""
        for product_id, position in positions.items():
            self.session.query(ProductCollection)\
                .filter(and_(
                    ProductCollection.collection_id == collection_id,
                    ProductCollection.product_id == product_id
                )).update({'position': position})
        
        self.session.commit()
        return True
    
    def sync_with_shopify(self, 
                         collection_id: int,
                         shopify_collection_id: str,
                         shopify_handle: str) -> bool:
        """Update collection with Shopify sync information."""
        collection = self.get(collection_id)
        if not collection:
            return False
        
        collection.shopify_collection_id = shopify_collection_id
        collection.shopify_handle = shopify_handle
        collection.shopify_synced_at = datetime.utcnow()
        collection.shopify_sync_status = 'synced'
        
        self.session.commit()
        return True
    
    def get_products_by_rules(self, 
                             rules_conditions: List[Dict],
                             disjunctive: bool = False) -> List[Product]:
        """Get products that match automatic collection rules."""
        if not rules_conditions:
            return []
        
        # Build query conditions
        conditions = []
        for rule in rules_conditions:
            field = rule.get('field')
            operator = rule.get('operator')
            value = rule.get('value')
            
            if field == 'product_type':
                if operator == 'equals':
                    conditions.append(Product.product_type == value)
                elif operator == 'contains':
                    conditions.append(Product.product_type.contains(value))
                elif operator == 'starts_with':
                    conditions.append(Product.product_type.startswith(value))
                elif operator == 'ends_with':
                    conditions.append(Product.product_type.endswith(value))
            
            elif field == 'vendor':
                if operator == 'equals':
                    conditions.append(Product.manufacturer == value)
                elif operator == 'contains':
                    conditions.append(Product.manufacturer.contains(value))
            
            elif field == 'title':
                if operator == 'contains':
                    conditions.append(Product.name.contains(value))
                elif operator == 'starts_with':
                    conditions.append(Product.name.startswith(value))
                elif operator == 'ends_with':
                    conditions.append(Product.name.endswith(value))
            
            elif field == 'tag':
                # Assuming tags are stored in meta_data JSON field
                conditions.append(Product.meta_data['tags'].contains(value))
        
        if not conditions:
            return []
        
        # Apply OR or AND logic
        if disjunctive:
            query = self.session.query(Product).filter(or_(*conditions))
        else:
            query = self.session.query(Product).filter(and_(*conditions))
        
        return query.all()
    
    def update_automatic_collection(self, collection_id: int) -> int:
        """Update products in an automatic collection based on its rules."""
        collection = self.get(collection_id)
        if not collection or collection.rules_type != 'automatic':
            return 0
        
        # Get products matching the rules
        matching_products = self.get_products_by_rules(
            collection.rules_conditions or [],
            collection.disjunctive
        )
        
        # Get current products in collection
        current_product_ids = set(
            self.session.query(ProductCollection.product_id)
            .filter(ProductCollection.collection_id == collection_id)
            .all()
        )
        current_product_ids = {pid[0] for pid in current_product_ids}
        
        # Get matching product IDs
        matching_product_ids = {p.id for p in matching_products}
        
        # Remove products that no longer match
        to_remove = current_product_ids - matching_product_ids
        if to_remove:
            self.remove_products_from_collection(collection_id, list(to_remove))
        
        # Add new matching products
        to_add = matching_product_ids - current_product_ids
        if to_add:
            self.add_products_to_collection(collection_id, list(to_add))
        
        return len(to_add) + len(to_remove)
    
    def get_product_types_summary(self) -> List[Dict[str, Any]]:
        """Get summary of product types for collection creation."""
        results = self.session.query(
            Product.product_type,
            func.count(Product.id).label('product_count'),
            func.avg(Product.price).label('avg_price'),
            func.array_agg(distinct(Product.brand)).label('brands'),
            func.array_agg(distinct(Product.category_id)).label('category_ids')
        ).filter(
            Product.product_type.isnot(None),
            Product.status == 'active'
        ).group_by(Product.product_type).all()
        
        summary = []
        for row in results:
            summary.append({
                'name': row.product_type,
                'product_count': row.product_count,
                'avg_price': float(row.avg_price) if row.avg_price else 0,
                'vendors': [b for b in row.brands if b],
                'categories': [c for c in row.category_ids if c]
            })
        
        return summary
    
    def _update_product_count(self, collection_id: int):
        """Update the product count for a collection."""
        count = self.session.query(ProductCollection)\
            .filter(ProductCollection.collection_id == collection_id)\
            .count()
        
        self.session.query(Collection)\
            .filter(Collection.id == collection_id)\
            .update({'products_count': count})