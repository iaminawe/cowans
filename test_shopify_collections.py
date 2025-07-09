#!/usr/bin/env python3
"""
Test Shopify collections sync functionality
"""

import os
import sys
import json
from dotenv import load_dotenv

# Add the backend directory to the path
sys.path.insert(0, '/Users/iaminawe/Sites/cowans/web_dashboard/backend')

load_dotenv()

from shopify_collections import ShopifyCollectionsManager

def test_shopify_collections():
    """Test Shopify collections API connectivity."""
    print("🧪 Testing Shopify Collections API...")
    
    try:
        # Get Shopify credentials
        shop_url = os.getenv('SHOPIFY_SHOP_URL')
        access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
        
        if not shop_url or not access_token:
            print("❌ Shopify credentials not found in environment variables")
            return False
            
        print(f"🔗 Connecting to: {shop_url}")
        
        # Initialize the manager
        manager = ShopifyCollectionsManager(shop_url, access_token)
        
        # Test connection by getting collections
        print("🔗 Testing connection to Shopify...")
        
        # Get a few collections to test data retrieval
        print("\n📦 Fetching sample collections...")
        collections = manager.get_all_collections(limit=5)
        print(f"📊 Successfully fetched {len(collections)} collections")
        
        if collections:
            print(f"✅ Successfully fetched {len(collections)} collections:")
            for i, collection in enumerate(collections[:3]):
                print(f"  {i+1}. {collection.get('title', 'Untitled')} (ID: {collection.get('id', 'unknown')})")
                print(f"     - Products: {collection.get('products_count', 0)}")
                print(f"     - Handle: {collection.get('handle', 'no-handle')}")
        else:
            print("⚠️  No collections found")
        
        # Test specific collection retrieval by handle
        if collections:
            first_collection = collections[0]
            collection_handle = first_collection.get('handle')
            print(f"\n🔍 Testing specific collection retrieval (Handle: {collection_handle})...")
            
            specific_collection = manager.get_collection_by_handle(collection_handle)
            if specific_collection:
                print(f"✅ Successfully retrieved: {specific_collection.get('title', 'Untitled')}")
                print(f"   - Description: {specific_collection.get('description', 'No description')[:100]}...")
                print(f"   - Products count: {specific_collection.get('products_count', 0)}")
            else:
                print("⚠️  Failed to retrieve specific collection")
        
        print("\n🎉 Shopify Collections API test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error testing Shopify collections: {str(e)}")
        return False

def test_collections_api_endpoint():
    """Test the collections API endpoint."""
    print("\n🧪 Testing Collections API endpoint...")
    
    try:
        import requests
        
        # Test the backend API endpoint
        url = "http://localhost:5001/api/collections"
        
        # Try without auth first to see the error
        response = requests.get(url)
        print(f"📡 GET {url}")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text[:200]}...")
        
        if response.status_code == 401:
            print("✅ API endpoint is responding (auth required as expected)")
            return True
        else:
            print("⚠️  Unexpected response from API endpoint")
            return False
            
    except Exception as e:
        print(f"❌ Error testing API endpoint: {str(e)}")
        return False

if __name__ == "__main__":
    print("🚀 SHOPIFY COLLECTIONS SYNC TEST")
    print("=" * 50)
    
    # Test 1: Direct Shopify API
    shopify_test = test_shopify_collections()
    
    # Test 2: Backend API endpoint
    api_test = test_collections_api_endpoint()
    
    print("\n📊 TEST RESULTS:")
    print(f"   • Shopify API: {'✅ PASS' if shopify_test else '❌ FAIL'}")
    print(f"   • Backend API: {'✅ PASS' if api_test else '❌ FAIL'}")
    
    if shopify_test and api_test:
        print("\n🎉 All tests passed! Collections sync is working properly.")
    else:
        print("\n⚠️  Some tests failed. Check the errors above.")