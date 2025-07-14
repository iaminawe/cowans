#!/usr/bin/env python3
"""
Debug script to check environment variables in container
"""

import os
import sys

print("🔍 Environment Variable Debug")
print("=" * 50)

# Check all relevant environment variables
env_vars = [
    'DATABASE_URL',
    'SUPABASE_URL', 
    'SUPABASE_SERVICE_ROLE_KEY',
    'SUPABASE_USE_POOLER',
    'FLASK_ENV'
]

for var in env_vars:
    value = os.getenv(var)
    if value:
        if 'key' in var.lower() or 'password' in var.lower() or 'url' in var.lower():
            # Mask sensitive data
            if len(value) > 10:
                masked = value[:10] + "***" + value[-5:]
            else:
                masked = "***"
            print(f"{var}: {masked}")
        else:
            print(f"{var}: {value}")
    else:
        print(f"{var}: NOT SET")

print("=" * 50)

# Test which database URL would be used
sys.path.append('/app')
try:
    from database import DatabaseManager
    db = DatabaseManager()
    db_url = db.database_url
    # Mask the password
    masked_url = db_url.replace(':fotMat-gomqih-8cybne@', ':***@') if 'fotMat-gomqih-8cybne' in db_url else db_url
    print(f"🎯 Database URL being used: {masked_url}")
except Exception as e:
    print(f"❌ Error checking database URL: {e}")

print("=" * 50)