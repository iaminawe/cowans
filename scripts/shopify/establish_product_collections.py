#!/usr/bin/env python3
"""
Establish product-collection associations based on product types and tags.
This script will:
1. Find all products with product types
2. Find or create collections for each product type
3. Associate products with their appropriate collections
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
from models import Product, Collection, ProductCollection
from repositories.collection_repository import CollectionRepository
from repositories.product_repository import ProductRepository
from sqlalchemy import func

# Initialize database
init_database(create_tables=False)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main function to establish product-collection associations."""
    logger.info("Starting product-collection association process...")
    
    stats = {
        'products_processed': 0,
        'collections_created': 0,
        'associations_created': 0,
        'products_with_types': 0,
        'products_without_types': 0,
        'errors': []
    }
    
    try:
        with db_session_scope() as session:
            # Get all products with their types
            products = session.query(Product).all()
            logger.info(f"Found {len(products)} total products")
            
            # Group products by type
            product_types = {}
            for product in products:
                if product.product_type:
                    stats['products_with_types'] += 1
                    if product.product_type not in product_types:
                        product_types[product.product_type] = []
                    product_types[product.product_type].append(product)
                else:
                    stats['products_without_types'] += 1
            
            logger.info(f"Found {len(product_types)} unique product types")
            logger.info(f"Products with types: {stats['products_with_types']}")
            logger.info(f"Products without types: {stats['products_without_types']}")
            
            # Process each product type
            repo = CollectionRepository(session)
            
            for product_type, products_list in product_types.items():
                logger.info(f"\nProcessing product type: {product_type} ({len(products_list)} products)")
                
                try:
                    # Check if collection exists for this product type
                    # First try to find by name (simpler approach)
                    collection_name = f"{product_type} Collection"
                    existing_collection = session.query(Collection).filter(
                        Collection.name == collection_name
                    ).first()
                    
                    if existing_collection:
                        logger.info(f"  Found existing collection: {existing_collection.name}")
                        collection = existing_collection
                    else:
                        # Create new collection
                        logger.info(f"  Creating new collection for {product_type}")
                        
                        # Generate collection name and description
                        collection_name = f"{product_type} Collection"
                        description = f"Browse our selection of {product_type.lower()} products"
                        
                        # Create more appealing names for common types
                        name_mappings = {
                            'pen': 'Premium Writing Instruments',
                            'paper': 'Paper & Stationery Essentials',
                            'folder': 'Organization & Filing Solutions',
                            'binder': 'Organization & Filing Solutions',
                            'ink': 'Ink & Toner Supplies',
                            'printer': 'Printing Solutions',
                            'office': 'Office Essentials'
                        }
                        
                        for key, mapped_name in name_mappings.items():
                            if key in product_type.lower():
                                collection_name = mapped_name
                                break
                        
                        collection_data = {
                            'name': collection_name,
                            'handle': collection_name.lower().replace(' ', '-').replace('&', 'and'),
                            'description': description,
                            'rules_type': 'automatic',
                            'rules_conditions': [{
                                'field': 'product_type',
                                'operator': 'equals',
                                'value': product_type
                            }],
                            'disjunctive': False,
                            'status': 'active',
                            'created_by': 1,  # System user
                            'updated_by': 1   # System user
                        }
                        
                        # Create collection directly
                        collection = Collection(**collection_data)
                        session.add(collection)
                        session.flush()  # Get the ID
                        stats['collections_created'] += 1
                        logger.info(f"  Created collection: {collection.name}")
                    
                    # Update automatic collection to ensure all products are linked
                    logger.info(f"  Updating automatic collection associations...")
                    repo.update_automatic_collection(collection.id)
                    
                    # Get count of products in collection
                    product_count = session.query(func.count(ProductCollection.product_id))\
                        .filter(ProductCollection.collection_id == collection.id)\
                        .scalar()
                    
                    logger.info(f"  Collection now has {product_count} products")
                    stats['associations_created'] += product_count
                    
                except Exception as e:
                    error_msg = f"Error processing product type {product_type}: {str(e)}"
                    logger.error(error_msg)
                    stats['errors'].append(error_msg)
                
                stats['products_processed'] += len(products_list)
            
            # Handle products without types using tags
            if stats['products_without_types'] > 0:
                logger.info("\nProcessing products without types using tags...")
                products_without_types = [p for p in products if not p.product_type]
                
                for product in products_without_types[:100]:  # Process first 100 as example
                    if product.tags:
                        # Use first meaningful tag as pseudo product type
                        tags = [t.strip() for t in product.tags.split(',')]
                        meaningful_tags = [t for t in tags if len(t) > 3 and t.lower() not in ['new', 'sale', 'featured']]
                        
                        if meaningful_tags:
                            logger.info(f"  Product {product.sku} has tags: {meaningful_tags[:3]}")
                            # Could create collections based on tags here
            
            session.commit()
            
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        stats['errors'].append(f"Fatal error: {str(e)}")
    
    # Print summary
    logger.info("\n" + "="*60)
    logger.info("PRODUCT-COLLECTION ASSOCIATION SUMMARY")
    logger.info("="*60)
    logger.info(f"Products processed: {stats['products_processed']}")
    logger.info(f"Products with types: {stats['products_with_types']}")
    logger.info(f"Products without types: {stats['products_without_types']}")
    logger.info(f"Collections created: {stats['collections_created']}")
    logger.info(f"Total associations: {stats['associations_created']}")
    logger.info(f"Errors: {len(stats['errors'])}")
    
    if stats['errors']:
        logger.info("\nErrors encountered:")
        for error in stats['errors']:
            logger.error(f"  - {error}")
    
    # Save report
    report_file = f"product_collection_association_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w') as f:
        json.dump(stats, f, indent=2)
    logger.info(f"\nReport saved to: {report_file}")


if __name__ == '__main__':
    main()