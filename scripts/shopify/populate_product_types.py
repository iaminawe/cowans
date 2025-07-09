#!/usr/bin/env python3
"""
Populate product_type field for existing products based on tags, categories, or other data.
"""

import os
import sys
from pathlib import Path
import logging
from datetime import datetime
import json

# Add project root to path
project_root = Path(__file__).parent.parent.parent
backend_path = project_root / 'web_dashboard' / 'backend'
sys.path.insert(0, str(backend_path))
sys.path.insert(0, str(project_root))

from database import db_session_scope, init_database
from models import Product, Category
from sqlalchemy import func

# Initialize database
init_database(create_tables=False)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def extract_product_type_from_tags(tags):
    """Extract product type from tags."""
    if not tags:
        return None
    
    # Split tags
    tag_list = [t.strip() for t in tags.split(',')]
    
    # Priority tags that indicate product type
    type_indicators = [
        'pens', 'markers', 'highlighters', 'pencils', 'writing instruments',
        'paper', 'notebooks', 'notepads', 'stationery',
        'folders', 'binders', 'filing', 'organization',
        'ink', 'toner', 'cartridges',
        'office supplies', 'office equipment',
        'furniture', 'chairs', 'desks',
        'printers', 'scanners', 'technology',
        'labels', 'labeling',
        'tape', 'adhesives',
        'staplers', 'fasteners'
    ]
    
    # Check for type indicators in tags
    for tag in tag_list:
        tag_lower = tag.lower()
        for indicator in type_indicators:
            if indicator in tag_lower:
                return tag.title()
    
    # If no specific type found, use first meaningful tag
    for tag in tag_list:
        if len(tag) > 3 and tag.lower() not in ['new', 'sale', 'featured', 'best seller']:
            return tag.title()
    
    return None


def main():
    """Main function to populate product types."""
    logger.info("Starting product type population process...")
    
    stats = {
        'total_products': 0,
        'updated_products': 0,
        'already_had_type': 0,
        'no_type_found': 0,
        'types_found': {}
    }
    
    try:
        with db_session_scope() as session:
            # Get all products
            products = session.query(Product).all()
            stats['total_products'] = len(products)
            logger.info(f"Found {len(products)} total products")
            
            for product in products:
                try:
                    # Skip if already has product type
                    if product.product_type:
                        stats['already_had_type'] += 1
                        continue
                    
                    # Try to extract from various sources
                    product_type = None
                    
                    # 1. Try from category name
                    if product.category and product.category.name:
                        product_type = product.category.name
                    
                    # 2. Try from tags
                    if not product_type and product.tags:
                        product_type = extract_product_type_from_tags(product.tags)
                    
                    # 3. Try from title keywords
                    if not product_type and product.name:
                        title_lower = product.name.lower()
                        if 'pen' in title_lower:
                            product_type = 'Pens'
                        elif 'pencil' in title_lower:
                            product_type = 'Pencils'
                        elif 'marker' in title_lower:
                            product_type = 'Markers'
                        elif 'paper' in title_lower:
                            product_type = 'Paper'
                        elif 'folder' in title_lower:
                            product_type = 'Folders'
                        elif 'binder' in title_lower:
                            product_type = 'Binders'
                        elif 'ink' in title_lower or 'toner' in title_lower:
                            product_type = 'Ink & Toner'
                        elif 'tape' in title_lower:
                            product_type = 'Tape & Adhesives'
                        elif 'stapl' in title_lower:
                            product_type = 'Staplers & Fasteners'
                    
                    # Update product if type found
                    if product_type:
                        product.product_type = product_type
                        stats['updated_products'] += 1
                        
                        # Track types
                        if product_type not in stats['types_found']:
                            stats['types_found'][product_type] = 0
                        stats['types_found'][product_type] += 1
                        
                        if stats['updated_products'] % 100 == 0:
                            logger.info(f"  Updated {stats['updated_products']} products...")
                    else:
                        stats['no_type_found'] += 1
                        if stats['no_type_found'] <= 10:
                            logger.warning(f"  No type found for: {product.sku} - {product.name}")
                    
                except Exception as e:
                    logger.error(f"Error processing product {product.sku}: {str(e)}")
            
            # Commit all changes
            session.commit()
            logger.info("All changes committed to database")
            
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
    
    # Print summary
    logger.info("\n" + "="*60)
    logger.info("PRODUCT TYPE POPULATION SUMMARY")
    logger.info("="*60)
    logger.info(f"Total products: {stats['total_products']}")
    logger.info(f"Already had type: {stats['already_had_type']}")
    logger.info(f"Updated products: {stats['updated_products']}")
    logger.info(f"No type found: {stats['no_type_found']}")
    logger.info(f"\nProduct types found: {len(stats['types_found'])}")
    
    # Sort types by count
    sorted_types = sorted(stats['types_found'].items(), key=lambda x: x[1], reverse=True)
    logger.info("\nTop 10 product types:")
    for product_type, count in sorted_types[:10]:
        logger.info(f"  {product_type}: {count} products")
    
    # Save report
    report_file = f"product_type_population_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w') as f:
        json.dump(stats, f, indent=2)
    logger.info(f"\nReport saved to: {report_file}")


if __name__ == '__main__':
    main()