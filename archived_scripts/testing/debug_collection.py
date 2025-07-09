#!/usr/bin/env python3
"""
Debug a specific collection to understand the association problem.
"""

import os
import sys
import csv

try:
    from scripts.shopify.shopify_base import ShopifyAPIBase
except ImportError:
    sys.path.append('scripts/shopify')
    from shopify_base import ShopifyAPIBase

# Check if product exists
CHECK_PRODUCT_QUERY = """
query checkProduct($handle: String!) {
  productByHandle(handle: $handle) {
    id
    handle
    title
    collections(first: 10) {
      edges {
        node {
          id
          handle
        }
      }
    }
  }
}
"""

# Check collection
CHECK_COLLECTION_QUERY = """
query checkCollection($handle: String!) {
  collectionByHandle(handle: $handle) {
    id
    handle
    title
    productsCount {
      count
    }
    products(first: 10) {
      edges {
        node {
          id
          handle
          title
        }
      }
    }
  }
}
"""

class DebugTool(ShopifyAPIBase):
    def __init__(self, shop_url: str, access_token: str):
        super().__init__(shop_url, access_token, True)
    
    def debug_collection(self, collection_handle: str):
        print(f"🔍 Debugging collection: {collection_handle}")
        
        # Check collection exists
        result = self.execute_graphql(CHECK_COLLECTION_QUERY, {'handle': collection_handle})
        collection = result.get('data', {}).get('collectionByHandle')
        
        if not collection:
            print(f"❌ Collection '{collection_handle}' not found!")
            return
        
        print(f"✅ Collection found: {collection['title']}")
        print(f"   ID: {collection['id']}")
        print(f"   Current products: {collection['productsCount']['count']}")
        
        # Show current products
        current_products = collection.get('products', {}).get('edges', [])
        if current_products:
            print(f"   First few products:")
            for edge in current_products:
                product = edge['node']
                print(f"     - {product['handle']} ({product['title'][:50]})")
        
        # Check expected products from CSV
        expected_products = []
        with open('product_collection_associations.csv', 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['collection_handle'] == collection_handle:
                    expected_products.append(row['product_handle'])
        
        print(f"\n📋 Expected {len(expected_products)} products from associations")
        
        # Check if first few expected products exist
        for i, product_handle in enumerate(expected_products[:5]):
            result = self.execute_graphql(CHECK_PRODUCT_QUERY, {'handle': product_handle})
            product = result.get('data', {}).get('productByHandle')
            
            if product:
                # Check if already in any collections
                current_collections = product.get('collections', {}).get('edges', [])
                collection_handles = [edge['node']['handle'] for edge in current_collections]
                
                print(f"   ✅ {product_handle} exists")
                print(f"      ID: {product['id']}")
                if collection_handles:
                    print(f"      In collections: {', '.join(collection_handles[:3])}")
                else:
                    print(f"      Not in any collections")
            else:
                print(f"   ❌ {product_handle} NOT FOUND")

if __name__ == '__main__':
    if len(sys.argv) < 4:
        print("Usage: python debug_collection.py <shop_url> <access_token> <collection_handle>")
        sys.exit(1)
    
    shop_url = sys.argv[1]
    access_token = sys.argv[2] 
    collection_handle = sys.argv[3]
    
    debug = DebugTool(shop_url, access_token)
    debug.debug_collection(collection_handle)