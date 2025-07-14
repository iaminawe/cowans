# Shopify Sync Technical Troubleshooting Guide

## Overview

This guide provides detailed troubleshooting steps for technical issues with the Shopify sync system. It's intended for developers and technical support staff.

## Table of Contents

1. [Diagnostic Tools](#diagnostic-tools)
2. [Common Issues and Solutions](#common-issues-and-solutions)
3. [Backend Troubleshooting](#backend-troubleshooting)
4. [Frontend Troubleshooting](#frontend-troubleshooting)
5. [WebSocket Issues](#websocket-issues)
6. [Database Issues](#database-issues)
7. [Performance Issues](#performance-issues)
8. [Emergency Procedures](#emergency-procedures)

## Diagnostic Tools

### 1. System Health Check

```bash
# Run comprehensive health check
python web_dashboard/backend/scripts/health_check.py

# Check specific components
python web_dashboard/backend/scripts/check_shopify_connection.py
python scripts/database/check_database_status.py
python web_dashboard/backend/scripts/check_websocket_status.py
```

### 2. Log Analysis

```bash
# View backend logs
tail -f web_dashboard/backend/logs/app.log
tail -f web_dashboard/backend/logs/sync.log
tail -f web_dashboard/backend/logs/websocket.log

# Search for errors
grep -i error web_dashboard/backend/logs/*.log
grep -i "sync failed" web_dashboard/backend/logs/sync.log

# View frontend console logs
# Open browser DevTools > Console
```

### 3. Database Queries

```sql
-- Check sync status
SELECT 
    COUNT(*) as total,
    COUNT(shopify_product_id) as synced,
    COUNT(*) - COUNT(shopify_product_id) as not_synced
FROM products;

-- Recent sync operations
SELECT * FROM sync_batches 
ORDER BY created_at DESC 
LIMIT 10;

-- Failed sync attempts
SELECT * FROM sync_history 
WHERE status = 'error' 
ORDER BY created_at DESC;

-- Staged changes pending
SELECT COUNT(*) FROM staged_product_changes 
WHERE status = 'pending';
```

## Common Issues and Solutions

### Issue 1: WebSocket Connection Failures

**Symptoms:**
- Red connection indicator
- No real-time updates
- Console errors: "WebSocket connection failed"

**Diagnostic Steps:**
```javascript
// Browser console
console.log(localStorage.getItem('auth_token'));
// Check if token exists

// Test WebSocket manually
const ws = new WebSocket('ws://localhost:3560/socket.io/?EIO=4&transport=websocket');
ws.onopen = () => console.log('Connected');
ws.onerror = (e) => console.error('Error:', e);
```

**Solutions:**

1. **Missing Auth Token**
   ```javascript
   // Force re-authentication
   localStorage.removeItem('auth_token');
   window.location.href = '/login';
   ```

2. **CORS Issues**
   ```python
   # backend/app.py
   socketio = SocketIO(
       app,
       cors_allowed_origins=["http://localhost:3055", "http://localhost:3056"],
       # Add your frontend URL
   )
   ```

3. **Firewall/Proxy Blocking**
   - Check if port 3560 is open
   - Try polling transport instead of WebSocket
   ```javascript
   // Force polling transport
   const socket = io(url, {
     transports: ['polling']
   });
   ```

### Issue 2: Sync Operations Not Starting

**Symptoms:**
- Clicking sync has no effect
- No progress indicators
- No error messages

**Diagnostic Steps:**
```bash
# Check API endpoint
curl -X POST http://localhost:3560/api/shopify/sync-down/start \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"sync_type": "full"}'

# Check backend logs
tail -f web_dashboard/backend/logs/app.log | grep sync
```

**Solutions:**

1. **Missing Shopify Credentials**
   ```bash
   # Check .env file
   grep SHOPIFY .env
   
   # Should see:
   # SHOPIFY_SHOP_URL=store.myshopify.com
   # SHOPIFY_ACCESS_TOKEN=shpat_xxxxx
   ```

2. **Database Lock**
   ```sql
   -- Check for locks
   SELECT * FROM pg_locks WHERE NOT granted;
   
   -- Kill blocking queries
   SELECT pg_cancel_backend(pid) 
   FROM pg_stat_activity 
   WHERE state = 'active' AND query_start < now() - interval '5 minutes';
   ```

3. **Rate Limiting**
   ```python
   # Check rate limit status
   python -c "
   from web_dashboard.backend.app import redis_client
   print(redis_client.get('shopify_rate_limit'))
   "
   ```

### Issue 3: Products Showing Wrong Sync Status

**Symptoms:**
- Status doesn't match reality
- Inconsistent icons
- Status not updating

**Diagnostic Steps:**
```sql
-- Check product sync status
SELECT 
    id,
    name,
    shopify_product_id,
    shopify_sync_status,
    shopify_synced_at
FROM products
WHERE shopify_sync_status IS NOT NULL
ORDER BY shopify_synced_at DESC
LIMIT 20;

-- Check for orphaned records
SELECT p.* FROM products p
LEFT JOIN shopify_products sp ON p.shopify_product_id = sp.id
WHERE p.shopify_product_id IS NOT NULL AND sp.id IS NULL;
```

**Solutions:**

1. **Rebuild Sync Status**
   ```python
   # Run sync status rebuild
   python web_dashboard/backend/scripts/rebuild_sync_status.py
   ```

2. **Clear Frontend Cache**
   ```javascript
   // Browser console
   localStorage.clear();
   sessionStorage.clear();
   location.reload();
   ```

3. **Update Status Manually**
   ```sql
   -- Reset sync status for investigation
   UPDATE products 
   SET shopify_sync_status = NULL 
   WHERE shopify_sync_status = 'error';
   ```

## Backend Troubleshooting

### Flask Application Issues

**1. Application Won't Start**
```bash
# Check for port conflicts
lsof -i :3560

# Kill existing process
kill -9 $(lsof -t -i:3560)

# Start with debug mode
FLASK_ENV=development python web_dashboard/backend/app.py
```

**2. Import Errors**
```bash
# Reinstall dependencies
cd web_dashboard/backend
pip install -r requirements.txt

# Check Python path
python -c "import sys; print('\n'.join(sys.path))"
```

**3. Database Connection Errors**
```python
# Test database connection
python -c "
from web_dashboard.backend.database import db_session
with db_session() as session:
    print('Connected successfully')
"
```

### Shopify API Issues

**1. Authentication Failures**
```python
# Test Shopify connection
from scripts.shopify.shopify_base import ShopifyAPIBase
client = ShopifyAPIBase(shop_url, access_token)
result = client.execute_graphql('{shop{name}}')
print(result)
```

**2. GraphQL Errors**
```python
# Enable debug mode
client = ShopifyAPIBase(shop_url, access_token, debug=True)
# This will print all GraphQL queries and responses
```

**3. Rate Limit Handling**
```python
# Check rate limit headers
import requests
response = requests.get(
    f"https://{shop_url}/admin/api/2024-01/shop.json",
    headers={"X-Shopify-Access-Token": access_token}
)
print(response.headers.get('X-Shopify-Shop-Api-Call-Limit'))
```

## Frontend Troubleshooting

### React Application Issues

**1. Components Not Rendering**
```javascript
// Check for errors in console
// Enable React Developer Tools
// Check component tree

// Add debug logging
console.log('Component props:', props);
console.log('Component state:', state);
```

**2. API Call Failures**
```javascript
// Debug API calls
window.localStorage.setItem('debug', 'api:*');

// Intercept all API calls
const originalFetch = window.fetch;
window.fetch = (...args) => {
  console.log('Fetch:', args);
  return originalFetch(...args)
    .then(response => {
      console.log('Response:', response);
      return response;
    });
};
```

**3. State Management Issues**
```javascript
// Install Redux DevTools (if using Redux)
// Or use React DevTools Profiler

// Debug context values
const contextValue = useContext(MyContext);
console.log('Context:', contextValue);
```

## WebSocket Issues

### Connection Debugging

**1. Socket.IO Debug Mode**
```javascript
// Enable debug mode
localStorage.setItem('debug', 'socket.io-client:*');

// Manual connection test
const socket = io('http://localhost:3560', {
  transports: ['websocket'],
  debug: true
});

socket.on('connect', () => console.log('Connected'));
socket.on('connect_error', (err) => console.error('Connection error:', err));
```

**2. Event Handling Issues**
```javascript
// Log all events
socket.onAny((eventName, ...args) => {
  console.log(`Event: ${eventName}`, args);
});

// Test specific events
socket.emit('test', { data: 'test' });
```

### Authentication Issues

**1. Token Validation**
```python
# Backend: Test token validation
from services.supabase_auth import auth_service
is_valid, user_data = auth_service.verify_token(token)
print(f"Valid: {is_valid}, User: {user_data}")
```

**2. Session Management**
```javascript
// Frontend: Check auth state
const checkAuth = async () => {
  const token = localStorage.getItem('auth_token');
  if (!token) {
    console.log('No token found');
    return;
  }
  
  try {
    const response = await fetch('/api/auth/verify', {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    console.log('Auth status:', response.status);
  } catch (error) {
    console.error('Auth check failed:', error);
  }
};
```

## Database Issues

### Migration Problems

**1. Failed Migrations**
```bash
# Check migration status
python web_dashboard/backend/migrations/check_status.py

# Rollback migration
python web_dashboard/backend/migrations/rollback.py --version 004

# Re-run migration
python web_dashboard/backend/migrations/run.py --version 005
```

**2. Schema Inconsistencies**
```sql
-- Check table structure
\d products
\d sync_batches
\d staged_product_changes

-- Verify indexes
SELECT indexname, indexdef 
FROM pg_indexes 
WHERE tablename = 'products';
```

### Data Integrity Issues

**1. Duplicate Records**
```sql
-- Find duplicates
SELECT sku, COUNT(*) 
FROM products 
GROUP BY sku 
HAVING COUNT(*) > 1;

-- Clean duplicates (keep newest)
DELETE FROM products a
USING products b
WHERE a.id < b.id AND a.sku = b.sku;
```

**2. Orphaned Records**
```sql
-- Find orphaned sync records
DELETE FROM sync_history 
WHERE product_id NOT IN (SELECT id FROM products);

-- Find products without categories
UPDATE products 
SET category_id = (SELECT id FROM categories WHERE name = 'Uncategorized')
WHERE category_id IS NULL;
```

## Performance Issues

### Slow Sync Operations

**1. Query Optimization**
```sql
-- Add missing indexes
CREATE INDEX idx_products_shopify_id ON products(shopify_product_id);
CREATE INDEX idx_products_sync_status ON products(shopify_sync_status);
CREATE INDEX idx_sync_history_created ON sync_history(created_at);
```

**2. Batch Size Tuning**
```python
# Adjust batch sizes in config
SYNC_BATCH_SIZE = 50  # Reduce if timeouts occur
PARALLEL_WORKERS = 4  # Adjust based on CPU cores
```

**3. Memory Usage**
```bash
# Monitor memory usage
ps aux | grep python | grep app.py

# Check for memory leaks
python -m memory_profiler web_dashboard/backend/app.py
```

### Frontend Performance

**1. Component Re-renders**
```javascript
// Use React.memo for expensive components
const MemoizedComponent = React.memo(ExpensiveComponent);

// Use useMemo for expensive calculations
const expensiveValue = useMemo(() => {
  return calculateExpensiveValue(data);
}, [data]);
```

**2. API Call Optimization**
```javascript
// Implement caching
const cache = new Map();

const cachedFetch = async (url) => {
  if (cache.has(url)) {
    return cache.get(url);
  }
  
  const response = await fetch(url);
  const data = await response.json();
  cache.set(url, data);
  return data;
};
```

## Emergency Procedures

### 1. Complete System Reset

```bash
# Stop all services
./stop_all_services.sh

# Clear all caches
redis-cli FLUSHALL

# Reset database sequences
psql cowans_db -c "SELECT setval(pg_get_serial_sequence('products', 'id'), MAX(id)) FROM products;"

# Restart services
./start_dashboard_unified.sh
```

### 2. Rollback Sync Operation

```python
# Emergency rollback script
python web_dashboard/backend/scripts/emergency_rollback.py --batch-id BATCH_ID
```

### 3. Disable Sync Operations

```python
# Set maintenance mode
python -c "
from web_dashboard.backend.app import redis_client
redis_client.set('maintenance_mode', 'true')
"
```

### 4. Data Recovery

```bash
# Restore from backup
pg_restore -d cowans_db backup_20250108.dump

# Replay sync operations
python web_dashboard/backend/scripts/replay_sync_log.py --from "2025-01-08" --to "2025-01-09"
```

## Monitoring and Alerts

### 1. Set Up Monitoring

```bash
# Install monitoring stack
docker-compose -f monitoring/docker-compose.yml up -d

# Configure alerts
cp monitoring/alerts.yml.example monitoring/alerts.yml
# Edit alerts.yml with your notification settings
```

### 2. Key Metrics to Monitor

- API response times
- WebSocket connection count
- Sync operation success rate
- Database connection pool usage
- Memory and CPU usage
- Error rates by endpoint

### 3. Log Aggregation

```bash
# Set up ELK stack for log analysis
docker run -d --name elasticsearch elasticsearch:7.x
docker run -d --name logstash logstash:7.x
docker run -d --name kibana kibana:7.x
```

## Support Escalation

### Level 1: Basic Troubleshooting
- Check logs for obvious errors
- Verify configuration
- Restart services
- Clear caches

### Level 2: Advanced Diagnostics
- Database query analysis
- API endpoint testing
- WebSocket event tracing
- Performance profiling

### Level 3: Development Team
- Code-level debugging
- Architecture changes
- Database schema modifications
- Third-party API issues

## Useful Scripts

### Quick Diagnostics
```bash
#!/bin/bash
# save as diagnose.sh

echo "=== System Status ==="
echo "Backend:" $(curl -s http://localhost:3560/health | jq .status)
echo "Database:" $(psql -c "SELECT 1" >/dev/null 2>&1 && echo "OK" || echo "Failed")
echo "Redis:" $(redis-cli ping)
echo "WebSocket:" $(curl -s http://localhost:3560/socket.io/ | grep -q "0" && echo "OK" || echo "Failed")

echo -e "\n=== Recent Errors ==="
tail -n 20 web_dashboard/backend/logs/app.log | grep ERROR

echo -e "\n=== Sync Status ==="
psql cowans_db -c "SELECT COUNT(*) as total, COUNT(shopify_product_id) as synced FROM products;"
```

---

*Last Updated: January 2025*
*For emergency support: Call the on-call engineer*