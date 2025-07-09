# Database Integration Guide

## Overview

This document describes the comprehensive SQLite database system that has been integrated into the Cowans Office Supplies Integration System. The database provides persistent storage for products, categories, icons, and all related data, replacing the previous file-based storage approach.

## Database Schema

### Core Tables

#### 1. **products**
Stores product information synchronized from Etilize FTP feeds.
- Primary Key: `id` (UUID)
- Key Fields: `sku`, `manufacturer_part_number`, `name`, `price`, `stock_status`
- Relationships: belongs to `categories`, has many `product_images`, `product_metafields`
- Indexes: `sku`, `manufacturer_part_number`, `category_id`, `shopify_product_id`

#### 2. **categories**
Hierarchical category structure for organizing products.
- Primary Key: `id` (UUID)
- Key Fields: `name`, `slug`, `parent_id`, `path` (materialized path for efficient queries)
- Relationships: self-referential for hierarchy, has many `products`, has one `icon`
- Features: Supports unlimited hierarchy depth with efficient path-based queries

#### 3. **icons**
Tracks AI-generated category icons with full metadata.
- Primary Key: `id` (UUID)  
- Key Fields: `filename`, `model`, `prompt`, `storage_path`, `file_hash`
- Relationships: belongs to `categories`
- Features: Prevents duplicates via SHA256 hash, tracks generation parameters

#### 4. **product_images**
Product image URLs and metadata.
- Primary Key: `id` (UUID)
- Key Fields: `image_url`, `position`, `alt_text`
- Relationships: belongs to `products`

#### 5. **product_metafields**
Flexible key-value storage for product attributes.
- Primary Key: `id` (UUID)
- Key Fields: `namespace`, `key`, `value`, `value_type`
- Relationships: belongs to `products`
- Features: Type-safe value storage with JSON support

#### 6. **sync_history**
Tracks all synchronization events and their outcomes.
- Primary Key: `id` (UUID)
- Key Fields: `sync_type`, `status`, `records_processed`, `errors`
- Features: Comprehensive error tracking and metrics

#### 7. **users**
User accounts for authentication and audit trails.
- Primary Key: `id` (UUID)
- Key Fields: `email`, `username`, `password_hash`
- Features: Secure password hashing, role-based access

#### 8. **jobs**
Background job tracking for async operations.
- Primary Key: `id` (UUID)
- Key Fields: `job_type`, `status`, `progress`, `result`
- Features: Progress tracking, error handling, result storage

## Key Features

### 1. **Automatic Migration**
The system automatically migrates existing JSON-based icon metadata to the database on first run:
```python
# Happens automatically in icon_storage.py
if os.path.exists(metadata_path):
    self._migrate_json_to_db(metadata_path)
```

### 2. **Database Initialization**
Simple initialization with optional test data:
```bash
cd web_dashboard/backend
python init_db.py  # Creates tables and default admin user
```

### 3. **Comprehensive API**
All endpoints now use database models with proper pagination and filtering:

```bash
# Products API
GET /api/products?page=1&per_page=50&category_id=123
GET /api/products/search?q=printer&brand=HP

# Categories API  
GET /api/categories?tree=true  # Returns hierarchical tree
GET /api/categories/123/products?page=1

# Sync History
GET /api/sync-logs?status=success&days=7
```

### 4. **Repository Pattern**
Clean separation of database logic:
```python
# Example usage
from repositories.product_repository import ProductRepository

repo = ProductRepository(db_session)
products = repo.find_by_category(category_id, page=1, per_page=50)
```

### 5. **Database Management CLI**
Powerful command-line interface for database operations:
```bash
# Backup database
python manage_db.py backup

# Health check
python manage_db.py health

# Export data
python manage_db.py export products products.csv

# Import data
python manage_db.py import products products.csv --update

# Seed development data
python manage_db.py seed all
```

## Migration System

### Alembic Integration
Database schema changes are managed through Alembic migrations:

```bash
# Create a new migration after model changes
alembic revision --autogenerate -m "Add new field to products"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

### Migration Files Location
- Configuration: `web_dashboard/backend/alembic.ini`
- Migration scripts: `web_dashboard/backend/migrations/versions/`
- Environment: `web_dashboard/backend/migrations/env.py`

## Development Workflow

### 1. **Initial Setup**
```bash
cd web_dashboard/backend

# Install dependencies
pip install -r requirements.txt

# Initialize database with test data
python init_db.py
python manage_db.py seed all
```

### 2. **Making Schema Changes**
```bash
# 1. Modify models in models.py
# 2. Create migration
alembic revision --autogenerate -m "Description of changes"

# 3. Review generated migration
# 4. Apply migration
alembic upgrade head
```

### 3. **Database Maintenance**
```bash
# Regular cleanup (remove old logs, jobs)
python manage_db.py cleanup --all --days 30

# Backup before major changes
python manage_db.py backup

# Check database health
python manage_db.py health
```

## Performance Optimizations

### 1. **SQLite Specific**
- WAL mode enabled for better concurrency
- Foreign keys enforced
- Strategic indexes on frequently queried columns

### 2. **Query Optimization**
- Materialized paths for efficient category queries
- Eager loading for relationships
- Pagination on all list endpoints

### 3. **Caching Strategy**
- Icon lookups cached in database
- Category hierarchy cached in memory
- Product counts cached per category

## Security Considerations

### 1. **Authentication**
- Passwords hashed with bcrypt
- JWT tokens for API authentication
- Role-based access control ready

### 2. **Data Validation**
- SQLAlchemy validation on all models
- Input sanitization in repositories
- SQL injection prevention via ORM

### 3. **Audit Trail**
- All models include created_at/updated_at timestamps
- User tracking on icon generation
- Comprehensive sync history logging

## Backup and Recovery

### Automated Backups
```python
from db_utils import DatabaseBackupManager

backup_manager = DatabaseBackupManager()
backup_path = backup_manager.create_backup(
    description="Before major update"
)
```

### Manual Backup/Restore
```bash
# Create backup
python manage_db.py backup

# List backups
python manage_db.py list-backups

# Restore from backup
python manage_db.py restore backups/backup_20240115_120000.zip
```

## Testing

### Database Tests
```python
# Test with in-memory SQLite
def test_product_creation():
    engine = create_engine('sqlite:///:memory:')
    # ... test code
```

### Seed Data for Testing
```bash
# Seed specific data types
python manage_db.py seed categories
python manage_db.py seed products --count 100
python manage_db.py seed users
```

## Troubleshooting

### Common Issues

1. **"Database is locked" errors**
   - Solution: WAL mode is enabled by default
   - If persists: Check for long-running transactions

2. **Migration conflicts**
   - Solution: Review migration files before applying
   - Use `alembic history` to check migration order

3. **Performance issues**
   - Run `python manage_db.py health` to check indexes
   - Use `EXPLAIN QUERY PLAN` for slow queries

### Debug Mode
Enable SQL query logging:
```python
# In database.py or app configuration
import logging
logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
```

## Best Practices

1. **Always use transactions** for multi-table operations
2. **Create migrations** for any schema changes
3. **Regular backups** before major updates
4. **Use repositories** instead of direct model access
5. **Test migrations** on a copy before production
6. **Monitor performance** with regular health checks

## API Integration Examples

### Frontend Integration
```javascript
// Fetch products with pagination
const response = await fetch('/api/products?page=1&per_page=50');
const { data, total, page, per_page } = await response.json();

// Search products
const searchResults = await fetch('/api/products/search', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ query: 'printer', category_id: '123' })
});
```

### Python Script Integration
```python
from web_dashboard.backend.database import get_db_session
from web_dashboard.backend.repositories.product_repository import ProductRepository

with get_db_session() as session:
    repo = ProductRepository(session)
    products = repo.get_all(page=1, per_page=100)
```

## Future Enhancements

1. **PostgreSQL Support** - Models are designed to work with both SQLite and PostgreSQL
2. **Full-Text Search** - Can be added with SQLite FTS5 or PostgreSQL extensions
3. **Caching Layer** - Redis integration for high-traffic scenarios
4. **Data Warehousing** - Historical data tracking and analytics

## Conclusion

The database integration provides a robust, scalable foundation for the Cowans Office Supplies Integration System. With comprehensive tooling, proper migrations, and clean architecture, the system is ready for both development and production use.