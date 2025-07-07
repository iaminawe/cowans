#!/usr/bin/env python3
"""
Test script to diagnose Shopify API issues with products.json returning empty results.

This script tests multiple approaches to fetch products from Shopify:
1. REST API with different parameters
2. GraphQL API 
3. Different authentication methods
4. API scope verification
"""

import os
import requests
import json
from datetime import datetime

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Configuration
SHOP_URL = os.getenv('SHOPIFY_SHOP_URL')
ACCESS_TOKEN = os.getenv('SHOPIFY_ACCESS_TOKEN')
API_VERSION = "2024-10"

def test_rest_api():
    """Test REST API with various approaches."""
    print("\n=== Testing REST API ===")
    
    # Ensure proper URL format
    shop_url = SHOP_URL.strip().rstrip('/')
    if not shop_url.startswith('https://'):
        shop_url = f"https://{shop_url}"
    
    headers = {
        'X-Shopify-Access-Token': ACCESS_TOKEN,
        'Content-Type': 'application/json'
    }
    
    # Test 1: Shop info
    print("\n1. Testing shop.json endpoint:")
    shop_response = requests.get(
        f"{shop_url}/admin/api/{API_VERSION}/shop.json",
        headers=headers
    )
    if shop_response.status_code == 200:
        shop_data = shop_response.json()['shop']
        print(f"✓ Shop Name: {shop_data.get('name')}")
        print(f"✓ Domain: {shop_data.get('myshopify_domain')}")
        print(f"✓ Product Count (field): {shop_data.get('product_count', 'Not shown')}")
    else:
        print(f"✗ Failed: {shop_response.status_code} - {shop_response.text}")
    
    # Test 2: Product count endpoint
    print("\n2. Testing products/count.json endpoint:")
    count_response = requests.get(
        f"{shop_url}/admin/api/{API_VERSION}/products/count.json",
        headers=headers,
        params={'status': 'any'}
    )
    if count_response.status_code == 200:
        count = count_response.json().get('count', 0)
        print(f"✓ Product count: {count}")
    else:
        print(f"✗ Failed: {count_response.status_code} - {count_response.text}")
    
    # Test 3: Products with different parameters
    print("\n3. Testing products.json with various parameters:")
    
    test_params = [
        {'limit': 10},
        {'limit': 10, 'status': 'any'},
        {'limit': 10, 'status': 'active'},
        {'limit': 10, 'published_status': 'any'},
        {'limit': 10, 'published_status': 'published'},
        {'limit': 1}  # Just try to get one product
    ]
    
    for params in test_params:
        print(f"\n   Parameters: {params}")
        products_response = requests.get(
            f"{shop_url}/admin/api/{API_VERSION}/products.json",
            headers=headers,
            params=params
        )
        
        if products_response.status_code == 200:
            products = products_response.json().get('products', [])
            print(f"   ✓ Status: 200, Products returned: {len(products)}")
            if products:
                print(f"   ✓ First product: {products[0].get('title', 'No title')}")
        else:
            print(f"   ✗ Failed: {products_response.status_code} - {products_response.text}")
    
    # Test 4: Check API scopes
    print("\n4. Testing oauth/access_scopes.json endpoint:")
    scopes_response = requests.get(
        f"{shop_url}/admin/api/{API_VERSION}/oauth/access_scopes.json",
        headers=headers
    )
    if scopes_response.status_code == 200:
        scopes = scopes_response.json().get('access_scopes', [])
        print(f"✓ Granted scopes: {[s.get('handle') for s in scopes]}")
        has_read_products = any(s.get('handle') == 'read_products' for s in scopes)
        print(f"✓ Has read_products scope: {has_read_products}")
    else:
        print(f"✗ Failed (may not be available for private apps): {scopes_response.status_code}")

def test_graphql_api():
    """Test GraphQL API."""
    print("\n\n=== Testing GraphQL API ===")
    
    # Ensure proper URL format
    shop_url = SHOP_URL.strip().rstrip('/')
    if not shop_url.startswith('https://'):
        shop_url = f"https://{shop_url}"
    
    headers = {
        'X-Shopify-Access-Token': ACCESS_TOKEN,
        'Content-Type': 'application/json'
    }
    
    # Simple products query
    query = """
    {
        products(first: 5) {
            edges {
                node {
                    id
                    title
                    handle
                    status
                }
            }
            pageInfo {
                hasNextPage
            }
        }
        shop {
            name
            productCount
        }
    }
    """
    
    graphql_response = requests.post(
        f"{shop_url}/admin/api/{API_VERSION}/graphql.json",
        headers=headers,
        json={'query': query}
    )
    
    if graphql_response.status_code == 200:
        data = graphql_response.json()
        
        if 'errors' in data:
            print(f"✗ GraphQL errors: {data['errors']}")
        else:
            shop_info = data['data'].get('shop', {})
            products = data['data'].get('products', {}).get('edges', [])
            
            print(f"✓ Shop name: {shop_info.get('name')}")
            print(f"✓ Product count (from shop): {shop_info.get('productCount')}")
            print(f"✓ Products fetched: {len(products)}")
            
            if products:
                print("\n✓ First few products:")
                for i, edge in enumerate(products[:3]):
                    product = edge['node']
                    print(f"   {i+1}. {product.get('title')} (Status: {product.get('status')})")
    else:
        print(f"✗ Failed: {graphql_response.status_code} - {graphql_response.text}")

def test_alternative_endpoints():
    """Test alternative REST endpoints that might work."""
    print("\n\n=== Testing Alternative Endpoints ===")
    
    shop_url = SHOP_URL.strip().rstrip('/')
    if not shop_url.startswith('https://'):
        shop_url = f"https://{shop_url}"
    
    headers = {
        'X-Shopify-Access-Token': ACCESS_TOKEN,
        'Content-Type': 'application/json'
    }
    
    # Test product by ID (if we know any ID)
    print("\n1. Testing specific product endpoint (if ID known):")
    print("   (Skipping - need product ID)")
    
    # Test collections endpoint
    print("\n2. Testing collections.json endpoint:")
    collections_response = requests.get(
        f"{shop_url}/admin/api/{API_VERSION}/collections.json",
        headers=headers,
        params={'limit': 5}
    )
    if collections_response.status_code == 200:
        collections = collections_response.json().get('collections', [])
        print(f"✓ Collections found: {len(collections)}")
    elif collections_response.status_code == 404:
        print("✗ Collections endpoint returned 404 - trying custom_collections.json")
        
        # Try custom_collections instead
        custom_collections_response = requests.get(
            f"{shop_url}/admin/api/{API_VERSION}/custom_collections.json",
            headers=headers,
            params={'limit': 5}
        )
        if custom_collections_response.status_code == 200:
            collections = custom_collections_response.json().get('custom_collections', [])
            print(f"✓ Custom collections found: {len(collections)}")
        else:
            print(f"✗ Custom collections failed too: {custom_collections_response.status_code}")
    else:
        print(f"✗ Failed: {collections_response.status_code}")

def main():
    """Run all tests."""
    print(f"Shopify API Diagnostic Test")
    print(f"===========================")
    print(f"Shop URL: {SHOP_URL}")
    print(f"API Version: {API_VERSION}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    if not SHOP_URL or not ACCESS_TOKEN:
        print("\n✗ ERROR: Missing SHOPIFY_SHOP_URL or SHOPIFY_ACCESS_TOKEN environment variables!")
        return
    
    test_rest_api()
    test_graphql_api()
    test_alternative_endpoints()
    
    print("\n\n=== Summary ===")
    print("\nIf REST API products.json returns 0 products but GraphQL works:")
    print("1. This confirms the REST API deprecation is affecting your store")
    print("2. You should migrate to GraphQL API immediately")
    print("3. The products.json endpoint may be returning empty due to the Feb 2025 deprecation")
    
    print("\nIf both REST and GraphQL return 0 products:")
    print("1. Check if the access token has read_products scope")
    print("2. Verify products exist and are not all in draft/archived status")
    print("3. Try regenerating the private app with all product permissions")
    
    print("\nRecommended action:")
    print("→ Switch to GraphQL API for all product operations")
    print("→ Update your code to use the GraphQL endpoints before February 2025")

if __name__ == "__main__":
    main()