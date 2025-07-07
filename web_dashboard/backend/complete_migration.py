#!/usr/bin/env python3
"""
Complete Migration - Sync Missing Data

This script completes the migration by syncing missing data from SQLite to Supabase.
"""

import os
import sqlite3
import psycopg2
from datetime import datetime
import logging
from dotenv import load_dotenv
import json
from tqdm import tqdm

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), '../../.env'))

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_missing_data():
    """Identify what data needs to be migrated."""
    logger.info("=== Analyzing Missing Data ===")
    
    # Connect to both databases
    sqlite_conn = sqlite3.connect('database.db')
    sqlite_cur = sqlite_conn.cursor()
    
    database_url = os.getenv('DATABASE_URL').replace('postgresql+psycopg://', 'postgresql://')
    pg_conn = psycopg2.connect(database_url)
    pg_cur = pg_conn.cursor()
    
    missing_data = {}
    
    # Check each table
    tables = ['users', 'icons', 'jobs', 'sync_history', 'etilize_import_batches', 'etilize_staging_products']
    
    for table in tables:
        try:
            # Get SQLite count
            sqlite_cur.execute(f"SELECT COUNT(*) FROM {table}")
            sqlite_count = sqlite_cur.fetchone()[0]
            
            # Get PostgreSQL count
            pg_cur.execute(f"SELECT COUNT(*) FROM {table}")
            pg_count = pg_cur.fetchone()[0]
            
            diff = sqlite_count - pg_count
            if diff > 0:
                missing_data[table] = {
                    'sqlite_count': sqlite_count,
                    'postgres_count': pg_count,
                    'missing': diff
                }
                logger.info(f"📋 {table}: {diff} records missing")
            else:
                logger.info(f"✅ {table}: up to date")
                
        except Exception as e:
            logger.error(f"❌ Error checking {table}: {str(e)}")
    
    sqlite_conn.close()
    pg_conn.close()
    
    return missing_data

def migrate_table_data(table, limit=None):
    """Migrate data for a specific table."""
    logger.info(f"\n🔄 Migrating {table}...")
    
    # Connect to databases
    sqlite_conn = sqlite3.connect('database.db')
    sqlite_conn.row_factory = sqlite3.Row  # Enable column access by name
    sqlite_cur = sqlite_conn.cursor()
    
    database_url = os.getenv('DATABASE_URL').replace('postgresql+psycopg://', 'postgresql://')
    pg_conn = psycopg2.connect(database_url)
    pg_cur = pg_conn.cursor()
    
    try:
        # Get all data from SQLite
        if limit:
            sqlite_cur.execute(f"SELECT * FROM {table} LIMIT {limit}")
        else:
            sqlite_cur.execute(f"SELECT * FROM {table}")
        
        rows = sqlite_cur.fetchall()
        
        if not rows:
            logger.info(f"  No data to migrate for {table}")
            return True
        
        # Get column names
        columns = [description[0] for description in sqlite_cur.description]
        
        # Clear existing data in PostgreSQL for fresh sync
        pg_cur.execute(f"DELETE FROM {table}")
        logger.info(f"  Cleared existing {table} data")
        
        # Prepare insert statement
        placeholders = ', '.join(['%s'] * len(columns))
        insert_sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
        
        # Insert data with progress bar
        success_count = 0
        error_count = 0
        
        for row in tqdm(rows, desc=f"Migrating {table}"):
            try:
                # Convert row to list of values
                values = []
                for i, col in enumerate(columns):
                    value = row[i]
                    
                    # Handle JSON fields
                    if col in ['meta_data', 'import_config', 'error_details', 'parameters']:
                        if value and isinstance(value, str):
                            try:
                                # Validate JSON
                                json.loads(value)
                                values.append(value)
                            except:
                                values.append('{}')
                        else:
                            values.append('{}' if value is None else value)
                    else:
                        values.append(value)
                
                pg_cur.execute(insert_sql, values)
                success_count += 1
                
            except Exception as e:
                logger.debug(f"Error inserting row: {str(e)}")
                error_count += 1
        
        pg_conn.commit()
        
        logger.info(f"  ✅ {table}: {success_count} records migrated")
        if error_count > 0:
            logger.warning(f"  ⚠️  {table}: {error_count} records failed")
        
        return True
        
    except Exception as e:
        logger.error(f"  ❌ Error migrating {table}: {str(e)}")
        pg_conn.rollback()
        return False
        
    finally:
        sqlite_conn.close()
        pg_conn.close()

def validate_migration():
    """Validate the completed migration."""
    logger.info("\n=== Validating Migration ===")
    
    # Connect to both databases
    sqlite_conn = sqlite3.connect('database.db')
    sqlite_cur = sqlite_conn.cursor()
    
    database_url = os.getenv('DATABASE_URL').replace('postgresql+psycopg://', 'postgresql://')
    pg_conn = psycopg2.connect(database_url)
    pg_cur = pg_conn.cursor()
    
    validation_passed = True
    
    # Get all tables
    sqlite_cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in sqlite_cur.fetchall()]
    
    for table in tables:
        try:
            # Compare counts
            sqlite_cur.execute(f"SELECT COUNT(*) FROM {table}")
            sqlite_count = sqlite_cur.fetchone()[0]
            
            pg_cur.execute(f"SELECT COUNT(*) FROM {table}")
            pg_count = pg_cur.fetchone()[0]
            
            if sqlite_count == pg_count:
                logger.info(f"✅ {table}: {sqlite_count} records (match)")
            else:
                logger.error(f"❌ {table}: SQLite {sqlite_count} vs PostgreSQL {pg_count}")
                validation_passed = False
                
        except Exception as e:
            logger.error(f"❌ Error validating {table}: {str(e)}")
            validation_passed = False
    
    sqlite_conn.close()
    pg_conn.close()
    
    return validation_passed

def main():
    """Main migration completion function."""
    logger.info("🔄 Completing Migration from SQLite to Supabase")
    logger.info("=" * 60)
    logger.info(f"Started at: {datetime.now()}")
    
    # Analyze missing data
    missing_data = get_missing_data()
    
    if not missing_data:
        logger.info("\n✅ No missing data found - migration appears complete!")
        return
    
    logger.info(f"\nFound {len(missing_data)} tables with missing data")
    
    # Migrate missing data
    success_count = 0
    for table in missing_data.keys():
        if migrate_table_data(table):
            success_count += 1
    
    # Validate migration
    logger.info(f"\n🔍 Validating complete migration...")
    if validate_migration():
        logger.info("\n🎉 Migration Completed Successfully!")
        logger.info("=" * 60)
        logger.info("✅ All data successfully migrated from SQLite to Supabase")
        logger.info("✅ Data validation passed")
        logger.info("✅ Your application is ready to use Supabase PostgreSQL")
        
        logger.info("\n🚀 Next Steps:")
        logger.info("1. Test your application functionality")
        logger.info("2. Verify authentication works")
        logger.info("3. Check all features are working")
        logger.info("4. Monitor for any issues")
        
    else:
        logger.error("\n❌ Migration validation failed!")
        logger.error("Please check the errors above and retry")

if __name__ == "__main__":
    main()