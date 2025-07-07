# Cowan's Product Dashboard - Backend

A comprehensive web dashboard for managing Shopify product synchronization with **advanced parallel batch processing**, collections management, real-time monitoring, and conflict detection.

## 🚀 Quick Start

**There is ONE main script to start the dashboard:**

```bash
./start_dashboard.sh
```

This script handles everything:
- ✅ Creates virtual environment
- ✅ Installs dependencies
- ✅ Initializes database
- ✅ Starts the Flask application
- ✅ Provides colored output for easy monitoring

## 📋 Features

### 🚀 NEW: Parallel Sync System
- **10x-31x faster** sync performance than sequential processing
- **90% reduction** in API calls through intelligent batching
- **Dynamic worker scaling** (2-10 workers based on load)
- **Real-time webhook processing** for immediate updates
- **Bulk Operations API** integration for massive scale operations

### 🗂️ Collections Management
- **Full CRUD operations** for collections with Shopify sync
- **Automatic collections** based on product types with configurable rules
- **Manual collections** with drag-and-drop product assignment
- **AI-powered suggestions** for collection naming and organization
- **Batch add products** to collections with progress tracking

### 📦 Enhanced Product Management
- **Advanced batch operations** (bulk updates, category changes, pricing)
- **Bulk sync to Shopify** with real-time progress tracking
- **Product details panel** with comprehensive information
- **Advanced search and filtering** capabilities
- **Real-time status updates** and progress monitoring

### 🔧 Core Features
- **Product Management**: Full CRUD operations for products with Shopify sync
- **Batch Processing**: Efficient handling of large datasets with progress tracking
- **Real-time Updates**: WebSocket support for live operation monitoring
- **Conflict Detection**: Smart detection and resolution of data conflicts
- **Memory Optimization**: Efficient processing of large product catalogs
- **Authentication**: JWT-based secure authentication system
- **Icon Generation**: AI-powered product icon generation with DALL-E 3

## 🔧 Manual Setup (if needed)

If you prefer to set up manually:

1. **Create virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables:**
   ```bash
   cp ../../.env.example ../../.env
   # Edit .env with your credentials
   ```

4. **Initialize database:**
   ```bash
   python -c "from database import initialize; initialize()"
   ```

5. **Start the application:**
   ```bash
   python app.py
   ```

## 🌐 API Endpoints

### 🚀 NEW: Parallel Sync APIs
- `POST /api/sync/parallel/start` - Start parallel batch sync
- `GET /api/sync/parallel/status` - Get sync status and metrics
- `POST /api/sync/parallel/stop` - Stop running sync operations
- `GET /api/sync/performance` - Get performance metrics and alerts
- `POST /api/sync/bulk/operations` - Manage bulk operations
- `GET /api/sync/bulk/<id>/status` - Track bulk operation progress

### 🗂️ Collections APIs
- `GET /api/collections` - List collections with filtering
- `GET /api/collections/<id>` - Get collection details
- `POST /api/collections` - Create collection
- `PUT /api/collections/<id>` - Update collection
- `DELETE /api/collections/<id>` - Delete collection
- `POST /api/collections/<id>/products` - Add products to collection
- `DELETE /api/collections/<id>/products/<product_id>` - Remove product
- `POST /api/collections/sync` - Sync collections with Shopify
- `GET /api/collections/product-types` - Get product types summary

### 📦 Enhanced Product Batch APIs
- `POST /api/products/batch/update-status` - Bulk status updates
- `POST /api/products/batch/update-category` - Bulk category changes
- `POST /api/products/batch/update-pricing` - Bulk pricing updates
- `POST /api/products/batch/add-to-collection` - Add to collections
- `POST /api/products/batch/sync-shopify` - Bulk Shopify sync
- `DELETE /api/products/batch/delete` - Bulk delete products
- `POST /api/products/batch/export` - Export products in multiple formats

### 🔗 Webhook APIs
- `POST /webhooks/shopify` - Shopify webhook endpoint
- `GET /api/webhooks/status` - Webhook processing status
- `GET /api/webhooks/metrics` - Webhook performance metrics
- `GET /api/webhooks/events` - Recent webhook events
- `POST /api/webhooks/test` - Test webhook processing

### Authentication
- `POST /api/auth/login` - User login
- `POST /api/auth/register` - User registration
- `GET /api/auth/me` - Get current user profile
- `POST /api/auth/logout` - Logout

### Products
- `GET /api/products` - List products with pagination
- `GET /api/products/<id>` - Get product details
- `POST /api/products` - Create product
- `PUT /api/products/<id>` - Update product
- `DELETE /api/products/<id>` - Delete product

### Legacy Batch Operations
- `POST /api/batch/create` - Create batch operation
- `POST /api/batch/<id>/process` - Process batch
- `GET /api/batch/<id>/status` - Get batch status
- `GET /api/batch/stats` - Get batch statistics

### Conflict Detection
- `POST /api/conflicts/detect` - Detect conflicts
- `GET /api/conflicts` - List conflicts
- `POST /api/conflicts/<id>/resolve` - Resolve conflict
- `GET /api/conflicts/stats` - Conflict statistics

### Icon Generation
- `POST /api/icons/generate` - Generate product icon
- `POST /api/icons/batch` - Batch icon generation
- `GET /api/icons/status/<job_id>` - Check generation status

## 🧪 Testing

### Performance Testing
Test the new parallel sync performance:

```bash
# Run parallel sync performance demo
python run_sync_demo.py

# Run comprehensive performance tests
python test_parallel_sync_performance.py
```

### Comprehensive Test Suite
Run the full test suite:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov

# Run specific test categories
pytest -m quick      # Quick unit tests
pytest -m integration # Integration tests
```

### Performance Benchmarks
The parallel sync system shows impressive improvements:
- **Sequential**: ~10 products/second
- **Parallel**: ~70 products/second (7x faster)
- **Batch**: ~300 products/second (30x faster)
- **API Efficiency**: 90% reduction in API calls

## 📁 Project Structure

```
backend/
├── app.py                          # Main Flask application
├── start_dashboard.sh              # Main startup script
├── requirements.txt                # Python dependencies
├── database.py                    # Database configuration
├── models.py                     # SQLAlchemy models (includes Collections)
├── schemas.py                    # Pydantic schemas
├── repositories/                 # Data access layer
│   ├── collection_repository.py  # Collections data access
│   └── product_repository.py     # Enhanced product repository
├── services/                     # Business logic
├── tests/                       # Test suite
├── logs/                       # Application logs
│
├── 🚀 NEW: Parallel Sync System
├── parallel_sync_engine.py        # Core parallel processing engine
├── shopify_bulk_operations.py     # Bulk API integration
├── graphql_batch_optimizer.py     # Query optimization
├── sync_performance_monitor.py    # Real-time monitoring
├── shopify_webhook_handler.py     # Webhook processing
├── webhook_api.py                 # Webhook management API
├── parallel_sync_api.py           # Parallel sync endpoints
│
├── 🗂️ Collections System
├── collections_api.py             # Collections API endpoints
├── apply_collections_migration.py # Database migration
│
├── 📦 Enhanced Batch Processing
├── products_batch_api.py          # Enhanced batch operations
├── batch_processor.py             # Advanced batch framework
│
└── 🧪 Testing & Documentation
    ├── run_sync_demo.py            # Performance demo script
    ├── test_parallel_sync_performance.py  # Comprehensive tests
    ├── demo_parallel_sync.py       # Simple demo
    ├── PARALLEL_SYNC_PERFORMANCE_SUMMARY.md  # Performance results
    └── SHOPIFY_SYNC_IMPLEMENTATION.md        # Implementation details
```

## 🔒 Security

- JWT-based authentication with secure token storage
- Input validation and sanitization
- SQL injection protection via SQLAlchemy ORM
- CORS configuration for frontend integration
- Rate limiting on sensitive endpoints

## 🚦 Monitoring

The dashboard provides:
- Real-time operation status via WebSocket
- Comprehensive logging with rotation
- Performance metrics and statistics
- Memory usage monitoring
- Error tracking and reporting

## 📞 Support

For issues or questions:
1. Check the logs in `logs/` directory
2. Ensure all environment variables are set correctly
3. Verify database connection
4. Check that required ports (5000) are available

## 🛠️ Development

When developing:
1. Always use the virtual environment
2. Run tests before committing
3. Follow the existing code structure
4. Update documentation for new features
5. Use the batch processing system for large operations

---

**Remember: Use `./start_dashboard.sh` to start the dashboard!**