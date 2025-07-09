#!/usr/bin/env python3
"""Quick check of current categories and product types in the system."""

import os
import sys
import json
from collections import Counter

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from database import db_session_scope
from models import Product, Category, Collection
from scripts.shopify.shopify_base import ShopifyAPIBase
from sqlalchemy import func

def check_current_state():
    """Check current categories and product types."""
    
    print("\n🔍 CURRENT SYSTEM STATE")
    print("="*60)
    
    with db_session_scope() as session:
        # Check existing categories
        categories = session.query(Category).all()
        print(f"\n📁 Existing Categories: {len(categories)}")
        for cat in categories[:10]:
            print(f"  - {cat.name} (ID: {cat.id}, Products: {len(cat.products)})")
        
        # Check products with product_type
        products_with_type = session.query(
            func.json_extract(Product.custom_attributes, '$.product_type').label('product_type'),
            func.count(Product.id).label('count')
        ).group_by('product_type').all()
        
        print(f"\n📦 Product Types in Database:")
        for product_type, count in products_with_type[:20]:
            if product_type:
                print(f"  - {product_type}: {count} products")
        
        # Check products with tags
        products_with_tags = session.query(Product).filter(
            func.json_extract(Product.custom_attributes, '$.tags') != None
        ).limit(10).all()
        
        print(f"\n🏷️ Sample Products with Tags:")
        for product in products_with_tags:
            tags = product.custom_attributes.get('tags', []) if product.custom_attributes else []
            if tags:
                print(f"  - {product.name}: {', '.join(tags[:5])}")
    
    # Quick Shopify check
    print("\n🛍️ Quick Shopify Check:")
    try:
        shop_url = os.getenv('SHOPIFY_SHOP_URL')
        access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
        
        if not shop_url or not access_token:
            print("  ❌ Shopify credentials not configured")
            return
        
        client = ShopifyAPIBase(shop_url, access_token, debug=False)
        
        # Get a small sample of products
        query = """
        query {
            products(first: 10) {
                nodes {
                    title
                    productType
                    vendor
                    tags
                }
            }
        }
        """
        
        result = client.execute_graphql(query)
        if 'data' in result:
            products = result['data']['products']['nodes']
            print(f"  ✅ Connected to Shopify - Sample products:")
            for p in products[:5]:
                print(f"    - {p['title']}")
                print(f"      Type: {p['productType']}, Vendor: {p['vendor']}")
                if p['tags']:
                    print(f"      Tags: {', '.join(p['tags'][:3])}")
    except Exception as e:
        print(f"  ❌ Error connecting to Shopify: {str(e)}")

if __name__ == "__main__":
    check_current_state()