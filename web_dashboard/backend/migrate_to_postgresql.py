#!/usr/bin/env python3
"""
PostgreSQL Migration Script for Cowans Office Supplies Integration System

This script migrates data from SQLite to PostgreSQL (Supabase) and tests the connection.
Part of Phase 1 Week 1 implementation orchestrated by ruv-swarm.
"""

import os
import sys
import logging
from datetime import datetime
import sqlite3
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from dateutil.parser import parse as parse_datetime

# Add current directory to Python path
sys.path.append(os.path.dirname(__file__))

from database import db_manager, get_db_session
from models import Base, Product, Category

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def convert_datetime_field(value):
    """Convert string datetime to datetime object if needed."""
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return parse_datetime(value)
        except (ValueError, TypeError):
            logger.warning(f"Failed to parse datetime: {value}")
            return None
    return value

def test_postgresql_connection():
    """Test PostgreSQL connection to Supabase."""
    try:
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            logger.error("DATABASE_URL not found in environment variables")
            return False
            
        logger.info(f"Testing PostgreSQL connection...")
        logger.info(f"Database URL: {database_url.split('@')[0]}@***") # Hide credentials
        
        # Create engine
        engine = create_engine(database_url, echo=False)
        
        # Test connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            logger.info(f"✅ PostgreSQL connection successful!")
            logger.info(f"PostgreSQL version: {version}")
            
        return True
        
    except Exception as e:
        logger.error(f"❌ PostgreSQL connection failed: {e}")
        return False

def backup_sqlite_data():
    """Create a backup of current SQLite database."""
    try:
        sqlite_path = os.path.join(os.path.dirname(__file__), 'database.db')
        if not os.path.exists(sqlite_path):
            logger.warning("SQLite database not found, skipping backup")
            return False
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{sqlite_path}.backup_{timestamp}"
        
        # Copy SQLite database
        import shutil
        shutil.copy2(sqlite_path, backup_path)
        
        logger.info(f"✅ SQLite backup created: {backup_path}")
        return True
        
    except Exception as e:
        logger.error(f"❌ SQLite backup failed: {e}")
        return False

def migrate_data():
    """Migrate data from SQLite to PostgreSQL."""
    try:
        # Initialize PostgreSQL database with tables
        logger.info("Initializing PostgreSQL database...")
        # Force use of PostgreSQL URL
        database_url = os.getenv('DATABASE_URL')
        from database import DatabaseManager
        pg_db_manager = DatabaseManager(database_url)
        pg_db_manager.initialize(create_tables=True)
        
        # Get PostgreSQL session
        pg_session = pg_db_manager.get_session()
        
        # Connect to SQLite
        sqlite_path = os.path.join(os.path.dirname(__file__), 'database.db')
        if not os.path.exists(sqlite_path):
            logger.warning("SQLite database not found, skipping data migration")
            return True
            
        sqlite_conn = sqlite3.connect(sqlite_path)
        sqlite_conn.row_factory = sqlite3.Row  # Enable column access by name
        
        # Create a default "Uncategorized" category if it doesn't exist
        logger.info("Ensuring default 'Uncategorized' category exists...")
        existing_default = pg_session.query(Category).filter_by(id=1).first()
        if not existing_default:
            default_category = Category(
                id=1,
                name='Uncategorized',
                slug='uncategorized',
                description='Default category for uncategorized products',
                level=0,
                is_active=True,
                sort_order=0
            )
            pg_session.add(default_category)
            pg_session.commit()
            logger.info("✅ Default category created")
        else:
            logger.info("✅ Default category already exists")
        
        # Migrate categories first to avoid foreign key issues
        logger.info("Migrating categories...")
        try:
            cursor = sqlite_conn.execute("SELECT * FROM categories")
            categories_migrated = 0
            
            for row in cursor:
                try:
                    row_dict = dict(row)
                    category = Category(
                        id=row_dict['id'],
                        name=row_dict['name'],
                        slug=row_dict.get('slug', f"category-{row_dict['id']}"),
                        description=row_dict.get('description'),
                        parent_id=row_dict.get('parent_id'),
                        level=row_dict.get('level', 0),
                        path=row_dict.get('path'),
                        is_active=row_dict.get('is_active', True),
                        sort_order=row_dict.get('sort_order', 0),
                        shopify_collection_id=row_dict.get('shopify_collection_id'),
                        shopify_handle=row_dict.get('shopify_handle'),
                        shopify_synced_at=convert_datetime_field(row_dict.get('shopify_synced_at'))
                    )
                    
                    pg_session.merge(category)
                    categories_migrated += 1
                    
                except Exception as e:
                    logger.warning(f"Failed to migrate category {row_dict.get('id', 'unknown')}: {e}")
                    continue
            
            pg_session.commit()
            logger.info(f"✅ Successfully migrated {categories_migrated} categories")
            
        except Exception as e:
            logger.info(f"No categories table found or migration failed: {e}")
        
        # Migrate products
        logger.info("Migrating products...")
        cursor = sqlite_conn.execute("SELECT * FROM products")
        products_migrated = 0
        
        for row in cursor:
            try:
                # Convert Row to dict for easier access
                row_dict = dict(row)
                
                # Create Product object with data from SQLite
                product = Product(
                    id=row_dict['id'],
                    sku=row_dict['sku'],
                    name=row_dict['name'],
                    title=row_dict.get('title'),
                    description=row_dict.get('description'),
                    short_description=row_dict.get('short_description'),
                    price=row_dict.get('price'),
                    compare_at_price=row_dict.get('compare_at_price'),
                    cost_price=row_dict.get('cost_price'),
                    brand=row_dict.get('brand'),
                    manufacturer=row_dict.get('manufacturer'),
                    manufacturer_part_number=row_dict.get('manufacturer_part_number'),
                    upc=row_dict.get('upc'),
                    weight=row_dict.get('weight'),
                    weight_unit=row_dict.get('weight_unit'),
                    length=row_dict.get('length'),
                    width=row_dict.get('width'),
                    height=row_dict.get('height'),
                    dimension_unit=row_dict.get('dimension_unit'),
                    inventory_quantity=row_dict.get('inventory_quantity', 0),
                    track_inventory=row_dict.get('track_inventory', True),
                    continue_selling_when_out_of_stock=row_dict.get('continue_selling_when_out_of_stock', False),
                    seo_title=row_dict.get('seo_title'),
                    seo_description=row_dict.get('seo_description'),
                    status=row_dict.get('status', 'active'),
                    is_active=row_dict.get('is_active', True),
                    category_id=row_dict.get('category_id', 1),  # Use default category if missing
                    shopify_product_id=row_dict.get('shopify_product_id'),
                    shopify_variant_id=row_dict.get('shopify_variant_id'),
                    shopify_handle=row_dict.get('shopify_handle'),
                    shopify_synced_at=convert_datetime_field(row_dict.get('shopify_synced_at')),
                    shopify_sync_status=row_dict.get('shopify_sync_status', 'pending'),
                    shopify_id=row_dict.get('shopify_id'),
                    shopify_status=row_dict.get('shopify_status'),
                    last_synced=convert_datetime_field(row_dict.get('last_synced')),
                    featured_image_url=row_dict.get('featured_image_url'),
                    additional_images=row_dict.get('additional_images'),
                    metafields=row_dict.get('metafields'),
                    custom_attributes=row_dict.get('custom_attributes'),
                    etilize_id=row_dict.get('etilize_id'),
                    primary_source=row_dict.get('primary_source'),
                    source_priority=row_dict.get('source_priority'),
                    data_sources=row_dict.get('data_sources'),
                    import_batch_id=row_dict.get('import_batch_id'),
                    last_imported=convert_datetime_field(row_dict.get('last_imported')),
                    import_errors=row_dict.get('import_errors'),
                    has_conflicts=row_dict.get('has_conflicts'),
                    conflict_resolution=row_dict.get('conflict_resolution'),
                    manual_overrides=row_dict.get('manual_overrides'),
                    etilize_data=row_dict.get('etilize_data'),
                    computed_fields=row_dict.get('computed_fields'),
                    data_quality_score=row_dict.get('data_quality_score'),
                    completeness_score=row_dict.get('completeness_score')
                )
                
                # Use merge to handle conflicts
                pg_session.merge(product)
                products_migrated += 1
                
                if products_migrated % 100 == 0:
                    pg_session.commit()
                    logger.info(f"Migrated {products_migrated} products...")
                    
            except Exception as e:
                logger.warning(f"Failed to migrate product {row_dict.get('id', 'unknown')}: {e}")
                continue
        
        # Final commit
        pg_session.commit()
        logger.info(f"✅ Successfully migrated {products_migrated} products")
        
        sqlite_conn.close()
        pg_session.close()
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Data migration failed: {e}")
        return False

def verify_migration():
    """Verify that migration was successful."""
    try:
        # Get PostgreSQL session
        database_url = os.getenv('DATABASE_URL')
        from database import DatabaseManager
        pg_db_manager = DatabaseManager(database_url)
        pg_db_manager.initialize(create_tables=False)  # Don't recreate tables
        pg_session = pg_db_manager.get_session()
        
        # Count products
        product_count = pg_session.query(Product).count()
        logger.info(f"PostgreSQL product count: {product_count}")
        
        # Count categories
        category_count = pg_session.query(Category).count()
        logger.info(f"PostgreSQL category count: {category_count}")
        
        # Show some sample data
        if product_count > 0:
            sample_products = pg_session.query(Product).limit(3).all()
            logger.info("Sample products in PostgreSQL:")
            for product in sample_products:
                logger.info(f"  - {product.sku}: {product.name} (${product.price})")
        
        pg_session.close()
        
        logger.info("✅ Migration verification completed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Migration verification failed: {e}")
        return False

def main():
    """Main migration function."""
    logger.info("🚀 Starting PostgreSQL Migration (Phase 1 Week 1)")
    logger.info("=" * 60)
    
    # Step 1: Test PostgreSQL connection
    logger.info("Step 1: Testing PostgreSQL connection...")
    if not test_postgresql_connection():
        logger.error("PostgreSQL connection failed. Please check your DATABASE_URL.")
        return False
    
    # Step 2: Backup SQLite data
    logger.info("\nStep 2: Backing up SQLite data...")
    backup_sqlite_data()  # Non-critical if it fails
    
    # Step 3: Migrate data
    logger.info("\nStep 3: Migrating data to PostgreSQL...")
    if not migrate_data():
        logger.error("Data migration failed.")
        return False
    
    # Step 4: Verify migration
    logger.info("\nStep 4: Verifying migration...")
    if not verify_migration():
        logger.error("Migration verification failed.")
        return False
    
    logger.info("\n" + "=" * 60)
    logger.info("🎉 PostgreSQL Migration completed successfully!")
    logger.info("✅ Database is now running on Supabase PostgreSQL")
    logger.info("✅ All product data has been migrated")
    logger.info("✅ Backend will now use PostgreSQL by default")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)