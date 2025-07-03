"""
Database Utilities Module

This module provides various utilities for database management including
backup, import/export, health checks, and maintenance functions.
"""

import os
import json
import csv
import logging
import shutil
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
import zipfile
import tempfile

from sqlalchemy import text, inspect, func
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from database import db_manager, db_session_scope
from models import (
    Base, User, Category, Product, Icon, Job, SyncHistory, 
    ProductImage, SystemLog, Configuration, ProductStatus, 
    SyncStatus, IconStatus, JobStatus
)

# Configure logging
logger = logging.getLogger(__name__)


class DatabaseBackupManager:
    """Manages database backup operations."""
    
    def __init__(self, backup_dir: str = None):
        """Initialize backup manager."""
        self.backup_dir = backup_dir or os.path.join(
            os.path.dirname(__file__), 'backups'
        )
        os.makedirs(self.backup_dir, exist_ok=True)
    
    def create_backup(self, description: str = None) -> str:
        """Create a full database backup."""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_name = f"backup_{timestamp}"
            
            if description:
                backup_name += f"_{description.replace(' ', '_')}"
            
            backup_path = os.path.join(self.backup_dir, f"{backup_name}.zip")
            
            with tempfile.TemporaryDirectory() as temp_dir:
                # Export database to JSON
                db_export_path = os.path.join(temp_dir, 'database.json')
                self._export_database_to_json(db_export_path)
                
                # Copy SQLite database file if applicable
                if db_manager.database_url.startswith('sqlite'):
                    db_file = db_manager.database_url.replace('sqlite:///', '')
                    if os.path.exists(db_file):
                        shutil.copy2(db_file, os.path.join(temp_dir, 'database.db'))
                
                # Create metadata file
                metadata_path = os.path.join(temp_dir, 'metadata.json')
                with open(metadata_path, 'w') as f:
                    json.dump({
                        'timestamp': timestamp,
                        'description': description,
                        'database_url': db_manager.database_url.split('@')[-1] if '@' in db_manager.database_url else db_manager.database_url,
                        'tables': self._get_table_info()
                    }, f, indent=2)
                
                # Create zip archive
                with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for root, dirs, files in os.walk(temp_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, temp_dir)
                            zipf.write(file_path, arcname)
            
            logger.info(f"Database backup created: {backup_path}")
            return backup_path
            
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            raise
    
    def restore_backup(self, backup_path: str) -> bool:
        """Restore database from backup."""
        try:
            if not os.path.exists(backup_path):
                raise FileNotFoundError(f"Backup file not found: {backup_path}")
            
            with tempfile.TemporaryDirectory() as temp_dir:
                # Extract backup
                with zipfile.ZipFile(backup_path, 'r') as zipf:
                    zipf.extractall(temp_dir)
                
                # Read metadata
                metadata_path = os.path.join(temp_dir, 'metadata.json')
                if os.path.exists(metadata_path):
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)
                    logger.info(f"Restoring backup from {metadata['timestamp']}")
                
                # Restore from JSON export
                db_export_path = os.path.join(temp_dir, 'database.json')
                if os.path.exists(db_export_path):
                    self._import_database_from_json(db_export_path)
                    logger.info("Database restored successfully")
                    return True
                else:
                    logger.error("No database export found in backup")
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to restore backup: {e}")
            raise
    
    def list_backups(self) -> List[Dict[str, Any]]:
        """List available backups."""
        backups = []
        
        for file in os.listdir(self.backup_dir):
            if file.endswith('.zip'):
                file_path = os.path.join(self.backup_dir, file)
                
                try:
                    # Get file info
                    stat = os.stat(file_path)
                    
                    # Try to read metadata
                    metadata = {}
                    with zipfile.ZipFile(file_path, 'r') as zipf:
                        if 'metadata.json' in zipf.namelist():
                            with zipf.open('metadata.json') as f:
                                metadata = json.load(f)
                    
                    backups.append({
                        'filename': file,
                        'path': file_path,
                        'size': stat.st_size,
                        'created': datetime.fromtimestamp(stat.st_ctime),
                        'description': metadata.get('description'),
                        'metadata': metadata
                    })
                    
                except Exception as e:
                    logger.warning(f"Failed to read backup {file}: {e}")
        
        # Sort by creation date
        backups.sort(key=lambda x: x['created'], reverse=True)
        
        return backups
    
    def cleanup_old_backups(self, keep_days: int = 30) -> int:
        """Remove backups older than specified days."""
        cutoff_date = datetime.now() - timedelta(days=keep_days)
        removed_count = 0
        
        for backup in self.list_backups():
            if backup['created'] < cutoff_date:
                try:
                    os.remove(backup['path'])
                    logger.info(f"Removed old backup: {backup['filename']}")
                    removed_count += 1
                except Exception as e:
                    logger.error(f"Failed to remove backup {backup['filename']}: {e}")
        
        return removed_count
    
    def _export_database_to_json(self, output_path: str) -> None:
        """Export entire database to JSON."""
        data = {}
        
        with db_session_scope() as session:
            # Get all table names
            inspector = inspect(db_manager.engine)
            tables = inspector.get_table_names()
            
            for table_name in tables:
                if table_name.startswith('sqlite_'):
                    continue
                
                # Get model class
                model_class = None
                for mapper in Base.registry.mappers:
                    if mapper.class_.__tablename__ == table_name:
                        model_class = mapper.class_
                        break
                
                if model_class:
                    # Query all records
                    records = session.query(model_class).all()
                    
                    # Convert to dictionaries
                    table_data = []
                    for record in records:
                        record_dict = {}
                        for column in inspector.get_columns(table_name):
                            col_name = column['name']
                            value = getattr(record, col_name, None)
                            
                            # Handle special types
                            if isinstance(value, datetime):
                                value = value.isoformat()
                            elif hasattr(value, 'value'):  # Enum
                                value = value.value
                            
                            record_dict[col_name] = value
                        
                        table_data.append(record_dict)
                    
                    data[table_name] = table_data
        
        # Write to file
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _import_database_from_json(self, input_path: str) -> None:
        """Import database from JSON."""
        with open(input_path, 'r') as f:
            data = json.load(f)
        
        with db_session_scope() as session:
            # Clear existing data (be careful!)
            for table_name in reversed(list(data.keys())):
                session.execute(text(f"DELETE FROM {table_name}"))
            
            # Import data
            for table_name, records in data.items():
                # Get model class
                model_class = None
                for mapper in Base.registry.mappers:
                    if mapper.class_.__tablename__ == table_name:
                        model_class = mapper.class_
                        break
                
                if model_class:
                    for record_data in records:
                        # Convert datetime strings back to datetime objects
                        for key, value in record_data.items():
                            if isinstance(value, str) and 'T' in value:
                                try:
                                    record_data[key] = datetime.fromisoformat(value)
                                except:
                                    pass
                        
                        # Create instance
                        instance = model_class(**record_data)
                        session.add(instance)
            
            session.commit()
    
    def _get_table_info(self) -> Dict[str, int]:
        """Get record counts for all tables."""
        return db_manager.get_table_stats()


class DatabaseImportExport:
    """Handles data import and export operations."""
    
    @staticmethod
    def export_products_to_csv(output_path: str, category_id: Optional[int] = None) -> int:
        """Export products to CSV file."""
        try:
            with db_session_scope() as session:
                query = session.query(Product)
                
                if category_id:
                    query = query.filter(Product.category_id == category_id)
                
                products = query.all()
                
                if not products:
                    logger.warning("No products found to export")
                    return 0
                
                # Write CSV
                with open(output_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=[
                        'sku', 'name', 'description', 'price', 'compare_at_price',
                        'brand', 'manufacturer', 'manufacturer_part_number',
                        'category_id', 'status', 'inventory_quantity',
                        'featured_image_url', 'shopify_product_id'
                    ])
                    
                    writer.writeheader()
                    
                    for product in products:
                        writer.writerow({
                            'sku': product.sku,
                            'name': product.name,
                            'description': product.description,
                            'price': product.price,
                            'compare_at_price': product.compare_at_price,
                            'brand': product.brand,
                            'manufacturer': product.manufacturer,
                            'manufacturer_part_number': product.manufacturer_part_number,
                            'category_id': product.category_id,
                            'status': product.status,
                            'inventory_quantity': product.inventory_quantity,
                            'featured_image_url': product.featured_image_url,
                            'shopify_product_id': product.shopify_product_id
                        })
                
                logger.info(f"Exported {len(products)} products to {output_path}")
                return len(products)
                
        except Exception as e:
            logger.error(f"Failed to export products: {e}")
            raise
    
    @staticmethod
    def import_products_from_csv(input_path: str, update_existing: bool = False) -> Dict[str, int]:
        """Import products from CSV file."""
        stats = {
            'total': 0,
            'created': 0,
            'updated': 0,
            'errors': 0
        }
        
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                with db_session_scope() as session:
                    for row in reader:
                        stats['total'] += 1
                        
                        try:
                            # Check if product exists
                            existing = session.query(Product).filter_by(
                                sku=row['sku']
                            ).first()
                            
                            if existing and not update_existing:
                                continue
                            
                            # Prepare product data
                            product_data = {
                                'sku': row['sku'],
                                'name': row['name'],
                                'description': row.get('description'),
                                'price': float(row['price']) if row.get('price') else 0,
                                'brand': row.get('brand'),
                                'manufacturer': row.get('manufacturer'),
                                'manufacturer_part_number': row.get('manufacturer_part_number'),
                                'category_id': int(row['category_id']) if row.get('category_id') else 1,
                                'status': row.get('status', ProductStatus.DRAFT.value),
                                'inventory_quantity': int(row.get('inventory_quantity', 0))
                            }
                            
                            if row.get('compare_at_price'):
                                product_data['compare_at_price'] = float(row['compare_at_price'])
                            
                            if row.get('featured_image_url'):
                                product_data['featured_image_url'] = row['featured_image_url']
                            
                            if existing:
                                # Update existing product
                                for key, value in product_data.items():
                                    setattr(existing, key, value)
                                stats['updated'] += 1
                            else:
                                # Create new product
                                product = Product(**product_data)
                                session.add(product)
                                stats['created'] += 1
                                
                        except Exception as e:
                            logger.error(f"Error importing product {row.get('sku', 'unknown')}: {e}")
                            stats['errors'] += 1
                    
                    session.commit()
            
            logger.info(f"Import completed: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Failed to import products: {e}")
            raise
    
    @staticmethod
    def export_categories_to_json(output_path: str) -> int:
        """Export category hierarchy to JSON."""
        try:
            with db_session_scope() as session:
                categories = session.query(Category).order_by(
                    Category.level, Category.sort_order
                ).all()
                
                # Build hierarchy
                category_dict = {}
                root_categories = []
                
                for category in categories:
                    cat_data = {
                        'id': category.id,
                        'name': category.name,
                        'slug': category.slug,
                        'description': category.description,
                        'level': category.level,
                        'sort_order': category.sort_order,
                        'shopify_collection_id': category.shopify_collection_id,
                        'children': []
                    }
                    
                    category_dict[category.id] = cat_data
                    
                    if category.parent_id:
                        parent = category_dict.get(category.parent_id)
                        if parent:
                            parent['children'].append(cat_data)
                    else:
                        root_categories.append(cat_data)
                
                # Write to file
                with open(output_path, 'w') as f:
                    json.dump(root_categories, f, indent=2)
                
                logger.info(f"Exported {len(categories)} categories to {output_path}")
                return len(categories)
                
        except Exception as e:
            logger.error(f"Failed to export categories: {e}")
            raise


class DatabaseHealthChecker:
    """Performs database health checks and diagnostics."""
    
    @staticmethod
    def run_health_check() -> Dict[str, Any]:
        """Run comprehensive health check."""
        health_report = {
            'timestamp': datetime.now().isoformat(),
            'status': 'healthy',
            'checks': {},
            'warnings': [],
            'errors': []
        }
        
        try:
            # Basic connectivity check
            connection_health = db_manager.health_check()
            health_report['checks']['connection'] = connection_health
            
            if connection_health.get('status') != 'healthy':
                health_report['status'] = 'unhealthy'
                health_report['errors'].append('Database connection failed')
                return health_report
            
            # Table statistics
            table_stats = db_manager.get_table_stats()
            health_report['checks']['tables'] = table_stats
            
            # Check for orphaned records
            orphans = DatabaseHealthChecker._check_orphaned_records()
            if orphans:
                health_report['warnings'].append(f"Found {len(orphans)} orphaned records")
                health_report['checks']['orphaned_records'] = orphans
            
            # Check indexes
            missing_indexes = DatabaseHealthChecker._check_indexes()
            if missing_indexes:
                health_report['warnings'].append(f"Missing {len(missing_indexes)} indexes")
                health_report['checks']['missing_indexes'] = missing_indexes
            
            # Check for large tables
            large_tables = DatabaseHealthChecker._check_large_tables()
            if large_tables:
                health_report['warnings'].append(f"Found {len(large_tables)} large tables")
                health_report['checks']['large_tables'] = large_tables
            
            # Check disk usage (SQLite only)
            if db_manager.database_url.startswith('sqlite'):
                disk_usage = DatabaseHealthChecker._check_disk_usage()
                health_report['checks']['disk_usage'] = disk_usage
            
            # Determine overall status
            if health_report['errors']:
                health_report['status'] = 'unhealthy'
            elif health_report['warnings']:
                health_report['status'] = 'degraded'
            
            return health_report
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            health_report['status'] = 'unhealthy'
            health_report['errors'].append(str(e))
            return health_report
    
    @staticmethod
    def _check_orphaned_records() -> List[Dict[str, Any]]:
        """Check for orphaned records."""
        orphans = []
        
        with db_session_scope() as session:
            # Check products without categories
            orphaned_products = session.query(Product).filter(
                ~Product.category_id.in_(
                    session.query(Category.id)
                )
            ).count()
            
            if orphaned_products > 0:
                orphans.append({
                    'table': 'products',
                    'count': orphaned_products,
                    'description': 'Products with non-existent category_id'
                })
            
            # Check icons without categories
            orphaned_icons = session.query(Icon).filter(
                ~Icon.category_id.in_(
                    session.query(Category.id)
                )
            ).count()
            
            if orphaned_icons > 0:
                orphans.append({
                    'table': 'icons',
                    'count': orphaned_icons,
                    'description': 'Icons with non-existent category_id'
                })
        
        return orphans
    
    @staticmethod
    def _check_indexes() -> List[str]:
        """Check for missing indexes."""
        missing_indexes = []
        
        # This is a simplified check - in production, you'd want more comprehensive index analysis
        inspector = inspect(db_manager.engine)
        
        # Define expected indexes
        expected_indexes = {
            'products': ['sku', 'manufacturer_part_number', 'shopify_product_id'],
            'categories': ['slug', 'shopify_collection_id'],
            'users': ['email'],
            'jobs': ['job_uuid', 'status']
        }
        
        for table_name, expected_cols in expected_indexes.items():
            try:
                indexes = inspector.get_indexes(table_name)
                indexed_columns = set()
                
                for index in indexes:
                    indexed_columns.update(index['column_names'])
                
                for col in expected_cols:
                    if col not in indexed_columns:
                        missing_indexes.append(f"{table_name}.{col}")
                        
            except Exception as e:
                logger.warning(f"Failed to check indexes for {table_name}: {e}")
        
        return missing_indexes
    
    @staticmethod
    def _check_large_tables(threshold: int = 10000) -> List[Dict[str, Any]]:
        """Check for tables with many records."""
        large_tables = []
        
        table_stats = db_manager.get_table_stats()
        
        for table, count in table_stats.items():
            if isinstance(count, int) and count > threshold:
                large_tables.append({
                    'table': table,
                    'count': count,
                    'threshold': threshold
                })
        
        return large_tables
    
    @staticmethod
    def _check_disk_usage() -> Dict[str, Any]:
        """Check disk usage for SQLite database."""
        db_file = db_manager.database_url.replace('sqlite:///', '')
        
        if os.path.exists(db_file):
            stat = os.stat(db_file)
            
            # Check WAL file
            wal_file = f"{db_file}-wal"
            wal_size = 0
            if os.path.exists(wal_file):
                wal_size = os.path.getsize(wal_file)
            
            return {
                'database_file': db_file,
                'size_bytes': stat.st_size,
                'size_mb': round(stat.st_size / 1024 / 1024, 2),
                'wal_size_bytes': wal_size,
                'wal_size_mb': round(wal_size / 1024 / 1024, 2),
                'total_size_mb': round((stat.st_size + wal_size) / 1024 / 1024, 2)
            }
        
        return {}


class DatabaseMaintenanceUtils:
    """Database maintenance and cleanup utilities."""
    
    @staticmethod
    def cleanup_old_logs(days: int = 30) -> int:
        """Remove system logs older than specified days."""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            with db_session_scope() as session:
                deleted = session.query(SystemLog).filter(
                    SystemLog.created_at < cutoff_date
                ).delete()
                
                session.commit()
                
                logger.info(f"Deleted {deleted} old system logs")
                return deleted
                
        except Exception as e:
            logger.error(f"Failed to cleanup logs: {e}")
            raise
    
    @staticmethod
    def cleanup_completed_jobs(days: int = 7) -> int:
        """Remove completed jobs older than specified days."""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            with db_session_scope() as session:
                deleted = session.query(Job).filter(
                    Job.status.in_([JobStatus.COMPLETED.value, JobStatus.FAILED.value]),
                    Job.created_at < cutoff_date
                ).delete()
                
                session.commit()
                
                logger.info(f"Deleted {deleted} old jobs")
                return deleted
                
        except Exception as e:
            logger.error(f"Failed to cleanup jobs: {e}")
            raise
    
    @staticmethod
    def rebuild_category_paths() -> int:
        """Rebuild materialized paths for categories."""
        try:
            updated = 0
            
            with db_session_scope() as session:
                # Get all categories ordered by level
                categories = session.query(Category).order_by(
                    Category.level
                ).all()
                
                for category in categories:
                    # Build path
                    path_parts = [str(category.id)]
                    current = category
                    
                    while current.parent_id:
                        current = session.query(Category).filter_by(
                            id=current.parent_id
                        ).first()
                        if current:
                            path_parts.insert(0, str(current.id))
                        else:
                            break
                    
                    new_path = '/'.join(path_parts)
                    
                    if category.path != new_path:
                        category.path = new_path
                        category.level = len(path_parts) - 1
                        updated += 1
                
                session.commit()
                
                logger.info(f"Updated paths for {updated} categories")
                return updated
                
        except Exception as e:
            logger.error(f"Failed to rebuild category paths: {e}")
            raise
    
    @staticmethod
    def fix_orphaned_records() -> Dict[str, int]:
        """Fix or remove orphaned records."""
        stats = {
            'products_fixed': 0,
            'icons_removed': 0,
            'images_removed': 0
        }
        
        try:
            with db_session_scope() as session:
                # Get default category (create if doesn't exist)
                default_category = session.query(Category).filter_by(
                    slug='uncategorized'
                ).first()
                
                if not default_category:
                    default_category = Category(
                        name='Uncategorized',
                        slug='uncategorized',
                        description='Default category for orphaned products',
                        level=0,
                        path='1'
                    )
                    session.add(default_category)
                    session.flush()
                
                # Fix orphaned products
                orphaned_products = session.query(Product).filter(
                    ~Product.category_id.in_(
                        session.query(Category.id)
                    )
                ).all()
                
                for product in orphaned_products:
                    product.category_id = default_category.id
                    stats['products_fixed'] += 1
                
                # Remove orphaned icons
                stats['icons_removed'] = session.query(Icon).filter(
                    ~Icon.category_id.in_(
                        session.query(Category.id)
                    )
                ).delete()
                
                # Remove orphaned product images
                stats['images_removed'] = session.query(ProductImage).filter(
                    ~ProductImage.product_id.in_(
                        session.query(Product.id)
                    )
                ).delete()
                
                session.commit()
                
                logger.info(f"Fixed orphaned records: {stats}")
                return stats
                
        except Exception as e:
            logger.error(f"Failed to fix orphaned records: {e}")
            raise
    
    @staticmethod
    def optimize_database() -> bool:
        """Run database optimization."""
        try:
            # Vacuum and analyze for SQLite
            if db_manager.database_url.startswith('sqlite'):
                with db_manager.engine.connect() as conn:
                    conn.execute(text("VACUUM"))
                    conn.execute(text("ANALYZE"))
                    conn.commit()
                
                logger.info("Database optimized (VACUUM and ANALYZE completed)")
            
            # For PostgreSQL
            elif 'postgresql' in db_manager.database_url:
                with db_manager.engine.connect() as conn:
                    conn.execute(text("VACUUM ANALYZE"))
                    conn.commit()
                
                logger.info("Database optimized (VACUUM ANALYZE completed)")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to optimize database: {e}")
            return False
    
    @staticmethod
    def reset_sequences() -> bool:
        """Reset primary key sequences."""
        try:
            if 'postgresql' in db_manager.database_url:
                with db_manager.engine.connect() as conn:
                    # Get all tables
                    result = conn.execute(text(
                        "SELECT tablename FROM pg_tables WHERE schemaname='public'"
                    ))
                    tables = [row[0] for row in result]
                    
                    for table in tables:
                        # Reset sequence
                        conn.execute(text(
                            f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                            f"COALESCE((SELECT MAX(id) FROM {table}), 1), false)"
                        ))
                    
                    conn.commit()
                
                logger.info("Reset sequences for all tables")
                return True
            
            # SQLite handles this automatically
            return True
            
        except Exception as e:
            logger.error(f"Failed to reset sequences: {e}")
            return False


# Export main classes and functions
__all__ = [
    'DatabaseBackupManager',
    'DatabaseImportExport',
    'DatabaseHealthChecker',
    'DatabaseMaintenanceUtils'
]