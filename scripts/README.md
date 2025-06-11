# Scripts Organization

This directory contains all the Python scripts for the Cowan's Product Feed Integration System, organized into logical modules for better maintainability and understanding.

## Directory Structure

```
scripts/
├── __init__.py
├── run_import.py                   # Main orchestration script
├── README.md                       # This documentation
│
├── shopify/                        # Shopify integration scripts
│   ├── __init__.py
│   ├── shopify_base.py            # Base classes and utilities
│   ├── shopify_image_manager.py   # Image operations and deduplication
│   ├── shopify_product_manager.py # Product CRUD and data transformation
│   ├── shopify_uploader.py        # Original monolithic uploader (legacy)
│   └── shopify_uploader_new.py    # New modular uploader (recommended)
│
├── data_processing/               # Data transformation scripts
│   ├── __init__.py
│   ├── filter_products.py         # Filter products against reference data
│   ├── categorize_products.py     # Product categorization
│   ├── create_metafields.py       # Generate Shopify metafields
│   ├── extract_additional_images.py # Extract additional product images
│   └── extract_columns.py         # Column extraction utilities
│
├── cleanup/                       # Maintenance and cleanup scripts
│   ├── __init__.py
│   ├── cleanup_duplicate_images.py # Remove duplicate images
│   ├── cleanup_size_duplicates.py # Size-based duplicate cleanup
│   └── find_duplicate_products.py # Find duplicate products
│
├── utilities/                     # Helper scripts and utilities
│   ├── __init__.py
│   ├── ftp_downloader.py          # Download files from FTP
│   ├── check_base_part.py         # Base part number validation
│   └── check_metafields.py        # Metafield validation
│
├── debug/                         # Debugging and diagnostic scripts
│   ├── __init__.py
│   ├── debug_base_part_mapping.py # Debug base part number mapping
│   ├── debug_filter_products.py   # Debug product filtering
│   └── debug_metafield_matching.py # Debug metafield matching
│
└── tests/                         # Test scripts and validation tools
    ├── __init__.py
    ├── test_categorize_products.py # Test product categorization
    ├── test_file_size_detection.py # Test file size detection
    └── test_xorosoft_api.py        # Test Xorosoft API integration
```

## Script Categories

### 1. Shopify Integration (`shopify/`)
Scripts that handle all Shopify API interactions:
- **shopify_uploader_new.py**: Main modular uploader (recommended for new work)
- **shopify_uploader.py**: Original monolithic uploader (legacy, still functional)
- **shopify_base.py**: Base classes, rate limiting, GraphQL execution
- **shopify_image_manager.py**: Image operations and deduplication
- **shopify_product_manager.py**: Product CRUD and data transformation

### 2. Data Processing (`data_processing/`)
Scripts that transform and process product data:
- **filter_products.py**: Filter products against reference data
- **categorize_products.py**: Product categorization using taxonomy
- **create_metafields.py**: Generate Shopify metafields from CSV data
- **extract_additional_images.py**: Extract additional product images
- **extract_columns.py**: Column extraction utilities

### 3. Cleanup and Maintenance (`cleanup/`)
Scripts for cleaning up duplicate data:
- **cleanup_duplicate_images.py**: Remove duplicate images from products
- **cleanup_size_duplicates.py**: Size-based duplicate cleanup
- **find_duplicate_products.py**: Find duplicate products in Shopify

### 4. Utilities (`utilities/`)
Helper scripts and general utilities:
- **ftp_downloader.py**: Download files from Etilize FTP
- **check_base_part.py**: Base part number validation
- **check_metafields.py**: Metafield validation

### 5. Debug (`debug/`)
Debugging and diagnostic scripts:
- **debug_base_part_mapping.py**: Debug base part number mapping
- **debug_filter_products.py**: Debug product filtering
- **debug_metafield_matching.py**: Debug metafield matching

### 6. Tests (`tests/`)
Test scripts and validation tools:
- **test_categorize_products.py**: Test product categorization
- **test_file_size_detection.py**: Test file size detection
- **test_xorosoft_api.py**: Test Xorosoft API integration

## Usage

### Main Workflow
The primary entry point is `run_import.py` which orchestrates the entire import process:

```bash
python scripts/run_import.py
```

### Individual Scripts
Scripts can also be run individually for specific tasks:

```bash
# Download files from FTP
python scripts/utilities/ftp_downloader.py

# Filter products
python scripts/data_processing/filter_products.py input.csv reference.csv

# Upload to Shopify (new modular version)
python scripts/shopify/shopify_uploader_new.py data.csv --shop-url store.myshopify.com --access-token TOKEN

# Cleanup duplicates
python scripts/cleanup/cleanup_duplicate_images.py --shop-url store.myshopify.com --access-token TOKEN
```

## Import Path Changes

With the new organization, import paths have been updated:

- Old: `from scripts.shopify_uploader import ShopifyUploader`
- New: `from scripts.shopify.shopify_uploader import ShopifyUploader`

- Old: `from scripts.ftp_downloader import FTPDownloader`
- New: `from scripts.utilities.ftp_downloader import FTPDownloader`

## Modular Architecture

The Shopify module has been refactored into a modular architecture:

1. **shopify_base.py** (253 lines): Base classes, rate limiting, GraphQL execution
2. **shopify_image_manager.py** (418 lines): Image operations and deduplication
3. **shopify_product_manager.py** (388 lines): Product CRUD and data transformation
4. **shopify_uploader_new.py** (350 lines): Main orchestrator

This replaces the original 1,393-line monolithic `shopify_uploader.py` with more maintainable modules.

## Migration Notes

- All existing functionality is preserved
- The original `shopify_uploader.py` remains available for compatibility
- New development should use the modular components in `shopify_uploader_new.py`
- File paths in `run_import.py` have been updated to match the new structure