#!/usr/bin/env python3
"""Apply collections tables migration directly to the database."""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
import logging
from config import config
import os

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def apply_migration():
    """Apply the collections migration to the database."""
    try:
        # Use SQLite database directly
        db_path = os.path.join(os.path.dirname(__file__), 'database.db')
        database_url = f'sqlite:///{db_path}'
        
        # Create engine
        engine = create_engine(database_url)
        
        with engine.connect() as conn:
            # Start transaction
            trans = conn.begin()
            
            try:
                # Check if collections table already exists
                result = conn.execute(text(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='collections'"
                ))
                if result.fetchone():
                    logger.info("Collections table already exists, skipping migration")
                    return
                
                logger.info("Creating collections table...")
                
                # Create collections table
                conn.execute(text("""
                    CREATE TABLE collections (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name VARCHAR(255) NOT NULL,
                        handle VARCHAR(255) NOT NULL UNIQUE,
                        description TEXT,
                        sort_order VARCHAR(50) DEFAULT 'manual',
                        status VARCHAR(20) DEFAULT 'draft',
                        is_visible BOOLEAN DEFAULT 1,
                        rules_type VARCHAR(20) DEFAULT 'manual',
                        rules_conditions JSON,
                        disjunctive BOOLEAN DEFAULT 0,
                        image_url VARCHAR(1000),
                        image_alt_text VARCHAR(255),
                        icon_id INTEGER,
                        seo_title VARCHAR(255),
                        seo_description TEXT,
                        products_count INTEGER DEFAULT 0,
                        template_suffix VARCHAR(100),
                        published_at DATETIME,
                        published_scope VARCHAR(50) DEFAULT 'global',
                        meta_data JSON,
                        shopify_collection_id VARCHAR(50) UNIQUE,
                        shopify_handle VARCHAR(255),
                        shopify_synced_at DATETIME,
                        shopify_sync_status VARCHAR(20) DEFAULT 'pending',
                        created_by INTEGER NOT NULL,
                        updated_by INTEGER,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (icon_id) REFERENCES icons(id),
                        FOREIGN KEY (created_by) REFERENCES users(id),
                        FOREIGN KEY (updated_by) REFERENCES users(id)
                    )
                """))
                
                # Create indexes for collections
                conn.execute(text("CREATE INDEX idx_collection_handle ON collections(handle)"))
                conn.execute(text("CREATE INDEX idx_collection_status ON collections(status)"))
                conn.execute(text("CREATE INDEX idx_collection_shopify ON collections(shopify_collection_id)"))
                conn.execute(text("CREATE INDEX idx_collection_created_by ON collections(created_by)"))
                
                logger.info("Creating product_collections table...")
                
                # Create product_collections table
                conn.execute(text("""
                    CREATE TABLE product_collections (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        product_id INTEGER NOT NULL,
                        collection_id INTEGER NOT NULL,
                        position INTEGER DEFAULT 0,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (product_id) REFERENCES products(id),
                        FOREIGN KEY (collection_id) REFERENCES collections(id),
                        UNIQUE(product_id, collection_id)
                    )
                """))
                
                # Create indexes for product_collections
                conn.execute(text("CREATE INDEX idx_product_collection_product ON product_collections(product_id)"))
                conn.execute(text("CREATE INDEX idx_product_collection_collection ON product_collections(collection_id)"))
                conn.execute(text("CREATE INDEX idx_product_collection_position ON product_collections(position)"))
                
                # Check if product_type column exists in products table
                result = conn.execute(text(
                    "PRAGMA table_info(products)"
                ))
                columns = [row[1] for row in result]
                
                if 'product_type' not in columns:
                    logger.info("Adding product_type column to products table...")
                    conn.execute(text("""
                        ALTER TABLE products ADD COLUMN product_type VARCHAR(255)
                    """))
                    conn.execute(text("CREATE INDEX idx_product_type ON products(product_type)"))
                
                # Commit transaction
                trans.commit()
                logger.info("Migration completed successfully!")
                
            except Exception as e:
                trans.rollback()
                logger.error(f"Error during migration: {str(e)}")
                raise
                
    except SQLAlchemyError as e:
        logger.error(f"Database error: {str(e)}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    logger.info("Starting collections migration...")
    apply_migration()
    logger.info("Migration process completed.")