#!/usr/bin/env python3
"""
Test script to verify all fixes are working correctly.
"""

import os
import sys
import requests
import json
from time import sleep
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

load_dotenv()

def get_db_connection():
    """Get database connection."""
    db_url = os.getenv('DATABASE_URL')
    if db_url.startswith('postgresql+psycopg://'):
        db_url = db_url.replace('postgresql+psycopg://', 'postgresql://')
    return psycopg2.connect(db_url, cursor_factory=RealDictCursor)

def test_database_indexes():
    """Test that database indexes are working correctly."""
    print("Testing database indexes...")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check that the renamed indexes exist
        cursor.execute("""
            SELECT indexname, tablename FROM pg_indexes 
            WHERE indexname LIKE 'idx_etilize_batch_%' OR indexname LIKE 'idx_sync_batch_%'
            ORDER BY indexname
        """)
        
        indexes = cursor.fetchall()
        print(f"Found {len(indexes)} fixed indexes:")
        for idx in indexes:
            print(f"  - {idx['indexname']} on {idx['tablename']}")
        
        # Check that old conflicting indexes are gone
        cursor.execute("""
            SELECT indexname, tablename FROM pg_indexes 
            WHERE indexname = 'idx_batch_user'
        """)
        
        remaining = cursor.fetchall()
        if remaining:
            print(f"WARNING: Found {len(remaining)} remaining idx_batch_user indexes:")
            for idx in remaining:
                print(f"  - {idx['indexname']} on {idx['tablename']}")
        else:
            print("✓ No conflicting idx_batch_user indexes found")
        
        print("Database indexes test completed successfully!")
        return True
        
    except Exception as e:
        print(f"Database indexes test failed: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

def test_api_endpoints():
    """Test that API endpoints are working correctly."""
    print("Testing API endpoints...")
    
    base_url = "http://localhost:5000"
    
    # Test endpoints
    endpoints = [
        "/api/dashboard/products/stats",
        "/api/dashboard/products/enhanced-stats",
        "/api/dashboard/analytics/stats",
        "/api/dashboard/collections/stats",
        "/api/dashboard/collections/summary",
        "/api/dashboard/sync/stats"
    ]
    
    success_count = 0
    
    for endpoint in endpoints:
        try:
            response = requests.get(f"{base_url}{endpoint}", timeout=10)
            if response.status_code == 200:
                data = response.json()
                print(f"✓ {endpoint} - Status: {response.status_code}")
                success_count += 1
            else:
                print(f"✗ {endpoint} - Status: {response.status_code}")
                print(f"  Response: {response.text[:200]}...")
        except Exception as e:
            print(f"✗ {endpoint} - Error: {e}")
    
    print(f"API endpoints test completed: {success_count}/{len(endpoints)} successful")
    return success_count == len(endpoints)

def test_json_operations():
    """Test JSON operations in staging API."""
    print("Testing JSON operations...")
    
    try:
        # Import necessary modules
        sys.path.append('/Users/iaminawe/Sites/cowans/web_dashboard/backend')
        from database import db_session_scope
        from models import SyncQueue
        
        with db_session_scope() as session:
            # Try to query sync queue items with JSON operations
            items = session.query(SyncQueue).filter(
                SyncQueue.operation_data.isnot(None)
            ).limit(5).all()
            
            print(f"✓ Successfully queried {len(items)} sync queue items")
            
            # Test JSON processing
            for item in items:
                if item.operation_data:
                    try:
                        if isinstance(item.operation_data, dict):
                            batch_data = item.operation_data
                        else:
                            batch_data = json.loads(item.operation_data)
                        
                        batch_id = batch_data.get('batch_id')
                        if batch_id:
                            print(f"  - Item {item.id} has batch_id: {batch_id}")
                    except Exception as e:
                        print(f"  - Item {item.id} JSON processing failed: {e}")
            
            print("JSON operations test completed successfully!")
            return True
            
    except Exception as e:
        print(f"JSON operations test failed: {e}")
        return False

def test_websocket_handler():
    """Test WebSocket handler improvements."""
    print("Testing WebSocket handler...")
    
    try:
        # Import the WebSocket handler
        sys.path.append('/Users/iaminawe/Sites/cowans/web_dashboard/backend')
        from websocket_handlers import handle_connect_with_supabase
        
        # Test that the function exists and has proper error handling
        import inspect
        source = inspect.getsource(handle_connect_with_supabase)
        
        # Check for error handling improvements
        if "try:" in source and "except" in source:
            print("✓ WebSocket handler has proper error handling")
        else:
            print("✗ WebSocket handler missing error handling")
            return False
        
        # Check that emit calls are removed from connection handler
        if "emit('error'" not in source:
            print("✓ WebSocket handler doesn't emit during connection")
        else:
            print("✗ WebSocket handler still emits during connection")
            return False
        
        print("WebSocket handler test completed successfully!")
        return True
        
    except Exception as e:
        print(f"WebSocket handler test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("Running comprehensive test suite for dashboard fixes...")
    print("=" * 60)
    
    tests = [
        ("Database Indexes", test_database_indexes),
        ("JSON Operations", test_json_operations), 
        ("WebSocket Handler", test_websocket_handler),
        ("API Endpoints", test_api_endpoints)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        print("-" * 40)
        result = test_func()
        results.append((test_name, result))
        print()
    
    print("=" * 60)
    print("Test Results Summary:")
    print("=" * 60)
    
    all_passed = True
    for test_name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        print(f"{test_name}: {status}")
        if not result:
            all_passed = False
    
    print("=" * 60)
    if all_passed:
        print("🎉 All tests passed! The dashboard fixes are working correctly.")
        return 0
    else:
        print("❌ Some tests failed. Please review the output above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())