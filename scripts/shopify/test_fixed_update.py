#!/usr/bin/env python3
"""Test the fixed ultra-fast update"""

import sys
sys.path.append('scripts/shopify')
from shopify_product_manager import ShopifyProductManager

shop_url = 'e19833-4.myshopify.com'
access_token = 'YOUR_SHOPIFY_ACCESS_TOKEN'  # Replace with your actual token

manager = ShopifyProductManager(shop_url, access_token, debug=True)

# Test with a product that should be published (from stocked list)
test_handle = 'acco-round-head-paper-fastener-71710'

print(f"Testing ultra-fast update for: {test_handle}")
print("This product should be PUBLISHED (it's in the stocked list)")

# Run ultra-fast update
success = manager.ultra_fast_update(test_handle, published=True, inventory_policy='CONTINUE')

if success:
    print("\n✅ Ultra-fast update successful!")
    
    # Now check if it worked
    query = """
    query checkProduct($handle: String!) {
      productByHandle(handle: $handle) {
        id
        handle
        title
        publishedAt
        status
        resourcePublications(first: 10) {
          edges {
            node {
              publication {
                name
              }
              isPublished
            }
          }
        }
        variants(first: 1) {
          edges {
            node {
              inventoryPolicy
            }
          }
        }
      }
    }
    """
    
    result = manager.execute_graphql(query, {'handle': test_handle})
    if result and 'data' in result and result['data']['productByHandle']:
        product = result['data']['productByHandle']
        print(f"\nProduct Status After Update:")
        print(f"  Title: {product['title']}")
        print(f"  Status: {product['status']}")
        print(f"  Published At: {product['publishedAt']}")
        
        print(f"\n  Sales Channels:")
        for pub in product['resourcePublications']['edges']:
            node = pub['node']
            print(f"    - {node['publication']['name']}: {'Published' if node['isPublished'] else 'Not Published'}")
        
        if product['variants']['edges']:
            variant = product['variants']['edges'][0]['node']
            print(f"\n  Inventory Policy: {variant['inventoryPolicy']}")
else:
    print("\n❌ Ultra-fast update failed!")