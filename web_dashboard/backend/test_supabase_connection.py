#!/usr/bin/env python3
"""
Test Supabase Database Connection

This script tests the connection to your Supabase PostgreSQL database
and provides diagnostic information.
"""

import os
import sys
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from datetime import datetime
import logging

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from supabase_migration_config import SUPABASE_DB_URL, SUPABASE_URL

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_connection():
    """Test connection to Supabase PostgreSQL database."""
    logger.info("=== Supabase Connection Test ===")
    logger.info(f"Started at: {datetime.now()}")
    
    # Check configuration
    logger.info("\nChecking configuration...")
    if SUPABASE_URL:
        logger.info(f"✅ Supabase URL configured: {SUPABASE_URL}")
    else:
        logger.warning("⚠️  Supabase URL not found in environment")
    
    if not SUPABASE_DB_URL:
        logger.error("❌ Supabase database URL not configured!")
        logger.error("Please set SUPABASE_DB_URL or database credentials in your .env file")
        logger.error("\nTo get your database credentials:")
        logger.error("1. Go to your Supabase dashboard")
        logger.error("2. Navigate to Settings → Database")
        logger.error("3. Copy the connection string")
        return False
    
    # Mask password in connection string for logging
    masked_url = SUPABASE_DB_URL
    if '@' in masked_url and ':' in masked_url.split('@')[0]:
        parts = masked_url.split('@')
        creds = parts[0].split('://')[-1]
        user = creds.split(':')[0]
        masked_url = masked_url.replace(creds, f"{user}:****")
    
    logger.info(f"Database URL: {masked_url}")
    
    # Test connection
    logger.info("\nTesting connection...")
    try:
        conn = psycopg2.connect(SUPABASE_DB_URL)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        
        logger.info("✅ Successfully connected to Supabase PostgreSQL!")
        
        # Get database version
        cur.execute("SELECT version();")
        version = cur.fetchone()[0]
        logger.info(f"\nDatabase version:\n{version}")
        
        # Get current database
        cur.execute("SELECT current_database();")
        db_name = cur.fetchone()[0]
        logger.info(f"\nCurrent database: {db_name}")
        
        # Get current user
        cur.execute("SELECT current_user;")
        user = cur.fetchone()[0]
        logger.info(f"Current user: {user}")
        
        # Check existing tables
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name;
        """)
        
        tables = cur.fetchall()
        if tables:
            logger.info(f"\nExisting tables ({len(tables)}):")
            for table in tables:
                logger.info(f"  - {table[0]}")
        else:
            logger.info("\nNo tables found in database (ready for migration)")
        
        # Check if specific migration tables exist
        migration_tables = [
            'users', 'products', 'categories', 'icons', 
            'jobs', 'sync_history', 'configurations'
        ]
        
        existing_migration_tables = [t[0] for t in tables if t[0] in migration_tables]
        if existing_migration_tables:
            logger.warning(f"\n⚠️  Some migration tables already exist: {', '.join(existing_migration_tables)}")
            logger.warning("You may need to drop these tables before running migration")
        
        # Close connection
        cur.close()
        conn.close()
        
        logger.info("\n✅ Connection test completed successfully!")
        return True
        
    except psycopg2.OperationalError as e:
        logger.error(f"\n❌ Failed to connect to Supabase: {str(e)}")
        logger.error("\nPossible causes:")
        logger.error("1. Invalid database credentials")
        logger.error("2. Database is not accessible (check firewall/network)")
        logger.error("3. Supabase project is paused or deleted")
        logger.error("\nPlease verify your credentials and try again")
        return False
    except Exception as e:
        logger.error(f"\n❌ Unexpected error: {str(e)}")
        return False

def main():
    """Main function."""
    success = test_connection()
    
    if success:
        logger.info("\n✅ Ready to proceed with migration!")
        logger.info("\nNext steps:")
        logger.info("1. Run 'python create_supabase_schema.py' to create schema")
        logger.info("2. Run 'python migrations/migrate_sqlite_to_supabase.py' to migrate data")
    else:
        logger.error("\n❌ Please fix the connection issues before proceeding")
        sys.exit(1)

if __name__ == "__main__":
    main()