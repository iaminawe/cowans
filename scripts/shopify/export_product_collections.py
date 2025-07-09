#!/usr/bin/env python3
"""
Shopify Product Collections Exporter

This script downloads product handles and their associated collections from a Shopify store.
It exports the data to a CSV file for analysis or migration purposes.

Usage:
    python export_product_collections.py --shop-url store.myshopify.com --access-token TOKEN
    python export_product_collections.py --shop-url store.myshopify.com --access-token TOKEN --output collections.csv
    python export_product_collections.py --shop-url store.myshopify.com --access-token TOKEN --limit 100
"""

import os
import sys
import csv
import argparse
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

try:
    from .shopify_base import ShopifyAPIBase
except ImportError:
    from shopify_base import ShopifyAPIBase

# GraphQL queries for fetching products and collections
PRODUCTS_WITH_COLLECTIONS_QUERY = """
query getProductsWithCollections($first: Int!, $after: String) {
  products(first: $first, after: $after) {
    edges {
      node {
        id
        handle
        title
        status
        publishedAt
        createdAt
        updatedAt
        vendor
        productType
        tags
        collections(first: 50) {
          edges {
            node {
              id
              handle
              title
              description
              updatedAt
              image {
                url
                altText
              }
            }
          }
        }
        variants(first: 1) {
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
      cursor
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""

# Alternative query for just collections info
COLLECTIONS_QUERY = """
query getCollections($first: Int!, $after: String) {
  collections(first: $first, after: $after) {
    edges {
      node {
        id
        handle
        title
        description
        updatedAt
        productsCount
        image {
          url
          altText
        }
        products(first: 100) {
          edges {
            node {
              id
              handle
              title
              status
            }
          }
        }
      }
      cursor
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""

class ShopifyCollectionExporter(ShopifyAPIBase):
    """Exports Shopify product handles and their collections to CSV."""
    
    def __init__(self, shop_url: str, access_token: str, debug: bool = False):
        """Initialize the exporter."""
        super().__init__(shop_url, access_token, debug)
        self.logger = logging.getLogger(__name__)
        
        # Export metrics
        self.export_metrics = {
            'products_processed': 0,
            'collections_found': 0,
            'products_with_collections': 0,
            'products_without_collections': 0,
            'api_calls': 0,
            'errors': 0
        }
    
    def export_product_collections(self, output_file: str, limit: Optional[int] = None, 
                                 collections_only: bool = False) -> None:
        """Export products and their collections to CSV."""
        try:
            print(f"🚀 Starting Shopify collection export to: {output_file}")
            self.logger.info(f"Starting export to {output_file}")
            
            if collections_only:
                self._export_collections_view(output_file, limit)
            else:
                self._export_products_view(output_file, limit)
            
            self._print_summary()
            print(f"✅ Export completed successfully: {output_file}")
            
        except Exception as e:
            self.logger.error(f"Export failed: {str(e)}")
            print(f"❌ Export failed: {str(e)}")
            raise
    
    def _export_products_view(self, output_file: str, limit: Optional[int] = None) -> None:
        """Export from products perspective (each product with its collections)."""
        print("📦 Fetching products and their collections...")
        
        # Prepare CSV writer
        fieldnames = [
            'product_id', 'product_handle', 'product_title', 'product_status', 
            'product_published_at', 'product_created_at', 'product_updated_at',
            'vendor', 'product_type', 'tags', 'sku', 'price', 'inventory_quantity',
            'collection_id', 'collection_handle', 'collection_title', 'collection_description',
            'collection_updated_at', 'collection_image_url', 'collection_image_alt'
        ]
        
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            # Pagination variables
            has_next_page = True
            cursor = None
            batch_size = 50  # Shopify recommended batch size
            
            while has_next_page and (not limit or self.export_metrics['products_processed'] < limit):
                try:
                    # Calculate remaining items if limit is set
                    remaining = None
                    if limit:
                        remaining = limit - self.export_metrics['products_processed']
                        batch_size = min(batch_size, remaining)
                    
                    # Fetch products batch
                    variables = {'first': batch_size}
                    if cursor:
                        variables['after'] = cursor
                    
                    print(f"📥 Fetching batch (processed: {self.export_metrics['products_processed']})...")
                    result = self.execute_graphql(PRODUCTS_WITH_COLLECTIONS_QUERY, variables)
                    self.export_metrics['api_calls'] += 1
                    
                    if 'errors' in result:
                        raise Exception(f"GraphQL errors: {result['errors']}")
                    
                    products_data = result.get('data', {}).get('products', {})
                    products = products_data.get('edges', [])
                    page_info = products_data.get('pageInfo', {})
                    
                    # Process each product
                    for product_edge in products:
                        product = product_edge['node']
                        self._process_product_row(writer, product)
                        
                        self.export_metrics['products_processed'] += 1
                        
                        # Check limit
                        if limit and self.export_metrics['products_processed'] >= limit:
                            break
                    
                    # Update pagination
                    has_next_page = page_info.get('hasNextPage', False)
                    cursor = page_info.get('endCursor')
                    
                    print(f"   Processed {len(products)} products in this batch")
                    
                except Exception as e:
                    self.logger.error(f"Error processing batch: {str(e)}")
                    self.export_metrics['errors'] += 1
                    break
    
    def _export_collections_view(self, output_file: str, limit: Optional[int] = None) -> None:
        """Export from collections perspective (each collection with its products)."""
        print("📂 Fetching collections and their products...")
        
        # Prepare CSV writer
        fieldnames = [
            'collection_id', 'collection_handle', 'collection_title', 'collection_description',
            'collection_updated_at', 'collection_image_url', 'collection_image_alt', 'products_count',
            'product_id', 'product_handle', 'product_title', 'product_status'
        ]
        
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            # Pagination variables
            has_next_page = True
            cursor = None
            batch_size = 50
            collections_processed = 0
            
            while has_next_page and (not limit or collections_processed < limit):
                try:
                    # Calculate remaining items if limit is set
                    remaining = None
                    if limit:
                        remaining = limit - collections_processed
                        batch_size = min(batch_size, remaining)
                    
                    # Fetch collections batch
                    variables = {'first': batch_size}
                    if cursor:
                        variables['after'] = cursor
                    
                    print(f"📥 Fetching batch (processed: {collections_processed})...")
                    result = self.execute_graphql(COLLECTIONS_QUERY, variables)
                    self.export_metrics['api_calls'] += 1
                    
                    if 'errors' in result:
                        raise Exception(f"GraphQL errors: {result['errors']}")
                    
                    collections_data = result.get('data', {}).get('collections', {})
                    collections = collections_data.get('edges', [])
                    page_info = collections_data.get('pageInfo', {})
                    
                    # Process each collection
                    for collection_edge in collections:
                        collection = collection_edge['node']
                        self._process_collection_row(writer, collection)
                        
                        collections_processed += 1
                        
                        # Check limit
                        if limit and collections_processed >= limit:
                            break
                    
                    # Update pagination
                    has_next_page = page_info.get('hasNextPage', False)
                    cursor = page_info.get('endCursor')
                    
                    print(f"   Processed {len(collections)} collections in this batch")
                    
                except Exception as e:
                    self.logger.error(f"Error processing batch: {str(e)}")
                    self.export_metrics['errors'] += 1
                    break
            
            self.export_metrics['collections_found'] = collections_processed
    
    def _process_product_row(self, writer: csv.DictWriter, product: Dict[str, Any]) -> None:
        """Process a single product and write rows for each collection."""
        try:
            # Extract product data
            product_data = {
                'product_id': product.get('id'),
                'product_handle': product.get('handle'),
                'product_title': product.get('title'),
                'product_status': product.get('status'),
                'product_published_at': product.get('publishedAt'),
                'product_created_at': product.get('createdAt'),
                'product_updated_at': product.get('updatedAt'),
                'vendor': product.get('vendor'),
                'product_type': product.get('productType'),
                'tags': ', '.join(product.get('tags', [])),
            }
            
            # Add variant data (first variant only)
            variants = product.get('variants', {}).get('edges', [])
            if variants:
                variant = variants[0]['node']
                product_data.update({
                    'sku': variant.get('sku'),
                    'price': variant.get('price'),
                    'inventory_quantity': variant.get('inventoryQuantity'),
                })
            
            # Get collections
            collections = product.get('collections', {}).get('edges', [])
            
            if collections:
                # Write one row per collection
                for collection_edge in collections:
                    collection = collection_edge['node']
                    row_data = product_data.copy()
                    
                    # Get collection image data
                    collection_image = collection.get('image', {})
                    collection_image_url = collection_image.get('url', '') if collection_image else ''
                    collection_image_alt = collection_image.get('altText', '') if collection_image else ''
                    
                    row_data.update({
                        'collection_id': collection.get('id'),
                        'collection_handle': collection.get('handle'),
                        'collection_title': collection.get('title'),
                        'collection_description': collection.get('description'),
                        'collection_updated_at': collection.get('updatedAt'),
                        'collection_image_url': collection_image_url,
                        'collection_image_alt': collection_image_alt,
                    })
                    writer.writerow(row_data)
                
                self.export_metrics['products_with_collections'] += 1
                self.export_metrics['collections_found'] += len(collections)
            else:
                # Product has no collections - write single row with empty collection fields
                row_data = product_data.copy()
                row_data.update({
                    'collection_id': '',
                    'collection_handle': '',
                    'collection_title': '',
                    'collection_description': '',
                    'collection_updated_at': '',
                    'collection_image_url': '',
                    'collection_image_alt': '',
                })
                writer.writerow(row_data)
                self.export_metrics['products_without_collections'] += 1
            
        except Exception as e:
            self.logger.error(f"Error processing product {product.get('handle', 'unknown')}: {str(e)}")
            self.export_metrics['errors'] += 1
    
    def _process_collection_row(self, writer: csv.DictWriter, collection: Dict[str, Any]) -> None:
        """Process a single collection and write rows for each product."""
        try:
            # Extract collection data
            collection_image = collection.get('image', {})
            collection_image_url = collection_image.get('url', '') if collection_image else ''
            collection_image_alt = collection_image.get('altText', '') if collection_image else ''
            
            collection_data = {
                'collection_id': collection.get('id'),
                'collection_handle': collection.get('handle'),
                'collection_title': collection.get('title'),
                'collection_description': collection.get('description'),
                'collection_updated_at': collection.get('updatedAt'),
                'collection_image_url': collection_image_url,
                'collection_image_alt': collection_image_alt,
                'products_count': collection.get('productsCount', 0),
            }
            
            # Get products in this collection
            products = collection.get('products', {}).get('edges', [])
            
            if products:
                # Write one row per product
                for product_edge in products:
                    product = product_edge['node']
                    row_data = collection_data.copy()
                    row_data.update({
                        'product_id': product.get('id'),
                        'product_handle': product.get('handle'),
                        'product_title': product.get('title'),
                        'product_status': product.get('status'),
                    })
                    writer.writerow(row_data)
            else:
                # Collection has no products - write single row with empty product fields
                row_data = collection_data.copy()
                row_data.update({
                    'product_id': '',
                    'product_handle': '',
                    'product_title': '',
                    'product_status': '',
                })
                writer.writerow(row_data)
            
        except Exception as e:
            self.logger.error(f"Error processing collection {collection.get('handle', 'unknown')}: {str(e)}")
            self.export_metrics['errors'] += 1
    
    def _print_summary(self) -> None:
        """Print export summary."""
        print(f"\n📊 Export Summary:")
        print(f"    📦 Products processed: {self.export_metrics['products_processed']}")
        print(f"    📂 Collections found: {self.export_metrics['collections_found']}")
        print(f"    ✅ Products with collections: {self.export_metrics['products_with_collections']}")
        print(f"    ⚠️  Products without collections: {self.export_metrics['products_without_collections']}")
        print(f"    🌐 API calls made: {self.export_metrics['api_calls']}")
        print(f"    ❌ Errors encountered: {self.export_metrics['errors']}")
        
        self.logger.info(
            f"Export completed - "
            f"Products: {self.export_metrics['products_processed']}, "
            f"Collections: {self.export_metrics['collections_found']}, "
            f"With collections: {self.export_metrics['products_with_collections']}, "
            f"Without collections: {self.export_metrics['products_without_collections']}, "
            f"API calls: {self.export_metrics['api_calls']}, "
            f"Errors: {self.export_metrics['errors']}"
        )

def main() -> None:
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description='Export Shopify product handles and their collections to CSV',
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    parser.add_argument('--shop-url', required=True, help='Shopify shop URL (*.myshopify.com)')
    parser.add_argument('--access-token', required=True, help='Shopify Admin API access token')
    parser.add_argument('--output', default='product_collections_export.csv', 
                       help='Output CSV file path (default: product_collections_export.csv)')
    parser.add_argument('--limit', type=int, help='Limit number of items to export (for testing)')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--collections-view', action='store_true', 
                       help='Export from collections perspective instead of products perspective')
    parser.add_argument('--validate-token', action='store_true', help='Validate Shopify access token')
    
    if len(sys.argv) == 1 or '--help' in sys.argv or '-h' in sys.argv:
        print("\nExample usage:")
        print("python export_product_collections.py --shop-url store.myshopify.com --access-token TOKEN")
        print("python export_product_collections.py --shop-url store.myshopify.com --access-token TOKEN --output my_export.csv")
        print("python export_product_collections.py --shop-url store.myshopify.com --access-token TOKEN --limit 100 --debug")
        print("python export_product_collections.py --shop-url store.myshopify.com --access-token TOKEN --collections-view")
        print("python export_product_collections.py --shop-url store.myshopify.com --access-token TOKEN --validate-token")
        sys.exit(1)
    
    args = parser.parse_args()
    
    try:
        # Format shop URL consistently
        shop_url = args.shop_url.strip().lower()
        if not shop_url.startswith('https://'):
            shop_url = f"https://{shop_url}"
        if '.' not in shop_url and not shop_url.endswith('myshopify.com'):
            shop_url += '.myshopify.com'
        
        # Initialize exporter
        exporter = ShopifyCollectionExporter(
            shop_url=shop_url,
            access_token=args.access_token.strip(),
            debug=args.debug
        )
        
        if args.validate_token:
            exporter.test_auth()
            return
        
        # Ensure output directory exists
        output_dir = os.path.dirname(os.path.abspath(args.output))
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # Add timestamp to output filename if not specified
        if args.output == 'product_collections_export.csv':
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            args.output = f'product_collections_export_{timestamp}.csv'
        
        # Perform export
        exporter.export_product_collections(
            output_file=args.output,
            limit=args.limit,
            collections_only=args.collections_view
        )
        
        print(f"\n🎉 Export completed successfully!")
        print(f"💾 File saved: {os.path.abspath(args.output)}")
        
    except KeyboardInterrupt:
        print(f"\n⚠️  Export interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()