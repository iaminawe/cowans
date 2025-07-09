#!/usr/bin/env python3
"""
Script to delete duplicate products from Shopify based on the removed duplicates CSV file.
This script uses the Shopify Admin GraphQL API to delete products.
"""

import pandas as pd
import requests
import json
import time
import sys
import os
from datetime import datetime

class ShopifyProductDeleter:
    def __init__(self, shop_url, access_token):
        """
        Initialize the Shopify product deleter.
        
        Args:
            shop_url (str): Shopify shop URL (e.g., 'your-shop.myshopify.com')
            access_token (str): Shopify Admin API access token
        """
        self.shop_url = shop_url.replace('https://', '').replace('http://', '')
        if not self.shop_url.endswith('.myshopify.com'):
            if '.' not in self.shop_url:
                self.shop_url += '.myshopify.com'
        
        self.access_token = access_token
        self.graphql_url = f"https://{self.shop_url}/admin/api/2024-10/graphql.json"
        self.headers = {
            'Content-Type': 'application/json',
            'X-Shopify-Access-Token': access_token
        }
        
        # Rate limiting
        self.request_count = 0
        self.start_time = time.time()
        self.max_requests_per_second = 2  # Conservative rate limit
        
    def rate_limit(self):
        """Implement rate limiting to respect Shopify API limits."""
        self.request_count += 1
        
        # Simple rate limiting: max 2 requests per second
        if self.request_count % self.max_requests_per_second == 0:
            elapsed_time = time.time() - self.start_time
            if elapsed_time < 1.0:
                sleep_time = 1.0 - elapsed_time
                print(f"Rate limiting: sleeping for {sleep_time:.2f} seconds...")
                time.sleep(sleep_time)
            self.start_time = time.time()
    
    def find_products_by_handle(self, handle):
        """
        Find products in Shopify by handle using GraphQL.
        
        Args:
            handle (str): The handle to search for
            
        Returns:
            list: List of product objects with their IDs
        """
        query = """
        query($handle: String!) {
            product(handle: $handle) {
                id
                title
                handle
                status
                variants(first: 50) {
                    edges {
                        node {
                            id
                            sku
                            title
                        }
                    }
                }
            }
        }
        """
        
        variables = {
            "handle": handle
        }
        
        self.rate_limit()
        
        try:
            response = requests.post(
                self.graphql_url,
                headers=self.headers,
                json={"query": query, "variables": variables}
            )
            
            if response.status_code == 200:
                data = response.json()
                if 'errors' in data:
                    print(f"GraphQL errors for handle {handle}: {data['errors']}")
                    return []
                
                product_data = data['data']['product']
                if not product_data:
                    return []
                
                # Return product info
                products = [{
                    'product_id': product_data['id'],
                    'title': product_data['title'],
                    'handle': product_data['handle'],
                    'status': product_data['status'],
                    'variants': [variant['node'] for variant in product_data['variants']['edges']]
                }]
                
                return products
            else:
                print(f"HTTP error {response.status_code} for handle {handle}: {response.text}")
                return []
                
        except Exception as e:
            print(f"Error searching for handle {handle}: {str(e)}")
            return []
    
    def delete_product(self, product_id):
        """
        Delete a product from Shopify using GraphQL.
        
        Args:
            product_id (str): The Shopify product ID
            
        Returns:
            bool: True if successful, False otherwise
        """
        mutation = """
        mutation productDelete($input: ProductDeleteInput!) {
            productDelete(input: $input) {
                deletedProductId
                userErrors {
                    field
                    message
                }
            }
        }
        """
        
        variables = {
            "input": {
                "id": product_id
            }
        }
        
        self.rate_limit()
        
        try:
            response = requests.post(
                self.graphql_url,
                headers=self.headers,
                json={"query": mutation, "variables": variables}
            )
            
            if response.status_code == 200:
                data = response.json()
                if 'errors' in data:
                    print(f"GraphQL errors deleting product {product_id}: {data['errors']}")
                    return False
                
                result = data['data']['productDelete']
                if result['userErrors']:
                    print(f"User errors deleting product {product_id}: {result['userErrors']}")
                    return False
                
                if result['deletedProductId']:
                    print(f"✅ Successfully deleted product {product_id}")
                    return True
                else:
                    print(f"❌ Failed to delete product {product_id} - no deletion confirmed")
                    return False
            else:
                print(f"HTTP error {response.status_code} deleting product {product_id}: {response.text}")
                return False
                
        except Exception as e:
            print(f"Error deleting product {product_id}: {str(e)}")
            return False

def delete_duplicate_products(removed_duplicates_file, shop_url, access_token, dry_run=True):
    """
    Delete duplicate products from Shopify based on the removed duplicates CSV.
    
    Args:
        removed_duplicates_file (str): Path to the CSV file with removed duplicates
        shop_url (str): Shopify shop URL
        access_token (str): Shopify Admin API access token
        dry_run (bool): If True, only show what would be deleted without actually deleting
    """
    print(f"Reading removed duplicates file: {removed_duplicates_file}")
    
    try:
        df = pd.read_csv(removed_duplicates_file, encoding='utf-8')
        print(f"Found {len(df)} duplicate products to process")
    except Exception as e:
        print(f"Error reading CSV file: {str(e)}")
        return
    
    # Check required columns  
    required_cols = ['shopify_handle', 'shopify_id'] if 'shopify_handle' in df.columns else ['url handle']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"Error: Required columns not found: {missing_cols}")
        print(f"Available columns: {list(df.columns)}")
        return
    
    deleter = ShopifyProductDeleter(shop_url, access_token)
    
    # Statistics tracking
    stats = {
        'total_duplicates': len(df),
        'products_found': 0,
        'products_deleted': 0,
        'products_not_found': 0,
        'deletion_errors': 0
    }
    
    print(f"\n{'DRY RUN - ' if dry_run else ''}Starting deletion process...")
    print("=" * 60)
    
    for index, row in df.iterrows():
        # Handle both CSV formats
        if 'shopify_handle' in row:
            handle = row['shopify_handle']
            product_id = row['shopify_id']
            sku = row.get('original_sku', 'Unknown')
            title = row.get('shopify_title', 'Unknown')[:50] + '...' if row.get('shopify_title') else 'Unknown'
            
            print(f"\nProcessing {index + 1}/{len(df)}: Handle '{handle}'")
            print(f"  SKU: {sku} | Title: {title} | ID: {product_id}")
            
            # We already have the product ID, so create a product object directly
            products = [{
                'product_id': product_id,
                'title': row.get('shopify_title', 'Unknown'),
                'handle': handle,
                'status': row.get('shopify_status', 'ACTIVE')
            }]
        else:
            handle = row['url handle']
            sku = row.get('sku', 'Unknown')
            title = row.get('title', 'Unknown')[:50] + '...' if row.get('title') else 'Unknown'
            
            print(f"\nProcessing {index + 1}/{len(df)}: Handle '{handle}'")
            print(f"  SKU: {sku} | Title: {title}")
            
            # Find products with this handle
            products = deleter.find_products_by_handle(handle)
        
        if not products:
            print(f"  ❌ No products found with handle '{handle}'")
            stats['products_not_found'] += 1
            continue
        
        stats['products_found'] += len(products)
        
        for product in products:
            product_id = product['product_id']
            product_title = product['title'][:50] + '...' if len(product['title']) > 50 else product['title']
            
            print(f"  Found product: {product_title} (ID: {product_id})")
            
            if dry_run:
                print(f"  🔍 DRY RUN: Would delete product {product_id}")
                stats['products_deleted'] += 1
            else:
                success = deleter.delete_product(product_id)
                if success:
                    stats['products_deleted'] += 1
                else:
                    stats['deletion_errors'] += 1
    
    # Print final statistics
    print("\n" + "=" * 60)
    print(f"{'DRY RUN ' if dry_run else ''}DELETION SUMMARY")
    print("=" * 60)
    print(f"Total duplicate records processed: {stats['total_duplicates']}")
    print(f"Products found in Shopify: {stats['products_found']}")
    print(f"Products not found: {stats['products_not_found']}")
    
    if dry_run:
        print(f"Products that would be deleted: {stats['products_deleted']}")
    else:
        print(f"Products successfully deleted: {stats['products_deleted']}")
        print(f"Deletion errors: {stats['deletion_errors']}")
    
    # Generate report file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = f"data/shopify_deletion_report_{timestamp}.txt"
    
    with open(report_file, 'w') as f:
        f.write(f"Shopify Product Deletion Report\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Mode: {'DRY RUN' if dry_run else 'LIVE DELETION'}\n")
        f.write(f"Shop URL: {shop_url}\n")
        f.write(f"Source file: {removed_duplicates_file}\n\n")
        f.write(f"Statistics:\n")
        f.write(f"- Total duplicate records: {stats['total_duplicates']}\n")
        f.write(f"- Products found: {stats['products_found']}\n")
        f.write(f"- Products not found: {stats['products_not_found']}\n")
        f.write(f"- Products {'that would be ' if dry_run else ''}deleted: {stats['products_deleted']}\n")
        if not dry_run:
            f.write(f"- Deletion errors: {stats['deletion_errors']}\n")
    
    print(f"\nReport saved to: {report_file}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Delete duplicate products from Shopify.')
    parser.add_argument('removed_duplicates_file', help='Path to the CSV file with removed duplicates')
    parser.add_argument('--shop-url', required=True, help='Shopify shop URL (e.g., your-shop.myshopify.com)')
    parser.add_argument('--access-token', required=True, help='Shopify Admin API access token')
    parser.add_argument('--dry-run', action='store_true', default=True, help='Perform a dry run (default: True)')
    parser.add_argument('--live', action='store_true', help='Perform live deletion (overrides --dry-run)')
    parser.add_argument('--confirm', action='store_true', help='Skip confirmation prompt for automated deletion')
    
    args = parser.parse_args()
    
    # Determine if this is a dry run or live deletion
    dry_run = not args.live  # If --live is specified, dry_run becomes False
    
    if not dry_run and not args.confirm:
        print("⚠️  WARNING: This will permanently delete products from Shopify!")
        print("⚠️  Make sure you have a backup before proceeding.")
        confirmation = input("Type 'DELETE' to confirm you want to proceed with live deletion: ")
        if confirmation != 'DELETE':
            print("Deletion cancelled.")
            sys.exit(0)
    
    delete_duplicate_products(
        args.removed_duplicates_file,
        args.shop_url,
        args.access_token,
        dry_run
    )