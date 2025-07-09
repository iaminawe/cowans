#!/usr/bin/env python3
"""
Fix duplicate index names in the database.
This script resolves conflicts where multiple tables have indexes with the same name.
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    """Get database connection."""
    db_url = os.getenv('DATABASE_URL')
    if db_url.startswith('postgresql+psycopg://'):
        db_url = db_url.replace('postgresql+psycopg://', 'postgresql://')
    return psycopg2.connect(db_url, cursor_factory=RealDictCursor)

def fix_duplicate_indexes():
    """Fix duplicate index names by renaming them."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if indexes exist and drop/recreate them with proper names
        index_fixes = [
            {
                'old_name': 'idx_batch_user',
                'new_name': 'idx_etilize_batch_user', 
                'table': 'etilize_import_batches',
                'column': 'triggered_by'
            },
            {
                'old_name': 'idx_batch_status',
                'new_name': 'idx_etilize_batch_status',
                'table': 'etilize_import_batches', 
                'column': 'status'
            },
            {
                'old_name': 'idx_batch_type',
                'new_name': 'idx_etilize_batch_type',
                'table': 'etilize_import_batches',
                'column': 'import_type'
            },
            {
                'old_name': 'idx_batch_started',
                'new_name': 'idx_etilize_batch_started',
                'table': 'etilize_import_batches',
                'column': 'started_at'
            },
            {
                'old_name': 'idx_batch_uuid',
                'new_name': 'idx_etilize_batch_uuid',
                'table': 'etilize_import_batches',
                'column': 'batch_uuid'
            }
        ]
        
        for fix in index_fixes:
            # Check if old index exists
            cursor.execute("""
                SELECT indexname FROM pg_indexes 
                WHERE indexname = %s
            """, (fix['old_name'],))
            
            if cursor.fetchone():
                print(f"Dropping index {fix['old_name']}")
                cursor.execute(f"DROP INDEX IF EXISTS {fix['old_name']}")
            
            # Check if new index already exists
            cursor.execute("""
                SELECT indexname FROM pg_indexes 
                WHERE indexname = %s
            """, (fix['new_name'],))
            
            if not cursor.fetchone():
                print(f"Creating index {fix['new_name']} on {fix['table']}({fix['column']})")
                cursor.execute(f"""
                    CREATE INDEX {fix['new_name']} 
                    ON {fix['table']} ({fix['column']})
                """)
        
        # Fix the sync_batches table index name (only if table exists)
        cursor.execute("""
            SELECT tablename FROM pg_tables 
            WHERE tablename = 'sync_batches'
        """)
        
        if cursor.fetchone():
            cursor.execute("""
                SELECT indexname FROM pg_indexes 
                WHERE indexname = 'idx_batch_user' AND tablename = 'sync_batches'
            """)
            
            if cursor.fetchone():
                print("Renaming idx_batch_user to idx_sync_batch_user on sync_batches table")
                cursor.execute("ALTER INDEX idx_batch_user RENAME TO idx_sync_batch_user")
            else:
                # Create the index if it doesn't exist
                cursor.execute("""
                    SELECT indexname FROM pg_indexes 
                    WHERE indexname = 'idx_sync_batch_user'
                """)
                
                if not cursor.fetchone():
                    print("Creating idx_sync_batch_user on sync_batches table")
                    cursor.execute("""
                        CREATE INDEX IF NOT EXISTS idx_sync_batch_user 
                        ON sync_batches (created_by)
                    """)
        else:
            print("sync_batches table does not exist, skipping index creation")
        
        conn.commit()
        print("Index fixes completed successfully!")
        
    except Exception as e:
        conn.rollback()
        print(f"Error fixing indexes: {e}")
        raise
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    fix_duplicate_indexes()