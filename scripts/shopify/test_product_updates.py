#!/usr/bin/env python3
"""Test if product updates were applied correctly"""

import sys
sys.path.append('scripts/shopify')
from shopify_product_manager import ShopifyProductManager

# Test with products we know exist
test_handles = [
    'basics-obusforme-elite-chair-2777-3-fu85-fu85-blk-g5-je-kd',
    'basics-ergo-boss-chair-2869-3-bl20-bl20-blk-g6-je-st',
    'basics-ergo-boss-chair-2869-3-bl24-bl24-blk-g6-je-st'
]

shop_url = 'e19833-4.myshopify.com'
access_token = 'YOUR_SHOPIFY_ACCESS_TOKEN'  # Replace with your actual token

manager = ShopifyProductManager(shop_url, access_token, debug=True)

# Simplified query
query = """
query checkProduct($handle: String!) {
  productByHandle(handle: $handle) {
    id
    handle
    title
    publishedAt
    status
    variants(first: 1) {
      edges {
        node {
          id
          inventoryPolicy
        }
      }
    }
  }
}
"""

print("Checking products that should have been updated...\n")

for handle in test_handles:
    try:
        result = manager.execute_graphql(query, {'handle': handle})
        
        if result and 'data' in result and result['data']['productByHandle']:
            product = result['data']['productByHandle']
            print(f"✓ Found: {handle}")
            print(f"  Title: {product.get('title', 'N/A')}")
            print(f"  Status: {product.get('status', 'N/A')}")
            print(f"  Published: {'Yes' if product.get('publishedAt') else 'No'}")
            
            variant = product['variants']['edges'][0]['node'] if product['variants']['edges'] else None
            if variant:
                print(f"  Inventory Policy: {variant.get('inventoryPolicy', 'N/A')}")
            print()
        else:
            print(f"✗ Not found: {handle}\n")
            
    except Exception as e:
        print(f"✗ Error checking {handle}: {str(e)}\n")