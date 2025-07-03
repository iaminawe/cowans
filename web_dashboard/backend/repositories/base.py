"""
Base Repository class with common database operations.
"""

from typing import Type, TypeVar, List, Optional, Dict, Any, Union
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy import and_, or_, func
import logging

from models import Base

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=Base)

class BaseRepository:
    """Base repository with common CRUD operations."""
    
    def __init__(self, model: Type[T], session: Session):
        self.model = model
        self.session = session
    
    def get(self, id: int) -> Optional[T]:
        """Get a single record by ID."""
        try:
            return self.session.query(self.model).filter(self.model.id == id).first()
        except SQLAlchemyError as e:
            logger.error(f"Error getting {self.model.__name__} with id {id}: {e}")
            raise
    
    def get_by(self, **kwargs) -> Optional[T]:
        """Get a single record by field values."""
        try:
            return self.session.query(self.model).filter_by(**kwargs).first()
        except SQLAlchemyError as e:
            logger.error(f"Error getting {self.model.__name__} by {kwargs}: {e}")
            raise
    
    def get_all(self, limit: Optional[int] = None, offset: Optional[int] = None) -> List[T]:
        """Get all records with optional pagination."""
        try:
            query = self.session.query(self.model)
            if offset:
                query = query.offset(offset)
            if limit:
                query = query.limit(limit)
            return query.all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting all {self.model.__name__}: {e}")
            raise
    
    def filter(self, filters: Dict[str, Any], limit: Optional[int] = None, offset: Optional[int] = None) -> List[T]:
        """Filter records by multiple fields."""
        try:
            query = self.session.query(self.model)
            
            for field, value in filters.items():
                if hasattr(self.model, field):
                    if value is None:
                        query = query.filter(getattr(self.model, field).is_(None))
                    elif isinstance(value, list):
                        query = query.filter(getattr(self.model, field).in_(value))
                    elif isinstance(value, dict):
                        # Handle complex filters like {'gt': 10, 'lt': 20}
                        if 'gt' in value:
                            query = query.filter(getattr(self.model, field) > value['gt'])
                        if 'gte' in value:
                            query = query.filter(getattr(self.model, field) >= value['gte'])
                        if 'lt' in value:
                            query = query.filter(getattr(self.model, field) < value['lt'])
                        if 'lte' in value:
                            query = query.filter(getattr(self.model, field) <= value['lte'])
                        if 'like' in value:
                            query = query.filter(getattr(self.model, field).like(f"%{value['like']}%"))
                        if 'ilike' in value:
                            query = query.filter(getattr(self.model, field).ilike(f"%{value['ilike']}%"))
                    else:
                        query = query.filter(getattr(self.model, field) == value)
            
            if offset:
                query = query.offset(offset)
            if limit:
                query = query.limit(limit)
            
            return query.all()
        except SQLAlchemyError as e:
            logger.error(f"Error filtering {self.model.__name__}: {e}")
            raise
    
    def create(self, **kwargs) -> T:
        """Create a new record."""
        try:
            instance = self.model(**kwargs)
            self.session.add(instance)
            self.session.flush()  # Flush to get ID without committing
            return instance
        except IntegrityError as e:
            logger.error(f"Integrity error creating {self.model.__name__}: {e}")
            raise
        except SQLAlchemyError as e:
            logger.error(f"Error creating {self.model.__name__}: {e}")
            raise
    
    def update(self, id: int, **kwargs) -> Optional[T]:
        """Update a record by ID."""
        try:
            instance = self.get(id)
            if not instance:
                return None
            
            for key, value in kwargs.items():
                if hasattr(instance, key):
                    setattr(instance, key, value)
            
            self.session.flush()
            return instance
        except IntegrityError as e:
            logger.error(f"Integrity error updating {self.model.__name__} {id}: {e}")
            raise
        except SQLAlchemyError as e:
            logger.error(f"Error updating {self.model.__name__} {id}: {e}")
            raise
    
    def delete(self, id: int) -> bool:
        """Delete a record by ID."""
        try:
            instance = self.get(id)
            if not instance:
                return False
            
            self.session.delete(instance)
            self.session.flush()
            return True
        except SQLAlchemyError as e:
            logger.error(f"Error deleting {self.model.__name__} {id}: {e}")
            raise
    
    def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count records with optional filters."""
        try:
            query = self.session.query(func.count(self.model.id))
            
            if filters:
                for field, value in filters.items():
                    if hasattr(self.model, field):
                        if value is None:
                            query = query.filter(getattr(self.model, field).is_(None))
                        elif isinstance(value, list):
                            query = query.filter(getattr(self.model, field).in_(value))
                        else:
                            query = query.filter(getattr(self.model, field) == value)
            
            return query.scalar()
        except SQLAlchemyError as e:
            logger.error(f"Error counting {self.model.__name__}: {e}")
            raise
    
    def exists(self, **kwargs) -> bool:
        """Check if a record exists."""
        try:
            return self.session.query(
                self.session.query(self.model).filter_by(**kwargs).exists()
            ).scalar()
        except SQLAlchemyError as e:
            logger.error(f"Error checking existence of {self.model.__name__}: {e}")
            raise
    
    def bulk_create(self, items: List[Dict[str, Any]]) -> List[T]:
        """Create multiple records."""
        try:
            instances = [self.model(**item) for item in items]
            self.session.bulk_save_objects(instances, return_defaults=True)
            self.session.flush()
            return instances
        except IntegrityError as e:
            logger.error(f"Integrity error bulk creating {self.model.__name__}: {e}")
            raise
        except SQLAlchemyError as e:
            logger.error(f"Error bulk creating {self.model.__name__}: {e}")
            raise
    
    def paginate(self, page: int = 1, per_page: int = 20, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Paginate results with metadata."""
        try:
            # Calculate offset
            offset = (page - 1) * per_page
            
            # Get total count
            total = self.count(filters)
            
            # Get items
            items = self.filter(filters, limit=per_page, offset=offset) if filters else self.get_all(limit=per_page, offset=offset)
            
            # Calculate pagination metadata
            total_pages = (total + per_page - 1) // per_page
            has_prev = page > 1
            has_next = page < total_pages
            
            return {
                'items': items,
                'total': total,
                'page': page,
                'per_page': per_page,
                'total_pages': total_pages,
                'has_prev': has_prev,
                'has_next': has_next
            }
        except SQLAlchemyError as e:
            logger.error(f"Error paginating {self.model.__name__}: {e}")
            raise