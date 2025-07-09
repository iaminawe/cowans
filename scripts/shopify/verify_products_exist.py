#!/usr/bin/env python3
"""
Script to verify which duplicate products actually exist in Shopify before deletion.
This helps identify products that may have already been deleted or have different handles.
"""

import pandas as pd
import requests
import json
import time
import sys
import os
from datetime import datetime

class ShopifyProductVerifier:
    def __init__(self, shop_url, access_token):
        """
        Initialize the Shopify product verifier.
        
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
        self.max_requests_per_second = 2
        
    def rate_limit(self):
        """Implement rate limiting to respect Shopify API limits."""
        self.request_count += 1
        
        if self.request_count % self.max_requests_per_second == 0:
            elapsed_time = time.time() - self.start_time
            if elapsed_time < 1.0:
                sleep_time = 1.0 - elapsed_time
                print(f"Rate limiting: sleeping for {sleep_time:.2f} seconds...")
                time.sleep(sleep_time)
            self.start_time = time.time()
    
    def verify_product_by_handle(self, handle):
        """
        Verify if a product exists in Shopify by handle.
        
        Args:
            handle (str): The handle to search for
            
        Returns:
            dict: Product info if found, None if not found
        """
        query = """
        query($query: String!) {
            products(first: 1, query: $query) {
                edges {
                    node {
                        id
                        title
                        handle
                        status
                        createdAt
                        updatedAt
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
        
        variables = {"query": f"handle:{handle}"}
        
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
                    return None
                
                products = data['data']['products']['edges']
                if products:
                    product_data = products[0]['node']
                    return {
                        'id': product_data['id'],
                        'title': product_data['title'],
                        'handle': product_data['handle'],
                        'status': product_data['status'],
                        'created_at': product_data['createdAt'],
                        'updated_at': product_data['updatedAt'],
                        'variants': [v['node'] for v in product_data['variants']['edges']]
                    }
                return None
            else:
                print(f"HTTP error {response.status_code} for handle {handle}: {response.text}")
                return None
                
        except Exception as e:
            print(f"Error verifying handle {handle}: {str(e)}")
            return None
    
    def search_product_by_sku(self, sku):
        """
        Search for products by SKU as a fallback.
        
        Args:
            sku (str): The SKU to search for
            
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
                        variants(first: 10) {
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
        
        variables = {"query": f"sku:{sku}"}
        
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
                    return []
                
                products = []
                for edge in data['data']['products']['edges']:
                    product = edge['node']
                    # Check if any variant has the matching SKU
                    for variant_edge in product['variants']['edges']:
                        variant = variant_edge['node']
                        if variant['sku'] == sku:
                            products.append({
                                'id': product['id'],
                                'title': product['title'],
                                'handle': product['handle'],
                                'status': product['status'],
                                'matching_variant': variant
                            })
                            break
                
                return products
            else:
                return []
                
        except Exception as e:
            print(f"Error searching SKU {sku}: {str(e)}")
            return []

def verify_duplicate_products(duplicates_file, shop_url, access_token):
    """
    Verify which duplicate products actually exist in Shopify.
    
    Args:
        duplicates_file (str): Path to the CSV file with duplicate products
        shop_url (str): Shopify shop URL
        access_token (str): Shopify Admin API access token
    """
    print(f"Reading duplicates file: {duplicates_file}")
    
    try:
        df = pd.read_csv(duplicates_file, encoding='utf-8')
        print(f"Found {len(df)} duplicate products to verify")
    except Exception as e:
        print(f"Error reading CSV file: {str(e)}")
        return
    
    verifier = ShopifyProductVerifier(shop_url, access_token)
    
    # Results tracking
    results = {
        'found_by_handle': [],
        'found_by_sku': [],
        'not_found': [],
        'errors': []
    }
    
    print(f"\nVerifying products...")
    print("=" * 80)
    
    for index, row in df.iterrows():
        handle = row.get('url handle', '')
        sku = row.get('sku', '')
        title = row.get('title', 'Unknown')[:50] + '...' if row.get('title') else 'Unknown'
        
        print(f"\n{index + 1:3d}/{len(df)}: Verifying '{handle}'")
        print(f"     SKU: {sku}")
        print(f"     Title: {title}")
        
        # First try to find by handle
        product = verifier.verify_product_by_handle(handle)
        
        if product:
            print(f"     ✅ Found by handle: {product['status']} (ID: {product['id']})")
            results['found_by_handle'].append({
                'original_row': index,
                'handle': handle,
                'sku': sku,
                'title': title,
                'shopify_product': product
            })
            continue
        
        # If not found by handle, try SKU search
        if sku:
            print(f"     🔍 Not found by handle, searching by SKU...")
            sku_products = verifier.search_product_by_sku(sku)
            
            if sku_products:
                print(f"     ✅ Found by SKU: {len(sku_products)} product(s)")
                for sp in sku_products:
                    print(f"         Handle: {sp['handle']} | Status: {sp['status']}")
                
                results['found_by_sku'].append({
                    'original_row': index,
                    'handle': handle,
                    'sku': sku,
                    'title': title,
                    'shopify_products': sku_products
                })
                continue
        
        # Not found by either method
        print(f"     ❌ Not found in Shopify")
        results['not_found'].append({
            'original_row': index,
            'handle': handle,
            'sku': sku,
            'title': title
        })
    
    # Generate summary report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    print(f"\n" + "=" * 80)
    print(f"VERIFICATION SUMMARY")
    print("=" * 80)
    print(f"Total products verified: {len(df)}")
    print(f"Found by handle: {len(results['found_by_handle'])}")
    print(f"Found by SKU (handle mismatch): {len(results['found_by_sku'])}")
    print(f"Not found: {len(results['not_found'])}")
    print(f"Errors: {len(results['errors'])}")
    
    # Save detailed results
    if results['found_by_handle']:
        found_by_handle_df = pd.DataFrame([
            {
                'original_row': r['original_row'],
                'handle': r['handle'],
                'sku': r['sku'],
                'title': r['title'],
                'shopify_id': r['shopify_product']['id'],
                'shopify_status': r['shopify_product']['status'],
                'verification_method': 'handle'
            }
            for r in results['found_by_handle']
        ])
        
        handle_file = f"data/duplicates_found_by_handle_{timestamp}.csv"
        found_by_handle_df.to_csv(handle_file, index=False)
        print(f"\nProducts found by handle saved to: {handle_file}")
    
    if results['found_by_sku']:
        found_by_sku_data = []
        for r in results['found_by_sku']:
            for sp in r['shopify_products']:
                found_by_sku_data.append({
                    'original_row': r['original_row'],
                    'original_handle': r['handle'],
                    'sku': r['sku'],
                    'title': r['title'],
                    'shopify_id': sp['id'],
                    'shopify_handle': sp['handle'],
                    'shopify_status': sp['status'],
                    'verification_method': 'sku'
                })
        
        sku_file = f"data/duplicates_found_by_sku_{timestamp}.csv"
        pd.DataFrame(found_by_sku_data).to_csv(sku_file, index=False)
        print(f"Products found by SKU saved to: {sku_file}")
    
    if results['not_found']:
        not_found_df = pd.DataFrame(results['not_found'])
        not_found_file = f"data/duplicates_not_found_{timestamp}.csv"
        not_found_df.to_csv(not_found_file, index=False)
        print(f"Products not found saved to: {not_found_file}")
    
    # Create deletion-ready file for products that were found
    deletion_ready = []
    
    # Add products found by handle (exact match)
    for r in results['found_by_handle']:
        deletion_ready.append({
            'handle': r['handle'],
            'sku': r['sku'],
            'title': r['title'],
            'shopify_id': r['shopify_product']['id'],
            'verification_method': 'handle',
            'ready_for_deletion': True
        })
    
    # Add products found by SKU (but handle might be different)
    for r in results['found_by_sku']:
        for sp in r['shopify_products']:
            deletion_ready.append({
                'handle': sp['handle'],  # Use the actual Shopify handle
                'sku': r['sku'],
                'title': r['title'],
                'shopify_id': sp['id'],
                'verification_method': 'sku',
                'ready_for_deletion': True,
                'note': f"Original handle: {r['handle']}"
            })
    
    if deletion_ready:
        deletion_file = f"data/verified_duplicates_for_deletion_{timestamp}.csv"
        pd.DataFrame(deletion_ready).to_csv(deletion_file, index=False)
        print(f"\nVerified products ready for deletion: {deletion_file}")
        print(f"Total products ready for deletion: {len(deletion_ready)}")
    
    return results

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Verify duplicate products exist in Shopify before deletion.')
    parser.add_argument('duplicates_file', help='Path to the CSV file with duplicate products')
    parser.add_argument('--shop-url', required=True, help='Shopify shop URL (e.g., your-shop.myshopify.com)')
    parser.add_argument('--access-token', required=True, help='Shopify Admin API access token')
    
    args = parser.parse_args()
    
    results = verify_duplicate_products(
        args.duplicates_file,
        args.shop_url,
        args.access_token
    )