# Scripts Comprehension Report

## Overview

This document provides a comprehensive analysis of the product data processing pipeline scripts. The pipeline consists of three main Python scripts and their associated configuration:

1. FTP Downloader (`scripts/utilities/ftp_downloader.py`)
2. Empty Columns Remover (`scripts/remove_empty_columns.py`)
3. Shopify Uploader (`scripts/shopify/shopify_uploader.py`)

## Environment Variables

Required environment variables (`.env.example`):

### Shopify Configuration
```
SHOPIFY_API_KEY=
SHOPIFY_API_SECRET=
SHOPIFY_STORE_URL=
```

### FTP Configuration
```
FTP_HOST=
FTP_USER=
FTP_PASSWORD=
FTP_PATH=
```

## Script Details

### 1. FTP Downloader (`ftp_downloader.py`)

**Purpose**: Downloads product data files from the FTP server securely.

**Key Features**:
- Secure FTP connection using credentials from environment variables
- Download progress monitoring and performance metrics
- Robust error handling
- Detailed logging

**Usage**:
```python
from scripts.ftp_downloader import FTPDownloader

downloader = FTPDownloader(
    host=os.getenv("FTP_HOST"),
    username=os.getenv("FTP_USER"),
    password=os.getenv("FTP_PASSWORD"),
    remote_path=os.getenv("FTP_PATH")
)

downloader.connect()
local_file = downloader.download()  # Downloads default file: CWS_Etilize_reduced.csv
```

### 2. Empty Columns Remover (`remove_empty_columns.py`)

**Purpose**: Processes large CSV files by removing entirely empty columns to reduce file size.

**Key Features**:
- Handles large files through chunked processing
- Automatic encoding detection
- Memory-efficient processing
- Creates a log of removed columns

**Configuration**:
```python
INPUT_CSV = "CWS_Etilize.csv"
OUTPUT_CSV = "CWS_Etilize_reduced.csv"
REMOVED_COLS_FILE = "removed_columns.txt"
CHUNK_SIZE = 10000
```

**Usage**:
```bash
python scripts/remove_empty_columns.py
```

### 3. Shopify Uploader (`shopify_uploader.py`)

**Purpose**: Uploads processed product data to Shopify using their Admin API.

**Key Features**:
- Concurrent uploads with ThreadPoolExecutor
- Advanced rate limiting with burst handling
- Connection pooling and retry logic
- Detailed performance metrics and logging
- Supports both single and batch uploads

**Usage**:
```python
from scripts.shopify_uploader import ShopifyUploader

uploader = ShopifyUploader(
    shop_url=os.getenv("SHOPIFY_STORE_URL"),
    access_token=os.getenv("SHOPIFY_API_KEY")
)

# Single product upload
product_data = {
    "title": "Test Product",
    "body_html": "<strong>Test product description</strong>",
    "vendor": "Test Vendor",
    "product_type": "Test Type",
    "status": "draft"
}
result = uploader.upload_product(product_data)

# Batch upload
products = [product_data1, product_data2, ...]
results = uploader.upload_batch(products)
```

## Data Flow

1. The FTP Downloader retrieves `CWS_Etilize.csv` from the FTP server
2. The Empty Columns Remover processes this file to create `CWS_Etilize_reduced.csv`
3. The Shopify Uploader reads the processed file and uploads products to Shopify

## Manual Execution Steps

1. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

2. Download product data:
   ```python
   # Run FTP downloader
   python scripts/utilities/ftp_downloader.py
   ```

3. Process the CSV:
   ```python
   # Remove empty columns
   python scripts/remove_empty_columns.py
   ```

4. Upload to Shopify:
   ```python
   # Upload products
   python scripts/shopify/shopify_uploader.py
   ```

## Potential Issues and Recommendations

1. **FTP Downloader**:
   - Consider implementing resume capability for large file downloads
   - Add file checksum verification
   - Implement concurrent downloads for multiple files

2. **Empty Columns Remover**:
   - Add progress bar for better visibility
   - Consider parallelizing the processing for larger files
   - Add validation for CSV structure

3. **Shopify Uploader**:
   - Implement webhook support for upload status notifications
   - Add product validation before upload
   - Consider implementing incremental updates

## Dependencies

### Required Python Packages
- `pandas`: For CSV processing
- `requests`: For Shopify API communication
- `chardet`: For file encoding detection
- `python-dotenv` (recommended): For environment variable management

### Installation
```bash
pip install pandas requests chardet python-dotenv