"""
Optimized Database Module for Supabase PostgreSQL
Using native psycopg3 instead of SQLAlchemy for better performance and lower resource usage.
"""

import os
import logging
from contextlib import contextmanager
from typing import Generator, Optional, Dict, Any, List
import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
import json
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)

class OptimizedDatabaseManager:
    """Lightweight database manager using psycopg3 directly."""
    
    def __init__(self, database_url: Optional[str] = None):
        """Initialize database manager."""
        self.database_url = database_url or self._get_database_url()
        self.pool = None
        
    def _get_database_url(self) -> str:
        """Get PostgreSQL database URL from configuration."""
        database_url = os.getenv('DATABASE_URL')
        if database_url:
            logger.info("Using DATABASE_URL environment variable")
            # psycopg3 uses standard postgresql:// URLs
            return database_url.replace('postgresql+psycopg://', 'postgresql://')
            
        # Construct from Supabase settings
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY', '')
        
        if supabase_url and supabase_key:
            project_id = supabase_url.replace('https://', '').replace('.supabase.co', '')
            use_pooler = os.getenv('SUPABASE_USE_POOLER', 'true').lower() == 'true'
            
            if use_pooler:
                # Use connection pooler (recommended)
                pooler_url = f"postgresql://postgres.{project_id}:{supabase_key}@aws-0-us-west-1.pooler.supabase.com:6543/postgres?sslmode=require"
                logger.info(f"Using Supabase connection pooler")
                return pooler_url
            else:
                # Direct connection
                direct_url = f"postgresql://postgres:{supabase_key}@db.{project_id}.supabase.co:5432/postgres?sslmode=require"
                logger.info(f"Using direct Supabase connection")
                return direct_url
        
        raise ValueError("No valid database configuration found")
    
    def initialize(self) -> None:
        """Initialize connection pool with minimal resources."""
        try:
            logger.info("Initializing optimized PostgreSQL connection pool")
            
            # Create a small connection pool (2-4 connections for 2CPU server)
            self.pool = ConnectionPool(
                self.database_url,
                min_size=1,      # Minimum 1 connection
                max_size=3,      # Maximum 3 connections (was 30!)
                timeout=30,      # Connection timeout
                max_idle=300,    # Close idle connections after 5 minutes
                max_lifetime=3600,  # Max connection lifetime 1 hour
                check=ConnectionPool.check_connection,
            )
            
            # Test connection
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    if cur.fetchone()[0] == 1:
                        logger.info("Database connection test successful")
                    
            logger.info("Optimized database pool initialized with minimal connections")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    @contextmanager
    def get_connection(self) -> Generator[psycopg.Connection, None, None]:
        """Get a database connection from the pool."""
        if not self.pool:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        
        conn = self.pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self.pool.putconn(conn)
    
    @contextmanager
    def get_cursor(self, row_factory=dict_row) -> Generator[psycopg.Cursor, None, None]:
        """Get a database cursor with dict row factory by default."""
        with self.get_connection() as conn:
            with conn.cursor(row_factory=row_factory) as cur:
                yield cur
    
    def execute(self, query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """Execute a query and return results as list of dicts."""
        with self.get_cursor() as cur:
            cur.execute(query, params)
            if cur.description:
                return cur.fetchall()
            return []
    
    def execute_one(self, query: str, params: Optional[tuple] = None) -> Optional[Dict[str, Any]]:
        """Execute a query and return single result."""
        with self.get_cursor() as cur:
            cur.execute(query, params)
            if cur.description:
                return cur.fetchone()
            return None
    
    def execute_many(self, query: str, params_list: List[tuple]) -> None:
        """Execute a query with multiple parameter sets."""
        with self.get_cursor() as cur:
            cur.executemany(query, params_list)
    
    def insert(self, table: str, data: Dict[str, Any], returning: str = "id") -> Any:
        """Insert a record and return specified column."""
        columns = list(data.keys())
        values = list(data.values())
        
        query = sql.SQL("INSERT INTO {} ({}) VALUES ({}) RETURNING {}").format(
            sql.Identifier(table),
            sql.SQL(', ').join(map(sql.Identifier, columns)),
            sql.SQL(', ').join(sql.Placeholder() * len(values)),
            sql.Identifier(returning)
        )
        
        with self.get_cursor() as cur:
            cur.execute(query, values)
            return cur.fetchone()[returning]
    
    def update(self, table: str, data: Dict[str, Any], where: Dict[str, Any]) -> int:
        """Update records and return count of affected rows."""
        set_columns = list(data.keys())
        set_values = list(data.values())
        where_columns = list(where.keys())
        where_values = list(where.values())
        
        query = sql.SQL("UPDATE {} SET {} WHERE {}").format(
            sql.Identifier(table),
            sql.SQL(', ').join(
                sql.SQL("{} = {}").format(sql.Identifier(col), sql.Placeholder())
                for col in set_columns
            ),
            sql.SQL(' AND ').join(
                sql.SQL("{} = {}").format(sql.Identifier(col), sql.Placeholder())
                for col in where_columns
            )
        )
        
        with self.get_cursor() as cur:
            cur.execute(query, set_values + where_values)
            return cur.rowcount
    
    def delete(self, table: str, where: Dict[str, Any]) -> int:
        """Delete records and return count of affected rows."""
        where_columns = list(where.keys())
        where_values = list(where.values())
        
        query = sql.SQL("DELETE FROM {} WHERE {}").format(
            sql.Identifier(table),
            sql.SQL(' AND ').join(
                sql.SQL("{} = {}").format(sql.Identifier(col), sql.Placeholder())
                for col in where_columns
            )
        )
        
        with self.get_cursor() as cur:
            cur.execute(query, where_values)
            return cur.rowcount
    
    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists."""
        query = """
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = %s
            )
        """
        result = self.execute_one(query, (table_name,))
        return result['exists'] if result else False
    
    def close(self) -> None:
        """Close the connection pool."""
        if self.pool:
            self.pool.close()
            logger.info("Database connection pool closed")
    
    def __enter__(self):
        """Context manager entry."""
        self.initialize()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

# Global instance (lazy initialization)
_db_manager = None

def get_db() -> OptimizedDatabaseManager:
    """Get the global database manager instance."""
    global _db_manager
    if _db_manager is None:
        _db_manager = OptimizedDatabaseManager()
        _db_manager.initialize()
    return _db_manager

@contextmanager
def db_session() -> Generator[OptimizedDatabaseManager, None, None]:
    """Get a database session for compatibility."""
    yield get_db()

# Compatibility layer for existing code
@contextmanager
def db_session_scope():
    """Compatibility wrapper for existing session_scope usage."""
    db = get_db()
    # Return a mock session object that delegates to our optimized manager
    class SessionCompat:
        def execute(self, query, params=None):
            if hasattr(query, 'text'):
                # Handle SQLAlchemy text() objects
                return db.execute(str(query), params)
            return db.execute(query, params)
        
        def commit(self):
            pass  # Commits are handled by connection context
        
        def rollback(self):
            pass  # Rollbacks are handled by connection context
        
        def close(self):
            pass  # Connections returned to pool automatically
    
    yield SessionCompat()

# Initialize database function for compatibility
def init_database(create_tables: bool = False) -> None:
    """Initialize the database."""
    db = get_db()
    if create_tables:
        logger.info("Table creation should be handled by migrations")
        # Note: Table creation should be handled by proper migrations
        # not by ORM models

# Export for compatibility
db_manager = get_db()