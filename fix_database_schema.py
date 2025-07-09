#!/usr/bin/env python3
"""
Fix database schema by adding missing columns for Shopify sync
"""

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def fix_database_schema():
    """Add missing columns to products table for Shopify sync."""
    
    # Get database connection
    db_url = os.getenv('DATABASE_URL')
    if db_url.startswith('postgresql+psycopg://'):
        db_url = db_url.replace('postgresql+psycopg://', 'postgresql://')
    
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()
    
    print("🔧 Fixing database schema for Shopify sync...")
    
    # List of columns that need to be added
    missing_columns = [
        ("handle", "VARCHAR(255)"),
        ("vendor", "VARCHAR(255)"),
        ("product_type", "VARCHAR(255)"),
        ("tags", "TEXT"),
        ("status", "VARCHAR(50) DEFAULT 'draft'"),
        ("published_at", "TIMESTAMP"),
        ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
        ("updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    ]
    
    # Check which columns already exist
    cursor.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'products' AND table_schema = 'public'
    """)
    existing_columns = {row[0] for row in cursor.fetchall()}
    print(f"📊 Existing columns: {sorted(existing_columns)}")
    
    # Add missing columns
    added_count = 0
    for column_name, column_type in missing_columns:
        if column_name not in existing_columns:
            try:
                print(f"➕ Adding column: {column_name} ({column_type})")
                cursor.execute(f"ALTER TABLE products ADD COLUMN {column_name} {column_type}")
                added_count += 1
            except Exception as e:
                print(f"⚠️  Error adding {column_name}: {str(e)}")
        else:
            print(f"✅ Column {column_name} already exists")
    
    # Commit changes
    conn.commit()
    
    # Verify the schema is now correct
    cursor.execute("""
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns 
        WHERE table_name = 'products' AND table_schema = 'public'
        ORDER BY column_name
    """)
    
    print(f"\n📋 Final products table schema:")
    for row in cursor.fetchall():
        column_name, data_type, is_nullable, default = row
        nullable = "NULL" if is_nullable == "YES" else "NOT NULL"
        default_str = f" DEFAULT {default}" if default else ""
        print(f"  • {column_name}: {data_type} {nullable}{default_str}")
    
    cursor.close()
    conn.close()
    
    print(f"\n✅ Schema update completed! Added {added_count} new columns.")
    return True

if __name__ == "__main__":
    try:
        fix_database_schema()
        print("\n🚀 Database is now ready for full Shopify sync!")
    except Exception as e:
        print(f"❌ Error: {str(e)}")