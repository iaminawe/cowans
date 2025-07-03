"""
Base Migration Class

This module provides the base class for all database migrations.
"""

from abc import ABC, abstractmethod
from typing import Optional
from sqlalchemy.orm import Session


class BaseMigration(ABC):
    """Base class for all database migrations."""
    
    def __init__(self, version: str, description: str):
        """Initialize migration."""
        self.version = version
        self.description = description
    
    @abstractmethod
    def upgrade(self, session: Session) -> None:
        """Upgrade the database schema."""
        pass
    
    @abstractmethod
    def downgrade(self, session: Session) -> None:
        """Downgrade the database schema."""
        pass
    
    def can_rollback(self) -> bool:
        """Check if this migration can be rolled back."""
        return True
    
    def get_dependencies(self) -> list:
        """Get list of migration versions this migration depends on."""
        return []
    
    def validate_upgrade(self, session: Session) -> bool:
        """Validate that the upgrade was successful."""
        return True
    
    def validate_downgrade(self, session: Session) -> bool:
        """Validate that the downgrade was successful."""
        return True
    
    def __str__(self):
        return f"Migration {self.version}: {self.description}"
    
    def __repr__(self):
        return f"<Migration(version='{self.version}', description='{self.description}')>"