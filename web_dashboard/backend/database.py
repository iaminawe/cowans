"""
Database Module for Cowans Office Supplies Integration System

This module handles database initialization, connection management, and session handling.
"""

import os
import logging
from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, scoped_session, Session
from sqlalchemy.pool import StaticPool
from sqlalchemy.exc import SQLAlchemyError

from models import Base, create_performance_indexes
from config import Config

# Configure logging
logger = logging.getLogger(__name__)

class DatabaseManager:
    """Manages database connections and sessions."""
    
    def __init__(self, database_url: Optional[str] = None):
        """Initialize database manager."""
        self.database_url = database_url or self._get_database_url()
        self.engine = None
        self.session_factory = None
        self._scoped_session = None
        
    def _get_database_url(self) -> str:
        """Get database URL from configuration with enhanced containerized environment support and fallback."""
        # Check for DATABASE_URL environment variable first
        database_url = os.getenv('DATABASE_URL')
        if database_url:
            # Handle containerized paths - ensure directory exists
            if database_url.startswith('sqlite'):
                db_path = database_url.replace('sqlite:///', '')
                db_dir = os.path.dirname(db_path)
                if db_dir and not os.path.exists(db_dir):
                    try:
                        os.makedirs(db_dir, exist_ok=True)
                        logger.info(f"Created database directory: {db_dir}")
                    except Exception as e:
                        logger.error(f"Failed to create database directory {db_dir}: {e}")
            return database_url
            
        # Check for Supabase configuration
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY', '')
        
        if supabase_url and supabase_key:
            # Check if we have a custom database URL from Supabase
            supabase_db_url = os.getenv('SUPABASE_DB_URL')
            if supabase_db_url:
                # Use the provided database URL (should include password)
                logger.info("Using custom SUPABASE_DB_URL")
                return supabase_db_url
            
            # Otherwise, construct the database URL
            # Extract database credentials from Supabase URL
            # Supabase URL format: https://[project-id].supabase.co
            project_id = supabase_url.replace('https://', '').replace('.supabase.co', '')
            
            # Check for pooler configuration to avoid IPv6 issues
            use_pooler = os.getenv('SUPABASE_USE_POOLER', 'true').lower() == 'true'
            
            if use_pooler:
                # Use connection pooler (recommended for containers)
                # This avoids IPv6 issues and provides better connection management
                logger.info(f"Using Supabase connection pooler for project: {project_id}")
                return f"postgresql://postgres.{project_id}:{supabase_key}@aws-0-us-west-1.pooler.supabase.com:6543/postgres?pgbouncer=true"
            else:
                # Direct connection (may have IPv6 issues in containers)
                logger.info(f"Using direct Supabase connection for project: {project_id}")
                return f"postgresql://postgres:{supabase_key}@db.{project_id}.supabase.co:5432/postgres"
        
        # Use config object if available
        if hasattr(Config, 'DATABASE_URL') and Config.DATABASE_URL:
            return Config.DATABASE_URL
        
        # Default to SQLite database - prefer containerized location if available
        if os.path.exists('/app/data'):
            # Containerized environment
            db_path = '/app/data/database.db'
            logger.info("Using containerized SQLite database")
        else:
            # Development environment
            db_path = os.path.join(os.path.dirname(__file__), 'database.db')
            logger.info("Using development SQLite database")
        
        # Ensure directory exists
        db_dir = os.path.dirname(db_path)
        if not os.path.exists(db_dir):
            try:
                os.makedirs(db_dir, exist_ok=True)
                logger.info(f"Created database directory: {db_dir}")
            except Exception as e:
                logger.error(f"Failed to create database directory {db_dir}: {e}")
        
        return f"sqlite:///{db_path}"
    
    def initialize(self, create_tables: bool = False) -> None:
        """Initialize database connection with enhanced containerized environment support."""
        try:
            # Create engine with appropriate settings
            if self.database_url.startswith('sqlite'):
                # SQLite-specific settings with containerized environment support
                is_containerized = os.path.exists('/app/data')
                if is_containerized:
                    logger.info("SQLite in containerized environment detected")
                else:
                    logger.info("SQLite in development environment")
                    
                self.engine = create_engine(
                    self.database_url,
                    echo=False,  # Set to True for SQL debugging
                    poolclass=StaticPool,
                    connect_args={
                        'check_same_thread': False,  # Allow SQLite to be used with multiple threads
                        'timeout': 30,  # Connection timeout
                    },
                    pool_pre_ping=True,  # Verify connections before use
                )
                
                # Enable foreign key constraints for SQLite
                @event.listens_for(self.engine, "connect")
                def set_sqlite_pragma(dbapi_connection, connection_record):
                    cursor = dbapi_connection.cursor()
                    cursor.execute("PRAGMA foreign_keys=ON")
                    cursor.execute("PRAGMA journal_mode=WAL")  # Enable WAL mode for better concurrency
                    cursor.execute("PRAGMA synchronous=NORMAL")  # Balance between safety and performance
                    cursor.execute("PRAGMA temp_store=MEMORY")  # Use memory for temp tables
                    cursor.execute("PRAGMA cache_size=10000")  # Increase cache size for better performance
                    cursor.close()
                    
            else:
                # PostgreSQL/Supabase settings
                self.engine = create_engine(
                    self.database_url,
                    echo=False,
                    pool_size=10,
                    max_overflow=20,
                    pool_pre_ping=True,
                    pool_recycle=3600,  # Recycle connections after 1 hour
                )
            
            # Create session factory
            self.session_factory = sessionmaker(
                bind=self.engine,
                autoflush=False,
                autocommit=False,
                expire_on_commit=False
            )
            
            # Create scoped session for thread-safe access
            self._scoped_session = scoped_session(self.session_factory)
            
            # Test connection immediately to catch issues early
            try:
                with self.session_scope() as session:
                    from sqlalchemy import text
                    result = session.execute(text("SELECT 1")).scalar()
                    if result == 1:
                        logger.info("Database connection test successful")
                    else:
                        logger.error("Database connection test failed")
            except Exception as conn_error:
                logger.error(f"Database connection test failed: {conn_error}")
                raise
            
            # Only create tables if explicitly requested
            if create_tables:
                logger.info("Creating database tables...")
                self.create_tables()
                
            # Only log database URL once per process (avoid spam in multi-worker setups)
            if not hasattr(self, '_logged_init'):
                # Mask sensitive information in logs
                safe_url = self.database_url
                if '@' in safe_url:
                    safe_url = safe_url.split('@')[0].split('://')[0] + '://***@' + safe_url.split('@')[1]
                logger.info(f"Database initialized successfully: {safe_url}")
                self._logged_init = True
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    def create_tables(self) -> None:
        """Create all database tables."""
        try:
            # Create all tables
            Base.metadata.create_all(self.engine)
            
            # Create performance indexes
            create_performance_indexes(self.engine)
            
            logger.info("Database tables created successfully")
            
        except Exception as e:
            logger.error(f"Failed to create database tables: {e}")
            raise
    
    def drop_tables(self) -> None:
        """Drop all database tables. Use with caution!"""
        try:
            Base.metadata.drop_all(self.engine)
            logger.warning("All database tables dropped")
            
        except Exception as e:
            logger.error(f"Failed to drop database tables: {e}")
            raise
    
    def get_session(self) -> Session:
        """Get a database session."""
        if not self._scoped_session:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        
        return self._scoped_session()
    
    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """Provide a transactional scope around a series of operations."""
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()
    
    def close(self) -> None:
        """Close database connections."""
        if self._scoped_session:
            self._scoped_session.remove()
        
        if self.engine:
            self.engine.dispose()
            
        logger.info("Database connections closed")
    
    def health_check(self) -> dict:
        """Check database health."""
        try:
            with self.session_scope() as session:
                # Simple query to test connection
                from sqlalchemy import text
                result = session.execute(text("SELECT 1")).scalar()
                
                return {
                    'status': 'healthy',
                    'database_url': self.database_url.split('@')[-1] if '@' in self.database_url else self.database_url,
                    'connection_test': result == 1
                }
                
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e)
            }
    
    def backup_database(self, backup_path: str) -> bool:
        """Create a backup of the database (SQLite only)."""
        if not self.database_url.startswith('sqlite'):
            logger.warning("Backup only supported for SQLite databases")
            return False
        
        try:
            import shutil
            
            # Extract database file path from URL
            db_path = self.database_url.replace('sqlite:///', '')
            
            # Create backup
            shutil.copy2(db_path, backup_path)
            
            logger.info(f"Database backup created: {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create database backup: {e}")
            return False
    
    def restore_database(self, backup_path: str) -> bool:
        """Restore database from backup (SQLite only)."""
        if not self.database_url.startswith('sqlite'):
            logger.warning("Restore only supported for SQLite databases")
            return False
        
        try:
            import shutil
            
            # Extract database file path from URL
            db_path = self.database_url.replace('sqlite:///', '')
            
            # Close existing connections
            self.close()
            
            # Restore backup
            shutil.copy2(backup_path, db_path)
            
            # Reinitialize
            self.initialize()
            
            logger.info(f"Database restored from: {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to restore database: {e}")
            return False
    
    def get_table_stats(self) -> dict:
        """Get statistics about database tables."""
        try:
            with self.session_scope() as session:
                stats = {}
                
                # Get table names
                if self.database_url.startswith('sqlite'):
                    tables_query = "SELECT name FROM sqlite_master WHERE type='table'"
                else:
                    tables_query = "SELECT tablename FROM pg_tables WHERE schemaname='public'"
                
                from sqlalchemy import text
                result = session.execute(text(tables_query))
                tables = [row[0] for row in result]
                
                # Get row counts for each table
                for table in tables:
                    if table.startswith('sqlite_'):  # Skip SQLite system tables
                        continue
                        
                    try:
                        count_result = session.execute(text(f"SELECT COUNT(*) FROM {table}"))
                        count = count_result.scalar()
                        stats[table] = count
                    except Exception as e:
                        logger.warning(f"Failed to get count for table {table}: {e}")
                        stats[table] = 'error'
                
                return stats
                
        except Exception as e:
            logger.error(f"Failed to get table statistics: {e}")
            return {}

# Global database manager instance
db_manager = DatabaseManager()

# Convenience functions for common operations
def init_database(database_url: Optional[str] = None, create_tables: bool = True) -> None:
    """Initialize the global database manager."""
    global db_manager
    if database_url:
        db_manager = DatabaseManager(database_url)
    db_manager.initialize(create_tables)

def get_db_session() -> Session:
    """Get a database session from the global manager."""
    return db_manager.get_session()

@contextmanager
def db_session_scope() -> Generator[Session, None, None]:
    """Get a transactional database session scope."""
    with db_manager.session_scope() as session:
        yield session

def close_database() -> None:
    """Close the global database manager."""
    db_manager.close()

def database_health_check() -> dict:
    """Check database health."""
    return db_manager.health_check()

# Database utilities
class DatabaseUtils:
    """Utility functions for database operations."""
    
    @staticmethod
    def create_admin_user(email: str, password: str, first_name: str = None, last_name: str = None) -> bool:
        """Create an admin user."""
        from models import User
        from werkzeug.security import generate_password_hash
        
        try:
            with db_session_scope() as session:
                # Check if user already exists
                existing_user = session.query(User).filter_by(email=email).first()
                if existing_user:
                    logger.warning(f"User {email} already exists")
                    return False
                
                # Create new admin user
                user = User(
                    email=email,
                    password_hash=generate_password_hash(password),
                    first_name=first_name,
                    last_name=last_name,
                    is_admin=True,
                    is_active=True
                )
                
                session.add(user)
                session.commit()
                
                logger.info(f"Admin user created: {email}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to create admin user: {e}")
            return False
    
    @staticmethod
    def seed_initial_data() -> None:
        """Seed database with initial data. WARNING: Only use in development!"""
        from models import Configuration, User
        from werkzeug.security import generate_password_hash
        
        # Check if we're in production and skip seeding
        if os.getenv('FLASK_ENV') == 'production':
            logger.info("Skipping data seeding in production environment")
            return
            
        try:
            # Ensure database is initialized
            if not db_manager.engine:
                db_manager.initialize()
                
            with db_session_scope() as session:
                # Only seed if no users exist (fresh database)
                user_count = session.query(User).count()
                if user_count > 0:
                    logger.info("Users already exist - skipping seeding")
                    return
                    
                # Create default dev user with ID 1 if it doesn't exist
                dev_user = session.query(User).filter_by(id=1).first()
                if not dev_user:
                    dev_user = User(
                        id=1,
                        email='dev@example.com',
                        password_hash=generate_password_hash('devpassword'),
                        first_name='Dev',
                        last_name='User',
                        is_admin=True,
                        is_active=True
                    )
                    session.add(dev_user)
                    session.commit()
                    logger.info("Created default dev user with ID 1")
                
                # Default configurations
                default_configs = [
                    {
                        'key': 'system.version',
                        'value': '1.0.0',
                        'category': 'system',
                        'description': 'System version'
                    },
                    {
                        'key': 'sync.auto_sync_enabled',
                        'value': 'false',
                        'data_type': 'boolean',
                        'category': 'sync',
                        'description': 'Enable automatic synchronization'
                    },
                    {
                        'key': 'sync.batch_size',
                        'value': '100',
                        'data_type': 'integer',
                        'category': 'sync',
                        'description': 'Default batch size for sync operations'
                    },
                    {
                        'key': 'icons.default_style',
                        'value': 'modern',
                        'category': 'icons',
                        'description': 'Default icon generation style'
                    },
                    {
                        'key': 'icons.default_color',
                        'value': '#3B82F6',
                        'category': 'icons',
                        'description': 'Default icon color'
                    }
                ]
                
                for config_data in default_configs:
                    # Check if configuration already exists
                    existing = session.query(Configuration).filter_by(key=config_data['key']).first()
                    if not existing:
                        config = Configuration(**config_data)
                        session.add(config)
                
                session.commit()
                logger.info("Initial data seeded successfully")
                
        except Exception as e:
            logger.error(f"Failed to seed initial data: {e}")
            raise
    
    @staticmethod
    def vacuum_database() -> bool:
        """Vacuum the database to optimize performance (SQLite only)."""
        if not db_manager.database_url.startswith('sqlite'):
            logger.warning("Vacuum only supported for SQLite databases")
            return False
        
        try:
            from sqlalchemy import text
            with db_manager.session_scope() as session:
                session.execute(text("VACUUM"))
                logger.info("Database vacuumed successfully")
                return True
                
        except Exception as e:
            logger.error(f"Failed to vacuum database: {e}")
            return False
    
    @staticmethod
    def analyze_database() -> bool:
        """Analyze database to update statistics (SQLite only)."""
        if not db_manager.database_url.startswith('sqlite'):
            logger.warning("ANALYZE only supported for SQLite databases")
            return False
        
        try:
            from sqlalchemy import text
            with db_manager.session_scope() as session:
                session.execute(text("ANALYZE"))
                logger.info("Database analyzed successfully")
                return True
                
        except Exception as e:
            logger.error(f"Failed to analyze database: {e}")
            return False

# Flask-style convenience functions for compatibility
def init_db():
    """Initialize database (Flask-style convenience function)."""
    init_database()

def get_db():
    """Get database session (Flask-style generator for dependency injection)."""
    session = get_db_session()
    try:
        yield session
    finally:
        session.close()

# Export commonly used items
__all__ = [
    'DatabaseManager',
    'db_manager',
    'init_database',
    'get_db_session',
    'db_session_scope',
    'close_database',
    'database_health_check',
    'DatabaseUtils',
    'init_db',
    'get_db'
]