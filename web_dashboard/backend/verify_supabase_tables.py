#!/usr/bin/env python3
"""
Verify and create Supabase tables if they don't exist
"""

import os
import sys
from dotenv import load_dotenv
from supabase import create_client, Client
from datetime import datetime

# Load environment variables
env_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
load_dotenv(env_path)

# Get Supabase credentials
url = os.getenv("SUPABASE_URL")
service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not url or not service_role_key:
    print("Error: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env")
    sys.exit(1)

# Create Supabase client with service role key
supabase: Client = create_client(url, service_role_key)

print("=== Checking Supabase Tables ===\n")

# Tables to check
tables_to_check = [
    'users',
    'products', 
    'categories',
    'collections',
    'sync_history',
    'product_collections',
    'product_images',
    'batch_operations',
    'jobs',
    'icons'
]

# Check each table
existing_tables = []
missing_tables = []

for table_name in tables_to_check:
    try:
        # Try to select from the table
        result = supabase.table(table_name).select('*').limit(1).execute()
        existing_tables.append(table_name)
        print(f"✅ Table '{table_name}' exists")
    except Exception as e:
        missing_tables.append(table_name)
        print(f"❌ Table '{table_name}' not found: {str(e)}")

print(f"\n=== Summary ===")
print(f"Existing tables: {len(existing_tables)}")
print(f"Missing tables: {len(missing_tables)}")

if missing_tables:
    print(f"\nMissing tables that need to be created in Supabase:")
    for table in missing_tables:
        print(f"  - {table}")
    
    print("\n=== SQL to create missing tables ===")
    print("\nYou can run these SQL commands in your Supabase SQL editor:\n")
    
    # Generate SQL for missing tables
    table_schemas = {
        'products': """
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    shopify_product_id BIGINT UNIQUE,
    title VARCHAR(255) NOT NULL,
    vendor VARCHAR(255),
    product_type VARCHAR(255),
    status VARCHAR(50),
    tags TEXT,
    category_id INTEGER,
    sku VARCHAR(255),
    barcode VARCHAR(255),
    price DECIMAL(10,2),
    inventory_quantity INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);""",
        
        'categories': """
CREATE TABLE IF NOT EXISTS categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) UNIQUE,
    parent_id INTEGER REFERENCES categories(id),
    level INTEGER DEFAULT 0,
    path TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);""",
        
        'collections': """
CREATE TABLE IF NOT EXISTS collections (
    id SERIAL PRIMARY KEY,
    shopify_collection_id BIGINT UNIQUE,
    title VARCHAR(255) NOT NULL,
    handle VARCHAR(255),
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);""",
        
        'sync_history': """
CREATE TABLE IF NOT EXISTS sync_history (
    id SERIAL PRIMARY KEY,
    sync_type VARCHAR(50),
    status VARCHAR(50),
    products_added INTEGER DEFAULT 0,
    products_updated INTEGER DEFAULT 0,
    products_deleted INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    error_details TEXT,
    duration INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);""",
        
        'product_collections': """
CREATE TABLE IF NOT EXISTS product_collections (
    id SERIAL PRIMARY KEY,
    product_id INTEGER REFERENCES products(id),
    collection_id INTEGER REFERENCES collections(id),
    position INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(product_id, collection_id)
);""",
        
        'batch_operations': """
CREATE TABLE IF NOT EXISTS batch_operations (
    id SERIAL PRIMARY KEY,
    operation_type VARCHAR(50),
    status VARCHAR(50),
    total_items INTEGER,
    processed_items INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    details JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);""",
        
        'product_images': """
CREATE TABLE IF NOT EXISTS product_images (
    id SERIAL PRIMARY KEY,
    product_id INTEGER REFERENCES products(id),
    shopify_image_id BIGINT,
    src TEXT,
    position INTEGER,
    alt_text TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);""",
        
        'jobs': """
CREATE TABLE IF NOT EXISTS jobs (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255),
    status VARCHAR(50),
    progress INTEGER DEFAULT 0,
    error_message TEXT,
    result JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);""",
        
        'icons': """
CREATE TABLE IF NOT EXISTS icons (
    id SERIAL PRIMARY KEY,
    product_id INTEGER REFERENCES products(id),
    category_id INTEGER REFERENCES categories(id),
    filename VARCHAR(255),
    url TEXT,
    prompt TEXT,
    style VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);"""
    }
    
    for table in missing_tables:
        if table in table_schemas:
            print(f"\n-- Create {table} table")
            print(table_schemas[table])
    
    print("\n\n=== Next Steps ===")
    print("1. Go to your Supabase dashboard")
    print("2. Navigate to the SQL editor")
    print("3. Run the SQL commands above to create the missing tables")
    print("4. Enable Row Level Security (RLS) if needed")
    print("5. Set up any necessary indexes for performance")

else:
    print("\n✅ All required tables exist in Supabase!")
    
print("\n=== Testing Data Access ===")

# Test reading from key tables
test_tables = ['products', 'categories', 'collections']
for table in test_tables:
    if table in existing_tables:
        try:
            result = supabase.table(table).select('*').limit(5).execute()
            count = len(result.data) if result.data else 0
            print(f"✅ {table}: {count} records found")
        except Exception as e:
            print(f"❌ Error reading from {table}: {str(e)}")