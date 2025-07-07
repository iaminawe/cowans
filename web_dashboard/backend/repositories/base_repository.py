"""Base repository class for common database operations."""
from typing import TypeVar, Generic, List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

T = TypeVar('T')


class BaseRepository(Generic[T]):
    """Base repository providing common database operations."""
    
    def __init__(self, model_class: type[T], session: Session):
        self.model_class = model_class
        self.session = session
    
    def get(self, id: int) -> Optional[T]:
        """Get a single record by ID."""
        return self.session.query(self.model_class).filter(self.model_class.id == id).first()
    
    def get_all(self, offset: int = 0, limit: int = 100) -> List[T]:
        """Get all records with pagination."""
        return self.session.query(self.model_class).offset(offset).limit(limit).all()
    
    def create(self, **kwargs) -> T:
        """Create a new record."""
        instance = self.model_class(**kwargs)
        self.session.add(instance)
        self.session.commit()
        return instance
    
    def update(self, id: int, **kwargs) -> Optional[T]:
        """Update a record by ID."""
        instance = self.get(id)
        if instance:
            for key, value in kwargs.items():
                setattr(instance, key, value)
            self.session.commit()
        return instance
    
    def delete(self, id: int) -> bool:
        """Delete a record by ID."""
        instance = self.get(id)
        if instance:
            self.session.delete(instance)
            self.session.commit()
            return True
        return False
    
    def count(self) -> int:
        """Get the total count of records."""
        return self.session.query(self.model_class).count()
    
    def exists(self, **kwargs) -> bool:
        """Check if a record exists with given criteria."""
        return self.session.query(self.model_class).filter_by(**kwargs).count() > 0