#!/usr/bin/env python3
"""
Test connection using existing DATABASE_URL from .env

This script uses the DATABASE_URL that's already configured in your .env file.
"""

import os
import sys
import psycopg2
from datetime import datetime
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), '../../.env'))

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_database_connection():
    """Test connection using existing DATABASE_URL."""
    logger.info("=== Database Connection Test ===")
    logger.info(f"Started at: {datetime.now()}")
    
    # Get DATABASE_URL
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        logger.error("❌ DATABASE_URL not found in environment variables")
        return False
    
    # Parse the database URL to extract components for logging
    if database_url.startswith('postgresql'):
        logger.info("✅ PostgreSQL connection string found")
        # Extract host for logging (mask password)
        try:
            # Extract just the host part for display
            if '@' in database_url:
                host_part = database_url.split('@')[1].split('/')[0]
                logger.info(f"Database host: {host_part}")
        except:
            pass
    else:
        logger.info(f"Database type: {database_url.split(':')[0]}")
    
    # Test connection
    logger.info("\nTesting connection...")
    try:
        # Use the raw DATABASE_URL, handling both psycopg2 and psycopg3 formats
        conn_string = database_url
        # Remove psycopg3 indicator if present
        if 'postgresql+psycopg://' in conn_string:
            conn_string = conn_string.replace('postgresql+psycopg://', 'postgresql://')
        
        conn = psycopg2.connect(conn_string)
        cur = conn.cursor()
        
        logger.info("✅ Successfully connected to PostgreSQL!")
        
        # Get database info
        cur.execute("SELECT version();")
        version = cur.fetchone()[0]
        logger.info(f"\nDatabase version:\n{version}")
        
        cur.execute("SELECT current_database();")
        db_name = cur.fetchone()[0]
        logger.info(f"\nCurrent database: {db_name}")
        
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
        
        # Close connection
        cur.close()
        conn.close()
        
        logger.info("\n✅ Connection test completed successfully!")
        logger.info("\nDatabase is ready for migration!")
        return True
        
    except psycopg2.OperationalError as e:
        logger.error(f"\n❌ Failed to connect to database: {str(e)}")
        logger.error("\nPossible causes:")
        logger.error("1. Invalid database credentials")
        logger.error("2. Database is not accessible")
        logger.error("3. Network connectivity issues")
        return False
    except Exception as e:
        logger.error(f"\n❌ Unexpected error: {str(e)}")
        return False

def main():
    """Main function."""
    success = test_database_connection()
    
    if success:
        logger.info("\n🚀 Ready to proceed with migration!")
        logger.info("\nNext steps:")
        logger.info("1. Run: python create_supabase_schema.py")
        logger.info("2. Run: python migrations/migrate_sqlite_to_supabase.py")
        logger.info("3. Run: python migrations/validate_migration.py")
        logger.info("\nOr run the complete migration:")
        logger.info("python run_migration.py")
    else:
        logger.error("\n❌ Please fix the connection issues before proceeding")
        sys.exit(1)

if __name__ == "__main__":
    main()