#!/usr/bin/env python3
"""Check current authentication status in app.py"""

import re

# Read app.py
with open('app.py', 'r') as f:
    content = f.read()

print("🔍 Checking authentication status in app.py\n")

# Check for Supabase imports
if 'from services.supabase_auth import' in content:
    print("✅ Supabase imports found")
else:
    print("❌ Supabase imports NOT found")

# Check for dev mode auth
if 'DEV_MODE = ' in content and 'dev_jwt_required' in content:
    print("❌ Dev mode authentication still present")
else:
    print("✅ Dev mode authentication removed")

# Count JWT decorators
jwt_count = content.count('@jwt_required()')
supabase_count = content.count('@supabase_jwt_required')
print(f"\n📊 Decorator counts:")
print(f"   @jwt_required(): {jwt_count}")
print(f"   @supabase_jwt_required: {supabase_count}")

# Check for auth endpoints
if 'auth_service.sign_in' in content:
    print("\n✅ Login endpoint uses Supabase")
else:
    print("\n❌ Login endpoint needs update")

if 'auth_service.sign_up' in content:
    print("✅ Register endpoint uses Supabase")
else:
    print("❌ Register endpoint needs update")

if '/api/auth/refresh' in content:
    print("✅ Refresh endpoint exists")
else:
    print("❌ Refresh endpoint missing")

# Check WebSocket auth
if 'websocket_handlers' in content:
    print("\n✅ WebSocket handlers imported")
else:
    print("\n❌ WebSocket handlers not imported")

print("\n📋 Summary:")
if jwt_count > 0:
    print(f"   Need to replace {jwt_count} @jwt_required() decorators")
if 'DEV_MODE' in content:
    print("   Need to remove dev mode authentication")
if 'auth_service.sign_in' not in content:
    print("   Need to update authentication endpoints")