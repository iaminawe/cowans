#!/usr/bin/env python3
"""
Script to cleanup duplicate images from Shopify products.
This script will identify and remove duplicate images based on filename similarity.
"""

import os
import sys
import argparse
import logging
from typing import Dict, List, Set
from collections import defaultdict
from datetime import datetime

# Add the parent directory to the path so we can import from scripts
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.shopify.shopify_uploader import ShopifyUploader

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class DuplicateImageCleaner:
    def __init__(self, shop_url: str, access_token: str, debug: bool = False, log_file: str = None):
        """Initialize the duplicate image cleaner."""
        self.uploader = ShopifyUploader(
            shop_url=shop_url,
            access_token=access_token,
            debug=debug,
            cleanup_duplicates=True
        )
        self.logger = logging.getLogger(__name__)
        if debug:
            self.logger.setLevel(logging.DEBUG)
        
        # Setup file logging
        self.log_file = log_file
        if self.log_file:
            # Create file handler
            file_handler = logging.FileHandler(self.log_file, mode='w')
            file_handler.setLevel(logging.INFO)
            file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(file_formatter)
            
            # Add handler to logger
            self.logger.addHandler(file_handler)
            
            # Also log to the main script logger
            main_logger = logging.getLogger('cleanup_duplicate_images')
            main_logger.addHandler(file_handler)
            main_logger.setLevel(logging.INFO)
    
    def get_all_products(self, limit: int = None) -> List[Dict]:
        """Get all products from Shopify."""
        query = """
        query getProducts($first: Int, $after: String) {
          products(first: $first, after: $after) {
            edges {
              node {
                id
                handle
                title
              }
            }
            pageInfo {
              hasNextPage
              endCursor
            }
          }
        }
        """
        
        products = []
        cursor = None
        batch_size = min(50, limit) if limit else 50
        
        while True:
            variables = {'first': batch_size}
            if cursor:
                variables['after'] = cursor
            
            result = self.uploader.execute_graphql(query, variables)
            
            if 'errors' in result:
                self.logger.error(f"GraphQL errors: {result['errors']}")
                break
            
            data = result.get('data', {}).get('products', {})
            edges = data.get('edges', [])
            
            for edge in edges:
                products.append(edge['node'])
                if limit and len(products) >= limit:
                    return products[:limit]
            
            page_info = data.get('pageInfo', {})
            if not page_info.get('hasNextPage'):
                break
            
            cursor = page_info.get('endCursor')
        
        return products
    
    def find_duplicates_in_product(self, product_id: str) -> Dict[str, List]:
        """Find duplicate images in a specific product with improved logic to avoid removing legitimate additional images."""
        images = self.uploader.get_product_images(product_id)
        
        if len(images) <= 1:
            return {}
        
        # Group images by exact URL (these are true duplicates)
        exact_url_groups = defaultdict(list)
        
        for img in images:
            normalized_url = img['originalSrc'].split('?')[0]  # Remove query params
            exact_url_groups[normalized_url].append(img)
        
        duplicates = {}
        
        # Find exact URL duplicates (same exact URL uploaded multiple times)
        for url, imgs in exact_url_groups.items():
            if len(imgs) > 1:
                filename = url.split('/')[-1]
                duplicates[f"exact_url_{filename}"] = imgs
                self.logger.info(f"Found exact URL duplicates: {len(imgs)} copies of {filename}")
        
        # More conservative approach for UUID detection
        # Only remove if we can definitively identify these as Shopify-generated duplicates
        # Look for patterns that indicate the same image was uploaded multiple times in quick succession
        
        potential_uuid_groups = defaultdict(list)
        
        for img in images:
            full_url = img['originalSrc']
            filename = full_url.split('/')[-1].split('?')[0]
            
            # Only consider UUID duplicates for Shopify CDN URLs (not Etilize URLs)
            if 'cdn.shopify.com' in full_url and '_' in filename:
                parts = filename.split('_')
                if len(parts) >= 2:
                    # Check if last part before extension looks like a UUID (36 chars, 4 dashes)
                    last_part = parts[-1].split('.')[0]
                    if len(last_part) == 36 and last_part.count('-') == 4:  # UUID format
                        base_name = '_'.join(parts[:-1]) + '.' + filename.split('.')[-1]
                        potential_uuid_groups[base_name].append(img)
        
        # For UUID groups, be very conservative - only remove if we're confident they're duplicates
        for base_name, imgs in potential_uuid_groups.items():
            if len(imgs) > 1:
                # Sort by timestamp to identify upload order
                sorted_imgs = sorted(imgs, key=lambda x: x['originalSrc'].split('?v=')[-1] if '?v=' in x['originalSrc'] else '0')
                
                # Get timestamps for all images
                timestamps = [int(img['originalSrc'].split('?v=')[-1]) if '?v=' in img['originalSrc'] else 0 for img in sorted_imgs]
                
                # Group images by upload batches (images uploaded within 2 minutes of each other)
                batch_groups = []
                current_batch = [sorted_imgs[0]]
                current_batch_timestamps = [timestamps[0]]
                
                for i in range(1, len(sorted_imgs)):
                    time_diff = timestamps[i] - timestamps[i-1]
                    
                    # If this image was uploaded within 2 minutes of the previous one, add to current batch
                    if time_diff <= 120:  # 2 minutes
                        current_batch.append(sorted_imgs[i])
                        current_batch_timestamps.append(timestamps[i])
                    else:
                        # Start a new batch if this image was uploaded much later
                        if len(current_batch) > 1:
                            batch_groups.append(current_batch)
                        current_batch = [sorted_imgs[i]]
                        current_batch_timestamps = [timestamps[i]]
                
                # Add the final batch if it has multiple images
                if len(current_batch) > 1:
                    batch_groups.append(current_batch)
                
                # Process all batches together - keep only the very first image, remove all others
                if batch_groups:
                    # Collect all duplicate images from all batches (excluding the very first one)
                    all_duplicates = []
                    first_image_kept = False
                    
                    for batch_idx, batch in enumerate(batch_groups):
                        if len(batch) > 1:
                            if not first_image_kept:
                                # Keep the first image of the first batch, mark all others as duplicates
                                all_duplicates.extend(batch[1:])  # Skip first image
                                first_image_kept = True
                                self.logger.info(f"Keeping original image from batch 1: {batch[0]['originalSrc'].split('/')[-1].split('?')[0]}")
                            else:
                                # For subsequent batches, mark ALL images as duplicates
                                all_duplicates.extend(batch)
                            
                            self.logger.info(f"Found time-based UUID duplicates batch {batch_idx + 1}: {len(batch)} copies of {base_name}")
                    
                    if all_duplicates:
                        duplicates[f"uuid_duplicates_{base_name}"] = all_duplicates
                        self.logger.info(f"Total UUID duplicates to remove for {base_name}: {len(all_duplicates)} images")
                        total_batches_found = len(batch_groups)
                    else:
                        total_batches_found = 0
                else:
                    total_batches_found = 0
                
                if total_batches_found == 0:
                    self.logger.info(f"Skipping potential UUID group {base_name}: all images appear to be legitimate (no tight upload clusters found)")
        
        return duplicates
    
    def cleanup_product_duplicates(self, product_id: str, handle: str, dry_run: bool = True, show_all_images: bool = False) -> int:
        """Clean up duplicate images for a specific product."""
        self.logger.info(f"Processing product: {handle} (ID: {product_id})")
        
        # Get all images first
        all_images = self.uploader.get_product_images(product_id)
        self.logger.info(f"Found {len(all_images)} total images for product {handle}")
        
        if show_all_images and all_images:
            print(f"  📸 All images for this product ({len(all_images)} total):")
            for i, img in enumerate(all_images, 1):
                filename = img['originalSrc'].split('/')[-1].split('?')[0]
                print(f"    {i}. {filename}")
                self.logger.info(f"Image {i}: {filename} - {img['originalSrc']}")
                if self.logger.level <= logging.DEBUG:
                    print(f"       URL: {img['originalSrc']}")
        
        duplicates = self.find_duplicates_in_product(product_id)
        
        if not duplicates:
            self.logger.info(f"No duplicates found for product {handle}")
            return 0
        
        total_removed = 0
        print(f"  🔍 Found {len(duplicates)} sets of duplicate images:")
        self.logger.info(f"Found {len(duplicates)} sets of duplicate images for product {handle}")
        
        for dup_key, imgs in duplicates.items():
            print(f"    📸 {dup_key}: {len(imgs)} copies")
            self.logger.info(f"Duplicate set '{dup_key}': {len(imgs)} images")
            
            # Log all images in this duplicate set
            for i, img in enumerate(imgs):
                filename = img['originalSrc'].split('/')[-1].split('?')[0]
                self.logger.info(f"  - Image {i+1}: {filename} (ID: {img['id']})")
            
            if dry_run:
                if dup_key.startswith('uuid_duplicates_'):
                    print(f"      [DRY RUN] Would remove {len(imgs) - 1} UUID duplicate images")
                    self.logger.info(f"[DRY RUN] Would remove {len(imgs) - 1} UUID duplicate images from {dup_key}")
                    total_removed += len(imgs) - 1
                elif dup_key.startswith('exact_url_'):
                    print(f"      [DRY RUN] Would remove {len(imgs) - 1} exact URL duplicates")
                    self.logger.info(f"[DRY RUN] Would remove {len(imgs) - 1} exact URL duplicates from {dup_key}")
                    total_removed += len(imgs) - 1
                elif dup_key.startswith('exact_'):
                    print(f"      [DRY RUN] Would remove {len(imgs) - 1} exact duplicates")
                    self.logger.info(f"[DRY RUN] Would remove {len(imgs) - 1} exact duplicates from {dup_key}")
                    total_removed += len(imgs) - 1
                else:
                    print(f"      [DRY RUN] Similar images detected - manual review recommended")
                    self.logger.info(f"[DRY RUN] Similar images detected in {dup_key} - manual review recommended")
            else:
                if dup_key.startswith('uuid_duplicates_') or dup_key.startswith('exact_url_') or dup_key.startswith('exact_'):
                    # Keep the first image (usually the original), remove the rest
                    to_remove = [img['id'] for img in imgs[1:]]
                    kept_image = imgs[0]
                    
                    self.logger.info(f"Keeping original image: {kept_image['originalSrc'].split('/')[-1].split('?')[0]} (ID: {kept_image['id']})")
                    
                    if to_remove:
                        print(f"      🗑️  Removing {len(to_remove)} duplicate images...")
                        self.logger.info(f"Attempting to remove {len(to_remove)} duplicate images...")
                        
                        # Log each image being removed
                        for img_id in to_remove:
                            img_to_remove = next(img for img in imgs if img['id'] == img_id)
                            filename = img_to_remove['originalSrc'].split('/')[-1].split('?')[0]
                            self.logger.info(f"Removing duplicate: {filename} (ID: {img_id})")
                        
                        success = self.uploader.delete_product_media(product_id, to_remove)
                        if success:
                            print(f"      ✅ Removed {len(to_remove)} duplicates")
                            self.logger.info(f"Successfully removed {len(to_remove)} duplicate images from {dup_key}")
                            total_removed += len(to_remove)
                        else:
                            print(f"      ❌ Failed to remove duplicates")
                            self.logger.error(f"Failed to remove {len(to_remove)} duplicate images from {dup_key}")
                else:
                    # Other types - be more cautious  
                    print(f"      ⚠️  Detected {len(imgs)} similar images - manual review recommended")
                    self.logger.warning(f"Detected {len(imgs)} similar images in {dup_key} - manual review recommended")
        
        self.logger.info(f"Completed processing product {handle}. Removed {total_removed} duplicate images.")
        return total_removed
    
    def cleanup_all_products(self, limit: int = None, dry_run: bool = True) -> None:
        """Clean up duplicate images across all products."""
        start_time = datetime.now()
        print("🧹 Starting duplicate image cleanup...")
        self.logger.info("=== STARTING DUPLICATE IMAGE CLEANUP ===")
        self.logger.info(f"Start time: {start_time}")
        self.logger.info(f"Mode: {'DRY RUN' if dry_run else 'EXECUTE'}")
        self.logger.info(f"Product limit: {limit if limit else 'All products'}")
        
        if dry_run:
            print("📝 DRY RUN MODE: No changes will be made")
        
        # Get all products
        self.logger.info("Fetching products from Shopify...")
        products = self.get_all_products(limit)
        print(f"📊 Found {len(products)} products to check")
        self.logger.info(f"Found {len(products)} products to process")
        
        total_products_with_duplicates = 0
        total_duplicates_removed = 0
        failed_products = []
        
        for i, product in enumerate(products, 1):
            product_id = product['id']
            handle = product['handle']
            title = product['title']
            
            print(f"\n[{i}/{len(products)}] Checking '{title[:50]}...' ({handle})")
            self.logger.info(f"=== PROCESSING PRODUCT {i}/{len(products)} ===")
            self.logger.info(f"Product: {title}")
            self.logger.info(f"Handle: {handle}")
            self.logger.info(f"Product ID: {product_id}")
            
            try:
                duplicates_removed = self.cleanup_product_duplicates(product_id, handle, dry_run, show_all_images=True)
                
                if duplicates_removed > 0:
                    total_products_with_duplicates += 1
                    total_duplicates_removed += duplicates_removed
                    print(f"  📊 Removed {duplicates_removed} duplicate images")
                    self.logger.info(f"SUCCESS: Removed {duplicates_removed} duplicate images from {handle}")
                else:
                    print(f"  ✅ No duplicates found")
                    self.logger.info(f"No duplicates found for {handle}")
            
            except Exception as e:
                print(f"  ❌ Error processing product: {str(e)}")
                self.logger.error(f"Failed to process product {handle}: {str(e)}")
                failed_products.append({'handle': handle, 'title': title, 'error': str(e)})
        
        # Calculate timing
        end_time = datetime.now()
        duration = end_time - start_time
        
        # Summary
        print(f"\n🎉 Cleanup Complete!")
        print(f"📊 Summary:")
        print(f"   Products checked: {len(products)}")
        print(f"   Products with duplicates: {total_products_with_duplicates}")
        print(f"   Total duplicates {'would be ' if dry_run else ''}removed: {total_duplicates_removed}")
        print(f"   Failed products: {len(failed_products)}")
        print(f"   Duration: {duration}")
        
        # Log final summary
        self.logger.info("=== CLEANUP COMPLETE ===")
        self.logger.info(f"End time: {end_time}")
        self.logger.info(f"Duration: {duration}")
        self.logger.info(f"Products checked: {len(products)}")
        self.logger.info(f"Products with duplicates: {total_products_with_duplicates}")
        self.logger.info(f"Total duplicates {'would be ' if dry_run else ''}removed: {total_duplicates_removed}")
        self.logger.info(f"Failed products: {len(failed_products)}")
        
        if failed_products:
            self.logger.error("=== FAILED PRODUCTS ===")
            for failed in failed_products:
                self.logger.error(f"Failed: {failed['handle']} - {failed['error']}")
        
        if dry_run and total_duplicates_removed > 0:
            print(f"\n💡 To actually remove duplicates, run with --execute flag")
            self.logger.info("This was a dry run. Use --execute flag to actually remove duplicates.")
        
        self.logger.info("=== LOG COMPLETE ===")
        
        if self.log_file:
            print(f"\n📝 Detailed log saved to: {self.log_file}")

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Cleanup duplicate images from Shopify products')
    parser.add_argument('--shop-url', required=True, help='Shopify shop URL (*.myshopify.com)')
    parser.add_argument('--access-token', required=True, help='Shopify Admin API access token')
    parser.add_argument('--limit', type=int, help='Limit number of products to check (for testing)')
    parser.add_argument('--execute', action='store_true', help='Actually remove duplicates (default is dry run)')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--log-file', help='Path to log file (default: data/cleanup_duplicates_TIMESTAMP.log)')
    
    if len(sys.argv) == 1:
        print("Usage:")
        print("python cleanup_duplicate_images.py --shop-url e19833-4.myshopify.com --access-token TOKEN")
        print("python cleanup_duplicate_images.py --shop-url e19833-4.myshopify.com --access-token TOKEN --execute")
        print("python cleanup_duplicate_images.py --shop-url e19833-4.myshopify.com --access-token TOKEN --log-file my_cleanup.log")
        sys.exit(1)
    
    args = parser.parse_args()
    
    # Generate default log file name if not provided
    log_file = args.log_file
    if not log_file:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        mode = "execute" if args.execute else "dryrun"
        log_file = f"data/cleanup_duplicates_{mode}_{timestamp}.log"
        
        # Ensure data directory exists
        os.makedirs("data", exist_ok=True)
    
    try:
        cleaner = DuplicateImageCleaner(
            shop_url=args.shop_url,
            access_token=args.access_token,
            debug=args.debug,
            log_file=log_file
        )
        
        print(f"📝 Logging to: {log_file}")
        
        cleaner.cleanup_all_products(
            limit=args.limit,
            dry_run=not args.execute
        )
        
    except Exception as e:
        print(f"Error: {str(e)}")
        # Log the error too if we have a logger set up
        logger = logging.getLogger('cleanup_duplicate_images')
        logger.error(f"Fatal error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()