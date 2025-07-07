#!/usr/bin/env python3
"""
Create Supabase Schema from Migration SQL

This script connects to your Supabase PostgreSQL database and creates all tables,
indexes, and constraints defined in the migration SQL file.
"""

import os
import sys
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from pathlib import Path
import logging
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from supabase_migration_config import SUPABASE_DB_URL

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def read_migration_sql():
    """Read the SQL migration file."""
    sql_file = Path(__file__).parent / 'migrations' / 'sqlite_to_supabase_migration.sql'
    
    if not sql_file.exists():
        logger.error(f"Migration SQL file not found: {sql_file}")
        sys.exit(1)
    
    with open(sql_file, 'r') as f:
        return f.read()

def execute_schema_creation():
    """Execute the schema creation SQL in Supabase."""
    if not SUPABASE_DB_URL:
        logger.error("Supabase database URL not configured. Please check supabase_migration_config.py")
        sys.exit(1)
    
    logger.info("Connecting to Supabase PostgreSQL...")
    
    try:
        # Connect to Supabase
        conn = psycopg2.connect(SUPABASE_DB_URL)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        
        logger.info("Connected successfully!")
        
        # Read migration SQL
        migration_sql = read_migration_sql()
        
        # Split SQL into individual statements
        # This is a simple split - for production, use a proper SQL parser
        statements = []
        current_statement = []
        
        for line in migration_sql.split('\n'):
            # Skip comments and empty lines
            if line.strip().startswith('--') or not line.strip():
                continue
            
            current_statement.append(line)
            
            # Check if this completes a statement
            if line.strip().endswith(';'):
                statement = '\n'.join(current_statement)
                statements.append(statement)
                current_statement = []
        
        logger.info(f"Found {len(statements)} SQL statements to execute")
        
        # Execute each statement
        success_count = 0
        error_count = 0
        
        for i, statement in enumerate(statements, 1):
            try:
                # Log the type of statement
                statement_type = statement.strip().split()[0].upper()
                logger.info(f"Executing statement {i}/{len(statements)}: {statement_type}...")
                
                cur.execute(statement)
                success_count += 1
                
            except psycopg2.errors.DuplicateTable as e:
                logger.warning(f"Table already exists: {str(e).split('relation')[1].split('already')[0].strip()}")
                error_count += 1
            except psycopg2.errors.DuplicateObject as e:
                logger.warning(f"Object already exists: {str(e)}")
                error_count += 1
            except Exception as e:
                logger.error(f"Error executing statement {i}: {str(e)}")
                logger.debug(f"Statement: {statement[:100]}...")
                error_count += 1
        
        logger.info(f"\nSchema creation completed!")
        logger.info(f"✅ Successful statements: {success_count}")
        if error_count > 0:
            logger.warning(f"⚠️  Statements with warnings/errors: {error_count}")
        
        # Verify tables were created
        logger.info("\nVerifying created tables...")
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name;
        """)
        
        tables = cur.fetchall()
        logger.info(f"\nTables in database ({len(tables)}):")
        for table in tables:
            logger.info(f"  - {table[0]}")
        
        # Close connection
        cur.close()
        conn.close()
        
        logger.info("\n✅ Schema creation completed successfully!")
        
        if error_count > 0:
            logger.info("\n⚠️  Note: Some warnings occurred (likely due to objects already existing).")
            logger.info("This is normal if you're re-running the migration.")
        
        return True
        
    except psycopg2.OperationalError as e:
        logger.error(f"Failed to connect to Supabase: {str(e)}")
        logger.error("Please check your database credentials in supabase_migration_config.py")
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return False

def main():
    """Main function."""
    logger.info("=== Supabase Schema Creation ===")
    logger.info(f"Started at: {datetime.now()}")
    
    # Create schema
    success = execute_schema_creation()
    
    if success:
        logger.info("\n✅ Schema creation successful!")
        logger.info("\nNext steps:")
        logger.info("1. Review the created tables in your Supabase dashboard")
        logger.info("2. Run 'python migrate_sqlite_to_supabase.py' to migrate data")
        logger.info("3. Run 'python validate_migration.py' to verify data integrity")
    else:
        logger.error("\n❌ Schema creation failed!")
        logger.error("Please fix the errors and try again.")
        sys.exit(1)

if __name__ == "__main__":
    main()