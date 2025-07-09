#!/usr/bin/env python3
"""
Find remaining products that still need to be deleted by checking
which SKUs from the original deletion list still exist in Shopify
"""

import csv
import sys
import time
from pathlib import Path
from datetime import datetime
from typing import Set, List, Dict
import os
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

from scripts.shopify.shopify_base import ShopifyAPIBase

class RemainingProductsFinder(ShopifyAPIBase):
    """Find products that still exist in Shopify from deletion list"""
    
    def __init__(self, shop_url: str, access_token: str):
        super().__init__(shop_url, access_token)
        self.found_products = []
        self.not_found_skus = []
    
    def check_product_exists(self, sku: str) -> Dict:
        """Check if a product with given SKU still exists in Shopify"""
        query = """
        query findProductBySKU($sku: String!) {
            products(first: 5, query: $sku) {
                edges {
                    node {
                        id
                        title
                        handle
                        status
                        vendor
                        variants(first: 10) {
                            edges {
                                node {
                                    id
                                    sku
                                    price
                                    inventoryQuantity
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
                            return {
                                'exists': True,
                                'product_id': product['node']['id'],
                                'title': product['node']['title'],
                                'handle': product['node']['handle'],
                                'vendor': product['node'].get('vendor', ''),
                                'status': product['node'].get('status', ''),
                                'price': variant['node'].get('price', ''),
                                'inventory': variant['node'].get('inventoryQuantity', 0)
                            }
            
            return {'exists': False}
            
        except Exception as e:
            self.logger.error(f"Error checking SKU {sku}: {str(e)}")
            return {'exists': False, 'error': str(e)}
    
    def find_remaining_products(self, csv_file: str) -> Dict[str, List]:
        """Check which products from the CSV still exist in Shopify"""
        results = {
            'still_exists': [],
            'not_found': [],
            'errors': []
        }
        
        # Load the original deletion list
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            products = list(reader)
        
        total = len(products)
        self.logger.info(f"Checking {total} products...")
        
        for i, row in enumerate(products, 1):
            sku = row.get('sku', '').strip()
            
            if not sku:
                continue
            
            # Progress update
            if i % 10 == 0:
                self.logger.info(f"Progress: {i}/{total} checked")
            
            # Check if product exists
            result = self.check_product_exists(sku)
            
            if result.get('error'):
                results['errors'].append({
                    'sku': sku,
                    'error': result['error']
                })
            elif result.get('exists'):
                results['still_exists'].append({
                    'sku': sku,
                    'handle': result.get('handle', ''),
                    'title': result.get('title', ''),
                    'vendor': result.get('vendor', ''),
                    'status': result.get('status', ''),
                    'price': result.get('price', ''),
                    'inventory_qty': result.get('inventory', '')
                })
                self.logger.info(f"Found: {sku} - {result.get('title', 'No title')}")
            else:
                results['not_found'].append(sku)
            
            # Rate limiting
            time.sleep(0.2)
        
        return results
    
    def save_remaining_products(self, products: List[Dict], output_file: str):
        """Save the list of products that still need to be deleted"""
        if not products:
            self.logger.info("No remaining products found!")
            return
        
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['sku', 'handle', 'title', 'vendor', 'price', 'inventory_qty', 'status']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(products)
        
        self.logger.info(f"Saved {len(products)} remaining products to: {output_file}")

def main():
    # Load environment variables
    load_dotenv()
    
    # Get credentials
    shop_url = os.getenv('SHOPIFY_SHOP_URL')
    access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
    
    if not shop_url or not access_token:
        print("Error: Shopify credentials not set in environment")
        sys.exit(1)
    
    # File paths
    data_dir = Path(__file__).parent.parent.parent / "data"
    original_file = data_dir / "products_to_delete_20250627_160334.csv"
    
    if not original_file.exists():
        print(f"Error: Original deletion file not found: {original_file}")
        sys.exit(1)
    
    # Initialize finder
    finder = RemainingProductsFinder(shop_url, access_token)
    
    # Find remaining products
    print("Checking which products still exist in Shopify...")
    print("This may take a few minutes...")
    
    start_time = time.time()
    results = finder.find_remaining_products(str(original_file))
    
    # Generate output filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = data_dir / f"remaining_products_to_delete_{timestamp}.csv"
    
    # Save remaining products
    if results['still_exists']:
        finder.save_remaining_products(results['still_exists'], str(output_file))
    
    # Print summary
    elapsed = time.time() - start_time
    print(f"\nCompleted in {elapsed:.2f} seconds")
    print(f"- Products still in Shopify: {len(results['still_exists'])}")
    print(f"- Products already deleted: {len(results['not_found'])}")
    print(f"- Errors: {len(results['errors'])}")
    
    if results['still_exists']:
        print(f"\nTo delete the remaining products, run:")
        print(f"python scripts/shopify/delete_products_by_sku.py {output_file}")

if __name__ == "__main__":
    main()