"""
Minimal SQLAlchemy configuration for production
Optimized for low resource usage on 2CPU/4GB servers
"""

import os
import logging
from contextlib import contextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import NullPool, StaticPool
from models import Base

logger = logging.getLogger(__name__)

class MinimalDatabaseManager:
    """Minimal SQLAlchemy setup with aggressive optimizations."""
    
    def __init__(self):
        self.database_url = self._get_database_url()
        self.engine = None
        self._scoped_session = None
        
    def _get_database_url(self) -> str:
        """Get database URL with pooler."""
        database_url = os.getenv('DATABASE_URL')
        if database_url:
            # Ensure we use psycopg3
            if database_url.startswith('postgresql://'):
                database_url = database_url.replace('postgresql://', 'postgresql+psycopg://', 1)
            return database_url
        raise ValueError("DATABASE_URL not set")
    
    def initialize(self, create_tables: bool = False) -> None:
        """Initialize with minimal resources."""
        try:
            # Option 1: No connection pooling at all (recommended for low traffic)
            # Each request gets its own connection
            if os.getenv('DISABLE_POOLING', 'false').lower() == 'true':
                self.engine = create_engine(
                    self.database_url,
                    poolclass=NullPool,  # No pooling - direct connections
                    echo=False,
                    connect_args={
                        "keepalives": 1,
                        "keepalives_idle": 30,
                        "keepalives_interval": 10,
                        "keepalives_count": 5,
                    }
                )
                logger.info("Database initialized with no connection pooling")
            else:
                # Option 2: Minimal static pool
                self.engine = create_engine(
                    self.database_url,
                    poolclass=StaticPool,  # Single connection reused
                    echo=False,
                    pool_pre_ping=True,  # Verify connections before use
                    connect_args={
                        "keepalives": 1,
                        "keepalives_idle": 30,
                        "keepalives_interval": 10,
                        "keepalives_count": 5,
                    }
                )
                logger.info("Database initialized with static pool (1 connection)")
            
            # Create lightweight session factory
            session_factory = sessionmaker(
                bind=self.engine,
                autoflush=False,
                autocommit=False,
                expire_on_commit=False
            )
            
            # Scoped session for thread safety
            self._scoped_session = scoped_session(session_factory)
            
            # Add connection lifecycle logging
            @event.listens_for(self.engine, "connect")
            def receive_connect(dbapi_connection, connection_record):
                logger.debug("Database connection established")
            
            @event.listens_for(self.engine, "close")
            def receive_close(dbapi_connection, connection_record):
                logger.debug("Database connection closed")
            
            # Test connection
            with self.session_scope() as session:
                session.execute("SELECT 1")
                logger.info("Database connection test successful")
                
            if create_tables:
                Base.metadata.create_all(self.engine)
                logger.info("Database tables created")
                
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise
    
    @contextmanager
    def session_scope(self):
        """Provide a transactional scope with automatic cleanup."""
        session = self._scoped_session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
            # Remove session from registry to free resources
            self._scoped_session.remove()
    
    def close(self):
        """Close all connections."""
        if self.engine:
            self.engine.dispose()
            logger.info("Database connections closed")

# Global instance
_db = None

def get_minimal_db():
    """Get minimal database instance."""
    global _db
    if _db is None:
        _db = MinimalDatabaseManager()
        _db.initialize()
    return _db

# Compatibility aliases
db_manager = get_minimal_db()
init_database = lambda create_tables=False: db_manager.initialize(create_tables)
db_session_scope = db_manager.session_scope