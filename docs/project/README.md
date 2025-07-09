# Cowans Office Supplies Integration System

This is a comprehensive Cowans Office Supplies Integration System for Shopify that automates synchronization of product data between Etilize (via FTP) and Shopify. The system provides both automated workflows and a web dashboard for monitoring and control.

## Quick Start

### 1. Environment Setup
Configure your environment by copying `.env.example` to `.env` and updating it with your credentials:
```bash
cp .env.example .env
# Edit .env with your FTP and Shopify credentials
```

Required environment variables:
```bash
# FTP Configuration
FTP_HOST=your-ftp-host
FTP_USERNAME=your-ftp-username
FTP_PASSWORD=your-ftp-password

# Shopify Configuration
SHOPIFY_SHOP_URL=your-shop.myshopify.com
SHOPIFY_ACCESS_TOKEN=your-access-token

# Web Dashboard
JWT_SECRET_KEY=your-jwt-secret
```

### 2. Installation
```bash
# Install Python dependencies
pip install -r requirements.txt

# Install frontend dependencies (optional - for web dashboard)
cd frontend/
npm install
```

### 3. Run the Integration
Execute the complete workflow with the main orchestration script:
```bash
python scripts/run_import.py
```

This will:
1. Download product data from Etilize FTP
2. Filter and process the data
3. Create Shopify metafields
4. Upload products to Shopify with duplicate detection

### 4. Web Dashboard (Optional)
Start the web dashboard for monitoring and manual control:
```bash
# Start backend
cd web_dashboard/backend/
python app.py

# Start frontend (in another terminal)
cd frontend/
npm start
```
Access the dashboard at `http://localhost:3000`

## System Architecture

The system consists of three main modules:

### 1. Core Integration Module (Python)
- **FTP Downloader**: Downloads product data from Etilize
- **Data Processing**: Filters, transforms, and validates product data
- **Shopify Integration**: Uploads products with advanced duplicate detection

### 2. Web Dashboard Module (React + Flask)
- **Authentication**: Secure login system
- **Manual Sync Control**: Trigger imports manually
- **Log Monitoring**: Real-time sync progress and logs
- **Sync History**: View past operations and results

### 3. Authentication & Scheduling Module
- **JWT Authentication**: Secure API access
- **Scheduled Operations**: Automated sync scheduling (planned)

## Script Organization

The system uses a modular script architecture organized by function:

### Main Entry Points
- `scripts/run_import.py` - **Primary workflow orchestrator**
- Individual module scripts for targeted operations

### Script Modules

#### Shopify Integration (`scripts/shopify/`)
- `shopify_uploader_new.py` - **RECOMMENDED**: Modular uploader with advanced features
- `shopify_uploader.py` - Legacy uploader (still functional)
- `shopify_base.py` - Base classes and rate limiting
- `shopify_image_manager.py` - Image operations and duplicate detection
- `shopify_product_manager.py` - Product CRUD operations

#### Data Processing (`scripts/data_processing/`)
- `filter_products.py` - Filter products against reference data
- `create_metafields.py` - Generate Shopify metafields from CSV
- `categorize_products.py` - Product categorization
- `extract_additional_images.py` - Extract product images
- `extract_columns.py` - Data extraction utilities

#### Utilities (`scripts/utilities/`)
- `ftp_downloader.py` - FTP operations
- `check_base_part.py` - Data validation
- `check_metafields.py` - Metafield validation

#### Maintenance (`scripts/cleanup/`)
- `cleanup_duplicate_images.py` - Remove duplicate product images
- `cleanup_size_duplicates.py` - Size-based duplicate cleanup
- `find_duplicate_products.py` - Find duplicate products

#### Debug Tools (`scripts/debug/`)
- `debug_filter_products.py` - Debug product filtering
- `debug_metafield_matching.py` - Debug metafield operations
- `debug_base_part_mapping.py` - Debug part number mapping

## Features

### Advanced Product Management
- **Intelligent Filtering**: Products filtered against reference catalogs
- **Duplicate Detection**: Multiple detection methods (filename, size, content)
- **Image Management**: Automatic image processing and deduplication
- **Metafield Generation**: Structured metadata for Shopify

### Data Processing
- **Large File Handling**: Chunk-based processing for memory efficiency
- **Encoding Detection**: Automatic file encoding detection and handling
- **Error Recovery**: Robust error handling and retry mechanisms
- **Progress Tracking**: Colorful console output with progress indicators

### Integration Capabilities
- **FTP Integration**: Automated download from Etilize servers
- **Shopify API**: Full GraphQL API integration with rate limiting
- **Batch Processing**: Efficient bulk operations
- **Change Detection**: Only update modified products

## Usage Examples

### Complete Workflow
```bash
# Run full import with all stages
python scripts/run_import.py

# Skip specific stages
python scripts/run_import.py --skip-download --skip-filter
```

### Individual Operations
```bash
# Download from FTP
python scripts/utilities/ftp_downloader.py

# Filter products
python scripts/data_processing/filter_products.py input.csv reference.csv

# Upload to Shopify (new modular version)
python scripts/shopify/shopify_uploader_new.py products.csv \
  --shop-url your-shop.myshopify.com \
  --access-token your-token

# Cleanup duplicate images
python scripts/cleanup/cleanup_duplicate_images.py \
  --shop-url your-shop.myshopify.com \
  --access-token your-token
```

### Testing
```bash
# Run all tests
pytest

# Run specific test types
pytest -m quick        # Fast unit tests
pytest -m integration  # Integration tests
pytest -m e2e          # End-to-end tests
pytest -m performance  # Performance tests
```

## Web Dashboard Features

### Authentication
- Secure JWT-based authentication
- User session management
- Protected API endpoints

### Sync Control
- **Manual Trigger**: Start sync operations on-demand
- **Progress Monitoring**: Real-time sync status
- **History View**: Past sync operations and results

### Log Viewer
- Real-time log streaming
- Filterable log levels
- Error highlighting and details

## Data Flow

1. **FTP Download**: Retrieve latest product data from Etilize
2. **Data Filtering**: Filter against reference catalogs (Xorosoft)
3. **Metafield Creation**: Transform data into Shopify metafield structure
4. **Product Upload**: Create/update products in Shopify
5. **Image Processing**: Add product images with duplicate detection
6. **Cleanup**: Remove duplicate images and validate data

## Configuration

### Environment Variables
- `FTP_HOST`, `FTP_USERNAME`, `FTP_PASSWORD` - Etilize FTP credentials
- `SHOPIFY_SHOP_URL`, `SHOPIFY_ACCESS_TOKEN` - Shopify API credentials
- `JWT_SECRET_KEY` - Web dashboard authentication

### File Locations
- **Input Data**: `data/` directory
- **Processed Files**: `data/shopify_*.csv`
- **Reference Data**: `data/Xorosoft*.csv`
- **Logs**: Console output with optional file logging

## Advanced Features

### Duplicate Detection
- **Filename-based**: Detect images with identical filenames
- **Size-based**: Identify images with identical file sizes
- **Content-based**: Future enhancement for content comparison

### Image Management
- **Multiple Format Support**: JPG, PNG, GIF, WebP
- **Batch Processing**: Efficient bulk image operations
- **Error Recovery**: Retry failed uploads with exponential backoff

### Performance Optimization
- **API Rate Limiting**: Respect Shopify API limits
- **Chunk Processing**: Memory-efficient large file handling
- **Concurrent Operations**: Multi-threaded processing where safe

## Troubleshooting

### Common Issues

**Authentication Errors**
```bash
# Verify credentials
python scripts/shopify/shopify_uploader_new.py --validate-token \
  --shop-url your-shop.myshopify.com --access-token your-token
```

**FTP Connection Issues**
- Check network connectivity
- Verify FTP credentials in `.env`
- Test with standalone FTP client

**Memory Issues**
- Reduce chunk sizes in processing scripts
- Process smaller data batches
- Monitor system memory usage

**Import Failures**
- Check Shopify API rate limits
- Verify product data format
- Review error logs for details

### Debug Mode
Enable debug logging for detailed troubleshooting:
```bash
python scripts/run_import.py --debug
```

### Log Analysis
- Console logs show progress and errors
- Use `--debug` flag for verbose output
- Check Shopify admin for import status

## Migration Notes

### From Legacy Scripts
- Use `shopify_uploader_new.py` instead of `shopify_uploader.py`
- Update import paths for modular organization
- New scripts provide enhanced duplicate detection

### Script Path Changes
- Old: `scripts/ftp_downloader.py`
- New: `scripts/utilities/ftp_downloader.py`

## Development

### Prerequisites
- Python 3.8+
- Node.js 16+ (for frontend)
- Git
- Virtual environment recommended

### Development Workflow
1. Set up virtual environment and install dependencies
2. Configure `.env` with development credentials
3. Run tests before making changes
4. Use modular scripts for new development
5. Update documentation for changes

### Testing Strategy
- **Unit Tests**: Individual function validation
- **Integration Tests**: Module interaction testing
- **End-to-End Tests**: Complete workflow validation
- **Performance Tests**: Load and stress testing

## Support

For technical issues:
1. Check this documentation
2. Review error logs with `--debug` flag
3. Test individual components
4. Verify credentials and network connectivity

## License

[Specify your license here]