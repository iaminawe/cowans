"""
Supabase Database Service

This module provides database operations using the Supabase client SDK
instead of direct PostgreSQL connections. This is more reliable and
handles authentication, connection pooling, and Supabase features automatically.
"""

import os
import logging
from typing import Optional, Dict, Any, List
from supabase import create_client, Client
from supabase.lib.client_options import ClientOptions

logger = logging.getLogger(__name__)


class SupabaseDatabaseService:
    """Manages database operations using Supabase client SDK"""
    
    def __init__(self):
        """Initialize Supabase database client"""
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_anon_key = os.getenv('SUPABASE_ANON_KEY')
        self.supabase_service_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
        
        if not all([self.supabase_url, self.supabase_anon_key]):
            raise ValueError("Missing required Supabase configuration")
        
        # Use service role key for database operations (full access)
        self.client: Client = create_client(
            self.supabase_url,
            self.supabase_service_key or self.supabase_anon_key,
            options=ClientOptions(
                auto_refresh_token=False,  # Service key doesn't need refresh
                persist_session=False     # Server-side, no need for persistence
            )
        )
        
        logger.info(f"Supabase database service initialized for {self.supabase_url}")
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the Supabase database connection
        
        Returns:
            Dict with health status information
        """
        try:
            # Simple query to test connection
            result = self.client.table('users').select('id').limit(1).execute()
            
            return {
                "status": "healthy",
                "connection": "active",
                "query_test": "passed",
                "url": self.supabase_url
            }
        except Exception as e:
            logger.error(f"Supabase health check failed: {e}")
            return {
                "status": "unhealthy",
                "connection": "failed",
                "error": str(e),
                "url": self.supabase_url
            }
    
    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        try:
            result = self.client.table('users').select('*').eq('id', user_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error getting user {user_id}: {e}")
            return None
    
    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email"""
        try:
            result = self.client.table('users').select('*').eq('email', email).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error getting user by email {email}: {e}")
            return None
    
    def create_user(self, user_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create new user"""
        try:
            result = self.client.table('users').insert(user_data).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            return None
    
    def update_user(self, user_id: str, user_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update user"""
        try:
            result = self.client.table('users').update(user_data).eq('id', user_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error updating user {user_id}: {e}")
            return None
    
    def get_products(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Get products with pagination"""
        try:
            result = self.client.table('products').select('*').range(offset, offset + limit - 1).execute()
            return result.data
        except Exception as e:
            logger.error(f"Error getting products: {e}")
            return []
    
    def get_product_by_id(self, product_id: str) -> Optional[Dict[str, Any]]:
        """Get product by ID"""
        try:
            result = self.client.table('products').select('*').eq('id', product_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error getting product {product_id}: {e}")
            return None
    
    def create_product(self, product_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create new product"""
        try:
            result = self.client.table('products').insert(product_data).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error creating product: {e}")
            return None
    
    def update_product(self, product_id: str, product_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update product"""
        try:
            result = self.client.table('products').update(product_data).eq('id', product_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error updating product {product_id}: {e}")
            return None
    
    def get_categories(self) -> List[Dict[str, Any]]:
        """Get all categories"""
        try:
            result = self.client.table('categories').select('*').execute()
            return result.data
        except Exception as e:
            logger.error(f"Error getting categories: {e}")
            return []
    
    def get_sync_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get sync history with pagination"""
        try:
            result = (self.client.table('sync_history')
                     .select('*')
                     .order('created_at', desc=True)
                     .limit(limit)
                     .execute())
            return result.data
        except Exception as e:
            logger.error(f"Error getting sync history: {e}")
            return []
    
    def create_sync_record(self, sync_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create sync history record"""
        try:
            result = self.client.table('sync_history').insert(sync_data).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error creating sync record: {e}")
            return None
    
    def execute_raw_query(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Execute raw SQL query using Supabase RPC (stored procedure)
        Note: For complex queries, create stored procedures in Supabase
        """
        try:
            # This would require creating an RPC function in Supabase
            # For now, we'll use a simple query test
            result = self.client.rpc('query_test').execute()
            return result.data
        except Exception as e:
            logger.error(f"Error executing raw query: {e}")
            return None


# Global instance
supabase_db = None

def get_supabase_db() -> SupabaseDatabaseService:
    """Get global Supabase database service instance"""
    global supabase_db
    if supabase_db is None:
        supabase_db = SupabaseDatabaseService()
    return supabase_db

def init_supabase_db() -> SupabaseDatabaseService:
    """Initialize Supabase database service"""
    global supabase_db
    supabase_db = SupabaseDatabaseService()
    return supabase_db