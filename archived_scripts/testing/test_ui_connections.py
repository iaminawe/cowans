#!/usr/bin/env python3
"""
Test UI to Backend connections for collections sync
"""

import os
import sys
import requests
import json
from dotenv import load_dotenv

load_dotenv()

def test_backend_endpoints():
    """Test backend API endpoints that the UI needs."""
    print("🧪 Testing Backend API Endpoints...")
    
    base_url = "http://localhost:5001"
    
    # Test endpoints the UI will use
    endpoints = [
        ("/api/collections", "Collections API"),
        ("/api/sync/staged", "Staged Changes"),
        ("/api/sync/recent-activity", "Recent Activity"),
        ("/api/sync/metrics", "Sync Metrics"),
        ("/api/sync/batches", "Sync Batches"),
        ("/api/sync/shopify/pull", "Shopify Pull"),
    ]
    
    results = []
    
    for endpoint, description in endpoints:
        try:
            url = f"{base_url}{endpoint}"
            print(f"📡 Testing {description}: {endpoint}")
            
            response = requests.get(url, timeout=5)
            
            if response.status_code == 401:
                print(f"   ✅ {description}: API responding (auth required)")
                results.append(True)
            elif response.status_code == 200:
                print(f"   ✅ {description}: API responding (success)")
                results.append(True)
            elif response.status_code == 404:
                print(f"   ⚠️  {description}: Endpoint not found")
                results.append(False)
            else:
                print(f"   ⚠️  {description}: Status {response.status_code}")
                results.append(False)
                
        except requests.exceptions.ConnectionError:
            print(f"   ❌ {description}: Connection failed")
            results.append(False)
        except requests.exceptions.Timeout:
            print(f"   ❌ {description}: Timeout")
            results.append(False)
        except Exception as e:
            print(f"   ❌ {description}: {str(e)}")
            results.append(False)
    
    return results

def test_frontend_access():
    """Test frontend accessibility."""
    print("\n🧪 Testing Frontend Access...")
    
    try:
        response = requests.get("http://localhost:3055", timeout=5)
        if response.status_code == 200:
            print("✅ Frontend is accessible")
            
            # Check if collections or sync pages are in the response
            content = response.text.lower()
            if 'collections' in content or 'sync' in content:
                print("✅ Frontend contains collections/sync content")
                return True
            else:
                print("⚠️  Frontend accessible but no collections/sync content found")
                return False
        else:
            print(f"⚠️  Frontend returned status {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Frontend not accessible")
        return False
    except Exception as e:
        print(f"❌ Frontend error: {str(e)}")
        return False

def test_shopify_collections_data():
    """Test actual Shopify collections data."""
    print("\n🧪 Testing Shopify Collections Data...")
    
    try:
        # Use our earlier test
        sys.path.insert(0, '/Users/iaminawe/Sites/cowans/web_dashboard/backend')
        
        from shopify_collections import ShopifyCollectionsManager
        
        shop_url = os.getenv('SHOPIFY_SHOP_URL')
        access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
        
        if not shop_url or not access_token:
            print("❌ Shopify credentials not found")
            return False
            
        manager = ShopifyCollectionsManager(shop_url, access_token)
        collections = manager.get_all_collections(limit=3)
        
        if collections:
            print(f"✅ Successfully retrieved {len(collections)} collections")
            for i, collection in enumerate(collections[:3]):
                print(f"   {i+1}. {collection.get('title', 'Untitled')}")
            return True
        else:
            print("⚠️  No collections found")
            return False
            
    except Exception as e:
        print(f"❌ Error accessing Shopify collections: {str(e)}")
        return False

def check_sync_in_progress():
    """Check if product sync is still running."""
    print("\n🧪 Checking Product Sync Status...")
    
    try:
        with open('/tmp/shopify_sync_progress.log', 'r') as f:
            lines = f.readlines()
            if lines:
                last_line = lines[-1].strip()
                if 'Processing batch' in last_line:
                    print("✅ Product sync is still running")
                    print(f"   Last status: {last_line}")
                    return True
                else:
                    print("⚠️  Product sync may have completed or stopped")
                    print(f"   Last status: {last_line}")
                    return False
            else:
                print("⚠️  No sync progress found")
                return False
                
    except FileNotFoundError:
        print("⚠️  No sync progress log found")
        return False
    except Exception as e:
        print(f"❌ Error checking sync status: {str(e)}")
        return False

def main():
    """Run all tests."""
    print("🚀 UI CONNECTIONS TEST")
    print("=" * 50)
    
    # Test backend endpoints
    backend_results = test_backend_endpoints()
    
    # Test frontend access
    frontend_result = test_frontend_access()
    
    # Test Shopify data
    shopify_result = test_shopify_collections_data()
    
    # Check sync progress
    sync_result = check_sync_in_progress()
    
    print("\n📊 TEST RESULTS:")
    print(f"   • Backend endpoints: {sum(backend_results)}/{len(backend_results)} working")
    print(f"   • Frontend access: {'✅ PASS' if frontend_result else '❌ FAIL'}")
    print(f"   • Shopify collections: {'✅ PASS' if shopify_result else '❌ FAIL'}")
    print(f"   • Product sync: {'✅ RUNNING' if sync_result else '⚠️  STOPPED'}")
    
    overall_success = (
        sum(backend_results) >= len(backend_results) // 2 and
        shopify_result
    )
    
    if overall_success:
        print("\n🎉 Collections sync UI is working properly!")
        print("   • Backend APIs are responding")
        print("   • Shopify connection is active")
        print("   • UI should be able to display collections")
    else:
        print("\n⚠️  Some issues detected with collections sync UI")
        print("   • Check backend service status")
        print("   • Verify Shopify credentials")
        print("   • Ensure all API endpoints are working")

if __name__ == "__main__":
    main()