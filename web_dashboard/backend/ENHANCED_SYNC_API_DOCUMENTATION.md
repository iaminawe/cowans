# Enhanced Sync API Documentation

## Overview

The Enhanced Sync API provides a robust, staged synchronization system between local database and Shopify. It introduces staging tables, version tracking, conflict detection, and approval workflows to ensure data integrity during sync operations.

## Key Features

- **Staged Changes**: Review changes before applying them
- **Version Tracking**: Full history of all changes with rollback capability
- **Conflict Detection**: Intelligent detection of conflicting changes
- **Approval Workflow**: Configurable rules for auto-approval or manual review
- **Batch Processing**: Efficient handling of large sync operations
- **Rollback Support**: Revert applied changes if needed

## API Endpoints

### 1. Pull from Shopify

**Endpoint**: `POST /api/sync/shopify/pull`

Pull products from Shopify and stage changes for review.

**Request Body**:
```json
{
  "batch_name": "Daily Sync",
  "sync_type": "incremental",  // or "full"
  "filters": {
    "updated_since": "2024-01-01T00:00:00Z",
    "collection_id": "123456789"
  }
}
```

**Response**:
```json
{
  "success": true,
  "batch_id": "pull_20250108_123456_1",
  "summary": {
    "total_changes": 150,
    "new_products": 10,
    "updated_products": 140,
    "conflicts": 5,
    "auto_approved": 135
  },
  "message": "Successfully pulled 150 products from Shopify"
}
```

### 2. Get Staged Changes

**Endpoint**: `GET /api/sync/staged`

Retrieve staged changes for review.

**Query Parameters**:
- `batch_id`: Filter by batch ID
- `status`: Filter by status (pending, approved, rejected, applied)
- `change_type`: Filter by change type (create, update, delete)
- `has_conflicts`: Filter by conflict status (true/false)
- `page`: Page number (default: 1)
- `per_page`: Items per page (default: 50)

**Response**:
```json
{
  "success": true,
  "items": [
    {
      "id": 1,
      "change_id": "pull_20250108_123456_1_product_123",
      "product_id": 456,
      "shopify_product_id": "123",
      "change_type": "update",
      "sync_direction": "pull_from_shopify",
      "status": "pending",
      "has_conflicts": true,
      "conflict_fields": ["price", "inventory_quantity"],
      "field_changes": {
        "price": {
          "old": 29.99,
          "new": 34.99
        },
        "inventory_quantity": {
          "old": 100,
          "new": 75
        }
      },
      "current_data": {...},
      "proposed_data": {...},
      "auto_approved": false,
      "created_at": "2025-01-08T12:34:56Z",
      "product": {
        "id": 456,
        "sku": "PROD-123",
        "name": "Example Product"
      }
    }
  ],
  "total": 150,
  "page": 1,
  "per_page": 50,
  "total_pages": 3
}
```

### 3. Approve Staged Change

**Endpoint**: `POST /api/sync/staged/{change_id}/approve`

Approve a single staged change.

**Request Body**:
```json
{
  "notes": "Approved after manual review"
}
```

**Response**:
```json
{
  "success": true,
  "message": "Change approved successfully"
}
```

### 4. Reject Staged Change

**Endpoint**: `POST /api/sync/staged/{change_id}/reject`

Reject a single staged change.

**Request Body**:
```json
{
  "reason": "Price change too significant"
}
```

**Response**:
```json
{
  "success": true,
  "message": "Change rejected successfully"
}
```

### 5. Bulk Approve Changes

**Endpoint**: `POST /api/sync/staged/bulk-approve`

Approve multiple staged changes at once.

**Request Body**:
```json
{
  "change_ids": [1, 2, 3, 4, 5],
  "notes": "Bulk approved non-conflicting changes"
}
```

**Response**:
```json
{
  "success": true,
  "updated": 5,
  "message": "Successfully approved 5 changes"
}
```

### 6. Push to Shopify

**Endpoint**: `POST /api/sync/shopify/push`

Push approved changes to Shopify.

**Request Body**:
```json
{
  "batch_id": "pull_20250108_123456_1",
  "batch_name": "Push approved changes",
  "confirm": true
}
```

Or push specific changes:
```json
{
  "change_ids": [1, 2, 3],
  "batch_name": "Selective push",
  "confirm": true
}
```

**Response**:
```json
{
  "success": true,
  "batch_id": "push_20250108_134567_1",
  "summary": {
    "total_processed": 135,
    "successful": 133,
    "failed": 2,
    "results": [
      {
        "change_id": "pull_20250108_123456_1_product_123",
        "success": true,
        "product_id": 456,
        "message": "Successfully applied update for product PROD-123"
      }
    ]
  },
  "message": "Pushed 133 changes to Shopify"
}
```

### 7. Get Sync Batches

**Endpoint**: `GET /api/sync/batches`

Get sync batch history.

**Query Parameters**:
- `direction`: Filter by sync direction (pull_from_shopify, push_to_shopify)
- `status`: Filter by status (pending, running, completed, failed)
- `page`: Page number
- `per_page`: Items per page

**Response**:
```json
{
  "success": true,
  "items": [
    {
      "id": 1,
      "batch_id": "pull_20250108_123456_1",
      "batch_name": "Daily Sync",
      "sync_type": "incremental",
      "sync_direction": "pull_from_shopify",
      "status": "completed",
      "total_items": 150,
      "processed_items": 150,
      "successful_items": 145,
      "failed_items": 5,
      "created_at": "2025-01-08T12:34:56Z",
      "started_at": "2025-01-08T12:35:00Z",
      "completed_at": "2025-01-08T12:40:00Z",
      "created_by": {
        "id": 1,
        "email": "admin@example.com"
      }
    }
  ],
  "total": 25,
  "page": 1,
  "per_page": 20,
  "total_pages": 2
}
```

### 8. Rollback Change

**Endpoint**: `POST /api/sync/rollback/{change_id}`

Rollback an applied change to its previous state.

**Request Body**:
```json
{
  "reason": "Incorrect price update"
}
```

**Response**:
```json
{
  "success": true,
  "message": "Change rolled back successfully",
  "rollback_id": "rollback_20250108_140000_1"
}
```

## Database Schema

### Staged Product Changes Table

Stores staged changes before they are applied:

```sql
CREATE TABLE staged_product_changes (
    id INTEGER PRIMARY KEY,
    change_id VARCHAR(100) UNIQUE NOT NULL,
    product_id INTEGER REFERENCES products(id),
    shopify_product_id VARCHAR(50),
    change_type VARCHAR(20) NOT NULL,
    sync_direction VARCHAR(30) NOT NULL,
    source_version VARCHAR(64),
    target_version VARCHAR(64),
    current_data JSON,
    proposed_data JSON,
    field_changes JSON,
    has_conflicts BOOLEAN DEFAULT FALSE,
    conflict_fields JSON,
    conflict_resolution JSON,
    status VARCHAR(20) NOT NULL,
    reviewed_by INTEGER REFERENCES users(id),
    reviewed_at TIMESTAMP,
    review_notes TEXT,
    auto_approved BOOLEAN DEFAULT FALSE,
    applied_at TIMESTAMP,
    applied_by INTEGER REFERENCES users(id),
    application_result JSON,
    rollback_data JSON,
    source_system VARCHAR(50),
    batch_id VARCHAR(100),
    priority INTEGER DEFAULT 3,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Sync Versions Table

Tracks version history for rollback support:

```sql
CREATE TABLE sync_versions (
    id INTEGER PRIMARY KEY,
    entity_type VARCHAR(50) NOT NULL,
    entity_id INTEGER NOT NULL,
    shopify_id VARCHAR(50),
    version_hash VARCHAR(64) NOT NULL,
    version_number INTEGER NOT NULL,
    data_snapshot JSON NOT NULL,
    source_system VARCHAR(50) NOT NULL,
    sync_direction VARCHAR(30),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER REFERENCES users(id),
    UNIQUE(entity_type, entity_id, version_number)
);
```

### Sync Batches Table

Tracks sync batch operations:

```sql
CREATE TABLE sync_batches (
    id INTEGER PRIMARY KEY,
    batch_id VARCHAR(100) UNIQUE NOT NULL,
    batch_name VARCHAR(255),
    sync_type VARCHAR(50) NOT NULL,
    sync_direction VARCHAR(30) NOT NULL,
    total_items INTEGER DEFAULT 0,
    processed_items INTEGER DEFAULT 0,
    successful_items INTEGER DEFAULT 0,
    failed_items INTEGER DEFAULT 0,
    skipped_items INTEGER DEFAULT 0,
    status VARCHAR(20) NOT NULL,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    estimated_completion TIMESTAMP,
    processing_rate FLOAT,
    api_calls_made INTEGER DEFAULT 0,
    api_quota_used INTEGER DEFAULT 0,
    error_summary JSON,
    warnings JSON,
    created_by INTEGER NOT NULL REFERENCES users(id),
    cancelled_by INTEGER REFERENCES users(id),
    configuration JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Sync Approval Rules Table

Configurable rules for auto-approval:

```sql
CREATE TABLE sync_approval_rules (
    id INTEGER PRIMARY KEY,
    rule_name VARCHAR(255) NOT NULL,
    rule_description TEXT,
    entity_type VARCHAR(50),
    change_type VARCHAR(20),
    field_patterns JSON,
    value_thresholds JSON,
    requires_approval BOOLEAN DEFAULT TRUE,
    auto_approve_conditions JSON,
    approval_level INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT TRUE,
    priority INTEGER DEFAULT 3,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER REFERENCES users(id)
);
```

## Workflow Examples

### Example 1: Daily Incremental Sync

1. **Pull Changes from Shopify**:
```bash
curl -X POST http://localhost:5001/api/sync/shopify/pull \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "batch_name": "Daily Sync",
    "sync_type": "incremental"
  }'
```

2. **Review Staged Changes**:
```bash
curl http://localhost:5001/api/sync/staged?batch_id=pull_20250108_123456_1 \
  -H "Authorization: Bearer $TOKEN"
```

3. **Bulk Approve Non-Conflicting Changes**:
```bash
curl -X POST http://localhost:5001/api/sync/staged/bulk-approve \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "change_ids": [1, 2, 3, 4, 5],
    "notes": "Auto-approved changes without conflicts"
  }'
```

4. **Apply Approved Changes**:
```bash
curl -X POST http://localhost:5001/api/sync/shopify/push \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "batch_id": "pull_20250108_123456_1",
    "confirm": true
  }'
```

### Example 2: Handling Conflicts

1. **Get Changes with Conflicts**:
```bash
curl "http://localhost:5001/api/sync/staged?has_conflicts=true" \
  -H "Authorization: Bearer $TOKEN"
```

2. **Review Specific Conflict**:
```bash
curl "http://localhost:5001/api/sync/staged/123" \
  -H "Authorization: Bearer $TOKEN"
```

3. **Approve with Resolution Note**:
```bash
curl -X POST http://localhost:5001/api/sync/staged/123/approve \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "notes": "Approved - keeping Shopify price as source of truth"
  }'
```

### Example 3: Rollback

1. **Get Recent Applied Changes**:
```bash
curl "http://localhost:5001/api/sync/staged?status=applied&page=1&per_page=10" \
  -H "Authorization: Bearer $TOKEN"
```

2. **Rollback Specific Change**:
```bash
curl -X POST http://localhost:5001/api/sync/rollback/456 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "Price was updated incorrectly"
  }'
```

## Approval Rules Configuration

### Default Rules

The system comes with default approval rules:

1. **Critical Price Changes**: Require approval for price changes over 20%
2. **Inventory Reduction**: Require approval for inventory reductions over 50%
3. **Minor Updates**: Auto-approve minor updates without conflicts
4. **New Products**: Require approval for new product creation

### Custom Rules

You can create custom approval rules:

```json
{
  "rule_name": "High Value Product Changes",
  "rule_description": "Require approval for changes to products over $100",
  "entity_type": "product",
  "change_type": "update",
  "field_patterns": ["price"],
  "value_thresholds": {
    "min_price": 100
  },
  "requires_approval": true,
  "auto_approve_conditions": {
    "max_price_change": 5
  },
  "priority": 1
}
```

## Performance Considerations

1. **Batch Processing**: The API processes changes in batches for efficiency
2. **Indexed Queries**: All staging tables have appropriate indexes
3. **Parallel Processing**: The sync engine uses parallel workers for better performance
4. **Incremental Sync**: Use incremental sync to reduce data transfer
5. **Pagination**: Always use pagination when retrieving large datasets

## Error Handling

All endpoints return consistent error responses:

```json
{
  "error": "Error message",
  "details": {
    "field": "Additional error context"
  }
}
```

Common HTTP status codes:
- 200: Success
- 400: Bad Request
- 401: Unauthorized
- 404: Not Found
- 409: Conflict
- 500: Internal Server Error

## Security

- All endpoints require authentication via JWT token
- Role-based access control for approval operations
- Audit trail for all changes
- Data encryption in transit and at rest

## Migration

To add the enhanced sync tables to your database:

```bash
cd web_dashboard/backend
alembic upgrade head
```

This will create all necessary tables and indexes for the enhanced sync system.