#!/usr/bin/env python3
"""
Test collections sync functionality
"""
import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_collections_sync():
    """Test the collections sync endpoint."""
    try:
        # Get environment variables
        api_url = os.getenv('REACT_APP_API_URL', 'http://localhost:3560/api')
        # For testing, we'll use a dummy token - in production this would be a real JWT
        
        print("Testing collections sync endpoint...")
        print(f"API URL: {api_url}")
        
        # Test sync status endpoint first
        print("\n1. Testing sync status endpoint...")
        status_url = f"{api_url}/shopify/collections/sync-status"
        
        # Note: This will fail without proper authentication in production
        # but we can see if the endpoint exists
        try:
            response = requests.get(status_url, timeout=10)
            print(f"   Status endpoint response: {response.status_code}")
            if response.status_code == 401:
                print("   ✓ Endpoint exists (authentication required)")
            elif response.status_code == 200:
                print("   ✓ Endpoint working")
                print(f"   Response: {response.json()}")
            else:
                print(f"   Response: {response.text}")
        except requests.exceptions.RequestException as e:
            print(f"   Connection error: {e}")
        
        # Test sync endpoint
        print("\n2. Testing sync endpoint...")
        sync_url = f"{api_url}/shopify/collections/sync"
        
        try:
            response = requests.post(sync_url, json={}, timeout=10)
            print(f"   Sync endpoint response: {response.status_code}")
            if response.status_code == 401:
                print("   ✓ Endpoint exists (authentication required)")
            elif response.status_code == 200:
                print("   ✓ Endpoint working")
                print(f"   Response: {response.json()}")
            else:
                print(f"   Response: {response.text}")
        except requests.exceptions.RequestException as e:
            print(f"   Connection error: {e}")
            
        print("\n3. Checking if collections exist in database...")
        # This uses the verification script we created earlier
        from simple_verify import verify_products
        verify_products()
        
    except Exception as e:
        print(f"Error testing collections sync: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_collections_sync()