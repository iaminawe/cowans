#!/usr/bin/env python3
"""
Script to find products in Shopify using multiple search methods:
1. By handle (exact match)
2. By SKU
3. By title (partial match)
4. By vendor + partial title
"""

import pandas as pd
import requests
import json
import time
import sys
import os
from datetime import datetime

class ShopifyProductFinder:
    def __init__(self, shop_url, access_token):
        """Initialize the Shopify product finder."""
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
        self.max_requests_per_second = 1  # Conservative
        
    def rate_limit(self):
        """Implement rate limiting."""
        self.request_count += 1
        
        if self.request_count % self.max_requests_per_second == 0:
            elapsed_time = time.time() - self.start_time
            if elapsed_time < 1.0:
                sleep_time = 1.0 - elapsed_time
                time.sleep(sleep_time)
            self.start_time = time.time()
    
    def search_products(self, query_string, search_type="general"):
        """
        Search for products using GraphQL.
        
        Args:
            query_string (str): The search query
            search_type (str): Type of search for logging
            
        Returns:
            list: List of products found
        """
        query = """
        query($query: String!) {
            products(first: 10, query: $query) {
                edges {
                    node {
                        id
                        title
                        handle
                        status
                        vendor
                        productType
                        variants(first: 5) {
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
            }
        }
        """
        
        variables = {"query": query_string}
        
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
                    print(f"GraphQL errors for {search_type} '{query_string}': {data['errors']}")
                    return []
                
                products = []
                for edge in data['data']['products']['edges']:
                    product = edge['node']
                    products.append({
                        'id': product['id'],
                        'title': product['title'],
                        'handle': product['handle'],
                        'status': product['status'],
                        'vendor': product['vendor'],
                        'product_type': product['productType'],
                        'variants': [v['node'] for v in product['variants']['edges']],
                        'search_method': search_type,
                        'search_query': query_string
                    })
                
                return products
            else:
                print(f"HTTP error {response.status_code} for {search_type}: {response.text}")
                return []
                
        except Exception as e:
            print(f"Error searching {search_type} '{query_string}': {str(e)}")
            return []
    
    def find_product_multiple_ways(self, row):
        """
        Try to find a product using multiple search methods.
        
        Args:
            row: DataFrame row with product info
            
        Returns:
            list: All products found by any method
        """
        handle = row.get('url handle', '')
        sku = row.get('sku', '')
        title = row.get('title', '')
        vendor = row.get('vendor', '')
        
        all_found_products = []
        
        # Method 1: Search by handle
        if handle:
            print(f"    🔍 Searching by handle: {handle}")
            products = self.search_products(f"handle:{handle}", "handle")
            if products:
                print(f"    ✅ Found {len(products)} by handle")
                all_found_products.extend(products)
            else:
                print(f"    ❌ No match by handle")
        
        # Method 2: Search by SKU
        if sku and not all_found_products:
            print(f"    🔍 Searching by SKU: {sku}")
            products = self.search_products(f"sku:{sku}", "sku")
            if products:
                print(f"    ✅ Found {len(products)} by SKU")
                all_found_products.extend(products)
            else:
                print(f"    ❌ No match by SKU")
        
        # Method 3: Search by title (first few words)
        if title and not all_found_products:
            # Get first 3-4 words of title for search
            title_words = title.split()[:4]
            title_search = ' '.join(title_words)
            print(f"    🔍 Searching by title: '{title_search}'")
            products = self.search_products(f"title:{title_search}", "title")
            if products:
                print(f"    ✅ Found {len(products)} by title")
                # Filter to products that actually match closely
                matching_products = []
                for p in products:
                    # Check if the titles are reasonably similar
                    if any(word.lower() in p['title'].lower() for word in title_words):
                        matching_products.append(p)
                if matching_products:
                    all_found_products.extend(matching_products)
                    print(f"    ✅ {len(matching_products)} have similar titles")
                else:
                    print(f"    ❌ No titles match closely enough")
            else:
                print(f"    ❌ No match by title")
        
        # Method 4: Search by vendor + product type
        if vendor and not all_found_products:
            print(f"    🔍 Searching by vendor: {vendor}")
            products = self.search_products(f"vendor:{vendor}", "vendor")
            if products:
                print(f"    ✅ Found {len(products)} by vendor")
                # Filter by title similarity
                matching_products = []
                title_words = title.lower().split()[:3] if title else []
                for p in products:
                    if any(word in p['title'].lower() for word in title_words):
                        matching_products.append(p)
                if matching_products:
                    all_found_products.extend(matching_products)
                    print(f"    ✅ {len(matching_products)} match vendor + title")
                else:
                    print(f"    ❌ No vendor products match title")
            else:
                print(f"    ❌ No match by vendor")
        
        return all_found_products

def find_duplicate_products(duplicates_file, shop_url, access_token, max_products=50):
    """
    Find duplicate products using multiple search methods.
    
    Args:
        duplicates_file (str): Path to the CSV file with duplicate products
        shop_url (str): Shopify shop URL
        access_token (str): Shopify Admin API access token
        max_products (int): Maximum number of products to process (for testing)
    """
    print(f"Reading duplicates file: {duplicates_file}")
    
    try:
        df = pd.read_csv(duplicates_file, encoding='utf-8')
        print(f"Found {len(df)} duplicate products")
        
        # Limit for testing
        if max_products and len(df) > max_products:
            df = df.head(max_products)
            print(f"Processing first {max_products} products for testing")
        
    except Exception as e:
        print(f"Error reading CSV file: {str(e)}")
        return
    
    finder = ShopifyProductFinder(shop_url, access_token)
    
    # Results tracking
    results = {
        'found_products': [],
        'not_found': [],
        'search_summary': {}
    }
    
    print(f"\nSearching for products using multiple methods...")
    print("=" * 80)
    
    for index, row in df.iterrows():
        handle = row.get('url handle', '')
        sku = row.get('sku', '')
        title = row.get('title', 'Unknown')[:50] + '...' if row.get('title') else 'Unknown'
        
        print(f"\n{index + 1:3d}/{len(df)}: {title}")
        print(f"     Handle: {handle}")
        print(f"     SKU: {sku}")
        
        # Try multiple search methods
        found_products = finder.find_product_multiple_ways(row)
        
        if found_products:
            print(f"     ✅ FOUND: {len(found_products)} matching product(s)")
            for i, product in enumerate(found_products):
                print(f"         {i+1}. ID: {product['id']} | Handle: {product['handle']}")
                print(f"            Title: {product['title'][:60]}...")
                print(f"            Method: {product['search_method']} | Status: {product['status']}")
            
            results['found_products'].append({
                'original_row': index,
                'original_handle': handle,
                'original_sku': sku,
                'original_title': title,
                'found_products': found_products
            })
            
            # Track search method stats
            for product in found_products:
                method = product['search_method']
                if method not in results['search_summary']:
                    results['search_summary'][method] = 0
                results['search_summary'][method] += 1
        else:
            print(f"     ❌ NOT FOUND by any method")
            results['not_found'].append({
                'original_row': index,
                'handle': handle,
                'sku': sku,
                'title': title
            })
    
    # Generate summary
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    print(f"\n" + "=" * 80)
    print(f"SEARCH SUMMARY")
    print("=" * 80)
    print(f"Total products searched: {len(df)}")
    print(f"Products found: {len(results['found_products'])}")
    print(f"Products not found: {len(results['not_found'])}")
    
    print(f"\nSearch method success:")
    for method, count in results['search_summary'].items():
        print(f"  {method}: {count} products")
    
    # Save results for deletion
    if results['found_products']:
        deletion_ready = []
        
        for result in results['found_products']:
            for product in result['found_products']:
                deletion_ready.append({
                    'original_handle': result['original_handle'],
                    'original_sku': result['original_sku'], 
                    'original_title': result['original_title'],
                    'shopify_id': product['id'],
                    'shopify_handle': product['handle'],
                    'shopify_title': product['title'],
                    'shopify_status': product['status'],
                    'search_method': product['search_method'],
                    'ready_for_deletion': True
                })
        
        deletion_file = f"data/found_duplicates_for_deletion_{timestamp}.csv"
        pd.DataFrame(deletion_ready).to_csv(deletion_file, index=False)
        print(f"\nProducts ready for deletion saved to: {deletion_file}")
        print(f"Total products ready for deletion: {len(deletion_ready)}")
    
    # Save not found list
    if results['not_found']:
        not_found_file = f"data/duplicates_not_found_{timestamp}.csv"
        pd.DataFrame(results['not_found']).to_csv(not_found_file, index=False)
        print(f"Products not found saved to: {not_found_file}")
    
    return results

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Find duplicate products using multiple search methods.')
    parser.add_argument('duplicates_file', help='Path to the CSV file with duplicate products')
    parser.add_argument('--shop-url', required=True, help='Shopify shop URL')
    parser.add_argument('--access-token', required=True, help='Shopify Admin API access token')
    parser.add_argument('--max-products', type=int, default=50, help='Maximum products to process (default: 50)')
    
    args = parser.parse_args()
    
    results = find_duplicate_products(
        args.duplicates_file,
        args.shop_url,
        args.access_token,
        args.max_products
    )