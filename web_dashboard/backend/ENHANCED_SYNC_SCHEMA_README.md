# Enhanced Sync System Database Schema

## Overview

The enhanced sync system introduces a comprehensive database schema for managing bi-directional synchronization between local products and Shopify, with additional support for Xorosoft inventory integration. The system provides staging capabilities, version tracking, conflict resolution, and performance monitoring.

## Key Features

### 1. **Staging Tables**
- `products_staging` - Temporary storage for product changes before sync
- Allows review and approval of changes before committing
- Supports batch operations and conflict detection

### 2. **Sync Operations Management**
- `sync_operations` - Tracks all sync operations with detailed statistics
- `sync_conflicts` - Manages and resolves data conflicts
- `sync_rollbacks` - Enables rollback of sync operations

### 3. **Version Tracking**
- `product_versions` - Complete version history for products
- `category_versions` - Version history for categories
- Supports rollback to previous versions
- Tracks who made changes and when

### 4. **Xorosoft Integration**
- `xorosoft_products` - Stock and inventory data from Xorosoft
- `xorosoft_sync_logs` - Tracks Xorosoft sync operations
- Real-time inventory updates

### 5. **Performance Monitoring**
- `sync_performance_logs` - Detailed performance metrics
- Identifies bottlenecks and optimization opportunities
- Tracks API usage and rate limiting

## Database Tables

### Core Sync Tables

#### `products_staging`
Staging area for product changes before synchronization.

Key fields:
- `source_product_id` - Reference to original product
- `change_type` - Type of change (create, update, delete)
- `change_data` - Specific fields that changed
- `has_conflicts` - Flag indicating conflicts
- `sync_operation_id` - Associated sync operation

#### `sync_operations`
Tracks sync operations and their lifecycle.

Key fields:
- `operation_uuid` - Unique identifier
- `sync_direction` - Direction of sync (up/down/bidirectional)
- `status` - Current status (pending, in_progress, completed, failed)
- `statistics` - Detailed counts of items processed
- `is_rollbackable` - Whether operation can be rolled back

#### `sync_conflicts`
Manages conflicts between local and remote data.

Key fields:
- `conflict_type` - Type of conflict
- `local_value` / `remote_value` - Conflicting values
- `resolution_strategy` - How conflict was resolved
- `auto_resolvable` - Whether conflict can be auto-resolved
- `severity` - Impact level of conflict

### Version Tracking Tables

#### `product_versions`
Complete version history for products.

Key fields:
- `version_number` - Sequential version number
- `product_data` - Complete snapshot of product state
- `changed_fields` - List of fields that changed
- `change_source` - Where change originated

#### `category_versions`
Version history for categories.

Similar structure to product_versions but for category data.

### Xorosoft Integration Tables

#### `xorosoft_products`
Stock and inventory data from Xorosoft system.

Key fields:
- `xorosoft_id` - Xorosoft's product identifier
- `stock_on_hand` - Current stock level
- `stock_available` - Available for sale
- `warehouse_code` - Location information
- `cost_price` - Current cost from Xorosoft

#### `xorosoft_sync_logs`
Tracks synchronization with Xorosoft.

Key fields:
- `sync_type` - Type of sync (stock_update, price_update, full_sync)
- `statistics` - Records processed, updated, failed
- `import_file` / `export_file` - File references if applicable

### Supporting Tables

#### `sync_rollbacks`
Tracks rollback operations for sync operations.

Key fields:
- `original_operation_id` - Operation being rolled back
- `rollback_type` - Full, partial, or selective
- `backup_data` - Snapshot before original operation

#### `sync_performance_logs`
Performance metrics for sync operations.

Key fields:
- `total_duration` - Total time taken
- `api_calls_count` - Number of API calls made
- `items_per_second` - Throughput metric
- `bottleneck_stage` - Identified performance bottleneck

## Enhanced Product Table Fields

The main `products` table has been enhanced with:
- `version` - Current version number
- `last_sync_version` - Version at last sync
- `sync_locked` - Prevents concurrent modifications
- `sync_locked_by` - User who locked the record
- `xorosoft_id` - Link to Xorosoft system
- `stock_synced_at` - Last stock update time

## Migration Instructions

1. **Backup your database** before applying migrations
2. Run the migration script:
   ```bash
   python apply_enhanced_sync_migration.py
   ```
3. Verify all tables were created successfully
4. Update application code to use new models

## Usage Examples

### Creating a Sync Operation
```python
from models_sync_enhanced import SyncOperation
from uuid import uuid4

sync_op = SyncOperation(
    operation_uuid=str(uuid4()),
    name="Daily Product Sync",
    operation_type="full_sync",
    sync_direction="down",
    created_by=user_id
)
session.add(sync_op)
session.commit()
```

### Staging Product Changes
```python
from models_sync_enhanced import ProductsStaging

staged_product = ProductsStaging(
    source_product_id=product.id,
    sku=product.sku,
    name=new_name,
    change_type="update",
    change_data={"name": {"old": product.name, "new": new_name}},
    sync_operation_id=sync_op.id,
    staged_by=user_id
)
session.add(staged_product)
session.commit()
```

### Recording Conflicts
```python
from models_sync_enhanced import SyncConflict

conflict = SyncConflict(
    conflict_uuid=str(uuid4()),
    sync_operation_id=sync_op.id,
    product_id=product.id,
    conflict_type="field_mismatch",
    field_name="price",
    local_value="19.99",
    remote_value="24.99",
    severity="high"
)
session.add(conflict)
session.commit()
```

## Best Practices

1. **Always use staging** for batch operations
2. **Check for conflicts** before applying changes
3. **Version sensitive data** for audit trails
4. **Monitor performance** to optimize sync operations
5. **Implement proper locking** to prevent race conditions

## Performance Considerations

- Indexes are created on all foreign keys and commonly queried fields
- JSON fields are used for flexible metadata storage
- Staging tables prevent blocking on main product tables
- Version tables use efficient snapshot storage

## Security Notes

- All operations track the user who initiated them
- Sync operations can be restricted by user permissions
- Sensitive data in conflicts should be handled carefully
- Rollback operations require elevated permissions