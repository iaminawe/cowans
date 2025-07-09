#!/usr/bin/env python3
"""
Test Shopify API connection and get basic info
"""

import os
import sys
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_shopify_connection():
    """Test connection to Shopify API with real credentials."""
    
    shop_url = os.getenv('SHOPIFY_SHOP_URL')
    access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
    
    if not shop_url or not access_token:
        print("❌ Error: Shopify credentials not found")
        return False
    
    print(f"🔗 Testing connection to: {shop_url}")
    print(f"🔑 Using access token: {access_token[:12]}...")
    
    # Test basic API access
    headers = {
        'X-Shopify-Access-Token': access_token,
        'Content-Type': 'application/json'
    }
    
    try:
        # Test 1: Get shop info
        print("\n📊 Test 1: Getting shop information...")
        response = requests.get(f"https://{shop_url}/admin/api/2023-10/shop.json", headers=headers)
        
        if response.status_code == 200:
            shop_data = response.json()
            shop = shop_data['shop']
            print(f"✅ Shop Name: {shop['name']}")
            print(f"✅ Shop Domain: {shop['domain']}")
            print(f"✅ Currency: {shop['currency']}")
            print(f"✅ Plan: {shop['plan_name']}")
        else:
            print(f"❌ Failed to get shop info: {response.status_code} - {response.text}")
            return False
        
        # Test 2: Get product count
        print("\n📦 Test 2: Getting product count...")
        response = requests.get(f"https://{shop_url}/admin/api/2023-10/products/count.json", headers=headers)
        
        if response.status_code == 200:
            count_data = response.json()
            product_count = count_data['count']
            print(f"✅ Total products in Shopify: {product_count:,}")
        else:
            print(f"❌ Failed to get product count: {response.status_code}")
            return False
        
        # Test 3: Get first few products
        print("\n🛍️ Test 3: Getting sample products...")
        response = requests.get(f"https://{shop_url}/admin/api/2023-10/products.json?limit=5", headers=headers)
        
        if response.status_code == 200:
            products_data = response.json()
            products = products_data['products']
            print(f"✅ Retrieved {len(products)} sample products:")
            for product in products:
                print(f"   • {product['title']} (ID: {product['id']})")
        else:
            print(f"❌ Failed to get products: {response.status_code}")
            return False
        
        # Test 4: Check API call limits
        if 'X-Shopify-Shop-Api-Call-Limit' in response.headers:
            api_limit = response.headers['X-Shopify-Shop-Api-Call-Limit']
            print(f"\n⚡ API Call Limit: {api_limit}")
        
        print("\n✅ All tests passed! Shopify API connection is working.")
        return True
        
    except Exception as e:
        print(f"❌ Connection test failed: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_shopify_connection()
    if success:
        print("\n🚀 Ready to proceed with full product sync!")
    else:
        print("\n❌ Please fix connection issues before proceeding.")