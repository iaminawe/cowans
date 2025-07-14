# Optimization Strategy for High-Concurrency Operations

## Context
- **Few concurrent users** (low web traffic)
- **Many concurrent operations** (Shopify sync, icon generation, batch updates)
- **Current issue**: 100% CPU usage from poor connection pooling

## Revised Strategy

### 1. Database Configuration for Operations

Since you have many operations but few users, you need:
- **More connections** for parallel operations
- **Better connection lifecycle** management
- **Operation tracking** to prevent connection leaks

**New Configuration (`database_operations.py`):**
```python
pool_size=5          # 5 base connections (was 2)
max_overflow=10      # Can burst to 15 total (was 1)
pool_timeout=30      # Wait for connections
pool_recycle=600     # 10-minute recycling
```

### 2. Celery Optimization

**Worker Configuration:**
```python
worker_concurrency = 4           # 4 parallel workers
worker_prefetch_multiplier = 1   # One task at a time
worker_max_tasks_per_child = 100 # Restart after 100 tasks
```

**Queue Prioritization:**
- `sync` - Priority 1 (Shopify sync)
- `generation` - Priority 2 (Icon generation)
- `batch` - Priority 3 (Batch updates)
- `import` - Priority 4 (Data imports)

### 3. Connection Management Best Practices

**For Operations:**
```python
# Track operations
with db_manager.session_scope(operation_id="shopify_sync_123") as session:
    # Your operation code
    pass

# Batch operations with auto-commit
@batch_operation("import_products", batch_size=100)
def import_products(session, products):
    for product in products:
        session.add(product)
        session.batch_commit()  # Auto-commits every 100
```

### 4. Resource Allocation (Adjusted)

For your use case, adjust Docker limits:

```yaml
backend:
  deploy:
    resources:
      limits:
        cpus: '0.5'    # Less CPU for web (few users)
        memory: 768M   # Less memory for web
        
celery:
  deploy:
    resources:
      limits:
        cpus: '1.2'    # More CPU for operations
        memory: 2G     # More memory for operations
```

### 5. Implementation Steps

1. **Replace database.py:**
```python
# In app.py, change:
from database import db_manager

# To:
from database_operations import db_manager
```

2. **Update Celery config:**
```python
# In celery_app.py
app.config_from_object('celery_config_optimized')
```

3. **Add monitoring endpoint:**
```python
@app.route('/api/health/pool')
def pool_status():
    return jsonify(db_manager.get_pool_status())
```

### 6. Environment Variables

```env
# Database
DATABASE_URL=postgresql+psycopg://...pooler.supabase.com...
SUPABASE_USE_POOLER=true

# Celery  
CELERY_WORKER_CONCURRENCY=4
CELERY_WORKER_MAX_TASKS_PER_CHILD=100

# Operations
MAX_CONCURRENT_OPERATIONS=15
OPERATION_TIMEOUT=300
```

### 7. Monitoring Operations

Check active operations:
```python
# In your logs, you'll see:
# "Operation shopify_sync_123 started - Active operations: 5"
# "Operation shopify_sync_123 completed - Active operations: 4"
```

Database connections:
```sql
-- Active queries by operation
SELECT 
    pid,
    application_name,
    state,
    query_start,
    substring(query, 1, 50) as query_preview
FROM pg_stat_activity
WHERE datname = 'postgres'
ORDER BY query_start;
```

### 8. Why This Works Better

1. **Connection Pooling**: 15 connections can handle many operations
2. **Operation Tracking**: Know exactly what's using connections
3. **Batch Commits**: Reduce transaction overhead
4. **Queue Priorities**: Important operations get resources first
5. **Worker Recycling**: Prevent memory leaks in long-running operations

### 9. Expected Improvements

- **CPU Usage**: Should drop to 30-50% during operations
- **Operation Speed**: 2-3x faster with proper pooling
- **Memory Stable**: Worker recycling prevents leaks
- **Better Debugging**: Operation tracking shows bottlenecks

### 10. SQLAlchemy Decision

For your use case, **keep SQLAlchemy** because:
- Operations benefit from ORM features (relationships, lazy loading)
- Batch operations work well with SQLAlchemy sessions
- The overhead is minimal with proper pooling
- Migration risk not worth it for operational workloads

The key is using the right pool size for operations, not eliminating the ORM.