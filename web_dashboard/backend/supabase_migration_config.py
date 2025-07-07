"""
Supabase Migration Configuration

This file contains the configuration for migrating from SQLite to Supabase PostgreSQL.
Update the connection strings with your actual Supabase credentials.
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# SQLite Configuration
SQLITE_DB_PATH = os.path.join(os.path.dirname(__file__), 'database.db')

# Supabase Configuration
SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://gqozcvqgsjaagnnjukmo.supabase.co')
SUPABASE_DB_URL = os.getenv('SUPABASE_DB_URL', '')  # Get from Supabase dashboard

# If SUPABASE_DB_URL is not set, construct it from components
if not SUPABASE_DB_URL:
    # You need to get these from Supabase dashboard under Settings > Database
    SUPABASE_DB_HOST = os.getenv('SUPABASE_DB_HOST', 'db.gqozcvqgsjaagnnjukmo.supabase.co')
    SUPABASE_DB_PORT = os.getenv('SUPABASE_DB_PORT', '5432')
    SUPABASE_DB_NAME = os.getenv('SUPABASE_DB_NAME', 'postgres')
    SUPABASE_DB_USER = os.getenv('SUPABASE_DB_USER', 'postgres')
    # Handle both possible password variable names
    SUPABASE_DB_PASSWORD = os.getenv('SUPABASE_DB_PASSWORD', '') or os.getenv('SUPBASE_DB_PASS', '')
    
    if SUPABASE_DB_PASSWORD:
        SUPABASE_DB_URL = f"postgresql://{SUPABASE_DB_USER}:{SUPABASE_DB_PASSWORD}@{SUPABASE_DB_HOST}:{SUPABASE_DB_PORT}/{SUPABASE_DB_NAME}"
    else:
        print("⚠️  WARNING: Supabase database credentials not found in environment variables.")
        print("Please set the following environment variables:")
        print("  - SUPABASE_DB_URL (full connection string)")
        print("  OR")
        print("  - SUPABASE_DB_HOST")
        print("  - SUPABASE_DB_PASSWORD")
        print("  - SUPABASE_DB_USER (optional, defaults to 'postgres')")
        print("  - SUPABASE_DB_NAME (optional, defaults to 'postgres')")
        print("  - SUPABASE_DB_PORT (optional, defaults to '5432')")
        print("\nYou can find these in your Supabase dashboard under Settings > Database")

# Migration Settings
BATCH_SIZE = 1000  # Number of records to process at once
LOG_LEVEL = 'INFO'  # Logging level
BACKUP_BEFORE_MIGRATION = True  # Create backup before migration
VALIDATE_AFTER_MIGRATION = True  # Run validation after migration

# Table migration order (respects foreign key dependencies)
TABLE_ORDER = [
    'users',
    'categories',
    'configurations',
    'sync_queue',
    'icons',
    'jobs',
    'import_rules',
    'sync_history',
    'system_logs',
    'etilize_import_batches',
    'products',
    'shopify_syncs',
    'product_images',
    'product_metafields',
    'etilize_staging_products',
    'product_sources',
    'product_change_logs'
]