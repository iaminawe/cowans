#!/usr/bin/env python3
"""
Shopify Product Uploader - Main Orchestrator

This is the main script that coordinates product uploads to Shopify.
It uses the modular components to handle CSV processing, product management,
and image operations.
"""

import os
import sys
import csv
import argparse
import logging
from typing import Dict, List, Optional
from collections import defaultdict

try:
    from .shopify_base import ShopifyAPIBase
    from .shopify_product_manager import ShopifyProductManager
    from .shopify_image_manager import ShopifyImageManager
except ImportError:
    from shopify_base import ShopifyAPIBase
    from shopify_product_manager import ShopifyProductManager
    from shopify_image_manager import ShopifyImageManager

class ShopifyUploader:
    """Main orchestrator for Shopify product uploads."""
    
    def __init__(self, shop_url: str, access_token: str, batch_size: int = 25,
                 max_workers: int = 1, debug: bool = False, data_source: str = 'default',
                 cleanup_duplicates: bool = False):
        """Initialize the uploader with all required managers."""
        self.shop_url = shop_url
        self.access_token = access_token
        self.batch_size = batch_size
        self.max_workers = max_workers
        self.debug = debug
        self.data_source = data_source
        self.cleanup_duplicates = cleanup_duplicates
        
        # Initialize managers
        self.product_manager = ShopifyProductManager(shop_url, access_token, debug, data_source)
        self.image_manager = ShopifyImageManager(shop_url, access_token, debug)
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        if debug:
            self.logger.setLevel(logging.DEBUG)
        
        # Upload metrics
        self.upload_metrics = {
            'successful_uploads': 0,
            'failed_uploads': 0,
            'skipped_uploads': 0,
            'duplicates_cleaned': 0,
            'retry_count': 0
        }
    
    def test_auth(self) -> None:
        """Test Shopify API authentication."""
        try:
            self.product_manager.test_auth()
            print("✅ Shopify authentication successful")
        except Exception as e:
            print(f"❌ Shopify authentication failed: {e}")
            raise
    
    def process_csv(self, csv_path: str, limit: Optional[int] = None) -> None:
        """Process CSV file and upload products to Shopify."""
        try:
            print(f"📁 Processing CSV file: {csv_path}")
            self.logger.info(f"Processing CSV file: {csv_path}")
            
            # Read and parse CSV
            products_data = self._read_csv_file(csv_path, limit)
            
            if not products_data:
                raise ValueError("No valid product data found in CSV file")
            
            print(f"📊 Found {len(products_data)} product(s) to process")
            
            # Process each product
            for i, (handle, product_rows) in enumerate(products_data.items(), 1):
                print(f"\n[{i}/{len(products_data)}] Processing: {handle}")
                self.logger.info(f"Processing product {i}/{len(products_data)}: {handle}")
                
                try:
                    self._process_single_product(handle, product_rows)
                except Exception as e:
                    print(f"    ❌ Failed to process product '{handle}': {str(e)}")
                    self.logger.error(f"Failed to process product {handle}: {str(e)}")
                    self.upload_metrics['failed_uploads'] += 1
                    continue
            
            # Print final summary
            self._print_summary()
            
        except Exception as e:
            self.logger.error(f"Fatal error processing CSV: {str(e)}")
            raise
    
    def _read_csv_file(self, csv_path: str, limit: Optional[int] = None) -> Dict[str, List[Dict]]:
        """Read and parse CSV file, grouping rows by product handle."""
        products_data = defaultdict(list)
        seen_handles = set()
        
        with open(csv_path, 'r', encoding='utf-8-sig') as file:
            # Detect delimiter
            sample = file.read(1024)
            file.seek(0)
            sniffer = csv.Sniffer()
            delimiter = sniffer.sniff(sample).delimiter
            
            reader = csv.DictReader(file, delimiter=delimiter)
            
            for idx, row in enumerate(reader, 1):
                # Clean up row data
                row = {k.strip() if k else f'col_{i}': v.strip() if v else '' 
                      for i, (k, v) in enumerate(row.items())}
                
                # Skip empty rows
                if not any(v for v in row.values()):
                    continue
                
                title = row.get('Title', row.get('title', '')).strip()
                handle = row.get('URL handle', row.get('url handle', '')).strip()
                
                if not title and not handle:
                    self.logger.warning(f"Skipping row {idx}: Missing both title and handle")
                    continue
                elif not title and handle:
                    # This is likely an additional image for an existing product
                    self.logger.debug(f"Row {idx}: Additional image for product handle '{handle}'")
                
                if handle in seen_handles:
                    self.logger.debug(f"Additional data/image for existing product {handle}")
                else:
                    seen_handles.add(handle)
                
                products_data[handle].append(row)
        
        # Apply limit if specified
        if limit:
            limited_data = {}
            for i, (handle, rows) in enumerate(products_data.items()):
                if i >= limit:
                    break
                limited_data[handle] = rows
            products_data = limited_data
        
        return dict(products_data)
    
    def _process_single_product(self, handle: str, product_rows: List[Dict]) -> None:
        """Process a single product with its associated data/images."""
        # Check if this is additional images only (no title in any row)
        has_titles = any(row.get('Title', row.get('title', '')).strip() for row in product_rows)
        
        if not has_titles:
            # This is additional images for an existing product
            self._process_additional_images(handle, product_rows)
        else:
            # This is a full product (create or update)
            self._process_full_product(handle, product_rows)
    
    def _process_additional_images(self, handle: str, product_rows: List[Dict]) -> None:
        """Process additional images for an existing product."""
        print(f"    📸 Processing additional images...")
        
        # Extract image URLs
        image_urls = self.product_manager.extract_images_from_rows(product_rows)
        
        if not image_urls:
            print(f"    ⚠️  No image URLs found in additional image rows")
            return
        
        print(f"    📸 Found {len(image_urls)} additional images:")
        for i, image_url in enumerate(image_urls, 1):
            print(f"    📸 Image {i}: {image_url}")
        
        # Get existing product
        product_id = self.product_manager.get_product_by_handle(handle)
        
        if product_id:
            print(f"    🖼️  Adding additional images to existing product...")
            self.logger.info(f"Adding {len(product_rows)} additional images to existing product {handle}")
            
            # For additional images, don't force update - let it check for changes
            self.image_manager.manage_product_images(product_id, image_urls, handle, force_update=False)
            self.upload_metrics['successful_uploads'] += 1
            print(f"    ✅ Successfully processed additional images!")
        else:
            print(f"    ❌ Cannot add images: Product {handle} not found")
            self.logger.warning(f"Cannot add additional images: Product {handle} not found in Shopify")
            self.upload_metrics['failed_uploads'] += 1
    
    def _process_full_product(self, handle: str, product_rows: List[Dict]) -> None:
        """Process a full product (create or update)."""
        # Use the first row for product data (should contain title, etc.)
        main_row = product_rows[0]
        
        try:
            # Map CSV data to product structure
            product_data = self.product_manager.map_row_to_product(main_row)
            
            # Validate product data
            if not self.product_manager.validate_product_data(product_data):
                raise ValueError("Product data validation failed")
            
            # Check if product exists
            existing_product_id = self.product_manager.get_product_by_handle(handle)
            
            if existing_product_id:
                # Product exists - check if it needs updating
                print(f"    📦 Product exists, checking for changes...")
                
                if self.product_manager.has_product_changed(product_data, handle):
                    print(f"    🔄 Product has changes, updating...")
                    product_id = self.product_manager.upload_product(product_data, existing_product_id)
                    self.upload_metrics['successful_uploads'] += 1
                    print(f"    ✅ Successfully updated product!")
                    self.logger.debug(f"Successfully updated product with ID: {product_id}")
                    
                    # Manage images for updated product
                    image_urls = self.product_manager.extract_images_from_rows(product_rows)
                    if image_urls:
                        self.image_manager.manage_product_images(product_id, image_urls, handle, force_update=True)
                else:
                    print(f"    ⏭️  No changes detected, skipping update")
                    self.logger.debug(f"Product {handle} unchanged, skipping")
                    self.upload_metrics['skipped_uploads'] += 1
                    
                    # Run duplicate cleanup for unchanged products if requested
                    if self.cleanup_duplicates:
                        print(f"    🧹 Running duplicate cleanup for unchanged product...")
                        image_urls = self.product_manager.extract_images_from_rows(product_rows)
                        self.image_manager.manage_product_images(existing_product_id, image_urls, 
                                                               handle, force_update=False, cleanup_only=True)
                    else:
                        print(f"    🖼️  Skipping image processing (product unchanged)")
            else:
                # Create new product
                print(f"    ➕ Creating new product...")
                product_id = self.product_manager.upload_product(product_data)
                self.upload_metrics['successful_uploads'] += 1
                print(f"    ✅ Successfully created product!")
                self.logger.debug(f"Successfully created product with ID: {product_id}")
                
                # Manage images for new product
                if product_id:
                    image_urls = self.product_manager.extract_images_from_rows(product_rows)
                    if image_urls:
                        self.image_manager.manage_product_images(product_id, image_urls, handle, force_update=True)
                        
        except Exception as e:
            print(f"    ❌ Failed to process product: {str(e)}")
            self.logger.error(f"Failed to process product {handle}: {str(e)}")
            raise
    
    def _print_summary(self) -> None:
        """Print upload summary."""
        print(f"\n📊 Upload Summary:")
        print(f"    ✅ Successful: {self.upload_metrics['successful_uploads']}")
        print(f"    ⏭️  Skipped: {self.upload_metrics['skipped_uploads']}")
        print(f"    ❌ Failed: {self.upload_metrics['failed_uploads']}")
        print(f"    🧹 Duplicates cleaned: {self.upload_metrics['duplicates_cleaned']}")
        print(f"    🔄 Retries: {self.upload_metrics['retry_count']}")
        
        self.logger.info(
            f"Upload completed - "
            f"Successful: {self.upload_metrics['successful_uploads']}, "
            f"Skipped: {self.upload_metrics['skipped_uploads']}, "
            f"Failed: {self.upload_metrics['failed_uploads']}, "
            f"Duplicates cleaned: {self.upload_metrics['duplicates_cleaned']}, "
            f"Retries: {self.upload_metrics['retry_count']}"
        )

def main() -> None:
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description='Upload products to Shopify from CSV using GraphQL API',
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    parser.add_argument('csv_file', type=str, help='Path to CSV file containing product data', nargs='?')
    parser.add_argument('--shop-url', required=True, help='Shopify shop URL (*.myshopify.com)')
    parser.add_argument('--access-token', required=True, help='Shopify Admin API access token')
    parser.add_argument('--batch-size', type=int, default=25, help='Batch size for uploads (default: 25)')
    parser.add_argument('--max-workers', type=int, default=1, help='Maximum number of concurrent uploads (default: 1)')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--data-source', choices=['default', 'etilize'], default='default',
                      help='Data source format (affects column mapping)')
    parser.add_argument('--limit', type=int, help='Limit number of products to import (for testing)')
    parser.add_argument('--validate-token', action='store_true', help='Validate Shopify access token')
    parser.add_argument('--cleanup-duplicates', action='store_true', 
                      help='Force cleanup of duplicate images even for unchanged products')
    
    if len(sys.argv) == 1 or '--help' in sys.argv or '-h' in sys.argv:
        print("\nExample usage:")
        print("python shopify_uploader_new.py data/products.csv --shop-url store.myshopify.com --access-token TOKEN")
        print("python shopify_uploader_new.py data/products.csv --shop-url store.myshopify.com --access-token TOKEN --data-source etilize")
        print("python shopify_uploader_new.py data/products.csv --shop-url store.myshopify.com --access-token TOKEN --limit 10 --debug")
        print("python shopify_uploader_new.py --shop-url store.myshopify.com --access-token TOKEN --validate-token")
        sys.exit(1)
    
    args = parser.parse_args()
    
    try:
        # Format shop URL consistently
        shop_url = args.shop_url.strip().lower()
        if not shop_url.startswith('https://'):
            shop_url = f"https://{shop_url}"
        if '.' not in shop_url and not shop_url.endswith('myshopify.com'):
            shop_url += '.myshopify.com'
            
        uploader = ShopifyUploader(
            shop_url=shop_url,
            access_token=args.access_token.strip(),
            batch_size=args.batch_size,
            max_workers=args.max_workers,
            debug=args.debug,
            data_source=args.data_source,
            cleanup_duplicates=args.cleanup_duplicates
        )
        
        if args.validate_token:
            uploader.test_auth()
            return
        
        if not args.csv_file:
            print("Error: CSV file is required unless using --validate-token")
            sys.exit(1)
            
        if not os.path.exists(args.csv_file):
            print(f"Error: CSV file '{args.csv_file}' not found")
            sys.exit(1)
        
        # Process the CSV file
        uploader.process_csv(args.csv_file, args.limit)
        
        print(f"\n🎉 Upload process completed successfully!")
        
    except KeyboardInterrupt:
        print(f"\n⚠️  Upload interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()