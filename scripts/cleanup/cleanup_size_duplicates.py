#!/usr/bin/env python3
"""
Script to cleanup duplicate images based on file size across all products.
"""

import os
import sys
import argparse
import logging
from datetime import datetime

# Add the parent directory to the path so we can import from scripts
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.shopify.shopify_uploader import ShopifyUploader

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class SizeDuplicateCleaner:
    def __init__(self, shop_url: str, access_token: str, debug: bool = False):
        """Initialize the size-based duplicate cleaner."""
        self.uploader = ShopifyUploader(
            shop_url=shop_url,
            access_token=access_token,
            debug=debug
        )
        self.logger = logging.getLogger(__name__)
        if debug:
            self.logger.setLevel(logging.DEBUG)
    
    def get_all_products(self, limit: int = None) -> list:
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
    
    def cleanup_product_size_duplicates(self, product_id: str, handle: str, title: str, dry_run: bool = True) -> int:
        """Clean up size-based duplicate images for a specific product."""
        print(f"Processing: {title[:60]}...")
        self.logger.info(f"Processing product: {handle} (ID: {product_id})")
        
        # Get existing images
        existing_images = self.uploader.get_product_images(product_id)
        if len(existing_images) <= 1:
            print(f"  ✅ Only {len(existing_images)} image(s), no duplicates possible")
            return 0
        
        print(f"  📊 Found {len(existing_images)} images")
        
        # Find size-based duplicates
        duplicate_groups = self.uploader.find_duplicate_images_by_size(existing_images)
        
        if not duplicate_groups:
            print(f"  ✅ No size-based duplicates found")
            return 0
        
        total_removed = 0
        print(f"  🚨 Found {len(duplicate_groups)} duplicate group(s):")
        
        for group_idx, duplicate_group in enumerate(duplicate_groups, 1):
            file_size = None
            if duplicate_group:
                file_size = self.uploader.get_image_file_size(duplicate_group[0]['originalSrc'])
            
            print(f"    Group {group_idx}: {len(duplicate_group)} images with size {file_size} bytes ({file_size/1024:.2f} KB)" if file_size else f"    Group {group_idx}: {len(duplicate_group)} images")
            
            # Show all images in group
            for i, img in enumerate(duplicate_group):
                filename = img['originalSrc'].split('/')[-1].split('?')[0]
                status = "KEEP" if i == 0 else "REMOVE"
                print(f"      {status}: {filename}")
                self.logger.info(f"  {status}: {filename} (ID: {img['id']})")
            
            if dry_run:
                print(f"      [DRY RUN] Would remove {len(duplicate_group) - 1} duplicate(s)")
                total_removed += len(duplicate_group) - 1
            else:
                # Remove duplicates (keep first, remove rest)
                duplicates_to_remove = [img['id'] for img in duplicate_group[1:]]
                
                if duplicates_to_remove:
                    print(f"      🗑️  Removing {len(duplicates_to_remove)} duplicate(s)...")
                    success = self.uploader.delete_product_media(product_id, duplicates_to_remove)
                    if success:
                        print(f"      ✅ Successfully removed {len(duplicates_to_remove)} duplicate(s)")
                        self.logger.info(f"Successfully removed {len(duplicates_to_remove)} size-based duplicates")
                        total_removed += len(duplicates_to_remove)
                    else:
                        print(f"      ❌ Failed to remove duplicates")
                        self.logger.error(f"Failed to remove size-based duplicates")
        
        return total_removed
    
    def cleanup_all_products(self, limit: int = None, dry_run: bool = True) -> None:
        """Clean up size-based duplicate images across all products."""
        start_time = datetime.now()
        print("🧹 Starting size-based duplicate cleanup...")
        self.logger.info("=== STARTING SIZE-BASED DUPLICATE CLEANUP ===")
        self.logger.info(f"Start time: {start_time}")
        self.logger.info(f"Mode: {'DRY RUN' if dry_run else 'EXECUTE'}")
        self.logger.info(f"Product limit: {limit if limit else 'All products'}")
        
        if dry_run:
            print("📝 DRY RUN MODE: No changes will be made")
        
        # Get all products
        print("📊 Fetching products from Shopify...")
        products = self.get_all_products(limit)
        print(f"📊 Found {len(products)} products to check")
        
        total_products_with_duplicates = 0
        total_duplicates_removed = 0
        failed_products = []
        
        for i, product in enumerate(products, 1):
            product_id = product['id']
            handle = product['handle']
            title = product['title']
            
            print(f"\n[{i}/{len(products)}] ", end="")
            
            try:
                duplicates_removed = self.cleanup_product_size_duplicates(product_id, handle, title, dry_run)
                
                if duplicates_removed > 0:
                    total_products_with_duplicates += 1
                    total_duplicates_removed += duplicates_removed
            
            except Exception as e:
                print(f"    ❌ Error processing product: {str(e)}")
                self.logger.error(f"Failed to process product {handle}: {str(e)}")
                failed_products.append({'handle': handle, 'title': title, 'error': str(e)})
        
        # Calculate timing
        end_time = datetime.now()
        duration = end_time - start_time
        
        # Summary
        print(f"\n🎉 Cleanup Complete!")
        print(f"📊 Summary:")
        print(f"   Products checked: {len(products)}")
        print(f"   Products with size duplicates: {total_products_with_duplicates}")
        print(f"   Total duplicates {'would be ' if dry_run else ''}removed: {total_duplicates_removed}")
        print(f"   Failed products: {len(failed_products)}")
        print(f"   Duration: {duration}")
        
        # Log final summary
        self.logger.info("=== CLEANUP COMPLETE ===")
        self.logger.info(f"End time: {end_time}")
        self.logger.info(f"Duration: {duration}")
        self.logger.info(f"Products checked: {len(products)}")
        self.logger.info(f"Products with size duplicates: {total_products_with_duplicates}")
        self.logger.info(f"Total duplicates {'would be ' if dry_run else ''}removed: {total_duplicates_removed}")
        self.logger.info(f"Failed products: {len(failed_products)}")
        
        if failed_products:
            self.logger.error("=== FAILED PRODUCTS ===")
            for failed in failed_products:
                self.logger.error(f"Failed: {failed['handle']} - {failed['error']}")
        
        if dry_run and total_duplicates_removed > 0:
            print(f"\n💡 To actually remove duplicates, run with --execute flag")

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Cleanup size-based duplicate images from Shopify products')
    parser.add_argument('--shop-url', required=True, help='Shopify shop URL (*.myshopify.com)')
    parser.add_argument('--access-token', required=True, help='Shopify Admin API access token')
    parser.add_argument('--limit', type=int, help='Limit number of products to check (for testing)')
    parser.add_argument('--execute', action='store_true', help='Actually remove duplicates (default is dry run)')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    if len(sys.argv) == 1:
        print("Usage:")
        print("python cleanup_size_duplicates.py --shop-url e19833-4.myshopify.com --access-token TOKEN")
        print("python cleanup_size_duplicates.py --shop-url e19833-4.myshopify.com --access-token TOKEN --execute")
        print("python cleanup_size_duplicates.py --shop-url e19833-4.myshopify.com --access-token TOKEN --limit 10")
        sys.exit(1)
    
    args = parser.parse_args()
    
    try:
        cleaner = SizeDuplicateCleaner(
            shop_url=args.shop_url,
            access_token=args.access_token,
            debug=args.debug
        )
        
        cleaner.cleanup_all_products(
            limit=args.limit,
            dry_run=not args.execute
        )
        
    except Exception as e:
        print(f"Error: {str(e)}")
        logger = logging.getLogger('cleanup_size_duplicates')
        logger.error(f"Fatal error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()