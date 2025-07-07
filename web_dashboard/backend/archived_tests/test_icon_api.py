#!/usr/bin/env python3
"""Test script for icon generation API endpoints."""

import requests
import json
import time
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:3560"
LOGIN_URL = f"{BASE_URL}/api/auth/login"
ICON_BASE_URL = f"{BASE_URL}/api/icons"

# Test user credentials
TEST_USER = {
    "email": "test@example.com",
    "password": "test123"
}

class IconAPITester:
    def __init__(self):
        self.session = requests.Session()
        self.token = None
        self.headers = {}
    
    def login(self):
        """Login and get access token."""
        print("🔐 Logging in...")
        response = self.session.post(LOGIN_URL, json=TEST_USER)
        
        if response.status_code == 200:
            data = response.json()
            self.token = data["access_token"]
            self.headers = {"Authorization": f"Bearer {self.token}"}
            print(f"✅ Login successful")
            return True
        else:
            print(f"❌ Login failed: {response.status_code} - {response.text}")
            return False
    
    def test_health_check(self):
        """Test health check endpoint."""
        print("\n🏥 Testing health check...")
        response = self.session.get(f"{BASE_URL}/api/health")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health check passed: {data}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    
    def test_get_categories(self):
        """Test getting categories."""
        print("\n📂 Testing get categories...")
        response = self.session.get(f"{ICON_BASE_URL}/categories", headers=self.headers)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Get categories successful: {len(data)} categories")
            return data
        else:
            print(f"❌ Get categories failed: {response.status_code} - {response.text}")
            return []
    
    def test_generate_single_icon(self):
        """Test generating a single icon."""
        print("\n🎨 Testing single icon generation...")
        
        test_category = {
            "category_id": 1,
            "category_name": "Office Supplies",
            "style": "modern",
            "color": "#3B82F6",
            "size": 128,
            "background": "transparent"
        }
        
        response = self.session.post(
            f"{ICON_BASE_URL}/generate", 
            json=test_category, 
            headers=self.headers
        )
        
        if response.status_code == 201:
            data = response.json()
            print(f"✅ Single icon generation successful: {data}")
            return data
        else:
            print(f"❌ Single icon generation failed: {response.status_code} - {response.text}")
            return None
    
    def test_generate_batch_icons(self):
        """Test generating batch icons."""
        print("\n📦 Testing batch icon generation...")
        
        test_categories = [
            {"id": 2, "name": "Computer Hardware"},
            {"id": 3, "name": "Office Furniture"},
            {"id": 4, "name": "Stationery"}
        ]
        
        batch_request = {
            "categories": test_categories,
            "options": {
                "style": "flat",
                "color": "#10B981",
                "size": 128,
                "background": "white"
            }
        }
        
        response = self.session.post(
            f"{ICON_BASE_URL}/generate/batch", 
            json=batch_request, 
            headers=self.headers
        )
        
        if response.status_code == 201:
            data = response.json()
            print(f"✅ Batch icon generation started: {data}")
            
            # Poll job status if job_id is provided
            if "job_id" in data:
                return self.poll_job_status(data["job_id"])
            else:
                return data
        else:
            print(f"❌ Batch icon generation failed: {response.status_code} - {response.text}")
            return None
    
    def poll_job_status(self, job_id):
        """Poll job status until completion."""
        print(f"📊 Polling job status for {job_id}...")
        
        for i in range(30):  # Max 30 attempts (30 seconds)
            response = self.session.get(f"{BASE_URL}/api/jobs/{job_id}", headers=self.headers)
            
            if response.status_code == 200:
                data = response.json()
                status = data.get("status", "unknown")
                progress = data.get("progress", 0)
                
                print(f"📈 Job {job_id}: {status} ({progress}%)")
                
                if status in ["completed", "failed", "cancelled"]:
                    return data
                
                time.sleep(1)
            else:
                print(f"❌ Failed to get job status: {response.status_code}")
                break
        
        print(f"⏰ Job polling timeout for {job_id}")
        return None
    
    def test_get_category_icon(self, category_id):
        """Test getting a specific category icon."""
        print(f"\n🖼️ Testing get category icon for ID {category_id}...")
        
        response = self.session.get(
            f"{ICON_BASE_URL}/categories/{category_id}", 
            headers=self.headers
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Get category icon successful: {data}")
            return data
        else:
            print(f"❌ Get category icon failed: {response.status_code} - {response.text}")
            return None
    
    def test_serve_icon(self, category_id):
        """Test serving an icon file."""
        print(f"\n🖼️ Testing serve icon for category {category_id}...")
        
        response = self.session.get(
            f"{ICON_BASE_URL}/categories/{category_id}/icon", 
            headers=self.headers
        )
        
        if response.status_code == 200:
            print(f"✅ Serve icon successful: {len(response.content)} bytes")
            return True
        else:
            print(f"❌ Serve icon failed: {response.status_code} - {response.text}")
            return False
    
    def test_regenerate_icon(self, category_id):
        """Test regenerating an icon."""
        print(f"\n🔄 Testing regenerate icon for category {category_id}...")
        
        regenerate_params = {
            "style": "outlined",
            "color": "#EF4444"
        }
        
        response = self.session.post(
            f"{ICON_BASE_URL}/categories/{category_id}/regenerate", 
            json=regenerate_params,
            headers=self.headers
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Regenerate icon successful: {data}")
            return data
        else:
            print(f"❌ Regenerate icon failed: {response.status_code} - {response.text}")
            return None
    
    def test_get_stats(self):
        """Test getting icon statistics."""
        print("\n📊 Testing get stats...")
        
        response = self.session.get(f"{ICON_BASE_URL}/stats", headers=self.headers)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Get stats successful: {data}")
            return data
        else:
            print(f"❌ Get stats failed: {response.status_code} - {response.text}")
            return None
    
    def test_delete_icon(self, category_id):
        """Test deleting an icon."""
        print(f"\n🗑️ Testing delete icon for category {category_id}...")
        
        response = self.session.delete(
            f"{ICON_BASE_URL}/categories/{category_id}", 
            headers=self.headers
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Delete icon successful: {data}")
            return True
        else:
            print(f"❌ Delete icon failed: {response.status_code} - {response.text}")
            return False
    
    def run_all_tests(self):
        """Run all tests."""
        print("🚀 Starting Icon API Tests")
        print("=" * 50)
        
        # Login first
        if not self.login():
            print("❌ Cannot proceed without login")
            return False
        
        # Test health check
        self.test_health_check()
        
        # Test get categories
        categories = self.test_get_categories()
        
        # Test single icon generation
        single_result = self.test_generate_single_icon()
        
        # Test batch icon generation
        batch_result = self.test_generate_batch_icons()
        
        # Test getting category icon details
        if single_result:
            category_id = single_result.get("icon", {}).get("category_id")
            if category_id:
                self.test_get_category_icon(category_id)
                self.test_serve_icon(category_id)
                self.test_regenerate_icon(category_id)
        
        # Test stats
        self.test_get_stats()
        
        # Test delete (comment out to preserve test data)
        # if single_result:
        #     category_id = single_result.get("icon", {}).get("category_id")
        #     if category_id:
        #         self.test_delete_icon(category_id)
        
        print("\n🎉 All tests completed!")
        return True

def main():
    """Run the test suite."""
    tester = IconAPITester()
    tester.run_all_tests()

if __name__ == "__main__":
    main()