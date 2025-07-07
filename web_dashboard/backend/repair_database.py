#!/usr/bin/env python3
"""
Database repair script for fixing corrupted SQLite database.
This script attempts to recover data from a corrupted database and create a new clean database.
"""

import os
import sys
import sqlite3
import shutil
from datetime import datetime
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from models import Base
from database import init_db

def backup_database(db_path):
    """Create a backup of the current database."""
    if not os.path.exists(db_path):
        print(f"Database file {db_path} not found.")
        return None
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{db_path}.backup_{timestamp}"
    
    try:
        shutil.copy2(db_path, backup_path)
        print(f"Created backup: {backup_path}")
        return backup_path
    except Exception as e:
        print(f"Failed to create backup: {e}")
        return None

def recover_data(corrupted_db_path):
    """Attempt to recover data from corrupted database."""
    recovered_data = {}
    
    try:
        # Try to connect with recover mode
        conn = sqlite3.connect(f"file:{corrupted_db_path}?mode=ro", uri=True)
        cursor = conn.cursor()
        
        # Get list of tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        print(f"Found {len(tables)} tables in corrupted database")
        
        for table_name in tables:
            table_name = table_name[0]
            if table_name.startswith('sqlite_'):
                continue
                
            try:
                cursor.execute(f"SELECT * FROM {table_name};")
                data = cursor.fetchall()
                
                # Get column names
                cursor.execute(f"PRAGMA table_info({table_name});")
                columns = [col[1] for col in cursor.fetchall()]
                
                recovered_data[table_name] = {
                    'columns': columns,
                    'data': data
                }
                print(f"Recovered {len(data)} rows from {table_name}")
            except Exception as e:
                print(f"Failed to recover data from {table_name}: {e}")
        
        conn.close()
        return recovered_data
        
    except Exception as e:
        print(f"Failed to open corrupted database: {e}")
        return {}

def rebuild_database(recovered_data, new_db_path):
    """Rebuild database with recovered data."""
    # Remove existing database if it exists
    if os.path.exists(new_db_path):
        os.remove(new_db_path)
    
    # Create new database with schema
    engine = create_engine(f'sqlite:///{new_db_path}')
    Base.metadata.create_all(engine)
    
    if not recovered_data:
        print("No data to recover. Created empty database.")
        return
    
    # Insert recovered data
    conn = sqlite3.connect(new_db_path)
    cursor = conn.cursor()
    
    for table_name, table_data in recovered_data.items():
        if not table_data['data']:
            continue
            
        columns = table_data['columns']
        placeholders = ','.join(['?' for _ in columns])
        column_names = ','.join(columns)
        
        try:
            for row in table_data['data']:
                query = f"INSERT INTO {table_name} ({column_names}) VALUES ({placeholders})"
                cursor.execute(query, row)
            
            conn.commit()
            print(f"Restored {len(table_data['data'])} rows to {table_name}")
        except Exception as e:
            print(f"Failed to restore data to {table_name}: {e}")
            conn.rollback()
    
    conn.close()

def main():
    """Main repair function."""
    db_path = "database.db"
    
    print("=== SQLite Database Repair Tool ===")
    print(f"Target database: {db_path}")
    
    # Step 1: Backup current database
    print("\nStep 1: Creating backup...")
    backup_path = backup_database(db_path)
    if not backup_path:
        print("No backup created (database may not exist)")
    
    # Step 2: Try to recover data
    if os.path.exists(db_path):
        print("\nStep 2: Attempting to recover data...")
        recovered_data = recover_data(db_path)
    else:
        recovered_data = {}
    
    # Step 3: Rebuild database
    print("\nStep 3: Rebuilding database...")
    new_db_path = "database_repaired.db"
    rebuild_database(recovered_data, new_db_path)
    
    # Step 4: Replace old database with repaired one
    if os.path.exists(new_db_path):
        print("\nStep 4: Replacing old database...")
        if os.path.exists(db_path):
            os.remove(db_path)
        os.rename(new_db_path, db_path)
        print("Database repair completed successfully!")
    else:
        print("Failed to create repaired database.")
        return 1
    
    # Step 5: Initialize with default data if needed
    print("\nStep 5: Initializing database with default data...")
    try:
        init_db()
        print("Database initialization completed.")
    except Exception as e:
        print(f"Failed to initialize database: {e}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())