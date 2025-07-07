#!/usr/bin/env python3
"""
Setup Supabase Environment Configuration

This script helps configure the environment variables needed for Supabase migration.
"""

import os
from pathlib import Path

def setup_supabase_env():
    """Interactive setup of Supabase environment variables."""
    print("🔧 Supabase Environment Setup")
    print("=" * 50)
    
    # Check current environment
    env_file = Path("../../.env")
    current_config = {}
    
    if env_file.exists():
        print(f"Found existing .env file: {env_file}")
        with open(env_file, 'r') as f:
            for line in f:
                if '=' in line and not line.strip().startswith('#'):
                    key, value = line.strip().split('=', 1)
                    current_config[key] = value
    else:
        print("No .env file found, will create one")
    
    # Check for existing Supabase configuration
    supabase_vars = [
        'SUPABASE_URL',
        'SUPABASE_ANON_KEY', 
        'SUPABASE_SERVICE_ROLE_KEY',
        'SUPABASE_JWT_SECRET',
        'SUPABASE_DB_URL',
        'SUPABASE_DB_HOST',
        'SUPABASE_DB_PASSWORD'
    ]
    
    print("\nCurrent Supabase configuration:")
    for var in supabase_vars:
        value = current_config.get(var, 'Not set')
        if value and value != 'Not set':
            # Mask sensitive values
            if 'PASSWORD' in var or 'SECRET' in var or 'KEY' in var:
                masked_value = value[:10] + '...' if len(value) > 10 else '***'
                print(f"  {var}: {masked_value}")
            else:
                print(f"  {var}: {value}")
        else:
            print(f"  {var}: {value}")
    
    print("\n" + "=" * 50)
    print("Supabase Configuration Guide")
    print("=" * 50)
    
    print("\nTo get your Supabase credentials:")
    print("1. Go to https://app.supabase.com")
    print("2. Select your project")
    print("3. Go to Settings → API")
    print("4. Copy the Project URL and anon/service_role keys")
    print("5. Go to Settings → Database") 
    print("6. Copy the database connection details")
    
    print("\nRequired environment variables:")
    print("SUPABASE_URL=https://your-project-id.supabase.co")
    print("SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...")
    print("SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...")
    print("SUPABASE_JWT_SECRET=your-jwt-secret")
    print("SUPABASE_DB_HOST=db.your-project-id.supabase.co")
    print("SUPABASE_DB_PASSWORD=your-database-password")
    
    # Check if we have enough configuration to proceed
    required_for_migration = ['SUPABASE_URL', 'SUPABASE_DB_HOST', 'SUPABASE_DB_PASSWORD']
    missing_required = [var for var in required_for_migration if not current_config.get(var)]
    
    if missing_required:
        print(f"\n⚠️  Missing required variables for migration: {', '.join(missing_required)}")
        print("Please add these to your .env file before running the migration.")
        return False
    else:
        print("\n✅ All required variables are configured!")
        return True

def create_sample_env():
    """Create a sample .env file with Supabase configuration."""
    sample_content = """# Supabase Configuration for Migration
# Get these values from your Supabase dashboard

# Supabase Project Settings (Settings → API)
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_JWT_SECRET=your-jwt-secret

# Supabase Database Settings (Settings → Database)
SUPABASE_DB_HOST=db.your-project-id.supabase.co
SUPABASE_DB_PORT=5432
SUPABASE_DB_NAME=postgres
SUPABASE_DB_USER=postgres
SUPABASE_DB_PASSWORD=your-database-password

# OR use the full connection string
# SUPABASE_DB_URL=postgresql://postgres:password@db.project-id.supabase.co:5432/postgres

# Application Database URL (update after migration)
# DATABASE_URL=postgresql://postgres:password@db.project-id.supabase.co:5432/postgres
"""
    
    sample_file = Path("../../.env.supabase.example")
    with open(sample_file, 'w') as f:
        f.write(sample_content)
    
    print(f"📝 Sample configuration created: {sample_file}")
    print("Copy this to your .env file and update with your actual values")

if __name__ == "__main__":
    print("Setting up Supabase environment...")
    
    # Check current configuration
    configured = setup_supabase_env()
    
    if not configured:
        create_sample_env()
        print("\n❌ Configuration incomplete. Please update your .env file and try again.")
    else:
        print("\n✅ Configuration complete. Ready for migration!")