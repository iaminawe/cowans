# User Guide - Cowan's Product Management Dashboard

## 🚀 Getting Started

### 1. Access the Dashboard
- **URL**: http://localhost:3055
- **Login**: gregg@iaminawe.com
- **Requirements**: Admin account for full access

### 2. Dashboard Navigation
The dashboard features 8 main tabs:

## 📊 Dashboard Tab - Overview & Controls

### Quick Actions
- **Sync Trigger**: Start manual Shopify synchronization
- **System Status**: View current sync status and history
- **Recent Activity**: Monitor latest system activities

### Sync History
- View all past synchronization attempts
- Check success/failure status
- Review sync details and error messages

## 🔧 Scripts Tab - Automation & Execution

### Script Execution
- Execute individual data processing scripts
- Monitor script progress in real-time
- View execution logs and results

### Available Scripts
- Product import and processing
- Category management
- Data cleanup and validation
- Shopify sync operations

## 📋 Logs Tab - Real-time Monitoring

### Live Activity Monitor
- Real-time system activity logs
- WebSocket-powered live updates
- Filter logs by type and severity

### Log Management
- Clear log history
- Export logs for debugging
- Monitor system performance

## 📦 Products Tab - Product Management

### Product Listings
- **Search**: Find products by name, SKU, or category
- **Filter**: Filter by status, category, vendor
- **Sort**: Sort by name, price, date modified
- **Pagination**: Navigate through large product catalogs

### Product Operations
- View detailed product information
- Edit product details and metadata
- Check Shopify sync status
- Bulk operations on selected products

### Product Creation
- Create new products manually
- Set product details, pricing, and categories
- Assign to collections
- Configure Shopify settings

## 📚 Collections Tab - Collection Management

### Collection Overview
- View all product collections
- Check collection status and product counts
- Monitor Shopify sync status

### Collection Management
- Create new collections
- Edit collection details and descriptions
- Add/remove products from collections
- Configure collection rules and automation

### AI Collection Suggestions
- Get AI-powered collection recommendations
- Auto-generate collections based on product types
- Optimize collection structure

## 🏷️ Categories Tab - Category Management *(Admin Only)*

### Category Hierarchy
- View category tree structure
- Create parent and child categories
- Reorganize category hierarchy

### Category Operations
- Create new categories
- Edit category details
- Assign icons to categories
- Bulk category operations

### Icon Assignment
- Assign generated icons to categories
- Preview icon assignments
- Manage category visual branding

## 🎨 Icons Tab - AI Icon Generation *(Admin Only)*

### Single Icon Generation
1. **Category Input**: Enter category name
2. **Style Selection**: Choose from modern, classic, minimalist
3. **Color Scheme**: Select brand colors, monochrome, or vibrant
4. **Custom Elements**: Add specific visual elements
5. **Generate**: Create AI-powered icon

### Batch Icon Generation
1. **Multiple Categories**: Enter categories (one per line)
2. **Batch Settings**: Configure style and color preferences
3. **Variations**: Set number of variations per category
4. **Monitor Progress**: Real-time generation progress
5. **Review Results**: Access generated icons in library

### Icon Library
- **Browse Icons**: View all generated icons
- **Download Icons**: Download icons for use
- **Assign to Collections**: Link icons to collections
- **Cache Management**: Clear old cached icons

### Icon Assignment to Collections
1. Click the **folder icon** on any generated icon
2. Select target collection from dropdown
3. Confirm assignment
4. Icon becomes collection's visual representation

## 👥 Admin Tab - System Administration *(Admin Only)*

### User Management
- **View Users**: See all registered users
- **User Details**: Check login history and activity
- **Role Management**: Assign admin/user roles
- **Account Status**: Activate/deactivate accounts

### System Statistics
- **Database Metrics**: Size, connection status
- **Performance Stats**: Response times, cache hit rates
- **System Health**: Uptime, memory usage
- **API Analytics**: Request counts, error rates

### Job Monitoring
- **Active Jobs**: View currently running tasks
- **Job History**: Review completed and failed jobs
- **Queue Status**: Monitor job queue health
- **Performance Metrics**: Job execution times

## 🔐 Authentication & Security

### Login Process
1. Navigate to dashboard URL
2. Enter email and password
3. System validates with Supabase
4. JWT token generated for session
5. Access granted based on user role

### Role-Based Access
- **Regular Users**: Dashboard, Scripts, Logs, Products tabs
- **Admin Users**: All tabs including Categories, Icons, Admin

### Session Management
- Sessions expire based on Supabase settings
- Automatic logout on token expiration
- Re-authentication required for sensitive operations

## 🛠️ Common Tasks

### Syncing Products with Shopify
1. Go to **Dashboard** tab
2. Click **Trigger Sync** button
3. Monitor progress in sync history
4. Check **Logs** tab for detailed information
5. Verify results in **Products** tab

### Creating Product Collections
1. Navigate to **Collections** tab
2. Click **Create Collection**
3. Enter collection details and rules
4. Add products manually or via automation
5. Sync to Shopify if needed

### Generating Category Icons
1. Go to **Icons** tab (admin only)
2. Enter category name
3. Choose style and color preferences
4. Click **Generate Icon**
5. Assign generated icon to collection

### Managing Users (Admin Only)
1. Access **Admin** tab
2. View user list with details
3. Click user to modify permissions
4. Toggle admin status or account activity
5. Changes take effect immediately

## 🔍 Troubleshooting

### Dashboard Won't Load
- Check if services are running: `./start_dashboard_unified.sh`
- Verify ports 3055 and 3560 are available
- Check logs: `logs/frontend.log` and `logs/backend.log`

### Login Issues
- Verify credentials with Supabase admin
- Check if user account exists and is active
- Ensure proper Supabase configuration in `.env`

### API Errors
- **404 Errors**: Endpoints not found (should be resolved)
- **401 Errors**: Authentication required - login again
- **500 Errors**: Server issues - check backend logs

### Sync Problems
- Verify Shopify credentials in `.env`
- Check network connectivity
- Review error messages in logs
- Validate product data format

### Icon Generation Issues
- Verify OpenAI API key is configured
- Check API quota and rate limits
- Ensure proper internet connectivity
- Review generation logs for errors

## 📱 Mobile Access

The dashboard is optimized for desktop use but provides basic mobile functionality:
- **Responsive Design**: Adapts to tablet and mobile screens
- **Touch-Friendly**: Buttons and controls work with touch
- **Limited Features**: Some advanced features require desktop

## 🎯 Best Practices

### Product Management
- Use consistent naming conventions
- Maintain proper categorization
- Regular sync with Shopify
- Monitor for conflicts and duplicates

### Collection Organization
- Create logical collection hierarchies
- Use descriptive names and handles
- Assign appropriate icons for visual clarity
- Regular review and optimization

### System Maintenance
- Monitor system logs regularly
- Keep track of job execution times
- Clean up old cache and temporary files
- Update user permissions as needed

### Performance Optimization
- Use batch operations for large datasets
- Schedule intensive operations during off-peak hours
- Monitor system resources and performance metrics
- Regular database maintenance

---

**🎯 The dashboard is now fully functional with all features working correctly. All major issues have been resolved, and the system is ready for daily use and production deployment.**