#!/usr/bin/env python
"""Test Shopify sync with limited data"""

import os
import sys
sys.path.append('.')
sys.path.append('../..')

from scripts.shopify.shopify_base import ShopifyAPIBase
from datetime import datetime
import json

def main():
    print(f'[{datetime.now()}] Starting Shopify sync test...')
    
    # Get credentials
    shop_url = os.getenv('SHOPIFY_SHOP_URL')
    access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
    
    if not shop_url or not access_token:
        print('ERROR: Missing Shopify credentials')
        return
    
    print(f'Shop URL: {shop_url}')
    
    # Create client
    client = ShopifyAPIBase(shop_url, access_token, debug=False)
    
    # Test auth
    print('\nTesting authentication...')
    try:
        client.test_auth()
        print('✓ Authentication successful')
    except Exception as e:
        print(f'✗ Authentication failed: {e}')
        return
    
    # Get product count
    print('\nGetting product count...')
    count_query = """
    query {
        products {
            count
        }
    }
    """
    
    try:
        result = client.execute_graphql(count_query, {})
        if 'errors' in result:
            print(f'GraphQL error: {result["errors"]}')
            return
            
        count = result.get('data', {}).get('products', {}).get('count', 0)
        print(f'Total products in Shopify: {count}')
    except Exception as e:
        print(f'Error getting count: {e}')
        return
    
    # Get first 10 products only
    print('\nFetching first 10 products...')
    query = """
    query GetProducts($first: Int!) {
        products(first: $first) {
            edges {
                node {
                    id
                    title
                    handle
                    status
                    vendor
                    variants(first: 1) {
                        edges {
                            node {
                                id
                                sku
                                price
                                inventoryQuantity
                            }
                        }
                    }
                }
            }
        }
    }
    """
    
    variables = {'first': 10}
    
    try:
        result = client.execute_graphql(query, variables)
        if 'errors' in result:
            print(f'GraphQL error: {result["errors"]}')
            return
        
        products = result.get('data', {}).get('products', {}).get('edges', [])
        print(f'\nRetrieved {len(products)} products:')
        
        for i, edge in enumerate(products):
            product = edge['node']
            sku = 'N/A'
            price = 'N/A'
            
            if product.get('variants', {}).get('edges'):
                variant = product['variants']['edges'][0]['node']
                sku = variant.get('sku', 'N/A')
                price = variant.get('price', 'N/A')
            
            print(f'{i+1}. {product["title"]}')
            print(f'   - ID: {product["id"]}')
            print(f'   - SKU: {sku}')
            print(f'   - Price: ${price}')
            print(f'   - Status: {product["status"]}')
            print()
        
        # Save result
        sync_result = {
            'timestamp': datetime.now().isoformat(),
            'total_products': count,
            'sample_products': len(products),
            'status': 'test_complete'
        }
        
        with open('/tmp/shopify_test_result.json', 'w') as f:
            json.dump(sync_result, f, indent=2)
            
        print('✓ Test complete! Results saved to /tmp/shopify_test_result.json')
        
    except Exception as e:
        print(f'Error fetching products: {e}')

if __name__ == '__main__':
    main()