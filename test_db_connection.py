#!/usr/bin/env python3
"""
Simple test script to verify database connection with pooler URL
"""

import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
load_dotenv('/Users/iaminawe/Sites/cowans/.env')

def test_database_connection():
    """Test database connection using the DATABASE_URL from .env"""
    
    # Reload environment to get fresh values
    load_dotenv('/Users/iaminawe/Sites/cowans/.env', override=True)
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        print("❌ DATABASE_URL not found in environment variables")
        return False
    
    print(f"🔍 Testing connection to: {database_url.replace(':fotMat-gomqih-8cybne@', ':***@')}")
    
    try:
        # Create engine
        engine = create_engine(
            database_url,
            echo=False,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=3600
        )
        
        # Test connection
        print("🔌 Attempting to connect...")
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1 as test")).scalar()
            if result == 1:
                print("✅ Database connection successful!")
                print("🎯 Pooler connection working - IPv6 issue resolved!")
                return True
            else:
                print("❌ Connection test failed - unexpected result")
                return False
                
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        if "2600:1f11:4e2:e202" in str(e):
            print("🚨 Still getting IPv6 error - pooler not working")
        return False
    
    finally:
        try:
            engine.dispose()
        except:
            pass

if __name__ == "__main__":
    print("🧪 Testing Supabase Database Connection")
    print("=" * 50)
    
    success = test_database_connection()
    
    print("=" * 50)
    if success:
        print("🎉 Database connection test PASSED")
        print("✅ Ready to deploy with pooler connection")
    else:
        print("💥 Database connection test FAILED")
        print("❌ Check your DATABASE_URL configuration")
    
    sys.exit(0 if success else 1)