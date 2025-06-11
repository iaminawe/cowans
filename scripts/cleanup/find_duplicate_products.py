#!/usr/bin/env python3
"""
Script to find duplicate products in Shopify store.
Identifies products that are duplicates based on title, SKU, or handle.
"""

import os
import sys
import argparse
import logging
from typing import Dict, List, Set, Tuple
from collections import defaultdict
from datetime import datetime

# Add the parent directory to the path so we can import from scripts
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.shopify.shopify_uploader import ShopifyUploader

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class DuplicateProductFinder:
    def __init__(self, shop_url: str, access_token: str, debug: bool = False):
        """Initialize the duplicate product finder."""
        self.uploader = ShopifyUploader(
            shop_url=shop_url,
            access_token=access_token,
            debug=debug
        )
        self.logger = logging.getLogger(__name__)
        if debug:
            self.logger.setLevel(logging.DEBUG)
    
    def get_all_products(self, limit: int = None) -> List[Dict]:
        """Get all products from Shopify with detailed information."""
        query = """
        query getProducts($first: Int, $after: String) {
          products(first: $first, after: $after) {
            edges {
              node {
                id
                handle
                title
                createdAt
                updatedAt
                variants(first: 1) {
                  edges {
                    node {
                      sku
                    }
                  }
                }
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
                node = edge['node']
                
                # Extract SKU from first variant
                sku = ''
                variants = node.get('variants', {}).get('edges', [])
                if variants:
                    sku = variants[0]['node'].get('sku', '')
                
                product = {
                    'id': node['id'],
                    'handle': node['handle'],
                    'title': node['title'],
                    'sku': sku,
                    'createdAt': node['createdAt'],
                    'updatedAt': node['updatedAt']
                }
                
                products.append(product)
                if limit and len(products) >= limit:
                    return products[:limit]
            
            page_info = data.get('pageInfo', {})
            if not page_info.get('hasNextPage'):
                break
            
            cursor = page_info.get('endCursor')
        
        return products
    
    def find_duplicates(self, products: List[Dict]) -> Dict[str, List[Dict]]:
        """Find duplicate products based on various criteria."""
        duplicates = {}
        
        # Group by title (normalized)
        title_groups = defaultdict(list)
        for product in products:
            normalized_title = product['title'].lower().strip()
            title_groups[normalized_title].append(product)
        
        # Find title duplicates
        for title, prods in title_groups.items():
            if len(prods) > 1:
                duplicates[f"title_duplicates: {title[:50]}..."] = prods
        
        # Group by SKU (if present)
        sku_groups = defaultdict(list)
        for product in products:
            sku = product['sku'].strip()
            if sku:  # Only group products that have SKUs
                sku_groups[sku].append(product)
        
        # Find SKU duplicates
        for sku, prods in sku_groups.items():
            if len(prods) > 1:
                duplicates[f"sku_duplicates: {sku}"] = prods
        
        # Group by handle
        handle_groups = defaultdict(list)
        for product in products:
            handle = product['handle'].strip()
            handle_groups[handle].append(product)
        
        # Find handle duplicates
        for handle, prods in handle_groups.items():
            if len(prods) > 1:
                duplicates[f"handle_duplicates: {handle}"] = prods
        
        return duplicates
    
    def analyze_duplicates(self, limit: int = None) -> None:
        """Analyze and report duplicate products."""
        start_time = datetime.now()
        print("🔍 Finding duplicate products...")
        self.logger.info("=== STARTING DUPLICATE PRODUCT ANALYSIS ===")
        self.logger.info(f"Start time: {start_time}")
        self.logger.info(f"Product limit: {limit if limit else 'All products'}")
        
        # Get all products
        self.logger.info("Fetching products from Shopify...")
        products = self.get_all_products(limit)
        print(f"📊 Found {len(products)} products to analyze")
        self.logger.info(f"Found {len(products)} products to analyze")
        
        # Find duplicates
        duplicates = self.find_duplicates(products)
        
        if not duplicates:
            print("✅ No duplicate products found!")
            self.logger.info("No duplicate products found")
            return
        
        print(f"\n🚨 Found {len(duplicates)} sets of duplicate products:")
        self.logger.info(f"Found {len(duplicates)} sets of duplicate products")
        
        total_duplicate_products = 0
        
        for dup_type, prods in duplicates.items():
            print(f"\n📋 {dup_type}")
            print(f"   Found {len(prods)} products:")
            self.logger.info(f"{dup_type}: {len(prods)} products")
            
            # Sort by creation date (oldest first)
            sorted_prods = sorted(prods, key=lambda x: x['createdAt'])
            
            for i, prod in enumerate(sorted_prods):
                status = "ORIGINAL" if i == 0 else "DUPLICATE"
                product_id = prod['id'].split('/')[-1]  # Extract numeric ID
                
                print(f"   {i+1}. [{status}] {prod['title'][:60]}...")
                print(f"      ID: {product_id} | Handle: {prod['handle']}")
                print(f"      SKU: {prod['sku']} | Created: {prod['createdAt'][:10]}")
                print(f"      URL: https://admin.shopify.com/store/e19833-4/products/{product_id}")
                
                self.logger.info(f"  {status}: {prod['title']} (ID: {product_id}, Handle: {prod['handle']}, SKU: {prod['sku']})")
                
                if i > 0:  # Count duplicates (not originals)
                    total_duplicate_products += 1
        
        # Calculate timing
        end_time = datetime.now()
        duration = end_time - start_time
        
        # Summary
        print(f"\n📊 Summary:")
        print(f"   Total products analyzed: {len(products)}")
        print(f"   Duplicate sets found: {len(duplicates)}")
        print(f"   Total duplicate products: {total_duplicate_products}")
        print(f"   Analysis duration: {duration}")
        
        print(f"\n💡 Next steps:")
        print(f"   1. Review the duplicate products above")
        print(f"   2. Manually delete duplicates from Shopify admin, keeping the ORIGINAL")
        print(f"   3. Or use a bulk delete script (to be created)")
        
        # Log final summary
        self.logger.info("=== ANALYSIS COMPLETE ===")
        self.logger.info(f"End time: {end_time}")
        self.logger.info(f"Duration: {duration}")
        self.logger.info(f"Total products analyzed: {len(products)}")
        self.logger.info(f"Duplicate sets found: {len(duplicates)}")
        self.logger.info(f"Total duplicate products: {total_duplicate_products}")

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Find duplicate products in Shopify store')
    parser.add_argument('--shop-url', required=True, help='Shopify shop URL (*.myshopify.com)')
    parser.add_argument('--access-token', required=True, help='Shopify Admin API access token')
    parser.add_argument('--limit', type=int, help='Limit number of products to analyze (for testing)')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    if len(sys.argv) == 1:
        print("Usage:")
        print("python find_duplicate_products.py --shop-url e19833-4.myshopify.com --access-token TOKEN")
        print("python find_duplicate_products.py --shop-url e19833-4.myshopify.com --access-token TOKEN --limit 100")
        sys.exit(1)
    
    args = parser.parse_args()
    
    try:
        finder = DuplicateProductFinder(
            shop_url=args.shop_url,
            access_token=args.access_token,
            debug=args.debug
        )
        
        finder.analyze_duplicates(limit=args.limit)
        
    except Exception as e:
        print(f"Error: {str(e)}")
        logger = logging.getLogger('find_duplicate_products')
        logger.error(f"Fatal error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()