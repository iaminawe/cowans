"""
User Repository for managing user database operations.
"""

from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

from models import User
from .base import BaseRepository

class UserRepository(BaseRepository):
    """Repository for User model operations."""
    
    def __init__(self, session: Session):
        super().__init__(User, session)
    
    def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        return self.get_by(email=email.lower())
    
    def get_by_supabase_id(self, supabase_id: str) -> Optional[User]:
        """Get user by Supabase ID."""
        return self.get_by(supabase_id=supabase_id)
    
    def create_user(self, email: str, password: str, first_name: Optional[str] = None,
                   last_name: Optional[str] = None, is_admin: bool = False,
                   supabase_id: Optional[str] = None) -> User:
        """Create a new user with hashed password."""
        return self.create(
            email=email.lower(),
            password_hash=generate_password_hash(password) if password else "",
            first_name=first_name,
            last_name=last_name,
            is_admin=is_admin,
            is_active=True,
            supabase_id=supabase_id
        )
    
    def verify_password(self, user: User, password: str) -> bool:
        """Verify user password."""
        return check_password_hash(user.password_hash, password)
    
    def update_password(self, user_id: int, new_password: str) -> Optional[User]:
        """Update user password."""
        return self.update(user_id, password_hash=generate_password_hash(new_password))
    
    def update_last_login(self, user_id: int) -> Optional[User]:
        """Update user's last login timestamp."""
        return self.update(user_id, last_login=datetime.utcnow())
    
    def get_active_users(self) -> List[User]:
        """Get all active users."""
        return self.filter({'is_active': True})
    
    def get_admins(self) -> List[User]:
        """Get all admin users."""
        return self.filter({'is_admin': True, 'is_active': True})
    
    def deactivate_user(self, user_id: int) -> Optional[User]:
        """Deactivate a user account."""
        return self.update(user_id, is_active=False)
    
    def activate_user(self, user_id: int) -> Optional[User]:
        """Activate a user account."""
        return self.update(user_id, is_active=True)
    
    def search_users(self, query: str) -> List[User]:
        """Search users by email, first name, or last name."""
        search_term = f"%{query}%"
        return self.session.query(User).filter(
            or_(
                User.email.ilike(search_term),
                User.first_name.ilike(search_term),
                User.last_name.ilike(search_term)
            )
        ).all()
    
    def count_active(self) -> int:
        """Count active users."""
        return self.count({'is_active': True})
    
    def count_admins(self) -> int:
        """Count admin users."""
        return self.count({'is_admin': True, 'is_active': True})
    
    def count_created_since(self, since_date: datetime) -> int:
        """Count users created since a specific date."""
        return self.session.query(User).filter(
            User.created_at >= since_date
        ).count()
    
    def get_paginated(self, page: int = 1, limit: int = 50, search: str = '', 
                     filters: Dict[str, Any] = None, sort_by: str = 'created_at', 
                     sort_order: str = 'desc') -> tuple:
        """Get paginated users with search and filters."""
        query = self.session.query(User)
        
        # Apply search
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    User.email.ilike(search_term),
                    User.first_name.ilike(search_term),
                    User.last_name.ilike(search_term)
                )
            )
        
        # Apply filters
        if filters:
            for field, value in filters.items():
                if hasattr(User, field):
                    query = query.filter(getattr(User, field) == value)
        
        # Get total count
        total = query.count()
        
        # Apply sorting
        if hasattr(User, sort_by):
            order_func = getattr(User, sort_by).desc() if sort_order == 'desc' else getattr(User, sort_by).asc()
            query = query.order_by(order_func)
        
        # Apply pagination
        query = query.offset((page - 1) * limit).limit(limit)
        
        return query.all(), total