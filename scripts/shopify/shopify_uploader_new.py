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
                 cleanup_duplicates: bool = False, skip_images: bool = False, ultra_fast: bool = False,
                 silent: bool = False, turbo: bool = False, hyper: bool = False):
        """Initialize the uploader with all required managers."""
        self.shop_url = shop_url
        self.access_token = access_token
        self.batch_size = batch_size
        self.max_workers = max_workers
        self.debug = debug
        self.data_source = data_source
        self.cleanup_duplicates = cleanup_duplicates
        self.skip_images = skip_images
        self.ultra_fast = ultra_fast
        self.silent = silent
        self.turbo = turbo
        self.hyper = hyper
        
        # Initialize managers with turbo/hyper mode
        self.product_manager = ShopifyProductManager(shop_url, access_token, debug, data_source, turbo, hyper)
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
    
    def process_csv(self, csv_path: str, limit: Optional[int] = None, start_from: Optional[int] = None) -> None:
        """Process CSV file and upload products to Shopify."""
        try:
            print(f"📁 Processing CSV file: {csv_path}")
            self.logger.info(f"Processing CSV file: {csv_path}")
            
            # Read and parse CSV
            products_data = self._read_csv_file(csv_path, limit, start_from)
            
            if not products_data:
                raise ValueError("No valid product data found in CSV file")
            
            print(f"📊 Found {len(products_data)} product(s) to process")
            if start_from:
                print(f"📍 Starting from record {start_from}")
            
            # Process each product
            total_products = len(products_data)
            for i, (handle, product_rows) in enumerate(products_data.items(), 1):
                actual_record_num = (start_from or 1) + i - 1
                if not self.silent:
                    print(f"\n[{actual_record_num}] Processing: {handle}")
                elif i % 100 == 0:  # Progress update every 100 products in silent mode
                    print(f"Progress: {i}/{total_products} ({i/total_products*100:.1f}%) - ✅ {self.upload_metrics['successful_uploads']} | ❌ {self.upload_metrics['failed_uploads']}")
                self.logger.info(f"Processing product {actual_record_num}: {handle}")
                
                try:
                    self._process_single_product(handle, product_rows)
                except Exception as e:
                    if not self.silent:
                        print(f"    ❌ Failed to process product '{handle}': {str(e)}")
                    self.logger.error(f"Failed to process product {handle}: {str(e)}")
                    self.upload_metrics['failed_uploads'] += 1
                    continue
            
            # Print final summary
            self._print_summary()
            
        except Exception as e:
            self.logger.error(f"Fatal error processing CSV: {str(e)}")
            raise
    
    def _read_csv_file(self, csv_path: str, limit: Optional[int] = None, start_from: Optional[int] = None) -> Dict[str, List[Dict]]:
        """Read and parse CSV file, grouping rows by product handle."""
        products_data = defaultdict(list)
        seen_handles = set()
        product_count = 0
        
        with open(csv_path, 'r', encoding='utf-8-sig') as file:
            # Use comma as delimiter and handle quoted fields properly
            reader = csv.DictReader(file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            
            # Debug: print column names from first row
            if self.debug:
                print(f"CSV columns found: {list(reader.fieldnames)}")
            
            for idx, row in enumerate(reader, 1):
                # Clean up row data
                cleaned_row = {}
                for i, (k, v) in enumerate(row.items()):
                    # Clean up column names
                    if k is None:
                        key = f'col_{i}'
                    elif isinstance(k, str):
                        key = k.strip()
                    else:
                        key = str(k).strip()
                    
                    # Clean up values
                    if v is None:
                        value = ''
                    elif isinstance(v, str):
                        value = v.strip()
                    else:
                        value = str(v).strip()
                    
                    cleaned_row[key] = value
                row = cleaned_row
                
                # Skip empty rows
                if not any(v for v in row.values()):
                    continue
                
                title = row.get('Title', row.get('title', '')).strip()
                handle = row.get('URL handle', row.get('url handle', '')).strip()
                
                # Debug first few rows
                if self.debug and idx <= 3:
                    print(f"Row {idx} debug:")
                    print(f"  Available keys: {list(row.keys())}")
                    print(f"  Title value: '{title}'")
                    print(f"  Handle value: '{handle}'")
                
                if not title and not handle:
                    if idx <= 5:  # Only log first 5 rows for debugging
                        self.logger.warning(f"Skipping row {idx}: Missing both title and handle")
                    continue
                elif not title and handle:
                    # This is likely an additional image for an existing product
                    self.logger.debug(f"Row {idx}: Additional image for product handle '{handle}'")
                
                # Count unique products for start_from logic
                if handle not in seen_handles:
                    product_count += 1
                    seen_handles.add(handle)
                    
                    # Apply start_from filter - skip products before start_from
                    if start_from and product_count < start_from:
                        continue
                
                # If we already processed this handle and it was skipped due to start_from, continue skipping
                if start_from and handle not in products_data and product_count < start_from:
                    continue
                
                products_data[handle].append(row)
        
        # Apply limit if specified (after start_from)
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
        # Ultra-fast mode: only update published status and inventory policy
        if self.ultra_fast:
            self._process_ultra_fast_update(handle, product_rows)
            return
        
        # Check if this is additional images only (no title in any row)
        has_titles = any(row.get('Title', row.get('title', '')).strip() for row in product_rows)
        
        if not has_titles:
            # This is additional images for an existing product
            self._process_additional_images(handle, product_rows)
        else:
            # This is a full product (create or update)
            self._process_full_product(handle, product_rows)
    
    def _process_ultra_fast_update(self, handle: str, product_rows: List[Dict]) -> None:
        """Ultra-fast update: only update published status and inventory policy."""
        # Get the first row for data
        row = product_rows[0]
        
        # Get published status
        published_str = row.get('published', 'False').strip()
        published = published_str.lower() in ['true', 'yes', '1']
        
        # Get inventory policy
        continue_selling = row.get('continue selling when out of stock', 'deny').strip().lower()
        inventory_policy = 'CONTINUE' if continue_selling in ['continue', 'true', 'yes', '1'] else 'DENY'
        
        if not self.silent:
            print(f"    ⚡ Ultra-fast update: published={published}, inventory_policy={inventory_policy}")
        
        # Perform ultra-fast update
        success = self.product_manager.ultra_fast_update(handle, published, inventory_policy)
        
        if success:
            if not self.silent:
                print(f"    ✅ Ultra-fast update successful!")
            self.upload_metrics['successful_uploads'] += 1
        else:
            if not self.silent:
                print(f"    ❌ Ultra-fast update failed (product may not exist)")
            self.upload_metrics['failed_uploads'] += 1
    
    def _process_additional_images(self, handle: str, product_rows: List[Dict]) -> None:
        """Process additional images for an existing product."""
        if self.skip_images:
            print(f"    🚫 Skipping image processing (--skip-images flag set)")
            self.upload_metrics['skipped_uploads'] += 1
            return
            
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
            mapped_data = self.product_manager.map_row_to_product(main_row)
            product_data = {'input': mapped_data['input']}
            variant_data = mapped_data.get('variant_data')
            
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
                    product_id = self.product_manager.upload_product(product_data, existing_product_id, variant_data)
                    self.upload_metrics['successful_uploads'] += 1
                    print(f"    ✅ Successfully updated product!")
                    self.logger.debug(f"Successfully updated product with ID: {product_id}")
                    
                    # Manage images for updated product
                    if not self.skip_images:
                        image_urls = self.product_manager.extract_images_from_rows(product_rows)
                        if image_urls:
                            self.image_manager.manage_product_images(product_id, image_urls, handle, force_update=True)
                    else:
                        print(f"    🚫 Skipping image processing (--skip-images flag set)")
                else:
                    print(f"    ⏭️  No changes detected, skipping update")
                    self.logger.debug(f"Product {handle} unchanged, skipping")
                    self.upload_metrics['skipped_uploads'] += 1
                    
                    # Run duplicate cleanup for unchanged products if requested
                    if self.cleanup_duplicates and not self.skip_images:
                        print(f"    🧹 Running duplicate cleanup for unchanged product...")
                        image_urls = self.product_manager.extract_images_from_rows(product_rows)
                        self.image_manager.manage_product_images(existing_product_id, image_urls, 
                                                               handle, force_update=False, cleanup_only=True)
                    else:
                        reason = "skip-images flag set" if self.skip_images else "product unchanged"
                        print(f"    🖼️  Skipping image processing ({reason})")
            else:
                # Create new product
                print(f"    ➕ Creating new product...")
                product_id = self.product_manager.upload_product(product_data, None, variant_data)
                self.upload_metrics['successful_uploads'] += 1
                print(f"    ✅ Successfully created product!")
                self.logger.debug(f"Successfully created product with ID: {product_id}")
                
                # Manage images for new product
                if product_id and not self.skip_images:
                    image_urls = self.product_manager.extract_images_from_rows(product_rows)
                    if image_urls:
                        self.image_manager.manage_product_images(product_id, image_urls, handle, force_update=True)
                elif self.skip_images:
                    print(f"    🚫 Skipping image processing (--skip-images flag set)")
                        
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
        
        if self.skip_images:
            print(f"    🚫 Images skipped: All (--skip-images flag enabled)")
        
        self.logger.info(
            f"Upload completed - "
            f"Successful: {self.upload_metrics['successful_uploads']}, "
            f"Skipped: {self.upload_metrics['skipped_uploads']}, "
            f"Failed: {self.upload_metrics['failed_uploads']}, "
            f"Duplicates cleaned: {self.upload_metrics['duplicates_cleaned']}, "
            f"Retries: {self.upload_metrics['retry_count']}, "
            f"Images skipped: {self.skip_images}"
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
    parser.add_argument('--start-from', type=int, help='Start processing from a specific product number (for resuming interrupted uploads)')
    parser.add_argument('--validate-token', action='store_true', help='Validate Shopify access token')
    parser.add_argument('--cleanup-duplicates', action='store_true', 
                      help='Force cleanup of duplicate images even for unchanged products')
    parser.add_argument('--skip-images', action='store_true',
                      help='Skip all image processing to speed up uploads (products only)')
    parser.add_argument('--ultra-fast', action='store_true',
                      help='Ultra-fast mode: Only update published status and inventory policy for existing products')
    parser.add_argument('--silent', action='store_true',
                      help='Silent mode: Minimal output, only show summary')
    parser.add_argument('--turbo', action='store_true',
                      help='Turbo mode: Reduce API delays (use with caution)')
    parser.add_argument('--hyper', action='store_true',
                      help='Hyper mode: Minimum delays, maximum risk of rate limits')
    
    if len(sys.argv) == 1 or '--help' in sys.argv or '-h' in sys.argv:
        print("\nExample usage:")
        print("python shopify_uploader_new.py data/products.csv --shop-url store.myshopify.com --access-token TOKEN")
        print("python shopify_uploader_new.py data/products.csv --shop-url store.myshopify.com --access-token TOKEN --data-source etilize")
        print("python shopify_uploader_new.py data/products.csv --shop-url store.myshopify.com --access-token TOKEN --limit 10 --debug")
        print("python shopify_uploader_new.py data/products.csv --shop-url store.myshopify.com --access-token TOKEN --start-from 50")
        print("python shopify_uploader_new.py data/products.csv --shop-url store.myshopify.com --access-token TOKEN --start-from 100 --limit 50")
        print("python shopify_uploader_new.py data/products.csv --shop-url store.myshopify.com --access-token TOKEN --skip-images")
        print("python shopify_uploader_new.py data/products.csv --shop-url store.myshopify.com --access-token TOKEN --ultra-fast")
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
            cleanup_duplicates=args.cleanup_duplicates,
            skip_images=args.skip_images,
            ultra_fast=args.ultra_fast,
            silent=args.silent,
            turbo=args.turbo,
            hyper=args.hyper
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
        uploader.process_csv(args.csv_file, args.limit, args.start_from)
        
        print(f"\n🎉 Upload process completed successfully!")
        
    except KeyboardInterrupt:
        print(f"\n⚠️  Upload interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()