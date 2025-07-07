#!/usr/bin/env python3
"""
Extract Database Configuration from Supabase URL

This script helps extract the database connection details from your Supabase project.
"""

import os
from pathlib import Path

def extract_db_config():
    """Extract database configuration from Supabase URL."""
    print("🔍 Extracting Database Configuration")
    print("=" * 50)
    
    # Read current .env file
    env_file = Path("../../.env")
    if not env_file.exists():
        print("❌ .env file not found")
        return
    
    current_config = {}
    with open(env_file, 'r') as f:
        for line in f:
            if '=' in line and not line.strip().startswith('#'):
                key, value = line.strip().split('=', 1)
                current_config[key] = value
    
    supabase_url = current_config.get('SUPABASE_URL', '')
    
    if not supabase_url:
        print("❌ SUPABASE_URL not found in .env file")
        return
    
    # Extract project ID from URL
    # Format: https://PROJECT_ID.supabase.co
    if 'supabase.co' in supabase_url:
        project_id = supabase_url.replace('https://', '').replace('.supabase.co', '')
        db_host = f"db.{project_id}.supabase.co"
        
        print(f"✅ Supabase URL: {supabase_url}")
        print(f"✅ Project ID: {project_id}")
        print(f"✅ Database Host: {db_host}")
        
        print("\n" + "=" * 50)
        print("Missing Configuration Needed")
        print("=" * 50)
        
        print(f"\nAdd these to your .env file:")
        print(f"SUPABASE_DB_HOST={db_host}")
        print(f"SUPABASE_DB_PASSWORD=your-database-password")
        print(f"SUPABASE_JWT_SECRET=your-jwt-secret")
        
        print(f"\nTo get the missing values:")
        print(f"1. Go to: https://app.supabase.com/project/{project_id}")
        print(f"2. Settings → Database → Copy the password")
        print(f"3. Settings → API → Copy the JWT Secret")
        
        # Check if we have service role key that might work as password
        service_key = current_config.get('SUPABASE_SERVICE_ROLE_KEY', '')
        if service_key:
            print(f"\n💡 You might be able to use your service role key as the database password:")
            print(f"SUPABASE_DB_PASSWORD={service_key}")
        
        return True
    else:
        print("❌ Invalid Supabase URL format")
        return False

def create_complete_env():
    """Create a complete .env example with all required variables."""
    env_file = Path("../../.env")
    current_config = {}
    
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                if '=' in line and not line.strip().startswith('#'):
                    key, value = line.strip().split('=', 1)
                    current_config[key] = value
    
    supabase_url = current_config.get('SUPABASE_URL', '')
    project_id = supabase_url.replace('https://', '').replace('.supabase.co', '') if supabase_url else 'your-project-id'
    
    complete_config = f"""# Supabase Configuration (Complete)
SUPABASE_URL={current_config.get('SUPABASE_URL', 'https://your-project-id.supabase.co')}
SUPABASE_ANON_KEY={current_config.get('SUPABASE_ANON_KEY', 'your-anon-key')}
SUPABASE_SERVICE_ROLE_KEY={current_config.get('SUPABASE_SERVICE_ROLE_KEY', 'your-service-role-key')}
SUPABASE_JWT_SECRET=your-jwt-secret-from-api-settings
SUPABASE_DB_HOST=db.{project_id}.supabase.co
SUPABASE_DB_PASSWORD=your-database-password-from-database-settings
SUPABASE_DB_PORT=5432
SUPABASE_DB_NAME=postgres
SUPABASE_DB_USER=postgres

# Alternative: Use full connection string
# SUPABASE_DB_URL=postgresql://postgres:PASSWORD@db.{project_id}.supabase.co:5432/postgres

# Application Database URL (update after migration)
# DATABASE_URL=postgresql://postgres:PASSWORD@db.{project_id}.supabase.co:5432/postgres
"""
    
    complete_file = Path("../../.env.complete.example")
    with open(complete_file, 'w') as f:
        f.write(complete_config)
    
    print(f"\n📝 Complete configuration template created: {complete_file}")
    print("Copy the missing values to your actual .env file")

if __name__ == "__main__":
    success = extract_db_config()
    if success:
        create_complete_env()
        print("\n✅ Configuration analysis complete!")
        print("\nNext steps:")
        print("1. Add the missing variables to your .env file")
        print("2. Run: python test_supabase_connection.py")
        print("3. Run: python run_migration.py")
    else:
        print("\n❌ Could not extract configuration")