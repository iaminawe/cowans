#!/usr/bin/env python3
"""
Script to create an admin user in Supabase for development
"""

import os
import sys
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv()

def create_admin_user():
    """Create an admin user in Supabase"""
    
    # Get Supabase configuration
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not supabase_url or not supabase_service_key:
        print("❌ Error: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env")
        sys.exit(1)
    
    # Create Supabase client with service role key
    supabase: Client = create_client(supabase_url, supabase_service_key)
    
    # Admin user details
    admin_email = "admin@example.com"
    admin_password = "admin123"
    
    print(f"🔧 Creating admin user: {admin_email}")
    
    try:
        # Create user using admin API
        response = supabase.auth.admin.create_user({
            "email": admin_email,
            "password": admin_password,
            "email_confirm": True,
            "user_metadata": {
                "first_name": "Admin",
                "last_name": "User"
            }
        })
        
        if response.user:
            print(f"✅ Admin user created successfully!")
            print(f"   Email: {admin_email}")
            print(f"   Password: {admin_password}")
            print(f"   User ID: {response.user.id}")
            
            # Also create a cowans.com version for the startup script
            cowans_email = "admin@cowans.com"
            print(f"\n🔧 Creating cowans admin user: {cowans_email}")
            
            response2 = supabase.auth.admin.create_user({
                "email": cowans_email,
                "password": admin_password,
                "email_confirm": True,
                "user_metadata": {
                    "first_name": "Admin",
                    "last_name": "Cowans"
                }
            })
            
            if response2.user:
                print(f"✅ Cowans admin user created successfully!")
                print(f"   Email: {cowans_email}")
                print(f"   Password: {admin_password}")
                print(f"   User ID: {response2.user.id}")
            
        else:
            print("❌ Failed to create admin user")
            
    except Exception as e:
        if "already registered" in str(e):
            print(f"⚠️  User {admin_email} already exists")
            print("You can use the existing credentials:")
            print(f"   Email: {admin_email}")
            print(f"   Password: {admin_password}")
        else:
            print(f"❌ Error creating admin user: {e}")
            sys.exit(1)

if __name__ == "__main__":
    create_admin_user()