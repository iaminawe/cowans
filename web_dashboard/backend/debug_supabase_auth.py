#!/usr/bin/env python3
"""Debug Supabase authentication issues."""

import os
import sys
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
env_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
load_dotenv(env_path)

# Get Supabase credentials
url = os.getenv("SUPABASE_URL")
anon_key = os.getenv("SUPABASE_ANON_KEY")
service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

print("=== Supabase Configuration ===")
print(f"URL: {url}")
print(f"Anon Key: {'Set' if anon_key else 'NOT SET'}")
print(f"Service Role Key: {'Set' if service_role_key else 'NOT SET'}")

if not url or not anon_key:
    print("\n❌ Error: SUPABASE_URL and SUPABASE_ANON_KEY must be set in .env")
    sys.exit(1)

# Test email
test_email = "gregg@iaminawe.com"
print(f"\n=== Testing Authentication for: {test_email} ===")

# Create client with anon key (what the app uses)
supabase: Client = create_client(url, anon_key)

# Try to check if user exists (using service role if available)
if service_role_key:
    print("\nUsing service role key to check user...")
    admin_supabase: Client = create_client(url, service_role_key)
    
    try:
        # List all users
        from postgrest.exceptions import APIError
        
        # Try to get user by email using RPC or direct query
        result = admin_supabase.auth.admin.list_users()
        
        print(f"\nTotal users in Supabase: {len(result)}")
        
        # Find our user
        user_found = False
        for user in result:
            if user.email == test_email:
                user_found = True
                print(f"\n✅ User found in Supabase!")
                print(f"   ID: {user.id}")
                print(f"   Email: {user.email}")
                print(f"   Confirmed: {user.email_confirmed_at is not None}")
                print(f"   Created: {user.created_at}")
                
                if not user.email_confirmed_at:
                    print("\n⚠️  WARNING: Email is not confirmed! This might prevent login.")
                break
        
        if not user_found:
            print(f"\n❌ User {test_email} NOT found in Supabase!")
            print("\nExisting users:")
            for user in result[:5]:  # Show first 5 users
                print(f"   - {user.email}")
            if len(result) > 5:
                print(f"   ... and {len(result) - 5} more")
                
    except Exception as e:
        print(f"\n❌ Error checking users: {e}")
        print("   This might be a permissions issue with the service role key")

# Test sign in with a dummy password
print(f"\n=== Testing Sign In ===")
print("Note: This will fail with 'Invalid credentials' if the password is wrong")
print("      But it should NOT fail with network or configuration errors")

try:
    # This will fail with invalid credentials, but that's expected
    response = supabase.auth.sign_in_with_password({
        "email": test_email,
        "password": "dummy_password_for_test"
    })
    print("✅ Unexpected: Sign in succeeded with dummy password!")
except Exception as e:
    error_message = str(e)
    if "Invalid login credentials" in error_message or "invalid_credentials" in error_message:
        print("✅ Authentication system is working correctly")
        print("   (Got expected 'Invalid credentials' error)")
    else:
        print(f"❌ Unexpected error: {error_message}")
        print("   This suggests a configuration or network issue")

print("\n=== Summary ===")
print("If you see 'Invalid credentials' errors, the system is working correctly.")
print("Make sure:")
print("1. The user exists in Supabase (check Supabase dashboard)")
print("2. The email is confirmed (if email confirmation is required)")
print("3. You're using the correct password")
print("4. There are no typos in the email or password")