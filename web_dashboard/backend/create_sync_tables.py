#!/usr/bin/env python3
"""
Create Enhanced Sync System Tables

This script creates the enhanced sync system tables directly using SQLAlchemy.
"""

import sys
import os

# Add the backend directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import init_database, db_manager
from models_sync_enhanced import (
    ProductsStaging, SyncOperation, SyncConflict, 
    ProductVersion, CategoryVersion, XorosoftProduct,
    XorosoftSyncLog, SyncPerformanceLog, SyncRollback
)

def create_sync_tables():
    """Create the enhanced sync system tables."""
    
    print("🔍 Initializing database...")
    init_database()
    
    print("🏗️ Creating enhanced sync system tables...")
    
    try:
        # Import the models to register them with SQLAlchemy
        from models_sync_enhanced import SyncBase
        
        # Create all tables
        SyncBase.metadata.create_all(db_manager.engine)
        
        print("✅ Enhanced sync system tables created successfully!")
        
        # Show created tables
        print("\n📋 Created tables:")
        tables = [
            "products_staging",
            "sync_operations", 
            "sync_conflicts",
            "product_versions",
            "category_versions",
            "xorosoft_products",
            "xorosoft_sync_log",
            "sync_performance_log",
            "sync_rollback"
        ]
        
        for table in tables:
            print(f"  ✓ {table}")
            
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("🚀 Enhanced Sync System - Table Creation")
    print("=" * 50)
    
    success = create_sync_tables()
    
    if success:
        print("\n🎉 Database migration completed successfully!")
        print("The enhanced sync system is now ready to use.")
    else:
        print("\n💥 Database migration failed!")
        sys.exit(1)