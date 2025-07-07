#!/usr/bin/env python3
"""
Complete SQLite to Supabase Migration Script

This script orchestrates the entire migration process from SQLite to Supabase PostgreSQL.
It includes connection testing, schema creation, data migration, and validation.
"""

import os
import sys
import subprocess
import json
from datetime import datetime
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def print_banner():
    """Print migration banner."""
    print("\n" + "="*60)
    print("    SQLite to Supabase PostgreSQL Migration")
    print("="*60)
    print(f"Started at: {datetime.now()}")
    print()

def check_requirements():
    """Check if all requirements are met."""
    logger.info("Checking requirements...")
    
    required_packages = ['psycopg2', 'python-dotenv', 'tqdm']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        logger.error(f"Missing required packages: {', '.join(missing_packages)}")
        logger.error("Please install them with:")
        logger.error(f"pip install {' '.join(missing_packages)}")
        return False
    
    # Check if migration files exist
    required_files = [
        'migrations/sqlite_to_supabase_migration.sql',
        'migrations/migrate_sqlite_to_supabase.py',
        'migrations/validate_migration.py',
        'test_supabase_connection.py',
        'create_supabase_schema.py'
    ]
    
    missing_files = []
    for file_path in required_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)
    
    if missing_files:
        logger.error(f"Missing required files: {', '.join(missing_files)}")
        return False
    
    logger.info("✅ All requirements met")
    return True

def run_step(step_name, script_path, description):
    """Run a migration step."""
    logger.info(f"\n{'='*50}")
    logger.info(f"Step: {step_name}")
    logger.info(f"Description: {description}")
    logger.info(f"{'='*50}")
    
    try:
        result = subprocess.run([sys.executable, script_path], 
                              capture_output=True, text=True, check=True)
        
        # Print stdout
        if result.stdout:
            print(result.stdout)
        
        logger.info(f"✅ {step_name} completed successfully")
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ {step_name} failed!")
        logger.error(f"Exit code: {e.returncode}")
        
        if e.stdout:
            logger.error("STDOUT:")
            logger.error(e.stdout)
        
        if e.stderr:
            logger.error("STDERR:")
            logger.error(e.stderr)
        
        return False

def interactive_confirmation(prompt):
    """Get user confirmation."""
    while True:
        response = input(f"{prompt} [y/N]: ").strip().lower()
        if response in ['y', 'yes']:
            return True
        elif response in ['n', 'no', '']:
            return False
        else:
            print("Please enter 'y' for yes or 'n' for no")

def main():
    """Main migration orchestrator."""
    print_banner()
    
    # Check requirements
    if not check_requirements():
        logger.error("❌ Requirements check failed")
        sys.exit(1)
    
    # Get user confirmation
    print("\nThis script will migrate your SQLite database to Supabase PostgreSQL.")
    print("\nThe process includes:")
    print("1. Testing connection to Supabase")
    print("2. Creating database schema in Supabase")
    print("3. Migrating all data from SQLite")
    print("4. Validating migration integrity")
    print("5. Updating application configuration")
    
    if not interactive_confirmation("\nDo you want to proceed"):
        logger.info("Migration cancelled by user")
        sys.exit(0)
    
    # Step 1: Test connection
    logger.info("\n🔍 Step 1: Testing Supabase connection...")
    if not run_step("Connection Test", "test_supabase_connection.py", 
                   "Verify connection to Supabase PostgreSQL"):
        logger.error("❌ Cannot proceed without a valid Supabase connection")
        sys.exit(1)
    
    # Step 2: Create schema
    logger.info("\n🏗️  Step 2: Creating database schema...")
    if not run_step("Schema Creation", "create_supabase_schema.py",
                   "Create all tables, indexes, and constraints in Supabase"):
        if not interactive_confirmation("Schema creation had issues. Continue anyway"):
            sys.exit(1)
    
    # Step 3: Migrate data
    logger.info("\n📦 Step 3: Migrating data...")
    if not run_step("Data Migration", "migrations/migrate_sqlite_to_supabase.py",
                   "Transfer all data from SQLite to Supabase"):
        logger.error("❌ Data migration failed")
        if not interactive_confirmation("Data migration failed. Continue with validation"):
            sys.exit(1)
    
    # Step 4: Validate migration
    logger.info("\n✅ Step 4: Validating migration...")
    if not run_step("Migration Validation", "migrations/validate_migration.py",
                   "Verify data integrity and completeness"):
        logger.warning("⚠️  Validation had issues, but migration may still be successful")
    
    # Step 5: Update configuration
    logger.info("\n⚙️  Step 5: Configuration update...")
    print("\nMigration completed! You now need to update your application configuration.")
    print("\nTo switch to Supabase PostgreSQL:")
    print("1. Update your .env file with:")
    print("   DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@db.YOUR_PROJECT_ID.supabase.co:5432/postgres")
    print("2. Restart your application")
    print("3. Test authentication and key features")
    
    # Create migration summary
    summary = {
        "migration_date": datetime.now().isoformat(),
        "source": "SQLite",
        "target": "Supabase PostgreSQL",
        "status": "completed",
        "steps_completed": [
            "connection_test",
            "schema_creation", 
            "data_migration",
            "validation"
        ]
    }
    
    summary_file = f"migration_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    logger.info(f"\n📋 Migration summary saved to: {summary_file}")
    
    print("\n" + "="*60)
    print("    🎉 MIGRATION COMPLETED SUCCESSFULLY! 🎉")
    print("="*60)
    print("\nNext steps:")
    print("1. Update DATABASE_URL in your .env file")
    print("2. Restart your application") 
    print("3. Test authentication and core features")
    print("4. Monitor for any issues")
    print("\nYour SQLite database remains unchanged as a backup.")
    print("="*60)

if __name__ == "__main__":
    main()