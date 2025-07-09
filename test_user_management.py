#!/usr/bin/env python3
"""
Comprehensive test suite for the User Management System
Tests all CRUD operations and admin features
"""

import requests
import json
import time
import os
from typing import Dict, Any, List

# Configuration
API_BASE_URL = "http://localhost:5000/api"
ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "admin123"

class UserManagementTester:
    def __init__(self):
        self.session = requests.Session()
        self.admin_token = None
        self.created_users = []
        
    def authenticate_admin(self):
        """Authenticate as admin to get access token"""
        login_data = {
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        }
        
        response = self.session.post(f"{API_BASE_URL}/auth/login", json=login_data)
        if response.status_code == 200:
            self.admin_token = response.json().get("access_token")
            self.session.headers.update({
                "Authorization": f"Bearer {self.admin_token}"
            })
            print("✅ Admin authentication successful")
            return True
        else:
            print(f"❌ Admin authentication failed: {response.status_code}")
            return False
    
    def test_user_creation(self) -> bool:
        """Test user creation with various scenarios"""
        print("\n🧪 Testing User Creation...")
        
        # Test 1: Create regular user
        user_data = {
            "email": "testuser1@example.com",
            "password": "testpassword123",
            "first_name": "Test",
            "last_name": "User1",
            "is_admin": False,
            "is_active": True
        }
        
        response = self.session.post(f"{API_BASE_URL}/admin/users", json=user_data)
        if response.status_code == 201:
            user_id = response.json().get("id")
            self.created_users.append(user_id)
            print("✅ Regular user creation successful")
        else:
            print(f"❌ Regular user creation failed: {response.status_code} - {response.text}")
            return False
        
        # Test 2: Create admin user
        admin_user_data = {
            "email": "testadmin@example.com",
            "password": "adminpassword123",
            "first_name": "Test",
            "last_name": "Admin",
            "is_admin": True,
            "is_active": True
        }
        
        response = self.session.post(f"{API_BASE_URL}/admin/users", json=admin_user_data)
        if response.status_code == 201:
            user_id = response.json().get("id")
            self.created_users.append(user_id)
            print("✅ Admin user creation successful")
        else:
            print(f"❌ Admin user creation failed: {response.status_code} - {response.text}")
            return False
        
        # Test 3: Test validation - duplicate email
        response = self.session.post(f"{API_BASE_URL}/admin/users", json=user_data)
        if response.status_code == 409:
            print("✅ Duplicate email validation working")
        else:
            print(f"❌ Duplicate email validation failed: {response.status_code}")
            return False
        
        # Test 4: Test validation - missing required fields
        invalid_user_data = {
            "email": "incomplete@example.com"
            # Missing password
        }
        
        response = self.session.post(f"{API_BASE_URL}/admin/users", json=invalid_user_data)
        if response.status_code == 400:
            print("✅ Required field validation working")
        else:
            print(f"❌ Required field validation failed: {response.status_code}")
            return False
        
        return True
    
    def test_user_listing(self) -> bool:
        """Test user listing with filters and pagination"""
        print("\n🧪 Testing User Listing...")
        
        # Test 1: Get all users
        response = self.session.get(f"{API_BASE_URL}/admin/users")
        if response.status_code == 200:
            data = response.json()
            if "users" in data and "pagination" in data:
                print(f"✅ User listing successful - {len(data['users'])} users found")
            else:
                print(f"❌ User listing response format incorrect: {data}")
                return False
        else:
            print(f"❌ User listing failed: {response.status_code}")
            return False
        
        # Test 2: Test pagination
        response = self.session.get(f"{API_BASE_URL}/admin/users?page=1&limit=10")
        if response.status_code == 200:
            data = response.json()
            if data["pagination"]["page"] == 1 and data["pagination"]["limit"] == 10:
                print("✅ Pagination working correctly")
            else:
                print(f"❌ Pagination incorrect: {data['pagination']}")
                return False
        else:
            print(f"❌ Pagination test failed: {response.status_code}")
            return False
        
        # Test 3: Test search
        response = self.session.get(f"{API_BASE_URL}/admin/users?search=testuser1")
        if response.status_code == 200:
            data = response.json()
            if len(data["users"]) >= 1:
                print("✅ Search functionality working")
            else:
                print(f"❌ Search functionality failed: {data}")
                return False
        else:
            print(f"❌ Search test failed: {response.status_code}")
            return False
        
        # Test 4: Test role filter
        response = self.session.get(f"{API_BASE_URL}/admin/users?is_admin=true")
        if response.status_code == 200:
            data = response.json()
            admin_users = [u for u in data["users"] if u["is_admin"]]
            if len(admin_users) >= 1:
                print("✅ Role filtering working")
            else:
                print(f"❌ Role filtering failed: {data}")
                return False
        else:
            print(f"❌ Role filter test failed: {response.status_code}")
            return False
        
        return True
    
    def test_user_updates(self) -> bool:
        """Test user update functionality"""
        print("\n🧪 Testing User Updates...")
        
        if not self.created_users:
            print("❌ No users to update")
            return False
        
        user_id = self.created_users[0]
        
        # Test 1: Update user details
        update_data = {
            "first_name": "Updated",
            "last_name": "Name",
            "is_active": True
        }
        
        response = self.session.put(f"{API_BASE_URL}/admin/users/{user_id}", json=update_data)
        if response.status_code == 200:
            print("✅ User details update successful")
        else:
            print(f"❌ User details update failed: {response.status_code} - {response.text}")
            return False
        
        # Test 2: Toggle admin status
        toggle_admin_data = {
            "is_admin": True
        }
        
        response = self.session.put(f"{API_BASE_URL}/admin/users/{user_id}", json=toggle_admin_data)
        if response.status_code == 200:
            print("✅ Admin status toggle successful")
        else:
            print(f"❌ Admin status toggle failed: {response.status_code} - {response.text}")
            return False
        
        # Test 3: Toggle active status
        toggle_active_data = {
            "is_active": False
        }
        
        response = self.session.put(f"{API_BASE_URL}/admin/users/{user_id}", json=toggle_active_data)
        if response.status_code == 200:
            print("✅ Active status toggle successful")
        else:
            print(f"❌ Active status toggle failed: {response.status_code} - {response.text}")
            return False
        
        # Test 4: Reactivate user
        reactivate_data = {
            "is_active": True
        }
        
        response = self.session.put(f"{API_BASE_URL}/admin/users/{user_id}", json=reactivate_data)
        if response.status_code == 200:
            print("✅ User reactivation successful")
        else:
            print(f"❌ User reactivation failed: {response.status_code} - {response.text}")
            return False
        
        return True
    
    def test_user_details(self) -> bool:
        """Test getting detailed user information"""
        print("\n🧪 Testing User Details...")
        
        if not self.created_users:
            print("❌ No users to get details for")
            return False
        
        user_id = self.created_users[0]
        
        response = self.session.get(f"{API_BASE_URL}/admin/users/{user_id}")
        if response.status_code == 200:
            data = response.json()
            required_fields = ["id", "email", "first_name", "last_name", "is_admin", "is_active", "created_at"]
            if all(field in data for field in required_fields):
                print("✅ User details retrieval successful")
                return True
            else:
                print(f"❌ User details missing required fields: {data}")
                return False
        else:
            print(f"❌ User details retrieval failed: {response.status_code}")
            return False
    
    def test_user_deletion(self) -> bool:
        """Test user deletion functionality"""
        print("\n🧪 Testing User Deletion...")
        
        if len(self.created_users) < 2:
            print("❌ Need at least 2 users to test deletion")
            return False
        
        user_to_delete = self.created_users[-1]  # Delete the last created user
        
        response = self.session.delete(f"{API_BASE_URL}/admin/users/{user_to_delete}")
        if response.status_code == 200:
            print("✅ User deletion successful")
            self.created_users.remove(user_to_delete)
            
            # Verify user is deleted
            response = self.session.get(f"{API_BASE_URL}/admin/users/{user_to_delete}")
            if response.status_code == 404:
                print("✅ User deletion verified")
                return True
            else:
                print(f"❌ User deletion verification failed: {response.status_code}")
                return False
        else:
            print(f"❌ User deletion failed: {response.status_code} - {response.text}")
            return False
    
    def test_admin_permissions(self) -> bool:
        """Test that admin features work correctly"""
        print("\n🧪 Testing Admin Permissions...")
        
        # Test that the admin toggle actually works
        if not self.created_users:
            print("❌ No users to test admin permissions on")
            return False
        
        user_id = self.created_users[0]
        
        # Make user admin
        response = self.session.put(f"{API_BASE_URL}/admin/users/{user_id}", json={"is_admin": True})
        if response.status_code != 200:
            print(f"❌ Failed to make user admin: {response.status_code}")
            return False
        
        # Verify user is admin
        response = self.session.get(f"{API_BASE_URL}/admin/users/{user_id}")
        if response.status_code == 200:
            data = response.json()
            if data.get("is_admin") == True:
                print("✅ Admin privilege grant successful")
            else:
                print(f"❌ Admin privilege not granted: {data}")
                return False
        else:
            print(f"❌ Failed to verify admin privilege: {response.status_code}")
            return False
        
        # Remove admin privilege
        response = self.session.put(f"{API_BASE_URL}/admin/users/{user_id}", json={"is_admin": False})
        if response.status_code != 200:
            print(f"❌ Failed to remove admin privilege: {response.status_code}")
            return False
        
        # Verify admin privilege removed
        response = self.session.get(f"{API_BASE_URL}/admin/users/{user_id}")
        if response.status_code == 200:
            data = response.json()
            if data.get("is_admin") == False:
                print("✅ Admin privilege removal successful")
                return True
            else:
                print(f"❌ Admin privilege not removed: {data}")
                return False
        else:
            print(f"❌ Failed to verify admin privilege removal: {response.status_code}")
            return False
    
    def cleanup(self):
        """Clean up created test users"""
        print("\n🧹 Cleaning up test users...")
        
        for user_id in self.created_users:
            try:
                response = self.session.delete(f"{API_BASE_URL}/admin/users/{user_id}")
                if response.status_code == 200:
                    print(f"✅ Deleted user {user_id}")
                else:
                    print(f"❌ Failed to delete user {user_id}: {response.status_code}")
            except Exception as e:
                print(f"❌ Error deleting user {user_id}: {e}")
        
        self.created_users = []
    
    def run_all_tests(self):
        """Run all user management tests"""
        print("🚀 Starting User Management System Tests")
        print("=" * 50)
        
        # Authenticate as admin
        if not self.authenticate_admin():
            print("❌ Cannot proceed without admin authentication")
            return False
        
        # Run all tests
        tests = [
            ("User Creation", self.test_user_creation),
            ("User Listing", self.test_user_listing),
            ("User Updates", self.test_user_updates),
            ("User Details", self.test_user_details),
            ("Admin Permissions", self.test_admin_permissions),
            ("User Deletion", self.test_user_deletion),
        ]
        
        passed = 0
        failed = 0
        
        for test_name, test_func in tests:
            try:
                if test_func():
                    passed += 1
                    print(f"✅ {test_name} - PASSED")
                else:
                    failed += 1
                    print(f"❌ {test_name} - FAILED")
            except Exception as e:
                failed += 1
                print(f"❌ {test_name} - ERROR: {e}")
            
            time.sleep(0.5)  # Small delay between tests
        
        # Cleanup
        self.cleanup()
        
        # Final results
        print("\n" + "=" * 50)
        print(f"🎯 Test Results: {passed} passed, {failed} failed")
        print(f"Success Rate: {(passed / (passed + failed) * 100):.1f}%")
        
        if failed == 0:
            print("🎉 All tests passed! User Management System is working correctly.")
            return True
        else:
            print("⚠️  Some tests failed. Please check the implementation.")
            return False

if __name__ == "__main__":
    tester = UserManagementTester()
    success = tester.run_all_tests()
    exit(0 if success else 1)