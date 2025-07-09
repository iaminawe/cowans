#!/usr/bin/env python3
"""
Test script to verify that the sync endpoints return the correct format.
"""

import requests
import json
from datetime import datetime

def test_endpoint_without_auth(endpoint, expected_structure):
    """Test that an endpoint returns the expected structure even without auth."""
    url = f"http://localhost:3560/api{endpoint}"
    
    try:
        response = requests.get(url)
        print(f"\n=== Testing {endpoint} ===")
        print(f"Status: {response.status_code}")
        
        if response.status_code == 401:
            print("✓ Authentication required (expected)")
            return
        
        try:
            data = response.json()
            print(f"Response type: {type(data)}")
            print(f"Response: {json.dumps(data, indent=2)}")
            
            if expected_structure == "array":
                if isinstance(data, list):
                    print("✓ Returns array as expected")
                else:
                    print(f"✗ Expected array, got {type(data)}")
            elif expected_structure == "object":
                if isinstance(data, dict):
                    print("✓ Returns object as expected")
                else:
                    print(f"✗ Expected object, got {type(data)}")
                    
        except json.JSONDecodeError:
            print(f"✗ Invalid JSON response")
            
    except Exception as e:
        print(f"✗ Error: {str(e)}")

def main():
    print("Testing Enhanced Sync API Endpoints")
    print("=" * 50)
    
    # Test the problematic endpoint
    test_endpoint_without_auth("/sync/recent-activity", "array")
    
    # Test metrics endpoint
    test_endpoint_without_auth("/sync/metrics", "object")
    
    print("\n" + "=" * 50)
    print("Test completed!")

if __name__ == "__main__":
    main()