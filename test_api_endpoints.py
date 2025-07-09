#!/usr/bin/env python3
"""
Test the enhanced sync API endpoints by making actual HTTP requests.
"""

import requests
import json
import sys
import os

# Configuration
BASE_URL = "http://localhost:5000"
METRICS_ENDPOINT = f"{BASE_URL}/api/sync/metrics"
ACTIVITY_ENDPOINT = f"{BASE_URL}/api/sync/recent-activity"

def test_endpoint(url, endpoint_name):
    """Test a specific endpoint."""
    print(f"Testing {endpoint_name} endpoint...")
    
    try:
        response = requests.get(url, timeout=10)
        print(f"  Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"  ✓ {endpoint_name} endpoint working correctly")
            print(f"  Response keys: {list(data.keys())}")
            return True
        else:
            print(f"  ✗ {endpoint_name} endpoint failed")
            print(f"  Response: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"  ✗ Cannot connect to {url}")
        print(f"  Make sure the server is running on {BASE_URL}")
        return False
    except Exception as e:
        print(f"  ✗ Error testing {endpoint_name}: {e}")
        return False

def main():
    """Test all endpoints."""
    print("Testing Enhanced Sync API Endpoints")
    print("=" * 50)
    
    # Test metrics endpoint
    metrics_success = test_endpoint(METRICS_ENDPOINT, "Metrics")
    print()
    
    # Test recent activity endpoint
    activity_success = test_endpoint(ACTIVITY_ENDPOINT, "Recent Activity")
    print()
    
    # Summary
    print("=" * 50)
    if metrics_success and activity_success:
        print("✓ All endpoints are working!")
        return 0
    else:
        print("✗ Some endpoints are not working!")
        return 1

if __name__ == "__main__":
    sys.exit(main())