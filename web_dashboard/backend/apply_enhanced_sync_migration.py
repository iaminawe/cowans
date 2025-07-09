#!/usr/bin/env python3
"""
Apply Enhanced Sync System Migration

This script applies the database migration for the enhanced sync system
with staging tables, versioning support, and Xorosoft integration.
"""

import sys
import os
from datetime import datetime

# Add the backend directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from database import db_manager, init_database


def check_current_revision():
    """Check the current database revision."""
    try:
        alembic_cfg = Config("alembic.ini")
        from alembic.script import ScriptDirectory
        from alembic.runtime.migration import MigrationContext
        
        script = ScriptDirectory.from_config(alembic_cfg)
        engine = create_engine(get_db_url())
        
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            current_rev = context.get_current_revision()
            
        return current_rev
    except Exception as e:
        print(f"Error checking current revision: {e}")
        return None


def backup_database():
    """Create a backup of the database before migration."""
    try:
        # For SQLite databases
        db_url = get_db_url()
        if db_url.startswith('sqlite:///'):
            import shutil
            db_path = db_url.replace('sqlite:///', '')
            backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copy2(db_path, backup_path)
            print(f"✅ Database backed up to: {backup_path}")
            return True
        else:
            print("⚠️  Database backup for PostgreSQL should be done using pg_dump")
            return True
    except Exception as e:
        print(f"❌ Error creating backup: {e}")
        return False


def apply_migration():
    """Apply the enhanced sync system migration."""
    try:
        # Check current revision
        current_rev = check_current_revision()
        print(f"Current database revision: {current_rev}")
        
        if current_rev == '005_enhanced_sync':
            print("✅ Enhanced sync migration already applied!")
            return True
        
        # Create backup
        if not backup_database():
            response = input("Continue without backup? (y/N): ")
            if response.lower() != 'y':
                print("Migration cancelled.")
                return False
        
        # Apply migration
        print("\n🔄 Applying enhanced sync system migration...")
        alembic_cfg = Config("alembic.ini")
        
        # Upgrade to the latest revision
        command.upgrade(alembic_cfg, "005_enhanced_sync")
        
        print("✅ Migration completed successfully!")
        
        # Verify new tables exist
        verify_migration()
        
        return True
        
    except Exception as e:
        print(f"❌ Error applying migration: {e}")
        return False


def verify_migration():
    """Verify that the migration was applied successfully."""
    try:
        engine = create_engine(get_db_url())
        
        # Check for new tables
        new_tables = [
            'products_staging',
            'sync_operations',
            'sync_conflicts',
            'product_versions',
            'category_versions',
            'xorosoft_products',
            'xorosoft_sync_logs',
            'sync_rollbacks',
            'sync_performance_logs'
        ]
        
        with engine.connect() as conn:
            # Get list of tables
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name
            """))
            existing_tables = [row[0] for row in result]
            
            print("\n📊 Verification Results:")
            all_present = True
            
            for table in new_tables:
                if table in existing_tables:
                    print(f"  ✅ {table} - Created")
                else:
                    print(f"  ❌ {table} - Missing")
                    all_present = False
            
            # Check for new columns in products table
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'products' 
                AND column_name IN ('version', 'last_sync_version', 'sync_locked', 
                                   'xorosoft_id', 'xorosoft_sku', 'stock_synced_at')
            """))
            new_columns = [row[0] for row in result]
            
            print("\n📋 Product Table Enhancements:")
            expected_columns = ['version', 'last_sync_version', 'sync_locked', 
                              'xorosoft_id', 'xorosoft_sku', 'stock_synced_at']
            
            for col in expected_columns:
                if col in new_columns:
                    print(f"  ✅ {col} column - Added")
                else:
                    print(f"  ❌ {col} column - Missing")
                    all_present = False
            
            if all_present:
                print("\n✅ All migration changes verified successfully!")
            else:
                print("\n⚠️  Some migration changes are missing. Please check the logs.")
                
    except Exception as e:
        print(f"❌ Error verifying migration: {e}")


def main():
    """Main function to run the migration."""
    print("🚀 Enhanced Sync System Migration")
    print("=" * 50)
    print("\nThis migration will add:")
    print("- Staging tables for sync operations")
    print("- Version tracking for products and categories")
    print("- Xorosoft integration tables")
    print("- Sync conflict management")
    print("- Performance monitoring")
    print("\n" + "=" * 50)
    
    response = input("\nProceed with migration? (y/N): ")
    if response.lower() != 'y':
        print("Migration cancelled.")
        return
    
    if apply_migration():
        print("\n🎉 Migration completed successfully!")
        print("\nNext steps:")
        print("1. Update your application code to use the new models")
        print("2. Configure Xorosoft integration settings")
        print("3. Test the sync operations with staging")
    else:
        print("\n❌ Migration failed. Please check the logs.")


if __name__ == "__main__":
    main()