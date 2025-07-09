# Shopify Sync User Guide

## Understanding Sync Status Indicators

This guide helps you understand the various sync status indicators in the Cowan's Product Management System and how to interpret them correctly.

## Quick Reference - Status Icons

| Icon | Color | Status | Meaning |
|------|-------|--------|---------|
| ✓ | Green | Synced | Product is synchronized with Shopify |
| ✓ | Blue | Assumed Synced | Product has Shopify ID but no recent sync status |
| ⏱ | Yellow | Pending | Sync operation in progress |
| ✗ | Red | Error | Sync failed - action required |
| ✗ | Gray | Not Synced | Product not yet synced to Shopify |
| 🔄 | Blue (spinning) | Syncing | Active sync operation |

## Dashboard Overview

### 1. Connection Status Indicator

Located in the top-right corner of the Enhanced Sync Management page:

- **🟢 Green Dot**: Connected - Real-time updates are active
- **🔴 Red Dot**: Disconnected - Real-time updates unavailable (page refresh may be needed)

### 2. Product Sync Status

In the Products table, each product shows its sync status:

#### **Not Synced to Shopify** (Gray X)
- Product exists only in local database
- No Shopify product ID assigned
- Action: Use "Sync to Shopify" to create product in Shopify

#### **Synced** (Green Checkmark)
- Product successfully synchronized
- All changes are up to date
- No action required

#### **Assumed Synced** (Blue Checkmark)
- Product has Shopify ID
- No recent sync activity recorded
- Likely synced but status not explicitly tracked
- Action: Run sync to update status

#### **Pending** (Yellow Clock)
- Sync operation in progress
- Changes being processed
- Action: Wait for completion

#### **Error** (Red X)
- Sync operation failed
- Check error details for specific issue
- Action: Review error and retry sync

## Using the Enhanced Sync Dashboard

### Overview Tab

Displays four status cards:

1. **Shopify Sync Down**
   - Shows status of importing from Shopify
   - Click to view detailed import options

2. **Staged Changes**
   - Number of pending changes for review
   - Click to review before applying

3. **Shopify Sync Up**
   - Status of exporting to Shopify
   - Shows approved changes ready to push

4. **System Health**
   - Overall sync system status
   - Connection indicators

### Sync Operations

#### 1. Pulling from Shopify (Sync Down)

**Steps:**
1. Navigate to "Shopify Down" tab
2. Select sync options:
   - Full Sync: Import all products
   - Incremental: Only changed items
   - Selective: Choose specific products
3. Click "Start Sync"
4. Monitor progress in real-time

**What happens:**
- Products fetched from Shopify
- Changes staged for review
- No immediate changes to local data

#### 2. Reviewing Staged Changes

**Steps:**
1. Go to "Staged Changes" tab
2. Review each change:
   - Green: New data
   - Yellow: Modified data
   - Red: Deleted data
3. Use buttons to:
   - ✓ Approve individual changes
   - ✗ Reject unwanted changes
   - ✓✓ Bulk approve all

**Important:** Changes are NOT applied until approved

#### 3. Pushing to Shopify (Sync Up)

**Steps:**
1. Navigate to "Shopify Up" tab
2. Review approved changes
3. Click "Push to Shopify"
4. Monitor upload progress

**What happens:**
- Approved changes sent to Shopify
- Products created/updated in Shopify store
- Sync status updated in real-time

## Common Sync Scenarios

### Scenario 1: Initial Product Upload

**Situation**: You have products in your database not yet in Shopify

**Steps:**
1. Go to Products tab
2. Select products with gray X status
3. Click "Sync Selected to Shopify"
4. Review in Staged Changes
5. Approve and push to Shopify

### Scenario 2: Updating Product Information

**Situation**: Product details changed locally

**Steps:**
1. Edit product information
2. Product status changes to "Modified"
3. Use Sync Up to push changes
4. Verify green checkmark after completion

### Scenario 3: Importing from Shopify

**Situation**: Products created directly in Shopify

**Steps:**
1. Go to Shopify Down tab
2. Click "Import New Products"
3. Review imported products
4. Approve to add to local database

### Scenario 4: Bulk Operations

**Situation**: Need to sync many products at once

**Steps:**
1. Use checkbox to select multiple products
2. Choose bulk action from dropdown
3. Monitor batch progress
4. Review results in activity log

## Troubleshooting Sync Issues

### "Connection Lost" Message

**Causes:**
- Network interruption
- Backend service restart
- Session timeout

**Solutions:**
1. Check internet connection
2. Refresh the page
3. Re-login if needed
4. Contact support if persists

### Products Stuck in "Pending"

**Causes:**
- Large sync operation
- Rate limiting
- API timeout

**Solutions:**
1. Wait 5-10 minutes
2. Check Recent Activity for errors
3. Cancel and retry if needed
4. Try smaller batches

### "Sync Failed" Errors

**Common Errors and Solutions:**

| Error | Cause | Solution |
|-------|-------|----------|
| "Invalid product data" | Missing required fields | Check product has title, description |
| "Rate limit exceeded" | Too many API calls | Wait 5 minutes, retry |
| "Authentication failed" | Invalid credentials | Check Shopify settings |
| "Product not found" | Deleted from Shopify | Remove local reference |
| "Network timeout" | Slow connection | Retry with smaller batch |

### Sync Status Not Updating

**Steps to resolve:**
1. Refresh the page
2. Check WebSocket connection (top-right indicator)
3. Clear browser cache
4. Try different browser
5. Contact support with details

## Best Practices

### 1. Regular Sync Schedule

- Run incremental sync daily
- Full sync weekly for verification
- Monitor sync metrics for patterns

### 2. Batch Size Management

- Keep batches under 100 products
- Use parallel sync for large catalogs
- Monitor memory usage

### 3. Change Review Process

- Always review staged changes
- Check for unintended modifications
- Use bulk approve carefully
- Keep sync history for audit

### 4. Error Prevention

- Ensure product data is complete
- Validate before syncing
- Monitor rate limits
- Keep backups before major syncs

## Advanced Features

### Sync Metrics Dashboard

Access via Overview tab → Metrics button:

- **Sync Performance**: Operations per minute
- **Success Rate**: Percentage of successful syncs
- **Average Duration**: Time per operation
- **Queue Status**: Pending operations

### Activity Log

View detailed sync history:

1. Click "Recent Activity" in Overview
2. Filter by:
   - Operation type
   - Date range
   - Status
   - User
3. Export logs for analysis

### Rollback Capability

If sync causes issues:

1. Go to Sync History
2. Find problematic batch
3. Click "Rollback"
4. Confirm to revert changes

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl + R` | Refresh sync status |
| `Ctrl + S` | Start sync operation |
| `Ctrl + A` | Select all items |
| `Space` | Toggle item selection |
| `Enter` | Approve selected |
| `Delete` | Reject selected |

## Getting Help

### In-App Help

- Hover over (?) icons for tooltips
- Click "Help" in navigation
- Use command palette (Ctrl+K)

### Support Resources

- **Email**: support@cowans.com
- **Documentation**: /docs folder
- **Video Tutorials**: YouTube channel
- **Community Forum**: forum.cowans.com

### Reporting Issues

When reporting sync issues, include:

1. Screenshot of error
2. Sync operation type
3. Number of products affected
4. Time of occurrence
5. Browser and OS info
6. Recent actions taken

## FAQ

**Q: Why do some products show blue checkmarks instead of green?**
A: Blue checkmarks indicate products that have Shopify IDs but haven't been synced recently. They're likely synchronized but the system hasn't explicitly confirmed their status.

**Q: Can I sync products without reviewing changes?**
A: No, the staging system requires review for safety. However, you can use "Bulk Approve" to quickly approve all changes after a brief review.

**Q: How often should I sync?**
A: Daily incremental syncs are recommended, with weekly full syncs for verification. Adjust based on your update frequency.

**Q: What happens if I lose connection during sync?**
A: The system will attempt to resume when connection is restored. Long operations are chunked to prevent data loss.

**Q: Can I cancel a sync operation?**
A: Yes, click the "Cancel" button next to the progress bar. Already processed items will remain, but pending items will be skipped.

---

*Last Updated: January 2025*
*Version: 1.0*