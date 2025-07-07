#!/usr/bin/env python3
"""Create a test user in Supabase for development."""

import os
import sys
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
env_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
load_dotenv(env_path)

# Get Supabase credentials
url = os.getenv("SUPABASE_URL")
service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not url or not service_role_key:
    print("Error: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env")
    sys.exit(1)

# Create Supabase client with service role key (bypasses RLS)
supabase: Client = create_client(url, service_role_key)

# Test user credentials
email = "test@cowans.com"
password = "test123456"

print(f"Creating test user: {email}")

try:
    # Create user using admin API
    response = supabase.auth.admin.create_user({
        "email": email,
        "password": password,
        "email_confirm": True,
        "user_metadata": {
            "first_name": "Test",
            "last_name": "User"
        }
    })
    
    print(f"✅ User created successfully!")
    print(f"User ID: {response.user.id}")
    print(f"Email: {response.user.email}")
    
except Exception as e:
    if "already exists" in str(e):
        print(f"✅ User already exists: {email}")
        
        # Try to sign in to verify
        try:
            auth_response = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            print(f"✅ Successfully signed in!")
            print(f"Access Token: {auth_response.session.access_token[:20]}...")
        except Exception as signin_error:
            print(f"❌ Sign in failed: {signin_error}")
            print("\nTrying to update password...")
            
            # Get user and update password
            try:
                users = supabase.auth.admin.list_users()
                user = next((u for u in users if u.email == email), None)
                if user:
                    supabase.auth.admin.update_user_by_id(
                        user.id,
                        {"password": password}
                    )
                    print(f"✅ Password updated successfully!")
            except Exception as update_error:
                print(f"❌ Failed to update password: {update_error}")
    else:
        print(f"❌ Error creating user: {e}")
        sys.exit(1)

print(f"\n📝 Login credentials:")
print(f"Email: {email}")
print(f"Password: {password}")
print(f"\nYou can now login at: http://localhost:3055/login")