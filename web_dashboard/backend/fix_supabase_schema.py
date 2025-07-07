#!/usr/bin/env python3
"""
Fix Supabase Schema Issues

This script fixes schema issues found after migration.
"""

import os
import psycopg2
from datetime import datetime
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), '../../.env'))

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fix_users_table():
    """Add supabase_id column to users table if missing."""
    logger.info("=== Fixing Users Table Schema ===")
    
    database_url = os.getenv('DATABASE_URL').replace('postgresql+psycopg://', 'postgresql://')
    
    try:
        conn = psycopg2.connect(database_url)
        cur = conn.cursor()
        
        # Check if supabase_id column exists
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'users' 
            AND column_name = 'supabase_id'
        """)
        
        if cur.fetchone():
            logger.info("✅ supabase_id column already exists")
        else:
            logger.info("Adding supabase_id column to users table...")
            
            # Add the column
            cur.execute("ALTER TABLE users ADD COLUMN supabase_id VARCHAR(255)")
            
            # Add unique index
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_supabase_id ON users(supabase_id)")
            
            conn.commit()
            logger.info("✅ Added supabase_id column and index")
        
        # Check column structure
        cur.execute("""
            SELECT column_name, data_type, is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'users'
            ORDER BY ordinal_position
        """)
        
        columns = cur.fetchall()
        logger.info(f"\nUsers table structure ({len(columns)} columns):")
        for col in columns:
            logger.info(f"  {col[0]}: {col[1]} ({'NULL' if col[2] == 'YES' else 'NOT NULL'})")
        
        cur.close()
        conn.close()
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error fixing users table: {str(e)}")
        return False

def fix_app_py():
    """Fix app.py issues."""
    logger.info("\n=== Fixing app.py Issues ===")
    
    # Read app.py
    try:
        with open('app.py', 'r') as f:
            content = f.read()
        
        # Check if jwt_required_bypass is defined but not imported
        if 'jwt_required_bypass' in content and 'def jwt_required_bypass' not in content:
            logger.info("Found jwt_required_bypass usage without definition")
            
            # Replace with supabase_jwt_optional
            content = content.replace('jwt_required_bypass', 'supabase_jwt_optional')
            
            with open('app.py', 'w') as f:
                f.write(content)
            
            logger.info("✅ Fixed jwt_required_bypass issue")
        else:
            logger.info("✅ No jwt_required_bypass issues found")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error fixing app.py: {str(e)}")
        return False

def test_application():
    """Test if application can start."""
    logger.info("\n=== Testing Application ===")
    
    try:
        # Test import
        import sys
        sys.path.insert(0, '.')
        
        # Try importing the app
        from app import app
        logger.info("✅ Application imports successfully")
        
        # Test database connection
        from database import db_manager
        if db_manager and db_manager.database_url:
            logger.info(f"✅ Database configured: PostgreSQL")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Application test failed: {str(e)}")
        return False

def main():
    """Main function."""
    logger.info("🔧 Fixing Supabase Integration Issues")
    logger.info("=" * 50)
    logger.info(f"Started at: {datetime.now()}")
    
    # Fix users table
    if not fix_users_table():
        logger.error("Failed to fix users table")
        return
    
    # Fix app.py
    if not fix_app_py():
        logger.error("Failed to fix app.py")
        return
    
    # Test application
    if test_application():
        logger.info("\n🎉 All Issues Fixed!")
        logger.info("=" * 50)
        logger.info("✅ Supabase schema corrected")
        logger.info("✅ Application code fixed")
        logger.info("✅ Ready to start application")
        
        logger.info("\n🚀 Next Steps:")
        logger.info("1. Start application: python app.py")
        logger.info("2. Test authentication endpoints")
        logger.info("3. Verify all features work")
    else:
        logger.error("\n❌ Issues remain - check error messages above")

if __name__ == "__main__":
    main()