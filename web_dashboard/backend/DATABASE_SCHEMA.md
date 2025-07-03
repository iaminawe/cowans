# Database Schema Documentation

## Overview

The Product Feed Integration System uses SQLAlchemy ORM with SQLite for development and supports PostgreSQL/MySQL for production. The schema is designed to handle product data synchronization between Etilize FTP and Shopify.

## Database Models

### 1. **User**
Manages user authentication and authorization.
- Fields: id, email, password_hash, first_name, last_name, is_active, is_admin, last_login, created_at, updated_at
- Relationships: jobs, icons, sync_history

### 2. **Category**
Hierarchical product categorization with Shopify collection integration.
- Fields: id, name, slug, description, parent_id, level, path, sort_order, is_active, shopify_collection_id, shopify_handle, shopify_synced_at, meta_data, created_at, updated_at
- Relationships: parent/children (self-referential), products, icons
- Features: Materialized path for efficient queries, hierarchical structure support

### 3. **Product**
Core product information with full Shopify integration.
- Fields: id, sku, name, description, short_description, price, compare_at_price, cost_price, brand, manufacturer, manufacturer_part_number, upc, weight, dimensions, inventory, SEO fields, status, category_id, shopify_product_id, shopify_variant_id, featured_image_url, additional_images, metafields, custom_attributes, created_at, updated_at
- Relationships: category, product_metafields
- Status: draft, active, archived, synced

### 4. **ProductMetafield**
Custom product attributes compatible with Shopify metafields.
- Fields: id, product_id, namespace, key, value, value_type, shopify_metafield_id, shopify_owner_id, description, is_visible, display_order, created_at, updated_at
- Relationships: product
- Features: Type-safe value storage with conversion methods
- Constraint: Unique per product/namespace/key combination

### 5. **Icon**
Category icon management with AI generation tracking.
- Fields: id, category_id, filename, file_path, file_size, file_hash, dimensions, format, prompt, style, color, background, model, status, shopify_image_id, shopify_image_url, generation_time, generation_cost, generation_batch_id, created_by, meta_data, created_at, updated_at
- Relationships: category, created_by_user
- Status: generating, active, inactive, failed

### 6. **ProductImage**
Product image management with deduplication.
- Fields: id, product_id, filename, file_path, url, alt_text, dimensions, file_size, format, file_hash, sort_order, is_featured, is_active, shopify_image_id, shopify_image_url, meta_data, created_at, updated_at
- Relationships: product
- Constraint: Unique file_hash per product for deduplication

### 7. **Job**
Background task tracking for long-running operations.
- Fields: id, job_uuid, script_name, display_name, description, status, progress, current_stage, timing fields, parameters, options, result, error_message, output_log, user_id, priority, retry_count, meta_data
- Relationships: user
- Status: pending, running, completed, failed, cancelled

### 8. **SyncHistory**
Detailed synchronization event tracking.
- Fields: id, sync_type, sync_source, sync_target, status, timing fields, statistics (total_items, processed, successful, failed, skipped), record counts, messages, errors, warnings, file paths, user_id, job_id, meta_data
- Relationships: user, job
- Status: pending, success, failed, partial

### 9. **SystemLog**
Application-level logging for debugging and audit.
- Fields: id, level, message, logger_name, module, function, line_number, user_id, job_id, session_id, request_id, extra_data, stack_trace, created_at
- Relationships: user, job

### 10. **Configuration**
System-wide settings storage.
- Fields: id, key, value, data_type, description, category, is_required, is_encrypted, validation_regex, created_at, updated_at

## Database Features

### Connection Management
- Connection pooling with configurable size and overflow
- Thread-safe session management with scoped sessions
- Automatic connection recycling
- Health check endpoints

### SQLite Optimizations
- WAL (Write-Ahead Logging) mode for better concurrency
- Foreign key constraints enabled
- Optimized synchronous mode
- Connection timeout configuration

### Performance Indexes
- Single column indexes on frequently queried fields
- Composite indexes for common query patterns:
  - products(category_id, status)
  - products(brand, category_id)
  - jobs(user_id, status)
  - sync_history(sync_type, status)
  - icons(category_id, status)
  - system_logs(level, created_at)
  - product_metafields(namespace)
  - product_metafields(product_id, namespace)

### Utilities
- Database backup/restore (SQLite)
- Table statistics and row counts
- Vacuum and analyze commands (SQLite)
- Initial data seeding
- Admin user creation

## Usage Examples

### Initialize Database
```python
from database import init_database

# Default SQLite
init_database()

# Custom database URL
init_database("postgresql://user:pass@localhost/dbname")
```

### Session Management
```python
from database import db_session_scope

# Using context manager
with db_session_scope() as session:
    product = session.query(Product).filter_by(sku="ABC123").first()
    product.price = 19.99
    # Automatically commits on success, rolls back on exception
```

### Create Admin User
```python
from database import DatabaseUtils

DatabaseUtils.create_admin_user(
    email="admin@example.com",
    password="secure_password",
    first_name="Admin",
    last_name="User"
)
```

### Health Check
```python
from database import database_health_check

health = database_health_check()
# Returns: {'status': 'healthy', 'database_url': '...', 'connection_test': True}
```

## Migration Support

The system is designed to work with Alembic for database migrations:
- Auto-generation of migration scripts from model changes
- Version control for schema changes
- Rollback support
- Migration hooks for data transformations

## Best Practices

1. **Always use context managers** for session handling to ensure proper cleanup
2. **Use appropriate indexes** for your query patterns
3. **Implement proper error handling** in database operations
4. **Use transactions** for related operations
5. **Monitor connection pool usage** in production
6. **Regular VACUUM and ANALYZE** for SQLite databases
7. **Backup before migrations** in production