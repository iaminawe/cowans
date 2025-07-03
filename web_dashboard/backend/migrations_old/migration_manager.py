"""
Migration Manager

This module manages database migrations.
"""

import os
import importlib.util
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

from .base_migration import BaseMigration

logger = logging.getLogger(__name__)

# Migration tracking table
MigrationBase = declarative_base()

class MigrationHistory(MigrationBase):
    """Track migration history in the database."""
    __tablename__ = 'migration_history'
    
    id = Column(Integer, primary_key=True)
    version = Column(String(50), unique=True, nullable=False)
    description = Column(String(500), nullable=False)
    applied_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    applied_by = Column(String(100))
    rollback_sql = Column(Text)
    is_rolled_back = Column(Boolean, default=False)
    rolled_back_at = Column(DateTime)
    
    def __repr__(self):
        return f"<MigrationHistory(version='{self.version}', applied_at='{self.applied_at}')>"


class MigrationManager:
    """Manages database migrations."""
    
    def __init__(self, database_url: str, migrations_dir: str = None):
        """Initialize migration manager."""
        self.database_url = database_url
        self.migrations_dir = migrations_dir or os.path.join(os.path.dirname(__file__), 'versions')
        self.engine = None
        self.session_factory = None
        
        # Ensure migrations directory exists
        os.makedirs(self.migrations_dir, exist_ok=True)
        
        self._initialize_database()
    
    def _initialize_database(self):
        """Initialize database connection for migrations."""
        try:
            # Create engine
            if self.database_url.startswith('sqlite'):
                self.engine = create_engine(
                    self.database_url,
                    echo=False,
                    connect_args={'check_same_thread': False}
                )
            else:
                self.engine = create_engine(self.database_url, echo=False)
            
            # Create session factory
            self.session_factory = sessionmaker(bind=self.engine)
            
            # Create migration history table
            MigrationBase.metadata.create_all(self.engine)
            
            logger.info("Migration manager initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize migration manager: {e}")
            raise
    
    def get_session(self) -> Session:
        """Get a database session."""
        return self.session_factory()
    
    def discover_migrations(self) -> List[BaseMigration]:
        """Discover all migration files in the migrations directory."""
        migrations = []
        
        # Get all Python files in migrations directory
        migration_files = []
        for filename in os.listdir(self.migrations_dir):
            if filename.endswith('.py') and not filename.startswith('__'):
                migration_files.append(filename)
        
        # Sort by filename (which should include version)
        migration_files.sort()
        
        # Load each migration
        for filename in migration_files:
            try:
                migration_path = os.path.join(self.migrations_dir, filename)
                
                # Load module
                spec = importlib.util.spec_from_file_location(
                    f"migration_{filename[:-3]}", migration_path
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Find migration class
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type) and 
                        issubclass(attr, BaseMigration) and 
                        attr != BaseMigration):
                        
                        migration = attr()
                        migrations.append(migration)
                        break
                        
            except Exception as e:
                logger.error(f"Failed to load migration {filename}: {e}")
                continue
        
        # Sort by version
        migrations.sort(key=lambda m: m.version)
        
        return migrations
    
    def get_applied_migrations(self) -> List[str]:
        """Get list of applied migration versions."""
        session = self.get_session()
        try:
            result = session.query(MigrationHistory).filter_by(is_rolled_back=False).all()
            return [m.version for m in result]
        finally:
            session.close()
    
    def get_pending_migrations(self) -> List[BaseMigration]:
        """Get list of pending migrations."""
        all_migrations = self.discover_migrations()
        applied_versions = set(self.get_applied_migrations())
        
        pending = []
        for migration in all_migrations:
            if migration.version not in applied_versions:
                pending.append(migration)
        
        return pending
    
    def apply_migration(self, migration: BaseMigration, applied_by: str = None) -> bool:
        """Apply a single migration."""
        session = self.get_session()
        try:
            # Check if migration is already applied
            existing = session.query(MigrationHistory).filter_by(
                version=migration.version, is_rolled_back=False
            ).first()
            
            if existing:
                logger.warning(f"Migration {migration.version} already applied")
                return True
            
            # Apply the migration
            logger.info(f"Applying migration {migration.version}: {migration.description}")
            
            # Start transaction
            session.begin()
            
            try:
                # Run upgrade
                migration.upgrade(session)
                
                # Validate upgrade
                if not migration.validate_upgrade(session):
                    raise Exception("Migration validation failed")
                
                # Record in history
                history = MigrationHistory(
                    version=migration.version,
                    description=migration.description,
                    applied_by=applied_by or 'system',
                    applied_at=datetime.utcnow()
                )
                session.add(history)
                
                # Commit transaction
                session.commit()
                
                logger.info(f"Migration {migration.version} applied successfully")
                return True
                
            except Exception as e:
                # Rollback transaction
                session.rollback()
                logger.error(f"Failed to apply migration {migration.version}: {e}")
                raise
                
        except Exception as e:
            logger.error(f"Error applying migration {migration.version}: {e}")
            return False
        finally:
            session.close()
    
    def rollback_migration(self, migration: BaseMigration, rolled_back_by: str = None) -> bool:
        """Rollback a single migration."""
        session = self.get_session()
        try:
            # Check if migration can be rolled back
            if not migration.can_rollback():
                logger.error(f"Migration {migration.version} cannot be rolled back")
                return False
            
            # Check if migration is applied
            history = session.query(MigrationHistory).filter_by(
                version=migration.version, is_rolled_back=False
            ).first()
            
            if not history:
                logger.warning(f"Migration {migration.version} not found or already rolled back")
                return True
            
            # Rollback the migration
            logger.info(f"Rolling back migration {migration.version}: {migration.description}")
            
            # Start transaction
            session.begin()
            
            try:
                # Run downgrade
                migration.downgrade(session)
                
                # Validate downgrade
                if not migration.validate_downgrade(session):
                    raise Exception("Migration rollback validation failed")
                
                # Update history
                history.is_rolled_back = True
                history.rolled_back_at = datetime.utcnow()
                
                # Commit transaction
                session.commit()
                
                logger.info(f"Migration {migration.version} rolled back successfully")
                return True
                
            except Exception as e:
                # Rollback transaction
                session.rollback()
                logger.error(f"Failed to rollback migration {migration.version}: {e}")
                raise
                
        except Exception as e:
            logger.error(f"Error rolling back migration {migration.version}: {e}")
            return False
        finally:
            session.close()
    
    def migrate_up(self, target_version: str = None, applied_by: str = None) -> bool:
        """Run all pending migrations up to target version."""
        try:
            pending = self.get_pending_migrations()
            
            if not pending:
                logger.info("No pending migrations")
                return True
            
            # Filter to target version if specified
            if target_version:
                pending = [m for m in pending if m.version <= target_version]
            
            # Apply migrations
            for migration in pending:
                if not self.apply_migration(migration, applied_by):
                    logger.error(f"Failed to apply migration {migration.version}")
                    return False
            
            logger.info(f"Applied {len(pending)} migrations successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error running migrations: {e}")
            return False
    
    def migrate_down(self, target_version: str, rolled_back_by: str = None) -> bool:
        """Rollback migrations down to target version."""
        try:
            applied = self.get_applied_migrations()
            all_migrations = self.discover_migrations()
            
            # Find migrations to rollback
            to_rollback = []
            for migration in reversed(all_migrations):
                if migration.version in applied and migration.version > target_version:
                    to_rollback.append(migration)
            
            if not to_rollback:
                logger.info("No migrations to rollback")
                return True
            
            # Rollback migrations
            for migration in to_rollback:
                if not self.rollback_migration(migration, rolled_back_by):
                    logger.error(f"Failed to rollback migration {migration.version}")
                    return False
            
            logger.info(f"Rolled back {len(to_rollback)} migrations successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error rolling back migrations: {e}")
            return False
    
    def get_migration_status(self) -> Dict[str, Any]:
        """Get current migration status."""
        try:
            all_migrations = self.discover_migrations()
            applied = self.get_applied_migrations()
            pending = self.get_pending_migrations()
            
            status = {
                'total_migrations': len(all_migrations),
                'applied_migrations': len(applied),
                'pending_migrations': len(pending),
                'current_version': applied[-1] if applied else None,
                'applied_versions': applied,
                'pending_versions': [m.version for m in pending]
            }
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting migration status: {e}")
            return {'error': str(e)}
    
    def create_migration_template(self, version: str, description: str) -> str:
        """Create a new migration template file."""
        # Clean version and description
        version = version.replace(' ', '_').replace('-', '_')
        description = description.replace(' ', '_').replace('-', '_')
        
        # Create filename
        filename = f"{version}_{description}.py"
        filepath = os.path.join(self.migrations_dir, filename)
        
        # Check if file already exists
        if os.path.exists(filepath):
            raise ValueError(f"Migration file already exists: {filename}")
        
        # Template content
        template = f'''"""
Migration: {version}
Description: {description.replace('_', ' ')}
"""

from migrations.base_migration import BaseMigration
from sqlalchemy.orm import Session


class Migration_{version}(BaseMigration):
    """Migration for {description.replace('_', ' ')}."""
    
    def __init__(self):
        super().__init__(
            version="{version}",
            description="{description.replace('_', ' ')}"
        )
    
    def upgrade(self, session: Session) -> None:
        """Upgrade the database schema."""
        # Add your upgrade logic here
        pass
    
    def downgrade(self, session: Session) -> None:
        """Downgrade the database schema."""
        # Add your downgrade logic here
        pass
    
    def can_rollback(self) -> bool:
        """Check if this migration can be rolled back."""
        return True
    
    def validate_upgrade(self, session: Session) -> bool:
        """Validate that the upgrade was successful."""
        return True
    
    def validate_downgrade(self, session: Session) -> bool:
        """Validate that the downgrade was successful."""
        return True
'''
        
        # Write template to file
        with open(filepath, 'w') as f:
            f.write(template)
        
        logger.info(f"Created migration template: {filename}")
        return filepath
    
    def close(self):
        """Close database connections."""
        if self.engine:
            self.engine.dispose()