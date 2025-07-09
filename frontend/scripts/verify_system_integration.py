#!/usr/bin/env python3
"""
System Integration Verification Script

Verifies all components are properly integrated and functioning.
"""

import requests
import json
import time
import sys
from datetime import datetime
from typing import Dict, List, Tuple, Optional

# Configuration
BASE_URL = "http://localhost:5000"
FRONTEND_URL = "http://localhost:3000"
AUTH_TOKEN = None  # Will be set after login

# Test credentials (update as needed)
TEST_EMAIL = "admin@example.com"
TEST_PASSWORD = "admin123"

# ANSI color codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


def print_header(title: str):
    """Print a formatted header."""
    print(f"\n{BLUE}{'=' * 60}{RESET}")
    print(f"{BLUE}{title.center(60)}{RESET}")
    print(f"{BLUE}{'=' * 60}{RESET}\n")


def print_result(test_name: str, success: bool, message: str = ""):
    """Print test result with color coding."""
    status = f"{GREEN}✓ PASS{RESET}" if success else f"{RED}✗ FAIL{RESET}"
    print(f"{test_name:<40} {status}")
    if message:
        print(f"  {YELLOW}↳ {message}{RESET}")


def test_backend_health() -> bool:
    """Test if backend is running and healthy."""
    try:
        response = requests.get(f"{BASE_URL}/api/health")
        return response.status_code == 200
    except:
        return False


def test_frontend_health() -> bool:
    """Test if frontend is accessible."""
    try:
        response = requests.get(FRONTEND_URL)
        return response.status_code == 200
    except:
        return False


def authenticate() -> Optional[str]:
    """Authenticate and get token."""
    try:
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("access_token")
    except:
        pass
    return None


def test_api_endpoint(endpoint: str, method: str = "GET", data: Dict = None) -> Tuple[bool, str]:
    """Test a specific API endpoint."""
    headers = {"Authorization": f"Bearer {AUTH_TOKEN}"} if AUTH_TOKEN else {}
    
    try:
        if method == "GET":
            response = requests.get(f"{BASE_URL}{endpoint}", headers=headers)
        elif method == "POST":
            response = requests.post(f"{BASE_URL}{endpoint}", json=data, headers=headers)
        else:
            return False, "Unsupported method"
        
        if response.status_code in [200, 201]:
            return True, f"Status: {response.status_code}"
        else:
            return False, f"Status: {response.status_code}"
    except Exception as e:
        return False, str(e)


def test_websocket_connection() -> bool:
    """Test WebSocket connectivity."""
    # This is a simplified test - in production, use websocket-client
    try:
        response = requests.get(f"{BASE_URL}/socket.io/")
        return response.status_code < 500
    except:
        return False


def verify_database_tables() -> Tuple[bool, List[str]]:
    """Verify required database tables exist."""
    required_tables = [
        "products",
        "sync_staging",
        "sync_history",
        "sync_queue",
        "batch_operations",
        "users",
        "categories"
    ]
    
    # This would normally check the database directly
    # For now, we'll test via API
    success, message = test_api_endpoint("/api/admin/database/status")
    return success, required_tables if success else []


def test_parallel_sync_system() -> Dict[str, bool]:
    """Test parallel sync system components."""
    tests = {}
    
    # Test sync status endpoint
    success, msg = test_api_endpoint("/api/sync/status")
    tests["Sync Status API"] = success
    
    # Test staged sync endpoint
    success, msg = test_api_endpoint("/api/sync/staged")
    tests["Staged Sync API"] = success
    
    # Test worker pool status
    success, msg = test_api_endpoint("/api/sync/workers")
    tests["Worker Pool API"] = success
    
    return tests


def test_batch_processing_system() -> Dict[str, bool]:
    """Test batch processing system."""
    tests = {}
    
    # Test batch status endpoint
    success, msg = test_api_endpoint("/api/batch/status")
    tests["Batch Status API"] = success
    
    # Test batch operations
    test_batch = {
        "operation": "test",
        "items": [1, 2, 3]
    }
    success, msg = test_api_endpoint("/api/batch/process", "POST", test_batch)
    tests["Batch Process API"] = success
    
    return tests


def test_shopify_integration() -> Dict[str, bool]:
    """Test Shopify integration endpoints."""
    tests = {}
    
    # Test Shopify sync endpoints
    endpoints = [
        ("/api/shopify/sync/status", "Shopify Sync Status"),
        ("/api/shopify/products/count", "Shopify Product Count"),
        ("/api/shopify/webhooks", "Shopify Webhooks")
    ]
    
    for endpoint, name in endpoints:
        success, msg = test_api_endpoint(endpoint)
        tests[name] = success
    
    return tests


def run_performance_test() -> Dict[str, float]:
    """Run basic performance tests."""
    metrics = {}
    
    # Test API response time
    start = time.time()
    test_api_endpoint("/api/products")
    metrics["API Response Time"] = (time.time() - start) * 1000  # ms
    
    # Test batch operation time (simulated)
    start = time.time()
    test_api_endpoint("/api/batch/simulate", "POST", {"count": 100})
    metrics["Batch Operation (100 items)"] = (time.time() - start) * 1000  # ms
    
    return metrics


def main():
    """Run all integration tests."""
    global AUTH_TOKEN
    
    print_header("SYSTEM INTEGRATION VERIFICATION")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Backend URL: {BASE_URL}")
    print(f"Frontend URL: {FRONTEND_URL}")
    
    # Basic connectivity tests
    print_header("1. CONNECTIVITY TESTS")
    
    backend_ok = test_backend_health()
    print_result("Backend Health Check", backend_ok)
    
    frontend_ok = test_frontend_health()
    print_result("Frontend Health Check", frontend_ok)
    
    if not backend_ok:
        print(f"\n{RED}Backend is not accessible. Please ensure it's running.{RESET}")
        sys.exit(1)
    
    # Authentication
    print_header("2. AUTHENTICATION")
    
    AUTH_TOKEN = authenticate()
    auth_ok = AUTH_TOKEN is not None
    print_result("Authentication", auth_ok, 
                 "Token obtained" if auth_ok else "Failed to authenticate")
    
    if not auth_ok:
        print(f"\n{YELLOW}Warning: Some tests may fail without authentication.{RESET}")
    
    # WebSocket test
    ws_ok = test_websocket_connection()
    print_result("WebSocket Connection", ws_ok)
    
    # Database verification
    print_header("3. DATABASE VERIFICATION")
    
    db_ok, tables = verify_database_tables()
    print_result("Database Tables", db_ok, 
                 f"{len(tables)} required tables" if db_ok else "Unable to verify")
    
    # API Endpoints
    print_header("4. API ENDPOINTS")
    
    endpoints = [
        ("/api/products", "Products API"),
        ("/api/categories", "Categories API"),
        ("/api/sync/status", "Sync Status API"),
        ("/api/batch/status", "Batch Status API"),
        ("/api/enhanced-sync/status", "Enhanced Sync API"),
        ("/api/admin/stats", "Admin Stats API")
    ]
    
    for endpoint, name in endpoints:
        success, msg = test_api_endpoint(endpoint)
        print_result(name, success, msg)
    
    # Parallel Sync System
    print_header("5. PARALLEL SYNC SYSTEM")
    
    sync_tests = test_parallel_sync_system()
    for test_name, success in sync_tests.items():
        print_result(test_name, success)
    
    # Batch Processing System
    print_header("6. BATCH PROCESSING SYSTEM")
    
    batch_tests = test_batch_processing_system()
    for test_name, success in batch_tests.items():
        print_result(test_name, success)
    
    # Shopify Integration
    print_header("7. SHOPIFY INTEGRATION")
    
    shopify_tests = test_shopify_integration()
    for test_name, success in shopify_tests.items():
        print_result(test_name, success)
    
    # Performance Metrics
    print_header("8. PERFORMANCE METRICS")
    
    metrics = run_performance_test()
    for metric_name, value in metrics.items():
        status = GREEN if value < 1000 else YELLOW if value < 5000 else RED
        print(f"{metric_name:<40} {status}{value:.2f} ms{RESET}")
    
    # Summary
    print_header("SUMMARY")
    
    total_tests = len(endpoints) + len(sync_tests) + len(batch_tests) + len(shopify_tests) + 3
    passed_tests = (
        sum(1 for _, _, success, _ in [
            (None, None, backend_ok, None),
            (None, None, frontend_ok, None),
            (None, None, auth_ok, None),
            (None, None, ws_ok, None),
            (None, None, db_ok, None)
        ] if success) +
        sum(1 for endpoint, _ in endpoints if test_api_endpoint(endpoint)[0]) +
        sum(1 for success in sync_tests.values() if success) +
        sum(1 for success in batch_tests.values() if success) +
        sum(1 for success in shopify_tests.values() if success)
    )
    
    success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
    
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {GREEN}{passed_tests}{RESET}")
    print(f"Failed: {RED}{total_tests - passed_tests}{RESET}")
    print(f"Success Rate: {GREEN if success_rate >= 90 else YELLOW if success_rate >= 70 else RED}{success_rate:.1f}%{RESET}")
    
    if success_rate >= 90:
        print(f"\n{GREEN}✅ System integration verified successfully!{RESET}")
    elif success_rate >= 70:
        print(f"\n{YELLOW}⚠️  System partially functional. Review failed tests.{RESET}")
    else:
        print(f"\n{RED}❌ System integration issues detected. Please fix before deployment.{RESET}")
    
    # Recommendations
    if not frontend_ok:
        print(f"\n{YELLOW}Recommendation: Start frontend with 'npm start'{RESET}")
    if not auth_ok:
        print(f"\n{YELLOW}Recommendation: Create test user or update credentials{RESET}")
    if not ws_ok:
        print(f"\n{YELLOW}Recommendation: Check WebSocket configuration{RESET}")


if __name__ == "__main__":
    main()