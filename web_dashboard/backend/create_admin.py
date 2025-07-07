#!/usr/bin/env python3
"""
Create admin user script - Simple utility to create an admin user
"""

import sys
import os
from getpass import getpass

# Add backend directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import init_database, db_session_scope
from repositories import UserRepository


def main():
    print("Creating admin user...")
    
    # Get user input
    email = input("Enter admin email: ").strip()
    if not email:
        email = "admin@cowans.com"
        print(f"Using default email: {email}")
    
    password = getpass("Enter password (or press Enter for 'changeme123'): ").strip()
    if not password:
        password = "changeme123"
        print("Using default password")
    
    first_name = input("Enter first name (optional): ").strip() or "Admin"
    last_name = input("Enter last name (optional): ").strip() or "User"
    
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
                print(f"\n✗ User with email '{email}' already exists!")
                update = input("Do you want to update the password? (y/n): ").lower().strip()
                if update == 'y':
                    # Update password
                    from werkzeug.security import generate_password_hash
                    existing.password_hash = generate_password_hash(password)
                    session.commit()
                    print("✓ Password updated successfully!")
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
            print(f"  Email: {email}")
            print(f"  Name: {first_name} {last_name}")
            print(f"  Password: {'*' * len(password)}")
            
            if password == "changeme123":
                print("\n⚠️  Warning: Using default password. Please change it after first login!")
                
    except Exception as e:
        print(f"\n✗ Error creating admin user: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()