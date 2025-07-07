# Shopify Sync Engine Integration Guide

This guide provides comprehensive instructions for integrating the new database-driven Shopify Sync Engine into the existing Product Feed Integration System.

## Overview

The Shopify Sync Engine replaces the current file-based synchronization approach with a comprehensive database-driven system that provides:

- **Real-time synchronization** with intelligent conflict resolution
- **Batch processing** with rate limiting and performance optimization
- **Bidirectional sync** capabilities between local database and Shopify
- **Comprehensive monitoring** and progress tracking
- **Robust error handling** with automatic retry mechanisms

## Architecture Components

### Core Components

1. **ShopifySyncEngine** (`shopify_sync_engine.py`)
   - Core synchronization engine with database-driven operations
   - Handles GraphQL optimization and rate limiting
   - Manages conflict detection and resolution
   - Provides batch processing with dependency management

2. **SyncService** (`sync_service.py`)
   - High-level service interface for sync operations
   - Job management and progress tracking
   - User-friendly API for web dashboard integration

3. **Sync API** (`sync_api.py`)
   - REST API endpoints for sync operations
   - Job monitoring and conflict resolution endpoints
   - Configuration management APIs

4. **Enhanced Repositories** (`repositories.py`)
   - Database access layer with sync-aware operations
   - Change tracking and conflict detection support
   - Performance-optimized queries for sync operations

5. **Sync Models** (`sync_models.py`)
   - Additional database models for sync operations
   - Conflict tracking, queue management, and performance metrics
   - Health monitoring and dependency tracking

## Integration Steps

### Step 1: Database Schema Updates

Add the new sync models to your database schema:

```python
# In your database initialization
from sync_models import (
    SyncConflict, SyncQueue, ChangeTracking, 
    SyncPerformanceMetrics, SyncDependency, 
    SyncHealthCheck, ApiRateLimit,
    create_sync_performance_indexes
)

# Create tables
Base.metadata.create_all(engine)

# Create performance indexes
create_sync_performance_indexes(engine)
```

### Step 2: Update Flask Application

Integrate the sync service and API into your Flask application:

```python
# In app.py
from sync_service import SyncService
from sync_api import sync_api, init_sync_service
import os

# Initialize sync service
shop_url = os.getenv('SHOPIFY_SHOP_URL')
access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')

if shop_url and access_token:
    sync_service = init_sync_service(shop_url, access_token)
    
    # Start sync service in background
    import threading
    import asyncio
    
    def run_sync_service():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(sync_service.start_service())
    
    sync_thread = threading.Thread(target=run_sync_service, daemon=True)
    sync_thread.start()

# Register API blueprint
app.register_blueprint(sync_api)
```

### Step 3: Environment Configuration

Add required environment variables:

```bash
# .env file
SHOPIFY_SHOP_URL=your-shop.myshopify.com
SHOPIFY_ACCESS_TOKEN=your_access_token

# Sync engine configuration
SYNC_BATCH_SIZE=20
SYNC_MAX_CONCURRENT=10
SYNC_CONFLICT_RESOLUTION=etilize_priority
SYNC_AUTO_RESOLVE=true
SYNC_BIDIRECTIONAL=false
```

### Step 4: Frontend Integration

Update your React frontend to use the new sync APIs:

```typescript
// Sync service client
class SyncService {
  private baseUrl = '/api/sync';

  async getStatus() {
    const response = await fetch(`${this.baseUrl}/status`);
    return response.json();
  }

  async startFullSync() {
    const response = await fetch(`${this.baseUrl}/full-sync`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });
    return response.json();
  }

  async startIncrementalSync(sinceHours: number = 24) {
    const response = await fetch(`${this.baseUrl}/incremental`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ since_hours: sinceHours })
    });
    return response.json();
  }

  async syncProducts(productIds: number[]) {
    const response = await fetch(`${this.baseUrl}/products/batch-sync`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ product_ids: productIds })
    });
    return response.json();
  }

  async getJobProgress(jobId: string) {
    const response = await fetch(`${this.baseUrl}/jobs/${jobId}`);
    return response.json();
  }

  async getActiveJobs() {
    const response = await fetch(`${this.baseUrl}/jobs`);
    return response.json();
  }

  async getConflicts() {
    const response = await fetch(`${this.baseUrl}/conflicts`);
    return response.json();
  }

  async resolveConflict(conflictId: string, resolvedValue: any) {
    const response = await fetch(`${this.baseUrl}/conflicts/${conflictId}/resolve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ resolved_value: resolvedValue })
    });
    return response.json();
  }
}
```

## Migration from File-Based System

### Phase 1: Parallel Operation (Recommended)

1. **Keep existing file-based scripts operational** during transition
2. **Run sync engine in "monitoring mode"** to track changes without actual sync
3. **Compare results** between old and new systems
4. **Gradually migrate categories** of products to the new system

### Phase 2: Feature Transition

1. **Start with low-risk operations** (description updates, SEO fields)
2. **Move to medium-risk operations** (pricing, inventory)
3. **Finally migrate high-risk operations** (product creation, deletion)

### Phase 3: Full Transition

1. **Disable file-based sync scripts**
2. **Enable full sync engine functionality**
3. **Monitor performance and error rates**
4. **Remove old scripts once confident in new system**

## Configuration Options

### Conflict Resolution Strategies

```python
from shopify_sync_engine import ConflictResolution

# Available strategies:
ConflictResolution.ETILIZE_PRIORITY     # Local data wins (recommended)
ConflictResolution.SHOPIFY_PRIORITY     # Shopify data wins
ConflictResolution.MANUAL_REVIEW        # Human intervention required
ConflictResolution.MERGE_FIELDS         # Intelligent field merging
ConflictResolution.TIMESTAMP_BASED      # Most recent wins
```

### Performance Tuning

```python
# Adjust based on your Shopify plan and performance requirements
sync_engine = ShopifySyncEngine(
    shop_url=shop_url,
    access_token=access_token,
    batch_size=20,        # Products per batch (10-50 recommended)
    max_concurrent=10     # Concurrent operations (5-20 recommended)
)

# Rate limiting configuration
sync_engine.product_manager.rate_limiter.base_delay = 0.1  # Seconds between requests
sync_engine.product_manager.rate_limiter.bucket_size = 40  # Shopify bucket size
```

## Monitoring and Health Checks

### Built-in Monitoring

The sync engine provides comprehensive monitoring:

1. **Real-time Metrics**
   - Sync success rates
   - API call usage
   - Rate limit hit rates
   - Average sync times
   - Conflict detection rates

2. **Health Checks**
   - Shopify API connectivity
   - Database performance
   - Queue processing health
   - Memory and resource usage

3. **Alerting**
   - Failed sync operations
   - High conflict rates
   - API rate limit issues
   - System performance degradation

### Custom Monitoring Integration

```python
# Add custom monitoring
def sync_progress_callback(progress):
    # Send to monitoring system (e.g., DataDog, New Relic)
    monitoring_client.gauge('sync.progress', progress.progress_percentage)
    monitoring_client.increment('sync.operations.total')
    
    if not progress.success:
        monitoring_client.increment('sync.operations.failed')
        monitoring_client.event('Sync operation failed', progress.error_message)

sync_service.register_job_callback(job_id, sync_progress_callback)
```

## Performance Optimization

### Database Optimization

1. **Indexes**: All critical paths have optimized indexes
2. **Batch Operations**: Bulk updates reduce database round trips
3. **Connection Pooling**: Efficient database connection management
4. **Query Optimization**: Optimized queries for common sync operations

### API Optimization

1. **GraphQL Batching**: Multiple operations in single API calls
2. **Rate Limiting**: Intelligent rate limiting to avoid 429 errors
3. **Request Optimization**: Minimal data fetching for faster responses
4. **Retry Logic**: Exponential backoff for failed requests

### Memory Management

1. **Streaming Processing**: Large datasets processed in streams
2. **Memory Monitoring**: Built-in memory usage tracking
3. **Garbage Collection**: Proactive memory cleanup
4. **Resource Limits**: Configurable memory and CPU limits

## Error Handling and Recovery

### Automatic Recovery

1. **Retry Mechanisms**: Exponential backoff for transient failures
2. **Circuit Breakers**: Automatic failover for system issues
3. **Dead Letter Queues**: Failed operations preserved for analysis
4. **Graceful Degradation**: Partial functionality during outages

### Manual Recovery

1. **Conflict Resolution Interface**: Web-based conflict resolution
2. **Manual Sync Triggers**: On-demand sync for specific products
3. **Data Validation Tools**: Integrity checking and repair
4. **Rollback Capabilities**: Undo problematic sync operations

## Security Considerations

### API Security

1. **Token Management**: Secure storage and rotation of Shopify tokens
2. **Request Signing**: HMAC verification for webhook requests
3. **Rate Limiting**: Protection against abuse and DoS attacks
4. **Audit Logging**: Comprehensive logging of all sync operations

### Data Protection

1. **Encryption**: Sensitive data encrypted at rest and in transit
2. **Access Control**: Role-based access to sync operations
3. **Data Masking**: Sensitive information masked in logs
4. **Compliance**: GDPR and data protection compliance

## Testing Strategy

### Unit Testing

```python
# Test sync engine components
import pytest
from shopify_sync_engine import ShopifySyncEngine

@pytest.fixture
def sync_engine():
    return ShopifySyncEngine("test-shop.myshopify.com", "test-token")

def test_product_sync(sync_engine, mock_product):
    result = sync_engine.sync_product_to_shopify(mock_product.id)
    assert result.success
    assert result.shopify_id is not None
```

### Integration Testing

```python
# Test end-to-end sync workflows
def test_full_sync_workflow():
    # Create test products
    # Start sync job
    # Monitor progress
    # Verify results in Shopify
    pass
```

### Performance Testing

```python
# Test sync performance under load
def test_batch_sync_performance():
    # Create 1000 test products
    # Measure sync time and resource usage
    # Verify no rate limiting issues
    pass
```

## Troubleshooting

### Common Issues

1. **Rate Limiting**
   - Reduce batch size
   - Increase delay between requests
   - Check Shopify plan limits

2. **Conflicts**
   - Review conflict resolution strategy
   - Check data quality in source systems
   - Implement data validation rules

3. **Performance Issues**
   - Monitor database query performance
   - Check API response times
   - Review memory usage patterns

### Debug Tools

```python
# Enable debug logging
import logging
logging.getLogger('shopify_sync_engine').setLevel(logging.DEBUG)

# Monitor sync queue
from sync_models import SyncQueue
pending_items = session.query(SyncQueue).filter(
    SyncQueue.status == 'pending'
).count()

# Check conflict status
from sync_models import SyncConflict
conflicts = session.query(SyncConflict).filter(
    SyncConflict.status == 'pending'
).all()
```

## Support and Maintenance

### Regular Maintenance

1. **Database Cleanup**: Archive old sync history and logs
2. **Performance Review**: Monitor and optimize slow queries
3. **Token Rotation**: Regular rotation of API tokens
4. **Health Checks**: Automated health monitoring and alerting

### Upgrades and Updates

1. **Version Control**: Track sync engine version and changes
2. **Migration Scripts**: Database schema migration tools
3. **Rollback Plans**: Safe rollback procedures for updates
4. **Testing Procedures**: Comprehensive testing before updates

## Conclusion

The Shopify Sync Engine provides a robust, scalable, and maintainable solution for synchronizing product data between your local database and Shopify. By following this integration guide, you can smoothly transition from the file-based approach to a modern database-driven sync system that will scale with your business needs.

For additional support or questions, refer to the individual module documentation or contact the development team.