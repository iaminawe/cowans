#!/usr/bin/env python3
"""Test the complete ultra-fast update with all three settings"""

import sys
sys.path.append('scripts/shopify')
from shopify_product_manager import ShopifyProductManager

shop_url = 'e19833-4.myshopify.com'
access_token = 'YOUR_SHOPIFY_ACCESS_TOKEN'  # Replace with your actual token

manager = ShopifyProductManager(shop_url, access_token, debug=True)

# Test with a product that should be published (from stocked list)
test_handle = 'acco-paper-clip-dispenser-72351'

print(f"Testing complete ultra-fast update for: {test_handle}")
print("This product should be PUBLISHED (it's in the stocked list)")
print("\nExpected results:")
print("  ✓ Published to Online Store")
print("  ✓ Inventory policy: CONTINUE")
print("  ✓ Track quantity: True")

# Run ultra-fast update
success = manager.ultra_fast_update(test_handle, published=True, inventory_policy='CONTINUE')

if success:
    print("\n✅ Ultra-fast update successful!")
    
    # Now check if all settings were applied
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
              id
              inventoryPolicy
              inventoryItem {
                id
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
        print(f"\n📊 Product Status After Update:")
        print(f"  Title: {product['title']}")
        print(f"  Status: {product['status']}")
        
        print(f"\n  📢 Sales Channels:")
        for pub in product['resourcePublications']['edges']:
            node = pub['node']
            status = '✅' if node['isPublished'] else '❌'
            print(f"    {status} {node['publication']['name']}")
        
        if product['variants']['edges']:
            variant = product['variants']['edges'][0]['node']
            inventory_item = variant.get('inventoryItem', {})
            
            print(f"\n  📦 Inventory Settings:")
            print(f"    Inventory Policy: {variant['inventoryPolicy']} {'✅' if variant['inventoryPolicy'] == 'CONTINUE' else '❌'}")
            print(f"    Track Quantity: {inventory_item.get('tracked', 'N/A')} {'✅' if inventory_item.get('tracked') else '❌'}")
            
            print(f"\n  🆔 IDs (for debugging):")
            print(f"    Product ID: {product['id']}")
            print(f"    Variant ID: {variant['id']}")
            print(f"    Inventory Item ID: {inventory_item.get('id', 'N/A')}")
else:
    print("\n❌ Ultra-fast update failed!")
    print("Check if the product exists in Shopify")