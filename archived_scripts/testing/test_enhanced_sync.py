#!/usr/bin/env python3
"""
Test Enhanced Sync System

This script tests the enhanced sync system components.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'web_dashboard', 'backend'))

from database import init_database, db_session_scope
from enhanced_sync_api import enhanced_sync_bp

def test_enhanced_sync_system():
    """Test the enhanced sync system."""
    
    print("🧪 Testing Enhanced Sync System")
    print("=" * 50)
    
    # Test 1: Database initialization
    print("1. Testing database initialization...")
    try:
        init_database(create_tables=False)  # Don't create tables, just connect
        print("✅ Database initialized successfully")
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return False
    
    # Test 2: API blueprint registration
    print("2. Testing API blueprint...")
    try:
        print(f"✅ Enhanced sync blueprint loaded: {enhanced_sync_bp.name}")
        print(f"✅ Blueprint URL prefix: {enhanced_sync_bp.url_prefix}")
    except Exception as e:
        print(f"❌ Blueprint test failed: {e}")
        return False
    
    # Test 3: Database session
    print("3. Testing database session...")
    try:
        from sqlalchemy import text
        with db_session_scope() as session:
            result = session.execute(text("SELECT 1")).scalar()
            if result == 1:
                print("✅ Database session working")
            else:
                print("❌ Database session failed")
                return False
    except Exception as e:
        print(f"❌ Database session test failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = test_enhanced_sync_system()
    
    if success:
        print("\n🎉 Enhanced Sync System Test Passed!")
        print("The enhanced sync system is ready for use.")
    else:
        print("\n💥 Enhanced Sync System Test Failed!")
        sys.exit(1)