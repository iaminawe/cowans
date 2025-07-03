"""
Migration: 001
Description: Initial schema creation
"""

from migrations.base_migration import BaseMigration
from sqlalchemy.orm import Session
from models import Base, create_performance_indexes


class Migration_001(BaseMigration):
    """Initial schema creation migration."""
    
    def __init__(self):
        super().__init__(
            version="001",
            description="Initial schema creation"
        )
    
    def upgrade(self, session: Session) -> None:
        """Create initial database schema."""
        # Create all tables
        Base.metadata.create_all(session.bind)
        
        # Create performance indexes
        create_performance_indexes(session.bind)
        
        # Seed initial configuration data
        self._seed_initial_data(session)
    
    def downgrade(self, session: Session) -> None:
        """Drop all tables."""
        # Drop all tables
        Base.metadata.drop_all(session.bind)
    
    def can_rollback(self) -> bool:
        """Check if this migration can be rolled back."""
        return True
    
    def validate_upgrade(self, session: Session) -> bool:
        """Validate that the upgrade was successful."""
        try:
            # Check if key tables exist
            from models import User, Product, Category, Job, Icon, SyncHistory, Configuration
            
            # Try to query each table
            session.query(User).count()
            session.query(Product).count()
            session.query(Category).count()
            session.query(Job).count()
            session.query(Icon).count()
            session.query(SyncHistory).count()
            session.query(Configuration).count()
            
            return True
        except Exception:
            return False
    
    def validate_downgrade(self, session: Session) -> bool:
        """Validate that the downgrade was successful."""
        try:
            # Check if tables are dropped
            from sqlalchemy import inspect
            inspector = inspect(session.bind)
            tables = inspector.get_table_names()
            
            # Should have no application tables (only migration_history)
            app_tables = [t for t in tables if t != 'migration_history']
            return len(app_tables) == 0
        except Exception:
            return False
    
    def _seed_initial_data(self, session: Session) -> None:
        """Seed initial configuration data."""
        from models import Configuration
        
        # Default configurations
        default_configs = [
            {
                'key': 'system.version',
                'value': '1.0.0',
                'category': 'system',
                'description': 'System version',
                'data_type': 'string'
            },
            {
                'key': 'system.initialized_at',
                'value': '2025-01-01T00:00:00Z',
                'category': 'system',
                'description': 'System initialization timestamp',
                'data_type': 'string'
            },
            {
                'key': 'sync.auto_sync_enabled',
                'value': 'false',
                'data_type': 'boolean',
                'category': 'sync',
                'description': 'Enable automatic synchronization',
                'is_required': False
            },
            {
                'key': 'sync.batch_size',
                'value': '100',
                'data_type': 'integer',
                'category': 'sync',
                'description': 'Default batch size for sync operations',
                'is_required': False
            },
            {
                'key': 'sync.retry_attempts',
                'value': '3',
                'data_type': 'integer',
                'category': 'sync',
                'description': 'Number of retry attempts for failed sync operations',
                'is_required': False
            },
            {
                'key': 'icons.default_style',
                'value': 'modern',
                'category': 'icons',
                'description': 'Default icon generation style',
                'data_type': 'string'
            },
            {
                'key': 'icons.default_color',
                'value': '#3B82F6',
                'category': 'icons',
                'description': 'Default icon color in hex format',
                'data_type': 'string'
            },
            {
                'key': 'icons.default_size',
                'value': '128',
                'data_type': 'integer',
                'category': 'icons',
                'description': 'Default icon size in pixels',
                'is_required': False
            },
            {
                'key': 'icons.batch_size',
                'value': '5',
                'data_type': 'integer',
                'category': 'icons',
                'description': 'Default batch size for icon generation',
                'is_required': False
            },
            {
                'key': 'shopify.rate_limit_delay',
                'value': '0.5',
                'data_type': 'float',
                'category': 'shopify',
                'description': 'Delay between Shopify API calls in seconds',
                'is_required': False
            },
            {
                'key': 'jobs.default_timeout',
                'value': '3600',
                'data_type': 'integer',
                'category': 'jobs',
                'description': 'Default job timeout in seconds',
                'is_required': False
            },
            {
                'key': 'jobs.retention_days',
                'value': '30',
                'data_type': 'integer',
                'category': 'jobs',
                'description': 'Number of days to retain job history',
                'is_required': False
            },
            {
                'key': 'logging.level',
                'value': 'INFO',
                'category': 'logging',
                'description': 'Default logging level',
                'data_type': 'string'
            },
            {
                'key': 'logging.retention_days',
                'value': '90',
                'data_type': 'integer',
                'category': 'logging',
                'description': 'Number of days to retain log entries',
                'is_required': False
            }
        ]
        
        for config_data in default_configs:
            # Check if configuration already exists
            existing = session.query(Configuration).filter_by(key=config_data['key']).first()
            if not existing:
                config = Configuration(**config_data)
                session.add(config)
        
        session.commit()
        
        # Create root categories
        from models import Category
        root_categories = [
            {
                'name': 'Office Supplies',
                'slug': 'office-supplies',
                'description': 'General office supplies and equipment',
                'level': 0,
                'path': '/office-supplies',
                'sort_order': 1
            },
            {
                'name': 'Technology',
                'slug': 'technology',
                'description': 'Technology products and accessories',
                'level': 0,
                'path': '/technology',
                'sort_order': 2
            },
            {
                'name': 'Furniture',
                'slug': 'furniture',
                'description': 'Office furniture and seating',
                'level': 0,
                'path': '/furniture',
                'sort_order': 3
            },
            {
                'name': 'Stationery',
                'slug': 'stationery',
                'description': 'Pens, pencils, and writing supplies',
                'level': 0,
                'path': '/stationery',
                'sort_order': 4
            }
        ]
        
        for category_data in root_categories:
            # Check if category already exists
            existing = session.query(Category).filter_by(slug=category_data['slug']).first()
            if not existing:
                category = Category(**category_data)
                session.add(category)
        
        session.commit()