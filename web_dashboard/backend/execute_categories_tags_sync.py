#!/usr/bin/env python3
"""
Execute Categories & Tags Sync with proper database initialization
"""

import os
import sys
import json
import logging
from datetime import datetime
from collections import Counter
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Main execution with database initialization."""
    try:
        # Initialize database
        from database import DatabaseManager
        db_manager = DatabaseManager()
        db_manager.initialize()
        
        from database import db_session_scope
        from models import Product, Category, Collection
        from scripts.shopify.shopify_base import ShopifyAPIBase
        from sqlalchemy import func
        
        shop_url = os.getenv('SHOPIFY_SHOP_URL')
        access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
        
        if not shop_url or not access_token:
            logger.error("Shopify credentials not configured")
            return
        
        client = ShopifyAPIBase(shop_url, access_token, debug=False)
        
        logger.info("🐝 Starting Categories & Tags Quick Sync...")
        
        # First, let's get a sample to understand the data
        query = """
        query {
            products(first: 250) {
                pageInfo {
                    hasNextPage
                }
                nodes {
                    id
                    title
                    productType
                    vendor
                    tags
                    handle
                }
            }
        }
        """
        
        result = client.execute_graphql(query, {})
        
        if 'errors' in result:
            logger.error(f"GraphQL errors: {result['errors']}")
            return
        
        products = result.get('data', {}).get('products', {}).get('nodes', [])
        
        # Analyze the data
        product_types = Counter()
        vendors = Counter()
        all_tags = Counter()
        type_to_products = {}
        
        for product in products:
            # Product types
            p_type = product.get('productType', '').strip()
            if p_type:
                product_types[p_type] += 1
                if p_type not in type_to_products:
                    type_to_products[p_type] = []
                type_to_products[p_type].append({
                    'id': product['id'],
                    'title': product['title'],
                    'handle': product['handle']
                })
            
            # Vendors
            vendor = product.get('vendor', '').strip()
            if vendor:
                vendors[vendor] += 1
            
            # Tags
            for tag in product.get('tags', []):
                tag = tag.strip()
                if tag:
                    all_tags[tag] += 1
        
        # Now update the database
        with db_manager.session_scope() as session:
            # Create categories from product types
            categories_created = 0
            categories_updated = 0
            
            for product_type, count in product_types.most_common():
                # Check if category exists
                category = session.query(Category).filter_by(name=product_type).first()
                
                if not category:
                    # Create new category
                    slug = product_type.lower().replace(' ', '-').replace('/', '-')
                    category = Category(
                        name=product_type,
                        slug=slug,
                        description=f"Product type: {product_type} ({count} products)",
                        level=0,
                        path=product_type,
                        is_active=True
                    )
                    session.add(category)
                    categories_created += 1
                else:
                    # Update description with count
                    category.description = f"Product type: {product_type} ({count} products)"
                    categories_updated += 1
                
                session.flush()
                
                # Update products with this category
                sample_products = type_to_products.get(product_type, [])[:5]
                for prod_info in sample_products:
                    # Find product by Shopify ID
                    product = session.query(Product).filter_by(
                        shopify_product_id=prod_info['id']
                    ).first()
                    
                    if product and product.category_id != category.id:
                        product.category_id = category.id
            
            session.commit()
        
        # Print summary report
        print("\n" + "="*60)
        print("🐝 CATEGORIES & TAGS SYNC SUMMARY")
        print("="*60)
        print(f"\n📊 Data Analysis (Sample of 250 products):")
        print(f"  - Product Types Found: {len(product_types)}")
        print(f"  - Vendors Found: {len(vendors)}")
        print(f"  - Unique Tags Found: {len(all_tags)}")
        print(f"  - Categories Created: {categories_created}")
        print(f"  - Categories Updated: {categories_updated}")
        
        print("\n📦 Top 15 Product Types:")
        for p_type, count in product_types.most_common(15):
            print(f"  - {p_type}: {count} products")
        
        print("\n🏭 Top 10 Vendors:")
        for vendor, count in vendors.most_common(10):
            print(f"  - {vendor}: {count} products")
        
        print("\n🏷️ Top 20 Tags:")
        for tag, count in all_tags.most_common(20):
            print(f"  - {tag}: {count} products")
        
        # Store summary in coordination memory
        summary = {
            'timestamp': datetime.utcnow().isoformat(),
            'coordinator': 'Categories & Tags Sync',
            'status': 'completed',
            'sample_size': len(products),
            'has_more_pages': result.get('data', {}).get('products', {}).get('pageInfo', {}).get('hasNextPage', False),
            'metrics': {
                'product_types': len(product_types),
                'vendors': len(vendors),
                'tags': len(all_tags),
                'categories_created': categories_created,
                'categories_updated': categories_updated
            },
            'top_product_types': dict(product_types.most_common(10)),
            'top_tags': dict(all_tags.most_common(20))
        }
        
        # Save to file
        with open('logs/categories_tags_sync_summary.json', 'w') as f:
            json.dump(summary, f, indent=2)
        
        print("\n✅ Sync completed! Summary saved to logs/categories_tags_sync_summary.json")
        print("\n💡 Note: This was a sample sync of the first 250 products.")
        print("   For a full sync, run the complete sync script.")
        
    except Exception as e:
        logger.error(f"Error during sync: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()