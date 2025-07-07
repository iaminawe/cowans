#!/usr/bin/env python3
"""
Check existing data in Supabase tables

This script checks what data already exists in the Supabase database.
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

def check_data():
    """Check existing data in Supabase tables."""
    logger.info("=== Supabase Data Check ===")
    logger.info(f"Started at: {datetime.now()}")
    
    # Get DATABASE_URL
    database_url = os.getenv('DATABASE_URL')
    conn_string = database_url.replace('postgresql+psycopg://', 'postgresql://')
    
    try:
        conn = psycopg2.connect(conn_string)
        cur = conn.cursor()
        
        logger.info("✅ Connected to Supabase PostgreSQL")
        
        # Get all tables
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name;
        """)
        
        tables = [row[0] for row in cur.fetchall()]
        
        total_records = 0
        supabase_data = {}
        
        logger.info(f"\nChecking data in {len(tables)} tables...")
        
        for table in tables:
            try:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                count = cur.fetchone()[0]
                supabase_data[table] = count
                total_records += count
                
                if count > 0:
                    logger.info(f"✅ {table}: {count:,} records")
                else:
                    logger.info(f"📭 {table}: empty")
                    
            except Exception as e:
                logger.error(f"❌ {table}: Error - {str(e)}")
        
        # Summary
        logger.info(f"\n📊 Supabase Database Summary:")
        logger.info(f"   Total tables: {len(tables)}")
        logger.info(f"   Total records: {total_records:,}")
        logger.info(f"   Empty tables: {len([t for t, count in supabase_data.items() if count == 0])}")
        logger.info(f"   Tables with data: {len([t for t, count in supabase_data.items() if count > 0])}")
        
        # Check if this looks like a fresh database or already migrated
        if total_records == 0:
            logger.info("\n🆕 Database appears to be empty - ready for fresh migration")
        else:
            logger.info("\n⚠️  Database contains data - may have been partially migrated")
            logger.info("You may want to:")
            logger.info("1. Clear the existing data first")
            logger.info("2. Or skip migration if data is already current")
        
        cur.close()
        conn.close()
        
        return supabase_data
        
    except Exception as e:
        logger.error(f"❌ Error checking database: {str(e)}")
        return {}

def compare_with_sqlite():
    """Compare with SQLite record counts."""
    logger.info("\n=== SQLite vs Supabase Comparison ===")
    
    try:
        import sqlite3
        
        # Connect to SQLite
        sqlite_conn = sqlite3.connect('database.db')
        sqlite_cur = sqlite_conn.cursor()
        
        # Get SQLite tables
        sqlite_cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        sqlite_tables = [row[0] for row in sqlite_cur.fetchall()]
        
        logger.info("SQLite database summary:")
        sqlite_total = 0
        for table in sqlite_tables:
            try:
                sqlite_cur.execute(f"SELECT COUNT(*) FROM {table}")
                count = sqlite_cur.fetchone()[0]
                sqlite_total += count
                if count > 0:
                    logger.info(f"  {table}: {count:,} records")
            except:
                pass
        
        logger.info(f"\nSQLite total records: {sqlite_total:,}")
        
        sqlite_conn.close()
        
    except Exception as e:
        logger.error(f"Error checking SQLite: {str(e)}")

def main():
    """Main function."""
    supabase_data = check_data()
    compare_with_sqlite()
    
    logger.info("\n🎯 Next Steps:")
    
    total_supabase = sum(supabase_data.values())
    
    if total_supabase == 0:
        logger.info("1. Run data migration: python migrations/migrate_sqlite_to_supabase.py")
        logger.info("2. Validate migration: python migrations/validate_migration.py")
        logger.info("Or run complete migration: python run_migration.py")
    else:
        logger.info("1. Check if migration is already complete")
        logger.info("2. Or clear Supabase data and re-migrate if needed")
        logger.info("3. Test your application with current data")

if __name__ == "__main__":
    main()