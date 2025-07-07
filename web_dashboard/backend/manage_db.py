#!/usr/bin/env python3
"""
Database Management CLI

This script provides command-line interface for database management operations.
"""

import os
import sys
import argparse
import logging
from datetime import datetime
import json

# Add the backend directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import DatabaseUtils, init_database as initialize_db, db_manager
from db_utils import (
    DatabaseBackupManager, 
    DatabaseImportExport, 
    DatabaseHealthChecker, 
    DatabaseMaintenanceUtils
)
from seed_data import DevelopmentDataSeeder, CategorySeeder, ProductSeeder, UserSeeder
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_database_url():
    """Get database URL from configuration."""
    # Check environment variable first
    db_url = os.environ.get('DATABASE_URL')
    if db_url:
        return db_url
    
    # Default to SQLite database
    db_path = os.path.join(os.path.dirname(__file__), 'database.db')
    return f"sqlite:///{db_path}"


def init_database(args):
    """Initialize database."""
    try:
        logger.info("Initializing database...")
        
        # Use the init_database function from database module
        initialize_db(create_tables=True)
        
        # Seed initial data
        DatabaseUtils.seed_initial_data()
        
        logger.info("Database initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        sys.exit(1)


def create_migration(args):
    """Create a new migration using Alembic."""
    logger.info("Please use 'alembic revision --autogenerate -m \"description\"' to create migrations")
    logger.info("This command should be run from the backend directory where alembic.ini is located")


def migrate_up(args):
    """Run migrations up."""
    logger.info("Please use 'alembic upgrade head' to apply all migrations")
    logger.info("Or 'alembic upgrade +1' to apply the next migration")
    logger.info("This command should be run from the backend directory where alembic.ini is located")


def migrate_down(args):
    """Run migrations down."""
    logger.info("Please use 'alembic downgrade -1' to rollback one migration")
    logger.info("Or 'alembic downgrade <revision>' to rollback to a specific revision")
    logger.info("This command should be run from the backend directory where alembic.ini is located")


def migration_status(args):
    """Show migration status."""
    logger.info("Please use 'alembic current' to see the current migration")
    logger.info("Or 'alembic history' to see all migrations")
    logger.info("This command should be run from the backend directory where alembic.ini is located")


def create_admin_user(args):
    """Create admin user."""
    try:
        # Ensure database is initialized
        if not db_manager.engine:
            initialize_db()
            
        success = DatabaseUtils.create_admin_user(
            email=args.email,
            password=args.password,
            first_name=args.first_name,
            last_name=args.last_name
        )
        
        if success:
            logger.info(f"Admin user created: {args.email}")
        else:
            logger.error("Failed to create admin user")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Failed to create admin user: {e}")
        sys.exit(1)


def backup_database(args):
    """Backup database."""
    try:
        # Ensure database is initialized
        if not db_manager.engine:
            initialize_db()
        
        backup_manager = DatabaseBackupManager()
        
        # Create backup with optional description
        backup_path = backup_manager.create_backup(
            description=args.description or "Manual backup via CLI"
        )
        
        if backup_path:
            logger.info(f"Database backup created: {backup_path}")
        else:
            logger.error("Failed to create database backup")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Failed to backup database: {e}")
        sys.exit(1)


def restore_database(args):
    """Restore database."""
    try:
        backup_manager = DatabaseBackupManager()
        
        success = backup_manager.restore_backup(args.backup_path)
        
        if success:
            logger.info(f"Database restored from: {args.backup_path}")
            # Re-initialize database after restore
            initialize_db()
        else:
            logger.error("Failed to restore database")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Failed to restore database: {e}")
        sys.exit(1)


def database_info(args):
    """Show database information."""
    try:
        # Ensure database is initialized
        if not db_manager.engine:
            initialize_db()
        
        print("\n=== Database Information ===")
        print(f"Database URL: {get_database_url()}")
        
        # Get table statistics using DatabaseUtils
        stats = DatabaseUtils.get_table_stats()
        
        print(f"\n=== Table Statistics ===")
        for table, count in stats.items():
            print(f"{table}: {count} records")
        
        # Check database health
        checker = DatabaseHealthChecker(db_manager.engine)
        report = checker.run_health_check()
        
        print(f"\n=== Health Status ===")
        print(f"Status: {report['status'].upper()}")
        print(f"Connection: {'✓ Connected' if report['status'] != 'unhealthy' else '✗ Disconnected'}")
        
        if report.get('warnings'):
            print(f"\nWarnings: {len(report['warnings'])}")
        
        print()
        
    except Exception as e:
        logger.error(f"Failed to get database info: {e}")
        sys.exit(1)


def optimize_database(args):
    """Optimize database."""
    try:
        # Ensure database is initialized
        if not db_manager.engine:
            initialize_db()
            
        success = DatabaseMaintenanceUtils.optimize_database()
        if success:
            logger.info("Database optimization completed")
        else:
            logger.error("Database optimization failed")
            sys.exit(1)
        
    except Exception as e:
        logger.error(f"Failed to optimize database: {e}")
        sys.exit(1)


def seed_data(args):
    """Seed development data."""
    try:
        # Ensure database is initialized
        if not db_manager.engine:
            logger.info("Initializing database before seeding...")
            initialize_db()
        
        if args.type == 'all':
            results = DevelopmentDataSeeder.seed_all(include_large_dataset=args.large)
            print(f"\nSeeding results: {json.dumps(results, indent=2)}")
        elif args.type == 'categories':
            results = CategorySeeder.seed_default_categories()
            print(f"\nCategory seeding results: {results}")
        elif args.type == 'products':
            count = args.count or 100
            results = ProductSeeder.seed_sample_products(count)
            print(f"\nProduct seeding results: {results}")
        elif args.type == 'users':
            results = UserSeeder.seed_test_users()
            print(f"\nUser seeding results: {results}")
        
        logger.info("Data seeding completed")
        
    except Exception as e:
        logger.error(f"Failed to seed data: {e}")
        sys.exit(1)


def health_check(args):
    """Run database health check."""
    try:
        # Ensure database is initialized
        if not db_manager.engine:
            initialize_db()
        
        checker = DatabaseHealthChecker(db_manager.engine)
        report = checker.run_health_check()
        
        print("\n=== Database Health Report ===")
        print(f"Timestamp: {report['timestamp']}")
        print(f"Status: {report['status'].upper()}")
        
        if report.get('errors'):
            print(f"\nErrors ({len(report['errors'])}):")
            for error in report['errors']:
                print(f"  - {error}")
        
        if report.get('warnings'):
            print(f"\nWarnings ({len(report['warnings'])}):")
            for warning in report['warnings']:
                print(f"  - {warning}")
        
        if report.get('checks'):
            print("\nDetailed Checks:")
            for check_name, check_data in report['checks'].items():
                print(f"\n  {check_name}:")
                if isinstance(check_data, dict):
                    for key, value in check_data.items():
                        print(f"    - {key}: {value}")
                else:
                    print(f"    {check_data}")
        
        print()
        
        # Exit with appropriate code
        if report['status'] == 'unhealthy':
            sys.exit(1)
        elif report['status'] == 'degraded':
            sys.exit(2)
        
    except Exception as e:
        logger.error(f"Failed to run health check: {e}")
        sys.exit(1)


def export_data(args):
    """Export data from database."""
    try:
        if args.format == 'csv':
            if args.table == 'products':
                count = DatabaseImportExport.export_products_to_csv(
                    args.output,
                    category_id=args.category_id
                )
                logger.info(f"Exported {count} products to {args.output}")
            else:
                logger.error(f"CSV export not supported for table: {args.table}")
                sys.exit(1)
        
        elif args.format == 'json':
            if args.table == 'categories':
                count = DatabaseImportExport.export_categories_to_json(args.output)
                logger.info(f"Exported {count} categories to {args.output}")
            else:
                logger.error(f"JSON export not supported for table: {args.table}")
                sys.exit(1)
        
        else:
            logger.error(f"Unsupported export format: {args.format}")
            sys.exit(1)
        
    except Exception as e:
        logger.error(f"Failed to export data: {e}")
        sys.exit(1)


def import_data(args):
    """Import data into database."""
    try:
        if args.format == 'csv':
            if args.table == 'products':
                stats = DatabaseImportExport.import_products_from_csv(
                    args.input,
                    update_existing=args.update
                )
                logger.info(f"Import completed: {stats}")
            else:
                logger.error(f"CSV import not supported for table: {args.table}")
                sys.exit(1)
        
        else:
            logger.error(f"Unsupported import format: {args.format}")
            sys.exit(1)
        
    except Exception as e:
        logger.error(f"Failed to import data: {e}")
        sys.exit(1)


def cleanup(args):
    """Run database cleanup operations."""
    try:
        results = {}
        
        # Cleanup old logs
        if args.logs:
            deleted = DatabaseMaintenanceUtils.cleanup_old_logs(days=args.days)
            results['logs_deleted'] = deleted
            logger.info(f"Deleted {deleted} old logs")
        
        # Cleanup old jobs
        if args.jobs:
            deleted = DatabaseMaintenanceUtils.cleanup_completed_jobs(days=args.days)
            results['jobs_deleted'] = deleted
            logger.info(f"Deleted {deleted} old jobs")
        
        # Fix orphaned records
        if args.orphans:
            stats = DatabaseMaintenanceUtils.fix_orphaned_records()
            results['orphans_fixed'] = stats
            logger.info(f"Fixed orphaned records: {stats}")
        
        # Rebuild category paths
        if args.paths:
            updated = DatabaseMaintenanceUtils.rebuild_category_paths()
            results['paths_rebuilt'] = updated
            logger.info(f"Rebuilt {updated} category paths")
        
        # Cleanup old backups
        if args.backups:
            backup_manager = DatabaseBackupManager()
            removed = backup_manager.cleanup_old_backups(keep_days=args.days)
            results['backups_removed'] = removed
            logger.info(f"Removed {removed} old backups")
        
        print(f"\nCleanup results: {json.dumps(results, indent=2)}")
        
    except Exception as e:
        logger.error(f"Failed to run cleanup: {e}")
        sys.exit(1)


def list_backups(args):
    """List available backups."""
    try:
        backup_manager = DatabaseBackupManager()
        backups = backup_manager.list_backups()
        
        if not backups:
            print("No backups found.")
            return
        
        print("\n=== Available Backups ===")
        print(f"Total: {len(backups)}")
        print()
        
        for backup in backups:
            print(f"File: {backup['filename']}")
            print(f"  Created: {backup['created']}")
            print(f"  Size: {backup['size'] / 1024 / 1024:.2f} MB")
            if backup.get('description'):
                print(f"  Description: {backup['description']}")
            print()
        
    except Exception as e:
        logger.error(f"Failed to list backups: {e}")
        sys.exit(1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Database Management CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Init command
    init_parser = subparsers.add_parser('init', help='Initialize database')
    init_parser.set_defaults(func=init_database)
    
    # Create migration command
    create_migration_parser = subparsers.add_parser('create-migration', help='Create new migration')
    create_migration_parser.add_argument('description', help='Migration description')
    create_migration_parser.add_argument('--version', help='Migration version (auto-generated if not provided)')
    create_migration_parser.set_defaults(func=create_migration)
    
    # Migrate up command
    migrate_up_parser = subparsers.add_parser('migrate', help='Run migrations up')
    migrate_up_parser.add_argument('--target', help='Target version')
    migrate_up_parser.add_argument('--applied-by', help='Applied by user')
    migrate_up_parser.set_defaults(func=migrate_up)
    
    # Migrate down command
    migrate_down_parser = subparsers.add_parser('rollback', help='Run migrations down')
    migrate_down_parser.add_argument('target', help='Target version')
    migrate_down_parser.add_argument('--rolled-back-by', help='Rolled back by user')
    migrate_down_parser.set_defaults(func=migrate_down)
    
    # Migration status command
    status_parser = subparsers.add_parser('status', help='Show migration status')
    status_parser.set_defaults(func=migration_status)
    
    # Create admin user command
    admin_parser = subparsers.add_parser('create-admin', help='Create admin user')
    admin_parser.add_argument('email', help='Admin email')
    admin_parser.add_argument('password', help='Admin password')
    admin_parser.add_argument('--first-name', help='First name')
    admin_parser.add_argument('--last-name', help='Last name')
    admin_parser.set_defaults(func=create_admin_user)
    
    # Backup command
    backup_parser = subparsers.add_parser('backup', help='Backup database')
    backup_parser.add_argument('--backup-path', help='Backup file path')
    backup_parser.set_defaults(func=backup_database)
    
    # Restore command
    restore_parser = subparsers.add_parser('restore', help='Restore database')
    restore_parser.add_argument('backup_path', help='Backup file path')
    restore_parser.set_defaults(func=restore_database)
    
    # Info command
    info_parser = subparsers.add_parser('info', help='Show database information')
    info_parser.set_defaults(func=database_info)
    
    # Optimize command
    optimize_parser = subparsers.add_parser('optimize', help='Optimize database')
    optimize_parser.set_defaults(func=optimize_database)
    
    # Seed data command
    seed_parser = subparsers.add_parser('seed', help='Seed development data')
    seed_parser.add_argument('type', choices=['all', 'categories', 'products', 'users'], 
                            help='Type of data to seed')
    seed_parser.add_argument('--count', type=int, help='Number of items to create (for products)')
    seed_parser.add_argument('--large', action='store_true', help='Include large dataset')
    seed_parser.set_defaults(func=seed_data)
    
    # Health check command
    health_parser = subparsers.add_parser('health', help='Run database health check')
    health_parser.set_defaults(func=health_check)
    
    # Export command
    export_parser = subparsers.add_parser('export', help='Export data from database')
    export_parser.add_argument('table', choices=['products', 'categories'], help='Table to export')
    export_parser.add_argument('output', help='Output file path')
    export_parser.add_argument('--format', choices=['csv', 'json'], default='csv', help='Export format')
    export_parser.add_argument('--category-id', type=int, help='Filter by category ID (products only)')
    export_parser.set_defaults(func=export_data)
    
    # Import command
    import_parser = subparsers.add_parser('import', help='Import data into database')
    import_parser.add_argument('table', choices=['products'], help='Table to import')
    import_parser.add_argument('input', help='Input file path')
    import_parser.add_argument('--format', choices=['csv'], default='csv', help='Import format')
    import_parser.add_argument('--update', action='store_true', help='Update existing records')
    import_parser.set_defaults(func=import_data)
    
    # Cleanup command
    cleanup_parser = subparsers.add_parser('cleanup', help='Run database cleanup operations')
    cleanup_parser.add_argument('--logs', action='store_true', help='Cleanup old logs')
    cleanup_parser.add_argument('--jobs', action='store_true', help='Cleanup old jobs')
    cleanup_parser.add_argument('--orphans', action='store_true', help='Fix orphaned records')
    cleanup_parser.add_argument('--paths', action='store_true', help='Rebuild category paths')
    cleanup_parser.add_argument('--backups', action='store_true', help='Cleanup old backups')
    cleanup_parser.add_argument('--all', action='store_true', help='Run all cleanup operations')
    cleanup_parser.add_argument('--days', type=int, default=30, help='Days to keep (default: 30)')
    cleanup_parser.set_defaults(func=cleanup)
    
    # List backups command
    list_backups_parser = subparsers.add_parser('list-backups', help='List available backups')
    list_backups_parser.set_defaults(func=list_backups)
    
    # Parse arguments
    args = parser.parse_args()
    
    # Handle cleanup --all flag
    if hasattr(args, 'all') and args.all:
        args.logs = True
        args.jobs = True
        args.orphans = True
        args.paths = True
        args.backups = True
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Execute command
    args.func(args)


if __name__ == '__main__':
    main()