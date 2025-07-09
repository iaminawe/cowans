#!/usr/bin/env python3
"""
Check the status of products to verify if updates were applied
"""

import sys
import csv
from shopify_product_manager import ShopifyProductManager

# GraphQL query to check product details
CHECK_PRODUCT_QUERY = """
query checkProduct($handle: String!) {
  productByHandle(handle: $handle) {
    id
    handle
    title
    publishedAt
    status
    publishedOnCurrentPublication
    variants(first: 1) {
      edges {
        node {
          id
          inventoryPolicy
          inventoryQuantity
          inventoryItem {
            tracked
          }
        }
      }
    }
  }
}
"""

def check_products(csv_file: str, shop_url: str, access_token: str, sample_size: int = 10):
    """Check a sample of products to see their current status."""
    
    # Initialize manager
    manager = ShopifyProductManager(shop_url, access_token, debug=True)
    
    # Read CSV to get product handles and expected status
    stocked_products = []
    unstocked_products = []
    
    with open(csv_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i >= sample_size * 2:  # Get enough samples
                break
            
            handle = row.get('url handle', '').strip()
            published = row.get('published', '').strip().lower() == 'true'
            
            if published and len(stocked_products) < sample_size:
                stocked_products.append({
                    'handle': handle,
                    'sku': row.get('newsku', ''),
                    'expected_published': True
                })
            elif not published and len(unstocked_products) < sample_size:
                unstocked_products.append({
                    'handle': handle,
                    'sku': row.get('newsku', ''),
                    'expected_published': False
                })
    
    print("Checking products...\n")
    
    # Check stocked products (should be published)
    print("=== STOCKED PRODUCTS (Should be published) ===")
    for product in stocked_products[:5]:
        check_single_product(manager, product)
    
    print("\n=== UNSTOCKED PRODUCTS (Should NOT be published) ===")
    for product in unstocked_products[:5]:
        check_single_product(manager, product)

def check_single_product(manager, product_info):
    """Check a single product's status."""
    handle = product_info['handle']
    sku = product_info['sku']
    expected = product_info['expected_published']
    
    try:
        result = manager.execute_graphql(CHECK_PRODUCT_QUERY, {"handle": handle})
        
        if result and 'data' in result and result['data']['productByHandle']:
            product = result['data']['productByHandle']
            variant = product['variants']['edges'][0]['node'] if product['variants']['edges'] else None
            
            print(f"\n{sku} - {handle}")
            print(f"  Expected published: {expected}")
            print(f"  Actual status: {product.get('status', 'N/A')}")
            print(f"  Published at: {product.get('publishedAt', 'None')}")
            print(f"  Published on current: {product.get('publishedOnCurrentPublication', 'N/A')}")
            
            if variant:
                print(f"  Inventory policy: {variant.get('inventoryPolicy', 'N/A')}")
                inventory_item = variant.get('inventoryItem', {})
                print(f"  Inventory tracked: {inventory_item.get('tracked', 'N/A') if inventory_item else 'N/A'}")
            else:
                print("  No variant found!")
        else:
            print(f"\n{sku} - {handle}: NOT FOUND")
    except Exception as e:
        print(f"\n{sku} - {handle}: ERROR - {str(e)}")

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python check_product_status.py <csv_file> <shop_url> <access_token>")
        sys.exit(1)
    
    csv_file = sys.argv[1]
    shop_url = sys.argv[2]
    access_token = sys.argv[3]
    
    check_products(csv_file, shop_url, access_token)