# Performance Optimizations for 2CPU/4GB Server

## Problem
The application was causing 100% CPU usage on deployment due to:
1. Excessive SQLAlchemy connection pooling (30 connections total)
2. Multiple database connections from various imports
3. Memory monitoring threads running in production
4. Gevent workers causing CPU spinning
5. Webpack configuration syntax error

## Solutions Implemented

### 1. Database Connection Pool Optimization
**File:** `web_dashboard/backend/database.py`
- Reduced `pool_size` from 10 to 2
- Reduced `max_overflow` from 20 to 1
- Reduced `pool_recycle` from 3600 to 300 seconds
- Total connections reduced from 30 to 3

### 2. Created Lightweight Database Alternative
**File:** `web_dashboard/backend/database_optimized.py`
- Native psycopg3 implementation without SQLAlchemy overhead
- Connection pool: min=1, max=3 (was 30)
- Automatic connection recycling after 5 minutes idle
- Direct PostgreSQL queries without ORM overhead

### 3. Gunicorn Configuration Updates
**Files:** 
- `web_dashboard/backend/gunicorn.conf.py`
- `web_dashboard/backend/Dockerfile.prod`
- Updated `docker-compose.yml` and `docker-compose.coolify.yml`

**Changes:**
- Workers: 1 (for 2 CPUs)
- Worker class: sync (not gevent)
- Connections: 25 (reduced from 50)
- Threads: 2
- Max requests: 500 (more frequent recycling)
- Request size limits added

### 4. Docker Resource Limits
**Files:** `docker-compose.yml`, `docker-compose.coolify.yml`
- Backend: 0.8 CPU, 1GB RAM
- Celery: 0.5 CPU, 768MB RAM  
- Redis: 0.2 CPU, 256MB RAM (with 200MB data limit)
- Frontend: 0.3 CPU, 256MB RAM
- Total: 1.8 CPU allocation (leaving 0.2 for OS)

### 5. Application Optimizations
**File:** `web_dashboard/backend/app_optimized.py`
- Lazy loading of heavy modules
- Conditional blueprint registration
- Disabled memory monitoring in production
- Simplified logging

### 6. Frontend Fix
**File:** `frontend/webpack.config.js`
- Fixed indentation in plugins array
- Corrected webpack syntax error

### 7. Environment Variables Added
```env
GUNICORN_WORKERS=1
GUNICORN_WORKER_CONNECTIONS=25
GUNICORN_THREADS=2
MEMORY_MONITOR_ENABLED=false
SUPABASE_USE_POOLER=true
```

## Expected Improvements
1. CPU usage should drop from 100% to ~40-60%
2. Memory usage stable under 3GB
3. Database connections reduced by 90%
4. Faster startup time
5. More responsive under load

## Deployment Instructions
1. Use `docker-compose.yml` for Coolify deployment
2. Ensure all environment variables are set
3. Monitor initial deployment for resource usage
4. Adjust limits if needed based on actual usage

## Monitoring
Check resource usage with:
```bash
docker stats
```

Check database connections:
```sql
SELECT count(*) FROM pg_stat_activity WHERE datname = 'postgres';
```

## Future Optimizations
1. Consider replacing SQLAlchemy entirely with psycopg3
2. Implement query result caching
3. Add CDN for static assets
4. Consider using pgBouncer for additional connection pooling