# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Product Feed Integration System for Shopify that automates synchronization of product data between Etilize (via FTP) and Shopify. The system is designed with three main modules:

1. **Core Integration Module** (Python) - Handles FTP download, data transformation, and Shopify API integration
2. **Web Dashboard Module** (React/TypeScript + Flask) - Provides UI for manual sync triggering and log viewing  
3. **Authentication and Scheduling Module** (Supabase) - Manages user auth and scheduled syncs

## Architecture

The system follows a modular architecture with clear separation between:
- **Backend scripts** (`scripts/`) - Core data processing logic organized in modules
- **Frontend dashboard** (`frontend/`) - React-based web interface
- **Web dashboard backend** (`web_dashboard/backend/`) - Flask API for dashboard

Key data flow: FTP Downloader → Data Transformer → Shopify Uploader

## Common Commands

### Python Backend
```bash
# Run full import workflow with interactive prompts
python scripts/run_import.py

# Skip specific stages
python scripts/run_import.py --skip-download --skip-filter

# Individual script execution (NEW MODULAR PATHS)
python scripts/utilities/ftp_downloader.py
python scripts/data_processing/filter_products.py <input_file> <reference_file>
python scripts/data_processing/create_metafields.py <input_file>

# Shopify upload (CHOOSE ONE - new modular version recommended)
python scripts/shopify/shopify_uploader_new.py <csv_file> --shop-url <url> --access-token <token>
python scripts/shopify/shopify_uploader.py <csv_file> --shop-url <url> --access-token <token>  # Legacy

# Cleanup operations
python scripts/cleanup/cleanup_duplicate_images.py --shop-url <url> --access-token <token>
python scripts/cleanup/cleanup_size_duplicates.py --shop-url <url> --access-token <token>

# Debug tools
python scripts/debug/debug_filter_products.py
python scripts/debug/debug_metafield_matching.py

# Run Python tests
pytest
pytest -m quick    # Basic function tests
pytest -m integration  # Component interaction tests
pytest -m e2e      # End-to-end flow tests
pytest -m performance  # Load and stress tests
```

### Frontend Development
```bash
cd frontend/
npm install
npm start          # Development server
npm run build      # Production build
npm test           # Run tests
npm run test:watch # Watch mode
npm run test:coverage  # Coverage report
```

### Web Dashboard Backend
```bash
cd web_dashboard/backend/
pip install -r requirements.txt
python app.py      # Start Flask server
```

## Script Organization

The project uses a modular script organization (see `scripts/README.md` for details):

### Shopify Integration (`scripts/shopify/`)
- `shopify_uploader_new.py` - **RECOMMENDED**: Main modular uploader
- `shopify_uploader.py` - Legacy monolithic uploader (still functional)
- `shopify_base.py` - Base classes, rate limiting, GraphQL execution
- `shopify_image_manager.py` - Image operations and deduplication
- `shopify_product_manager.py` - Product CRUD and data transformation

### Data Processing (`scripts/data_processing/`)
- `filter_products.py` - Filter products against reference data
- `categorize_products.py` - Product categorization using taxonomy
- `create_metafields.py` - Generate Shopify metafields from CSV data
- `extract_additional_images.py` - Extract additional product images
- `extract_columns.py` - Column extraction utilities

### Cleanup and Maintenance (`scripts/cleanup/`)
- `cleanup_duplicate_images.py` - Remove duplicate images from products
- `cleanup_size_duplicates.py` - Size-based duplicate cleanup
- `find_duplicate_products.py` - Find duplicate products in Shopify

### Utilities (`scripts/utilities/`)
- `ftp_downloader.py` - Download files from Etilize FTP
- `check_base_part.py` - Base part number validation
- `check_metafields.py` - Metafield validation

### Debug Tools (`scripts/debug/`)
- `debug_base_part_mapping.py` - Debug base part number mapping
- `debug_filter_products.py` - Debug product filtering
- `debug_metafield_matching.py` - Debug metafield matching

### Tests (`scripts/tests/`)
- `test_categorize_products.py` - Test product categorization
- `test_file_size_detection.py` - Test file size detection
- `test_xorosoft_api.py` - Test Xorosoft API integration

## Testing Strategy

The project uses a recursive testing strategy with custom pytest markers:
- `quick`: Basic function tests (run on every code change)
- `integration`: Component interaction tests (run before merge)  
- `e2e`: End-to-end flow tests (run nightly)
- `performance`: Load and stress tests (run weekly)

## Key Files & Directories

### Main Orchestration
- `scripts/run_import.py` - Main orchestration script with colorful progress tracking

### Data Flow
- Raw data: `data/` directory (CSV files from Etilize)
- Processed files: `data/shopify_*.csv` (ready for Shopify upload)
- Reference data: `data/Xorosoft*.csv` (for product filtering)

### Configuration
- Environment variables in `.env` file
- FTP credentials: `FTP_HOST`, `FTP_USERNAME`, `FTP_PASSWORD`
- Shopify credentials: `SHOPIFY_SHOP_URL`, `SHOPIFY_ACCESS_TOKEN`
- JWT secret: `JWT_SECRET_KEY`

## Development Workflow

1. **Data Processing**: Use `run_import.py` for full workflow or individual scripts for specific stages
2. **Frontend Changes**: Work in `frontend/` with hot reload via `npm start`
3. **API Changes**: Modify Flask app in `web_dashboard/backend/app.py`
4. **Testing**: Run appropriate test markers before committing

## Important Notes

- The system respects Shopify API rate limits through batch processing
- Product matching uses SKU or Manufacturer Part Number fields
- All operations are comprehensively logged for debugging
- The frontend uses Shadcn/UI components with Tailwind CSS
- Mock authentication is currently implemented (Supabase integration planned)
- **NEW**: Advanced duplicate detection includes filename and file size-based deduplication
- **NEW**: Modular architecture allows for better maintainability and testing

## Migration from Legacy Scripts

When using the new modular architecture:
- Use `shopify_uploader_new.py` instead of `shopify_uploader.py` for new development
- Import from organized modules: `from scripts.shopify.shopify_uploader import ShopifyUploader`
- Use the appropriate module path: `scripts/utilities/ftp_downloader.py` instead of `scripts/ftp_downloader.py`

## File Patterns

- Test files: `test_*.py`, `*_test.py`, `*_tests.py`
- Configuration: `*.ini`, `*.json`, `*.env`
- Data files: `data/*.csv`
- Build outputs: `frontend/dist/`, `frontend/node_modules/`

# important-instruction-reminders
Do what has been asked; nothing more, nothing less.
NEVER create files unless they're absolutely necessary for achieving your goal.
ALWAYS prefer editing an existing file to creating a new one.
NEVER proactively create documentation files (*.md) or README files. Only create documentation files if explicitly requested by the User.