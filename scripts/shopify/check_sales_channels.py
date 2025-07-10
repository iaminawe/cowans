#!/usr/bin/env python3
"""Check available sales channels and publication status"""

import sys
sys.path.append('scripts/shopify')
from shopify_product_manager import ShopifyProductManager

shop_url = 'e19833-4.myshopify.com'
access_token = 'YOUR_SHOPIFY_ACCESS_TOKEN'  # Replace with your actual token

manager = ShopifyProductManager(shop_url, access_token)

# Query to get publications (sales channels)
publications_query = """
query {
  publications(first: 10) {
    edges {
      node {
        id
        name
        supportsFuturePublishing
      }
    }
  }
}
"""

# Query to check product publication status
product_query = """
query checkProduct($id: ID!) {
  product(id: $id) {
    id
    handle
    publishedAt
    resourcePublications(first: 10) {
      edges {
        node {
          publication {
            id
            name
          }
          isPublished
        }
      }
    }
  }
}
"""

print("=== Available Sales Channels ===")
result = manager.execute_graphql(publications_query, {})
if result and 'data' in result:
    publications = result['data']['publications']['edges']
    for pub in publications:
        node = pub['node']
        print(f"ID: {node['id']}")
        print(f"Name: {node['name']}")
        print(f"Supports Future Publishing: {node['supportsFuturePublishing']}")
        print()

# Check a specific product
print("\n=== Checking Product Publication Status ===")
test_product_id = "gid://shopify/Product/7274675634222"  # This needs to be a real product ID

# First get a product ID
handle_query = """
query {
  productByHandle(handle: "basics-obusforme-elite-chair-2777-3-fu85-fu85-blk-g5-je-kd") {
    id
  }
}
"""

result = manager.execute_graphql(handle_query, {})
if result and 'data' in result and result['data']['productByHandle']:
    product_id = result['data']['productByHandle']['id']
    
    # Now check its publication status
    result = manager.execute_graphql(product_query, {'id': product_id})
    if result and 'data' in result:
        product = result['data']['product']
        print(f"Product: {product['handle']}")
        print(f"Published At: {product['publishedAt']}")
        print(f"\nPublication Status:")
        
        pubs = product['resourcePublications']['edges']
        if pubs:
            for pub in pubs:
                node = pub['node']
                print(f"  - {node['publication']['name']}: {'Published' if node['isPublished'] else 'Not Published'}")
        else:
            print("  No publications found")