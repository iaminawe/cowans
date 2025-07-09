# Shopify Handles and Collections Downloader - Usage Guide

## Overview

This script downloads product handles and their associated collections from a Shopify store and exports them to a CSV file. This is useful for data analysis, inventory management, and creating collection mappings.

## Prerequisites

- Python 3.7+
- Shopify Admin API access
- Valid Shopify store URL and access token

## Installation

```bash
# Install required dependencies
pip install requests pandas python-dotenv

# Ensure the script is in your Python path
export PYTHONPATH="${PYTHONPATH}:/path/to/cowans/scripts"
```

## Configuration

### Environment Variables

Create a `.env` file in your project root:

```env
SHOPIFY_SHOP_URL=your-store.myshopify.com
SHOPIFY_ACCESS_TOKEN=your_access_token_here
```

### Required Permissions

Your Shopify app/access token needs the following permissions:
- `read_products`
- `read_collections`

## Usage Examples

### Basic Usage

```python
from scripts.shopify.shopify_handles_collections_downloader import ShopifyHandlesCollectionsDownloader

# Initialize the downloader
downloader = ShopifyHandlesCollectionsDownloader(
    shop_url="your-store.myshopify.com",
    access_token="your_access_token",
    output_file="product_handles_collections.csv"
)

# Download and export all products
result = downloader.download_and_export()
print(f"Exported {result['products_count']} products to {result['csv_file']}")
```

### Command Line Usage

```bash
# Basic download
python scripts/shopify/shopify_handles_collections_downloader.py \
    --shop-url your-store.myshopify.com \
    --access-token your_access_token \
    --output product_handles.csv

# With environment variables
python scripts/shopify/shopify_handles_collections_downloader.py \
    --output product_handles.csv

# Limited download (first 100 products)
python scripts/shopify/shopify_handles_collections_downloader.py \
    --shop-url your-store.myshopify.com \
    --access-token your_access_token \
    --limit 100 \
    --output sample_products.csv
```

### Advanced Usage

```python
# Custom configuration with error handling
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO)

try:
    downloader = ShopifyHandlesCollectionsDownloader(
        shop_url="your-store.myshopify.com",
        access_token="your_access_token",
        output_file="exports/product_data.csv"
    )
    
    # Test connection first
    if downloader.connect():
        print("✓ Successfully connected to Shopify")
        
        # Download with progress tracking
        result = downloader.download_and_export(limit=500)
        
        print(f"✓ Export completed successfully!")
        print(f"  - Products exported: {result['products_count']}")
        print(f"  - File location: {result['csv_file']}")
        print(f"  - Execution time: {result['execution_time']:.2f} seconds")
        
    else:
        print("✗ Failed to connect to Shopify")
        
except Exception as e:
    print(f"✗ Error: {e}")
```

### Batch Processing for Large Stores

```python
# For stores with many products, use batch processing
def download_in_batches(downloader, batch_size=250):
    all_results = []
    batch_num = 0
    
    while True:
        batch_num += 1
        print(f"Processing batch {batch_num}...")
        
        # Fetch batch
        products = downloader.fetch_products_with_collections(
            limit=batch_size,
            offset=(batch_num - 1) * batch_size
        )
        
        if not products:
            break
            
        # Export batch
        batch_file = f"batch_{batch_num}_products.csv"
        downloader.output_file = batch_file
        downloader.export_to_csv(products)
        
        all_results.extend(products)
        print(f"✓ Batch {batch_num}: {len(products)} products exported to {batch_file}")
        
        # Rate limiting
        time.sleep(1)
    
    return all_results

# Usage
downloader = ShopifyHandlesCollectionsDownloader(shop_url, access_token)
all_products = download_in_batches(downloader)
print(f"Total products processed: {len(all_products)}")
```

## Output Format

The script generates a CSV file with the following columns:

| Column | Description | Example |
|--------|-------------|---------|
| `product_id` | Shopify product ID | `gid://shopify/Product/123456789` |
| `product_handle` | URL handle/slug | `ergonomic-office-chair` |
| `product_title` | Product title | `Ergonomic Office Chair - Black` |
| `collection_handles` | Semicolon-separated collection handles | `furniture;office-chairs;ergonomic` |
| `collection_titles` | Semicolon-separated collection titles | `Furniture;Office Chairs;Ergonomic` |
| `collection_count` | Number of collections | `3` |

### Example CSV Output

```csv
product_id,product_handle,product_title,collection_handles,collection_titles,collection_count
gid://shopify/Product/123,ergonomic-chair,Ergonomic Office Chair,furniture;office-chairs,Furniture;Office Chairs,2
gid://shopify/Product/124,wireless-mouse,Wireless Mouse,electronics;computer-accessories,Electronics;Computer Accessories,2
gid://shopify/Product/125,desk-lamp,LED Desk Lamp,lighting;office-accessories,Lighting;Office Accessories,2
```

## Error Handling

### Common Errors and Solutions

1. **Authentication Error**
   ```
   Error: Invalid Shopify access token
   ```
   - Verify your access token is correct
   - Check token permissions include `read_products` and `read_collections`
   - Ensure shop URL format is correct (your-store.myshopify.com)

2. **Rate Limit Error**
   ```
   Error: API rate limit exceeded
   ```
   - The script automatically handles rate limiting with exponential backoff
   - For large stores, consider using batch processing
   - Monitor API usage in Shopify Admin

3. **Network Connection Error**
   ```
   Error: Connection timeout
   ```
   - Check internet connection
   - Verify Shopify store is accessible
   - Try again with retry logic

4. **File Permission Error**
   ```
   Error: Permission denied writing to file
   ```
   - Check write permissions for output directory
   - Ensure output path exists
   - Use absolute file paths

### Debugging

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Now run your script - you'll see detailed API requests and responses
```

## Performance Considerations

### Large Stores (1000+ products)
- Use batch processing with appropriate delays
- Monitor API rate limits (40 calls per second for REST, 1000 points per second for GraphQL)
- Consider running during off-peak hours

### Memory Usage
- The script processes products in batches to minimize memory usage
- For very large stores (10,000+ products), consider streaming to CSV

### Network Optimization
- Use GraphQL queries to fetch only required fields
- Implement connection pooling for multiple requests
- Add retry logic with exponential backoff

## Integration with Existing Codebase

### Using with Existing Shopify Modules

```python
# Integration with existing shopify_base.py
from scripts.shopify.shopify_base import ShopifyAPIBase
from scripts.shopify.shopify_handles_collections_downloader import ShopifyHandlesCollectionsDownloader

# The downloader extends the same base patterns
class CustomDownloader(ShopifyAPIBase):
    def __init__(self, shop_url, access_token):
        super().__init__(shop_url, access_token)
        self.downloader = ShopifyHandlesCollectionsDownloader(shop_url, access_token)
    
    def custom_export(self):
        return self.downloader.download_and_export()
```

### Using with Existing Test Framework

```python
# The script follows the same testing patterns as other modules
import pytest
from tests.test_shopify_handles_collections_downloader import test_downloader_initialization

# Run specific tests
pytest tests/test_shopify_handles_collections_downloader.py -m quick
pytest tests/test_shopify_handles_collections_downloader.py -m integration
```

## Troubleshooting

### Script Not Found
```bash
# Ensure script is in correct location
ls scripts/shopify/shopify_handles_collections_downloader.py

# Check Python path
python -c "import sys; print('\\n'.join(sys.path))"
```

### Import Errors
```python
# If getting import errors, check dependencies
pip list | grep -E "(requests|pandas|python-dotenv)"

# Install missing dependencies
pip install -r requirements.txt
```

### Permission Issues
```bash
# Check file permissions
ls -la scripts/shopify/shopify_handles_collections_downloader.py

# Make executable if needed
chmod +x scripts/shopify/shopify_handles_collections_downloader.py
```

## Best Practices

1. **Always test with a small limit first**
   ```python
   # Test with first 10 products
   result = downloader.download_and_export(limit=10)
   ```

2. **Use meaningful output filenames**
   ```python
   from datetime import datetime
   timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
   output_file = f"product_handles_{timestamp}.csv"
   ```

3. **Monitor API usage**
   - Check Shopify Admin for API usage
   - Implement logging for API calls
   - Use appropriate delays between requests

4. **Backup existing data**
   ```python
   import shutil
   if os.path.exists("product_handles.csv"):
       shutil.copy("product_handles.csv", "product_handles_backup.csv")
   ```

5. **Validate output data**
   ```python
   import pandas as pd
   df = pd.read_csv("product_handles.csv")
   print(f"Exported {len(df)} products")
   print(f"Products with collections: {df[df['collection_count'] > 0].shape[0]}")
   ```

## Support

For issues or questions:
1. Check the test suite for examples: `tests/test_shopify_handles_collections_downloader.py`
2. Review existing Shopify modules in `scripts/shopify/`
3. Check Shopify API documentation: https://shopify.dev/api
4. Enable debug logging for detailed error information