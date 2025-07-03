# Database System Documentation

This document provides comprehensive documentation for the Product Feed Integration System's database architecture.

## Overview

The database system is built using SQLAlchemy ORM with support for both SQLite (development) and PostgreSQL (production). It includes a complete migration system for schema management and utilities for database operations.

## Architecture

### Core Components

1. **Models** (`models.py`) - SQLAlchemy models for all entities
2. **Database Manager** (`database.py`) - Connection and session management
3. **Migration System** (`migrations/`) - Schema versioning and migration tools
4. **CLI Management** (`manage_db.py`) - Command-line interface for database operations

### Database Schema

The system includes the following main entities:

#### Core Entities

- **User**: Authentication and audit trails
- **Category**: Hierarchical product categories with Shopify collection mapping
- **Product**: Complete product information with Shopify integration
- **Icon**: Category icons with generation metadata and sync status
- **Job**: Background task tracking with progress monitoring
- **SyncHistory**: Data synchronization event tracking

#### Supporting Entities

- **ProductImage**: Product image management with deduplication
- **SystemLog**: Application-level logging
- **Configuration**: System settings and configuration

## Setup and Installation

### 1. Install Dependencies

```bash
cd /Users/iaminawe/Sites/cowans/web_dashboard/backend
pip install -r requirements.txt
```

### 2. Configure Database

Set environment variables in your `.env` file:

```env
# Development (SQLite)
DATABASE_URL=sqlite:///dev_database.db

# Production (PostgreSQL)
DATABASE_URL=postgresql://user:password@localhost/production_db

# Optional database settings
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20
DATABASE_POOL_TIMEOUT=30
DATABASE_POOL_RECYCLE=3600
DATABASE_ECHO=false

# Migration settings
MIGRATION_AUTO_UPGRADE=false
MIGRATION_BACKUP_BEFORE_UPGRADE=true
```

### 3. Initialize Database

```bash
# Initialize database and run initial migration
python manage_db.py init

# Or run migrations manually
python manage_db.py migrate
```

## Database Management

### Using the CLI Tool

The `manage_db.py` script provides comprehensive database management:

```bash
# Initialize database
python manage_db.py init

# Show migration status
python manage_db.py status

# Run migrations
python manage_db.py migrate

# Rollback to specific version
python manage_db.py rollback 001

# Create new migration
python manage_db.py create-migration "Add new field to products"

# Create admin user
python manage_db.py create-admin admin@example.com password123

# Backup database
python manage_db.py backup --backup-path backup.db

# Restore database
python manage_db.py restore backup.db

# Show database information
python manage_db.py info

# Optimize database (SQLite only)
python manage_db.py optimize
```

### Programmatic Usage

```python
from database import init_database, db_session_scope
from models import User, Product, Category

# Initialize database
init_database()

# Using session scope
with db_session_scope() as session:
    # Query users
    users = session.query(User).all()
    
    # Create new product
    product = Product(
        sku="TEST001",
        name="Test Product",
        price=19.99,
        category_id=1
    )
    session.add(product)
    # Session automatically commits or rolls back
```

## Schema Details

### User Model

```python
class User(Base):
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    first_name = Column(String(100))
    last_name = Column(String(100))
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    # ... timestamps and relationships
```

### Product Model

```python
class Product(Base):
    id = Column(Integer, primary_key=True)
    sku = Column(String(100), unique=True, nullable=False)
    name = Column(String(500), nullable=False)
    description = Column(Text)
    price = Column(Float, nullable=False)
    
    # Product attributes
    brand = Column(String(200))
    manufacturer = Column(String(200))
    manufacturer_part_number = Column(String(200))
    
    # Shopify integration
    shopify_product_id = Column(String(50))
    shopify_synced_at = Column(DateTime)
    
    # Category relationship
    category_id = Column(Integer, ForeignKey('categories.id'))
    # ... additional fields
```

### Category Model

```python
class Category(Base):
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False)
    parent_id = Column(Integer, ForeignKey('categories.id'))
    level = Column(Integer, default=0)
    path = Column(String(500))  # Materialized path
    
    # Shopify integration
    shopify_collection_id = Column(String(50))
    shopify_handle = Column(String(255))
    # ... additional fields
```

## Migration System

### Creating Migrations

```bash
# Create new migration
python manage_db.py create-migration "Description of changes"
```

This creates a new migration file in `migrations/versions/` with the following structure:

```python
class Migration_YYYYMMDD_HHMMSS(BaseMigration):
    def __init__(self):
        super().__init__(
            version="YYYYMMDD_HHMMSS",
            description="Description of changes"
        )
    
    def upgrade(self, session: Session) -> None:
        """Upgrade the database schema."""
        # Add your upgrade logic here
        pass
    
    def downgrade(self, session: Session) -> None:
        """Downgrade the database schema."""
        # Add your downgrade logic here
        pass
```

### Migration Best Practices

1. **Always test migrations** on a copy of production data
2. **Write reversible migrations** when possible
3. **Backup before major migrations** (automatic with `MIGRATION_BACKUP_BEFORE_UPGRADE=true`)
4. **Use descriptive migration names** that explain the changes
5. **Validate migrations** by implementing `validate_upgrade()` and `validate_downgrade()`

## Performance Considerations

### Indexing Strategy

The system includes comprehensive indexing for common query patterns:

- **Primary keys** on all tables
- **Foreign key indexes** for relationship queries
- **Unique indexes** for business keys (SKU, email, etc.)
- **Composite indexes** for common multi-field queries
- **Partial indexes** for conditional queries

### Query Optimization

1. **Use session scopes** for transactional operations
2. **Leverage eager loading** for relationships with `joinedload()` or `selectinload()`
3. **Use query pagination** for large result sets
4. **Monitor slow queries** with database logging

### SQLite Optimizations

For SQLite databases, the system automatically applies:

- **WAL mode** for better concurrency
- **Foreign key constraints** enabled
- **Connection pooling** with proper settings
- **Regular VACUUM and ANALYZE** operations

## Security Considerations

### Data Protection

1. **Password hashing** using Werkzeug's secure hash functions
2. **SQL injection prevention** through parameterized queries
3. **Foreign key constraints** to maintain referential integrity
4. **Input validation** at the model level

### Access Control

1. **User authentication** through the User model
2. **Admin privileges** with `is_admin` flag
3. **Audit trails** with created_at/updated_at timestamps
4. **Session management** through SQLAlchemy sessions

## Monitoring and Maintenance

### Health Checks

```python
from database import database_health_check

health = database_health_check()
print(health)  # {'status': 'healthy', 'connection_test': True, ...}
```

### Backup and Recovery

```bash
# Create backup
python manage_db.py backup --backup-path "backup_$(date +%Y%m%d_%H%M%S).db"

# Restore from backup
python manage_db.py restore backup_20250101_120000.db
```

### Log Management

System logs are stored in the `system_logs` table and can be queried:

```python
from models import SystemLog

with db_session_scope() as session:
    recent_errors = session.query(SystemLog)\
        .filter(SystemLog.level == 'ERROR')\
        .order_by(SystemLog.created_at.desc())\
        .limit(10).all()
```

## Troubleshooting

### Common Issues

1. **Migration failures**: Check logs in migration output and validate schema changes
2. **Connection issues**: Verify DATABASE_URL and network connectivity
3. **Permission errors**: Ensure database user has required privileges
4. **Lock timeouts**: Check for long-running transactions

### Debug Mode

Enable SQL logging for debugging:

```env
DATABASE_ECHO=true
```

Or programmatically:

```python
import logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
```

### Performance Issues

1. **Check query performance** with EXPLAIN ANALYZE
2. **Monitor connection pool** usage
3. **Review index usage** with database tools
4. **Optimize frequent queries** with proper indexing

## Integration with Flask Application

The database system integrates seamlessly with the Flask application:

```python
from flask import Flask
from database import init_database, db_session_scope
from models import User

app = Flask(__name__)

# Initialize database on startup
with app.app_context():
    init_database()

@app.route('/users')
def get_users():
    with db_session_scope() as session:
        users = session.query(User).all()
        return jsonify([{'id': u.id, 'email': u.email} for u in users])
```

## Future Enhancements

### Planned Features

1. **Multi-tenant support** with tenant isolation
2. **Read replicas** for improved performance
3. **Sharding support** for horizontal scaling
4. **Advanced caching** with Redis integration
5. **Database versioning** for blue-green deployments

### Extensibility

The modular design allows for easy extension:

1. **Custom models** by extending Base
2. **Additional migrations** following the established pattern
3. **Database plugins** through the DatabaseManager interface
4. **Custom utilities** in the DatabaseUtils class

## Support and Documentation

For additional help:

1. Check the inline documentation in model files
2. Review migration examples in `migrations/versions/`
3. Use the CLI help: `python manage_db.py --help`
4. Enable debug logging for detailed operation traces