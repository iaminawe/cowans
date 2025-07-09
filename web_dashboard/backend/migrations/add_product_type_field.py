#!/usr/bin/env python3
"""
Add product_type field to products table
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
backend_path = project_root / 'web_dashboard' / 'backend'
sys.path.insert(0, str(backend_path))

from database import init_database
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_product_type_field():
    """Add product_type field to products table if it doesn't exist."""
    try:
        # Initialize database
        init_database(create_tables=False)
        
        from database import db_session_scope
        
        with db_session_scope() as session:
            # Check if column already exists
            check_query = """
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'products' 
                AND column_name = 'product_type'
            """
            
            result = session.execute(text(check_query))
            exists = result.fetchone() is not None
            
            if exists:
                logger.info("product_type column already exists in products table")
                return
            
            # Add the column
            logger.info("Adding product_type column to products table...")
            alter_query = """
                ALTER TABLE products 
                ADD COLUMN product_type VARCHAR(255)
            """
            session.execute(text(alter_query))
            
            # Create index
            logger.info("Creating index on product_type...")
            index_query = """
                CREATE INDEX idx_product_type ON products(product_type)
            """
            session.execute(text(index_query))
            
            session.commit()
            logger.info("Successfully added product_type field to products table")
            
    except Exception as e:
        logger.error(f"Error adding product_type field: {str(e)}")
        raise

if __name__ == '__main__':
    add_product_type_field()