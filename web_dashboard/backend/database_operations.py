"""
Database configuration optimized for high concurrent operations with few users
Perfect for background jobs, batch processing, and automated operations
"""

import os
import logging
from contextlib import contextmanager
from sqlalchemy import create_engine, event, pool
from sqlalchemy.orm import sessionmaker, scoped_session
from models import Base
import threading

logger = logging.getLogger(__name__)

class OperationsOptimizedDatabaseManager:
    """Database manager optimized for many concurrent operations, few users."""
    
    def __init__(self):
        self.database_url = self._get_database_url()
        self.engine = None
        self._scoped_session = None
        self._operation_sessions = {}  # Track sessions per operation
        self._lock = threading.Lock()
        
    def _get_database_url(self) -> str:
        """Get database URL with pooler for operations."""
        database_url = os.getenv('DATABASE_URL')
        if database_url:
            # Ensure we use psycopg3 and connection pooler
            if database_url.startswith('postgresql://'):
                database_url = database_url.replace('postgresql://', 'postgresql+psycopg://', 1)
            # Force pooler usage for better concurrency
            if 'pooler.supabase.com' not in database_url:
                logger.warning("Not using Supabase pooler - this may cause issues with many operations")
            return database_url
        raise ValueError("DATABASE_URL not set")
    
    def initialize(self, create_tables: bool = False) -> None:
        """Initialize optimized for concurrent operations."""
        try:
            # Optimized for operations: more connections, shorter lifecycle
            self.engine = create_engine(
                self.database_url,
                # QueuePool for better concurrency handling
                poolclass=pool.QueuePool,
                pool_size=5,          # Base connections for operations
                max_overflow=10,      # Allow burst to 15 total
                pool_timeout=30,      # Wait up to 30s for connection
                pool_recycle=600,     # Recycle every 10 minutes
                pool_pre_ping=True,   # Verify connections
                echo=False,
                # Connection arguments for stability
                connect_args={
                    "keepalives": 1,
                    "keepalives_idle": 10,
                    "keepalives_interval": 5,
                    "keepalives_count": 3,
                    # Prepared statements for better performance
                    "prepare_threshold": 5,
                    # Statement timeout to prevent long-running queries
                    "options": "-c statement_timeout=30000"  # 30 seconds
                }
            )
            
            logger.info("Database initialized for high-concurrency operations")
            
            # Session factory with operation-friendly settings
            session_factory = sessionmaker(
                bind=self.engine,
                autoflush=False,      # Control flushes manually
                autocommit=False,     # Explicit commits
                expire_on_commit=False # Keep objects usable after commit
            )
            
            # Scoped session for thread safety
            self._scoped_session = scoped_session(session_factory)
            
            # Monitor pool usage
            @event.listens_for(self.engine, "connect")
            def receive_connect(dbapi_connection, connection_record):
                connection_record.info['pid'] = os.getpid()
                logger.debug(f"Connection opened - Pool size: {self.engine.pool.size()}")
            
            @event.listens_for(self.engine, "checkout")
            def receive_checkout(dbapi_connection, connection_record, connection_proxy):
                logger.debug(f"Connection checked out - Overflow: {self.engine.pool.overflow()}")
            
            @event.listens_for(self.engine, "checkin")
            def receive_checkin(dbapi_connection, connection_record):
                logger.debug(f"Connection returned - Checked out: {self.engine.pool.checkedout()}")
            
            # Test connection
            with self.session_scope() as session:
                from sqlalchemy import text
                session.execute(text("SELECT 1"))
                logger.info("Database connection test successful")
                
            if create_tables:
                Base.metadata.create_all(self.engine)
                
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise
    
    @contextmanager
    def session_scope(self, operation_id: str = None):
        """Session scope with operation tracking."""
        session = self._scoped_session()
        
        # Track operation if ID provided
        if operation_id:
            with self._lock:
                self._operation_sessions[operation_id] = session
                logger.debug(f"Operation {operation_id} started - Active operations: {len(self._operation_sessions)}")
        
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Operation {operation_id or 'unknown'} failed: {e}")
            raise
        finally:
            session.close()
            self._scoped_session.remove()
            
            # Clean up operation tracking
            if operation_id:
                with self._lock:
                    self._operation_sessions.pop(operation_id, None)
                    logger.debug(f"Operation {operation_id} completed - Active operations: {len(self._operation_sessions)}")
    
    @contextmanager
    def batch_operation_scope(self, operation_id: str, batch_size: int = 100):
        """Optimized scope for batch operations."""
        session = self._scoped_session()
        processed = 0
        
        try:
            yield session
            
            # Auto-commit every batch_size records
            def batch_commit():
                nonlocal processed
                processed += 1
                if processed % batch_size == 0:
                    session.commit()
                    logger.debug(f"Batch commit for {operation_id}: {processed} records")
                    # Clear session to free memory
                    session.expire_all()
            
            session.batch_commit = batch_commit
            
            # Final commit
            session.commit()
            logger.info(f"Batch operation {operation_id} completed: {processed} total records")
            
        except Exception as e:
            session.rollback()
            logger.error(f"Batch operation {operation_id} failed after {processed} records: {e}")
            raise
        finally:
            session.close()
            self._scoped_session.remove()
    
    def get_pool_status(self):
        """Get current connection pool status."""
        if self.engine:
            return {
                "size": self.engine.pool.size(),
                "checked_out": self.engine.pool.checkedout(),
                "overflow": self.engine.pool.overflow(),
                "total": self.engine.pool.size() + self.engine.pool.overflow(),
                "active_operations": len(self._operation_sessions)
            }
        return None
    
    def close_idle_connections(self):
        """Close idle connections to free resources."""
        if self.engine:
            self.engine.dispose()
            self.engine.pool.recreate()
            logger.info("Idle connections closed and pool recreated")
    
    def close(self):
        """Close all connections."""
        if self.engine:
            # Clear all tracked operations
            with self._lock:
                self._operation_sessions.clear()
            
            self.engine.dispose()
            logger.info("All database connections closed")

# Global instance
_db = None

def get_operations_db():
    """Get operations-optimized database instance."""
    global _db
    if _db is None:
        _db = OperationsOptimizedDatabaseManager()
        _db.initialize()
    return _db

# Compatibility layer
db_manager = get_operations_db()
init_database = lambda create_tables=False: db_manager.initialize(create_tables)
db_session_scope = db_manager.session_scope

# Operation-specific helpers
def with_operation_session(operation_id: str):
    """Decorator for operations needing tracked sessions."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            with db_manager.session_scope(operation_id=operation_id) as session:
                return func(session, *args, **kwargs)
        return wrapper
    return decorator

def batch_operation(operation_id: str, batch_size: int = 100):
    """Decorator for batch operations."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            with db_manager.batch_operation_scope(operation_id, batch_size) as session:
                return func(session, *args, **kwargs)
        return wrapper
    return decorator