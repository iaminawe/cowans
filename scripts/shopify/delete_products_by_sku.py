#!/usr/bin/env python3
"""
Delete products from Shopify based on a CSV list of SKUs.
Uses the modular Shopify architecture for better error handling and rate limiting.
"""

import csv
import sys
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import argparse
import os
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

from scripts.shopify.shopify_base import ShopifyAPIBase, RateLimiter
from scripts.shopify.shopify_product_manager import ShopifyProductManager

class ShopifyProductDeleter(ShopifyAPIBase):
    """Handle deletion of products from Shopify by SKU"""
    
    def __init__(self, shop_url: str, access_token: str):
        super().__init__(shop_url, access_token)
        self.product_manager = ShopifyProductManager(shop_url, access_token)
        self.deleted_count = 0
        self.failed_count = 0
        self.not_found_count = 0
    
    def find_product_by_sku(self, sku: str) -> Optional[str]:
        """Find product ID by SKU using GraphQL"""
        query = """
        query findProductBySKU($sku: String!) {
            products(first: 5, query: $sku) {
                edges {
                    node {
                        id
                        title
                        handle
                        variants(first: 10) {
                            edges {
                                node {
                                    id
                                    sku
                                }
                            }
                        }
                    }
                }
            }
        }
        """
        
        variables = {"sku": f"sku:{sku}"}
        
        try:
            result = self.execute_graphql(query, variables)
            
            if result and 'data' in result and 'products' in result['data']:
                products = result['data']['products']['edges']
                
                # Look for exact SKU match
                for product in products:
                    for variant in product['node']['variants']['edges']:
                        if variant['node']['sku'] == sku:
                            return product['node']['id']
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error finding product by SKU {sku}: {str(e)}")
            return None
    
    def delete_product(self, product_id: str, sku: str) -> bool:
        """Delete a product from Shopify"""
        mutation = """
        mutation deleteProduct($id: ID!) {
            productDelete(input: {id: $id}) {
                deletedProductId
                userErrors {
                    field
                    message
                }
            }
        }
        """
        
        variables = {"id": product_id}
        
        try:
            result = self.execute_graphql(mutation, variables)
            
            if result and 'data' in result and 'productDelete' in result['data']:
                delete_result = result['data']['productDelete']
                
                if delete_result.get('userErrors'):
                    errors = delete_result['userErrors']
                    self.logger.error(f"Failed to delete product {sku}: {errors}")
                    return False
                
                if delete_result.get('deletedProductId'):
                    self.logger.info(f"Successfully deleted product {sku}")
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error deleting product {sku}: {str(e)}")
            return False
    
    def delete_products_from_csv(self, csv_file: str, dry_run: bool = False) -> Dict[str, List[str]]:
        """Delete products listed in CSV file"""
        results = {
            'deleted': [],
            'failed': [],
            'not_found': []
        }
        
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            products = list(reader)
        
        total_products = len(products)
        self.logger.info(f"Processing {total_products} products for deletion")
        
        for i, row in enumerate(products, 1):
            sku = row.get('sku', '').strip()
            
            if not sku:
                self.logger.warning(f"Row {i}: Empty SKU, skipping")
                continue
            
            # Progress update
            if i % 10 == 0:
                self.logger.info(f"Progress: {i}/{total_products} products processed")
            
            # Find product
            self.logger.info(f"[{i}/{total_products}] Looking for product with SKU: {sku}")
            product_id = self.find_product_by_sku(sku)
            
            if not product_id:
                self.logger.warning(f"Product not found for SKU: {sku}")
                results['not_found'].append(sku)
                self.not_found_count += 1
                continue
            
            if dry_run:
                self.logger.info(f"DRY RUN: Would delete product {sku} (ID: {product_id})")
                results['deleted'].append(sku)
                self.deleted_count += 1
            else:
                # Delete product
                if self.delete_product(product_id, sku):
                    results['deleted'].append(sku)
                    self.deleted_count += 1
                else:
                    results['failed'].append(sku)
                    self.failed_count += 1
            
            # Rate limiting between deletions
            time.sleep(0.5)
        
        return results
    
    def save_results(self, results: Dict[str, List[str]], output_dir: str):
        """Save deletion results to CSV files"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save successfully deleted products
        if results['deleted']:
            deleted_file = os.path.join(output_dir, f"deleted_products_{timestamp}.csv")
            with open(deleted_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['SKU', 'Status'])
                for sku in results['deleted']:
                    writer.writerow([sku, 'Deleted'])
            self.logger.info(f"Saved deleted products to: {deleted_file}")
        
        # Save failed deletions
        if results['failed']:
            failed_file = os.path.join(output_dir, f"failed_deletions_{timestamp}.csv")
            with open(failed_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['SKU', 'Status'])
                for sku in results['failed']:
                    writer.writerow([sku, 'Failed'])
            self.logger.info(f"Saved failed deletions to: {failed_file}")
        
        # Save not found products
        if results['not_found']:
            not_found_file = os.path.join(output_dir, f"not_found_products_{timestamp}.csv")
            with open(not_found_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['SKU', 'Status'])
                for sku in results['not_found']:
                    writer.writerow([sku, 'Not Found'])
            self.logger.info(f"Saved not found products to: {not_found_file}")

def main():
    parser = argparse.ArgumentParser(description='Delete products from Shopify by SKU')
    parser.add_argument('csv_file', help='CSV file containing SKUs to delete')
    parser.add_argument('--shop-url', help='Shopify shop URL (or set SHOPIFY_SHOP_URL env var)')
    parser.add_argument('--access-token', help='Shopify access token (or set SHOPIFY_ACCESS_TOKEN env var)')
    parser.add_argument('--dry-run', action='store_true', help='Simulate deletion without actually deleting')
    parser.add_argument('--output-dir', default='data', help='Directory to save results (default: data)')
    
    args = parser.parse_args()
    
    # Load environment variables
    load_dotenv()
    
    # Get credentials
    shop_url = args.shop_url or os.getenv('SHOPIFY_SHOP_URL')
    access_token = args.access_token or os.getenv('SHOPIFY_ACCESS_TOKEN')
    
    if not shop_url or not access_token:
        print("Error: Shopify credentials not provided")
        print("Set SHOPIFY_SHOP_URL and SHOPIFY_ACCESS_TOKEN environment variables")
        print("Or provide --shop-url and --access-token arguments")
        sys.exit(1)
    
    # Check if CSV file exists
    if not os.path.exists(args.csv_file):
        print(f"Error: CSV file not found: {args.csv_file}")
        sys.exit(1)
    
    # Create output directory if needed
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Initialize deleter
    deleter = ShopifyProductDeleter(shop_url, access_token)
    
    # Confirm deletion
    if not args.dry_run:
        print(f"\nWARNING: This will DELETE products from your Shopify store!")
        print(f"CSV file: {args.csv_file}")
        confirm = input("Are you sure you want to proceed? Type 'DELETE' to confirm: ")
        if confirm != 'DELETE':
            print("Deletion cancelled.")
            sys.exit(0)
    
    # Delete products
    print(f"\nStarting deletion process {'(DRY RUN)' if args.dry_run else ''}...")
    start_time = time.time()
    
    results = deleter.delete_products_from_csv(args.csv_file, dry_run=args.dry_run)
    
    # Save results
    deleter.save_results(results, args.output_dir)
    
    # Print summary
    elapsed_time = time.time() - start_time
    print(f"\nDeletion {'simulation' if args.dry_run else 'process'} completed in {elapsed_time:.2f} seconds")
    print(f"- Products deleted: {deleter.deleted_count}")
    print(f"- Failed deletions: {deleter.failed_count}")
    print(f"- Products not found: {deleter.not_found_count}")
    print(f"- Total processed: {deleter.deleted_count + deleter.failed_count + deleter.not_found_count}")

if __name__ == "__main__":
    main()