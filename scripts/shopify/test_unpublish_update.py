#!/usr/bin/env python3
"""Test unpublishing a product"""

import sys
sys.path.append('scripts/shopify')
from shopify_product_manager import ShopifyProductManager

shop_url = 'e19833-4.myshopify.com'
access_token = 'YOUR_SHOPIFY_ACCESS_TOKEN'  # Replace with your actual token

manager = ShopifyProductManager(shop_url, access_token)

# Test with a product that should NOT be published
test_handle = 'basics-ergo-boss-chair-2869-3-bl20-bl20-blk-g6-je-st'

print(f"Testing unpublish for: {test_handle}")
print("This product should be UNPUBLISHED (not in stocked list)")

# Run ultra-fast update to unpublish
success = manager.ultra_fast_update(test_handle, published=False, inventory_policy='CONTINUE')

if success:
    print("\n✅ Ultra-fast update successful!")
    
    # Check the result
    query = """
    query checkProduct($handle: String!) {
      productByHandle(handle: $handle) {
        title
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
              inventoryItem {
                tracked
              }
            }
          }
        }
      }
    }
    """
    
    result = manager.execute_graphql(query, {'handle': test_handle})
    if result and 'data' in result and result['data']['productByHandle']:
        product = result['data']['productByHandle']
        print(f"\nProduct: {product['title']}")
        
        print(f"\nSales Channels:")
        pubs = product['resourcePublications']['edges']
        if pubs:
            for pub in pubs:
                node = pub['node']
                status = '✅ Published' if node['isPublished'] else '❌ Not Published'
                print(f"  {node['publication']['name']}: {status}")
        else:
            print("  ❌ Not published to any channels")
        
        if product['variants']['edges']:
            variant = product['variants']['edges'][0]['node']
            print(f"\nInventory Policy: {variant['inventoryPolicy']}")
            print(f"Track Quantity: {variant['inventoryItem']['tracked']}")
else:
    print("\n❌ Update failed!")