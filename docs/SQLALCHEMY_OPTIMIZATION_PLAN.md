# SQLAlchemy Optimization Plan

## Current Situation
- SQLAlchemy is deeply integrated (models, repositories, APIs)
- Causing high CPU usage due to connection pooling
- Full replacement would require 2-3 weeks of refactoring

## Immediate Optimizations (Already Applied)

### 1. Connection Pool Reduction
```python
# Before: 30 total connections
pool_size=10, max_overflow=20

# After: 3 total connections  
pool_size=2, max_overflow=1
```

### 2. Alternative Implementations Created
- `database_optimized.py` - Pure psycopg3 implementation
- `database_minimal.py` - SQLAlchemy with minimal pooling

## Recommended Approach: Keep SQLAlchemy, Optimize Aggressively

### Option 1: No Connection Pooling (Best for Low Traffic)
```python
# Set environment variable
DISABLE_POOLING=true

# Uses NullPool - each request gets fresh connection
# Pros: Zero idle connections, minimal resources
# Cons: Slight connection overhead per request
```

### Option 2: Single Connection Reuse (Good Balance)
```python
# Default behavior in database_minimal.py
# Uses StaticPool - one connection reused
# Pros: No connection overhead, minimal resources
# Cons: Single connection bottleneck
```

### Option 3: Hybrid Approach
```python
# Use SQLAlchemy for complex queries
# Use psycopg3 for simple queries
# Gradually migrate hot paths
```

## Implementation Steps

### 1. Quick Win (5 minutes)
Replace database.py import in app.py:
```python
# Change this:
from database import db_manager, init_database, db_session_scope

# To this:
from database_minimal import db_manager, init_database, db_session_scope
```

### 2. Environment Variables
```bash
# Add to .env
DISABLE_POOLING=true  # For zero pooling
# or
DISABLE_POOLING=false # For static pool
```

### 3. Monitor Performance
```sql
-- Check active connections
SELECT count(*) FROM pg_stat_activity 
WHERE datname = 'postgres' AND state = 'active';

-- Check idle connections  
SELECT count(*) FROM pg_stat_activity 
WHERE datname = 'postgres' AND state = 'idle';
```

## Why Not Replace SQLAlchemy Entirely?

### Effort Required:
1. **Models** - Convert 20+ SQLAlchemy models to dataclasses
2. **Repositories** - Rewrite 11 repository classes
3. **APIs** - Update 20+ API endpoints
4. **Migrations** - Replace Alembic with custom system
5. **Testing** - Rewrite all database tests
6. **Risk** - High chance of introducing bugs

### Time Estimate: 2-3 weeks

### Alternative: Gradual Migration
1. Keep SQLAlchemy for complex operations
2. Use psycopg3 for new features
3. Migrate hot paths over time
4. No downtime or risk

## Conclusion

**Recommendation**: Use `database_minimal.py` with `DISABLE_POOLING=true` for immediate relief. This gives you:
- SQLAlchemy compatibility (no code changes)
- Minimal resource usage (no idle connections)
- Easy rollback if needed
- Time to plan gradual migration

The full replacement isn't worth the effort unless you're seeing continued issues after optimization.