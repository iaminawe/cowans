# Bulk Operations User Guide

## Overview

The Cowans Product Management System provides powerful bulk operation capabilities for efficiently managing large product catalogs across multiple platforms.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Parallel Sync Operations](#parallel-sync-operations)
3. [Batch Processing](#batch-processing)
4. [Enhanced Sync Workflow](#enhanced-sync-workflow)
5. [Performance Optimization](#performance-optimization)
6. [Best Practices](#best-practices)
7. [Troubleshooting](#troubleshooting)

## Getting Started

### Accessing Bulk Operations

1. Log in to the Cowans Dashboard
2. Navigate to the "Sync" tab for synchronization operations
3. Or use the "Products" tab for batch product management

### Understanding the Interface

```
┌───────────────────────────────────────────────┐
│            Navigation Tabs                    │
├───────────────────────────────────────────────┤
│  [🔄 Sync] [📝 Scripts] [📦 Products]      │
│  [🏞️ Collections] [🛠️ Admin]              │
└───────────────────────────────────────────────┘
```

## Parallel Sync Operations

### What is Parallel Sync?

Parallel Sync allows you to process multiple products simultaneously using multiple worker threads, dramatically reducing sync time.

### Configuring Parallel Sync

1. **Navigate to Sync Tab**
   - Click on the 🔄 Sync tab

2. **Access Parallel Sync Control**
   - Look for the "Parallel Sync Control" panel

3. **Configure Settings**:

   #### Basic Settings
   - **Enable Parallel Processing**: Toggle to activate
   - **Worker Pool Size**: 
     - Minimum Workers: 1-10 (start with 2)
     - Maximum Workers: 1-10 (recommend 4-6)
   - **Batch Size**: 50-100 items (optimal)
   - **Priority**: Low/Normal/High
   - **Operation Type**: Create/Update/Delete/All

   #### Sync Strategies
   - **⚡ Speed Priority**: Maximum workers, larger batches
   - **💰 Cost Optimized**: Fewer workers, smaller batches
   - **📊 Balanced**: Optimal mix of speed and efficiency

4. **Start Sync**
   - Click "Start Parallel Sync"
   - Monitor progress in real-time

### Example Configuration

```yaml
Recommended Settings for 10,000 Products:
- Workers: 2-4
- Batch Size: 50
- Priority: Normal
- Strategy: Balanced
- Expected Time: ~15-20 minutes
```

## Batch Processing

### Selecting Products for Batch Operations

1. **Navigate to Products Tab**
2. **Use Filters** to narrow down products:
   - Search by name, SKU, or barcode
   - Filter by status, vendor, or category
   - Sort by date, price, or inventory

3. **Select Products**:
   - Click checkboxes for individual products
   - Use "Select All" for current page
   - Use "Select All Matching" for filtered results

### Available Batch Operations

#### 1. Bulk Status Update
```
Operation: Update Product Status
Options:
  - Active
  - Draft
  - Archived
Max Items: 1000 per batch
```

#### 2. Bulk Tag Management
```
Operation: Add/Remove Tags
Options:
  - Add tags (comma-separated)
  - Remove tags
  - Replace all tags
Max Items: 500 per batch
```

#### 3. Bulk Price Update
```
Operation: Update Pricing
Options:
  - Fixed price
  - Percentage increase/decrease
  - Round to nearest .99
Max Items: 250 per batch
```

#### 4. Bulk Export
```
Operation: Export Products
Formats:
  - CSV
  - Excel
  - JSON
Max Items: 10,000 per export
```

### Executing Batch Operations

1. Select products
2. Choose operation from "Bulk Actions" dropdown
3. Configure operation parameters
4. Review affected products
5. Click "Execute Batch Operation"
6. Monitor progress
7. Review results

## Enhanced Sync Workflow

### The Three-Stage Process

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Stage 1   │    │   Stage 2   │    │   Stage 3   │
│ Pull from   │ →  │   Review    │ →  │  Push to    │
│  Shopify    │    │  Changes    │    │  Shopify    │
└─────────────┘    └─────────────┘    └─────────────┘
```

### Stage 1: Pull from Shopify

1. Click on "Shopify Down" tab
2. Configure sync options:
   - **Sync Mode**: Full/Incremental
   - **Include**: Products/Variants/Images/Inventory
   - **Filters**: By collection, vendor, or date
3. Click "Start Sync Down"
4. Wait for completion

### Stage 2: Review Staged Changes

1. Click on "Staged Changes" tab
2. Review detected changes:
   - **New Products**: Items to be created
   - **Updated Products**: Items with changes
   - **Deleted Products**: Items to be removed
3. For each change:
   - View detailed diff
   - Approve or reject
   - Add notes if needed
4. Click "Approve Selected Changes"

### Stage 3: Push to Shopify

1. Click on "Shopify Up" tab
2. Review approved changes summary
3. Configure upload options:
   - **Update Mode**: Create/Update/Both
   - **Conflict Resolution**: Skip/Overwrite/Merge
4. Click "Start Sync Up"
5. Monitor progress
6. Review results

## Performance Optimization

### Optimal Settings by Catalog Size

| Products | Workers | Batch Size | Strategy | Est. Time |
|----------|---------|------------|----------|----------|
| < 1,000  | 1-2     | 50         | Balanced | 5-10 min |
| 1-10K    | 2-4     | 50-100     | Balanced | 15-30 min|
| 10-50K   | 4-6     | 100        | Speed    | 30-60 min|
| 50K+     | 6-10    | 100-200    | Speed    | 1-2 hours|

### Tips for Better Performance

1. **Schedule During Off-Peak Hours**
   - Early morning or late evening
   - Avoid high-traffic periods

2. **Use Incremental Sync**
   - Only sync changed items
   - Run daily for best results

3. **Optimize Batch Sizes**
   - Larger batches = fewer API calls
   - Smaller batches = better error recovery

4. **Monitor System Resources**
   - Check CPU and memory usage
   - Adjust workers if needed

## Best Practices

### 1. Regular Sync Schedule

```
Recommended Schedule:
- Full Sync: Weekly (weekends)
- Incremental Sync: Daily (night)
- Inventory Sync: Every 4 hours
```

### 2. Data Validation

- Always review staged changes before approval
- Use test mode for new configurations
- Keep backups before major operations

### 3. Error Handling

- Monitor error logs
- Set up email notifications
- Have rollback plan ready

### 4. Performance Monitoring

- Track sync times
- Monitor API usage
- Review error rates

## Troubleshooting

### Common Issues and Solutions

#### Sync Takes Too Long

**Symptoms**: Sync running for hours
**Solutions**:
1. Reduce batch size
2. Increase workers
3. Use incremental sync
4. Check network connection

#### High Error Rate

**Symptoms**: Many failed items
**Solutions**:
1. Check API credentials
2. Verify rate limits
3. Reduce workers
4. Review error logs

#### Memory Issues

**Symptoms**: Dashboard becomes slow
**Solutions**:
1. Reduce batch size
2. Clear browser cache
3. Use fewer workers
4. Process in smaller chunks

#### Duplicate Products

**Symptoms**: Same products appearing multiple times
**Solutions**:
1. Run deduplication tool
2. Check SKU uniqueness
3. Review sync settings
4. Enable conflict resolution

### Getting Help

1. **Check Logs**
   - Navigate to "Logs" tab
   - Filter by error type
   - Download for support

2. **Contact Support**
   - Email: support@cowans.com
   - Include:
     - Sync job ID
     - Error messages
     - Screenshots
     - Configuration used

3. **Emergency Stop**
   - Click "Stop Sync" button
   - Wait for graceful shutdown
   - Review partial results

## Appendix: Keyboard Shortcuts

| Action | Shortcut |
|--------|----------|
| Start Sync | Ctrl+S |
| Stop Sync | Ctrl+X |
| Select All | Ctrl+A |
| Approve Changes | Ctrl+Enter |
| Refresh Status | F5 |
| Toggle Filters | Ctrl+F |
| Export Results | Ctrl+E |

## Glossary

- **Batch**: Group of items processed together
- **Worker**: Processing thread handling sync tasks
- **Staging**: Temporary storage for pending changes
- **Incremental Sync**: Only sync changed items
- **Full Sync**: Sync all items regardless of changes
- **GraphQL**: Efficient API query language used by Shopify
- **Rate Limit**: Maximum API calls allowed per second
- **Webhook**: Real-time notification of changes