#!/usr/bin/env python3
"""
Use the existing Shopify sync API endpoints to recover products
"""
import os
import requests
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def run_shopify_sync_via_api():
    """Use the existing API endpoints to sync products from Shopify."""
    try:
        # Get API URL - try both local and deployed
        api_urls = [
            'https://cowans.apps.iaminawe.net/api',  # Deployed version
            'http://localhost:3560/api'  # Local version
        ]
        
        # Try to get an admin token (you'll need to login first)
        print("🔑 You'll need to be logged into the dashboard to run this sync.")
        print("Please copy your access token from localStorage in the browser:")
        print("1. Go to https://cowans.apps.iaminawe.net")
        print("2. Login to the dashboard")
        print("3. Open browser dev tools > Application > Local Storage")
        print("4. Copy the 'access_token' value")
        print()
        
        access_token = input("Enter your access token: ").strip()
        
        if not access_token:
            print("❌ No access token provided")
            return
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        # Try to find working API URL
        working_api_url = None
        for api_url in api_urls:
            try:
                print(f"🧪 Testing API at {api_url}...")
                response = requests.get(f"{api_url}/shopify/test-connection", headers=headers, timeout=10)
                if response.status_code == 200:
                    working_api_url = api_url
                    print(f"✅ Connected to API at {api_url}")
                    break
                else:
                    print(f"❌ API at {api_url} returned {response.status_code}")
            except Exception as e:
                print(f"❌ Could not connect to {api_url}: {e}")
        
        if not working_api_url:
            print("❌ Could not connect to any API endpoint")
            return
        
        # Test Shopify connection
        print("\n🔍 Testing Shopify connection...")
        response = requests.get(f"{working_api_url}/shopify/test-connection", headers=headers)
        
        if response.status_code != 200:
            print(f"❌ Shopify connection failed: {response.text}")
            return
        
        conn_data = response.json()
        if conn_data.get('connected'):
            print(f"✅ Shopify connected: {conn_data.get('shop', {}).get('name', 'Unknown shop')}")
        else:
            print(f"❌ Shopify not connected: {conn_data.get('error', 'Unknown error')}")
            return
        
        # Get current product count
        print("\n📊 Checking current product count...")
        response = requests.get(f"{working_api_url}/products/summary", headers=headers)
        
        if response.status_code == 200:
            summary = response.json().get('summary', {})
            current_count = summary.get('total_products', 0)
            print(f"Current products in database: {current_count}")
        else:
            print("Could not get current product count")
            current_count = 0
        
        # Check if there's a bulk import endpoint
        print("\n🚀 Looking for bulk import functionality...")
        
        # Try the enhanced sync API
        print("Trying enhanced sync API...")
        response = requests.post(f"{working_api_url}/enhanced-sync/products/pull", 
                               headers=headers, 
                               json={"force_refresh": True})
        
        if response.status_code == 200:
            print("✅ Enhanced sync initiated successfully!")
            sync_data = response.json()
            print(f"Sync response: {sync_data}")
        else:
            print(f"❌ Enhanced sync failed: {response.status_code} - {response.text}")
            
            # Try alternative: direct Shopify import
            print("\nTrying direct Shopify import...")
            
            # Since we don't have a direct bulk import endpoint, 
            # let's suggest using the deployed sync functionality
            print("\n💡 RECOMMENDATION:")
            print("Use the deployed dashboard to trigger a sync:")
            print("1. Go to https://cowans.apps.iaminawe.net")
            print("2. Navigate to the Shopify sync section")
            print("3. Use the bulk sync functionality in the UI")
            print("4. Or trigger individual sync operations")
        
        # Check final count
        print("\n📊 Checking final product count...")
        time.sleep(5)  # Wait a bit for sync to process
        
        response = requests.get(f"{working_api_url}/products/summary", headers=headers)
        if response.status_code == 200:
            summary = response.json().get('summary', {})
            final_count = summary.get('total_products', 0)
            print(f"Final products in database: {final_count}")
            
            if final_count > current_count:
                print(f"🎉 Success! Recovered {final_count - current_count} products!")
            else:
                print("⚠️  No new products were added")
        
    except Exception as e:
        print(f"❌ Error running sync: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_shopify_sync_via_api()