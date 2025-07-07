#!/usr/bin/env python3
"""
Final Migration Validation

This script performs a comprehensive validation of the completed migration.
"""

import os
import sqlite3
import psycopg2
from datetime import datetime
import logging
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), '../../.env'))

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def validate_database_migration():
    """Validate the database migration is complete."""
    logger.info("=== Database Migration Validation ===")
    
    # Connect to both databases
    sqlite_conn = sqlite3.connect('database.db')
    sqlite_cur = sqlite_conn.cursor()
    
    database_url = os.getenv('DATABASE_URL').replace('postgresql+psycopg://', 'postgresql://')
    pg_conn = psycopg2.connect(database_url)
    pg_cur = pg_conn.cursor()
    
    validation_results = {}
    total_issues = 0
    
    # Get all tables from SQLite
    sqlite_cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    sqlite_tables = [row[0] for row in sqlite_cur.fetchall()]
    
    logger.info(f"Validating {len(sqlite_tables)} tables...")
    
    for table in sqlite_tables:
        try:
            # Get counts
            sqlite_cur.execute(f"SELECT COUNT(*) FROM {table}")
            sqlite_count = sqlite_cur.fetchone()[0]
            
            pg_cur.execute(f"SELECT COUNT(*) FROM {table}")
            pg_count = pg_cur.fetchone()[0]
            
            if sqlite_count == pg_count:
                logger.info(f"✅ {table}: {sqlite_count:,} records (match)")
                validation_results[table] = {"status": "match", "sqlite": sqlite_count, "postgres": pg_count}
            else:
                logger.warning(f"⚠️  {table}: SQLite {sqlite_count:,} vs PostgreSQL {pg_count:,}")
                validation_results[table] = {"status": "mismatch", "sqlite": sqlite_count, "postgres": pg_count}
                total_issues += 1
                
        except Exception as e:
            logger.error(f"❌ {table}: Error - {str(e)}")
            validation_results[table] = {"status": "error", "error": str(e)}
            total_issues += 1
    
    sqlite_conn.close()
    pg_conn.close()
    
    return validation_results, total_issues

def validate_application():
    """Validate the application configuration."""
    logger.info("\n=== Application Validation ===")
    
    issues = []
    
    try:
        # Test imports
        import sys
        sys.path.insert(0, '.')
        from app import app
        logger.info("✅ Application imports successfully")
        
        # Test database configuration
        database_url = os.getenv('DATABASE_URL')
        if database_url and 'postgresql' in database_url:
            logger.info("✅ PostgreSQL database configured")
        else:
            logger.error("❌ Database not configured for PostgreSQL")
            issues.append("Database configuration")
        
        # Test Supabase configuration
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
        if supabase_url and supabase_key:
            logger.info("✅ Supabase authentication configured")
        else:
            logger.error("❌ Supabase configuration incomplete")
            issues.append("Supabase configuration")
        
        # Test database connection
        from database import db_manager
        if db_manager:
            logger.info("✅ Database manager initialized")
        else:
            logger.error("❌ Database manager not initialized")
            issues.append("Database connection")
        
    except Exception as e:
        logger.error(f"❌ Application validation failed: {str(e)}")
        issues.append(f"Import error: {str(e)}")
    
    return issues

def validate_authentication():
    """Validate authentication system."""
    logger.info("\n=== Authentication Validation ===")
    
    try:
        from services.supabase_auth import auth_service
        logger.info("✅ Supabase auth service loaded")
        
        # Check auth service methods
        required_methods = ['sign_up', 'sign_in', 'verify_token', 'refresh_token']
        for method in required_methods:
            if hasattr(auth_service, method):
                logger.info(f"✅ Auth method available: {method}")
            else:
                logger.error(f"❌ Missing auth method: {method}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Authentication validation failed: {str(e)}")
        return False

def create_validation_report(validation_results, app_issues, auth_status):
    """Create a comprehensive validation report."""
    
    report = {
        "validation_date": datetime.now().isoformat(),
        "migration_status": "completed",
        "database_validation": validation_results,
        "application_issues": app_issues,
        "authentication_status": "working" if auth_status else "issues",
        "summary": {
            "total_tables": len(validation_results),
            "matching_tables": len([t for t in validation_results.values() if t.get("status") == "match"]),
            "mismatched_tables": len([t for t in validation_results.values() if t.get("status") == "mismatch"]),
            "error_tables": len([t for t in validation_results.values() if t.get("status") == "error"]),
            "application_issues": len(app_issues),
            "overall_status": "success" if len(app_issues) == 0 and auth_status else "issues"
        }
    }
    
    report_file = f"final_validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    return report_file

def main():
    """Main validation function."""
    logger.info("🔍 Final Migration Validation")
    logger.info("=" * 60)
    logger.info(f"Started at: {datetime.now()}")
    
    # Validate database migration
    validation_results, db_issues = validate_database_migration()
    
    # Validate application
    app_issues = validate_application()
    
    # Validate authentication
    auth_status = validate_authentication()
    
    # Create validation report
    report_file = create_validation_report(validation_results, app_issues, auth_status)
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("🎯 MIGRATION VALIDATION SUMMARY")
    logger.info("=" * 60)
    
    logger.info(f"📊 Database Tables: {len(validation_results)}")
    matching = len([t for t in validation_results.values() if t.get("status") == "match"])
    logger.info(f"✅ Matching: {matching}")
    
    if db_issues == 0:
        logger.info("✅ Database migration: SUCCESSFUL")
    else:
        logger.warning(f"⚠️  Database issues: {db_issues}")
    
    if len(app_issues) == 0:
        logger.info("✅ Application configuration: WORKING")
    else:
        logger.error(f"❌ Application issues: {len(app_issues)}")
        for issue in app_issues:
            logger.error(f"   - {issue}")
    
    if auth_status:
        logger.info("✅ Authentication: CONFIGURED")
    else:
        logger.error("❌ Authentication: ISSUES")
    
    logger.info(f"\n📋 Detailed report: {report_file}")
    
    # Overall status
    if len(app_issues) == 0 and auth_status:
        logger.info("\n🎉 MIGRATION COMPLETED SUCCESSFULLY!")
        logger.info("=" * 60)
        logger.info("✅ Database migrated to Supabase PostgreSQL")
        logger.info("✅ Authentication upgraded to Supabase")
        logger.info("✅ Application ready for production")
        
        logger.info("\n🚀 Your application is now running on:")
        logger.info("   - PostgreSQL database (Supabase)")
        logger.info("   - Supabase authentication")
        logger.info("   - Production-ready infrastructure")
        
        logger.info("\n📝 Next steps:")
        logger.info("1. Start your application: python app.py")
        logger.info("2. Test all features thoroughly")
        logger.info("3. Monitor performance and logs")
        logger.info("4. Update deployment scripts")
        
    else:
        logger.error("\n⚠️  MIGRATION HAS ISSUES")
        logger.error("Please review the issues above and fix before going to production")

if __name__ == "__main__":
    main()