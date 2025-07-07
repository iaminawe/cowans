#!/usr/bin/env python3
"""
Auto-create admin user script - Creates admin user with default values
"""

import sys
import os
from dotenv import load_dotenv

# Load environment variables first
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

# Add backend directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import init_database, db_session_scope
from repositories import UserRepository


def main():
    print("Creating admin user with default values...")
    
    # Default admin user
    email = "admin@cowans.com"
    password = "changeme123"
    first_name = "Admin"
    last_name = "User"
    
    print(f"Email: {email}")
    print(f"Password: {password}")
    print(f"Name: {first_name} {last_name}")
    
    # Initialize database
    print("\nInitializing database...")
    init_database()
    
    # Create admin user
    try:
        with db_session_scope() as session:
            user_repo = UserRepository(session)
            
            # Check if user already exists
            existing = user_repo.get_by_email(email)
            if existing:
                print(f"\n✓ User with email '{email}' already exists!")
                print(f"  ID: {existing.id}")
                print(f"  Admin: {existing.is_admin}")
                print(f"  Active: {existing.is_active}")
                return
            
            # Create new admin user
            admin = user_repo.create_user(
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                is_admin=True
            )
            session.commit()
            
            print(f"\n✓ Admin user created successfully!")
            print(f"  ID: {admin.id}")
            print(f"  Email: {email}")
            print(f"  Name: {first_name} {last_name}")
            print(f"  Admin: {admin.is_admin}")
            print(f"  Active: {admin.is_active}")
            
            print("\n⚠️  Warning: Using default password. Please change it after first login!")
                
    except Exception as e:
        print(f"\n✗ Error creating admin user: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()