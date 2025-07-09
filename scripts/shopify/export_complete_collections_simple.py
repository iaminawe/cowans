#!/usr/bin/env python3
"""
Shopify Complete Collections Exporter (Simplified)

This script downloads comprehensive collection data from a Shopify store,
including all metadata needed to recreate collections on another site.

Usage:
    python export_complete_collections_simple.py --shop-url store.myshopify.com --access-token TOKEN
"""

import os
import sys
import csv
import json
import argparse
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

try:
    from .shopify_base import ShopifyAPIBase
except ImportError:
    from shopify_base import ShopifyAPIBase

# Comprehensive collections query
COMPLETE_COLLECTIONS_QUERY = """
query getCompleteCollections($first: Int!, $after: String) {
  collections(first: $first, after: $after) {
    edges {
      node {
        id
        handle
        title
        description
        descriptionHtml
        updatedAt
        
        image {
          url
          altText
        }
        
        seo {
          title
          description
        }
        
        sortOrder
        templateSuffix
        
        products(first: 250) {
          edges {
            node {
              id
              handle
              title
              status
              vendor
              productType
              tags
            }
          }
          pageInfo {
            hasNextPage
            endCursor
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

# Query to check collection types
COLLECTION_METAFIELDS_QUERY = """
query getCollectionMetafields($id: ID!) {
  collection(id: $id) {
    id
    handle
    metafields(first: 100) {
      edges {
        node {
          id
          namespace
          key
          value
          type
        }
      }
    }
  }
}
"""

class ShopifyCompleteCollectionExporter(ShopifyAPIBase):
    """Exports complete Shopify collection data for recreation."""
    
    def __init__(self, shop_url: str, access_token: str, debug: bool = False):
        """Initialize the exporter."""
        super().__init__(shop_url, access_token, debug)
        self.logger = logging.getLogger(__name__)
        
    def export_collections(self, output_dir: str = "collection_export") -> None:
        """Export all collection data to multiple files."""
        print(f"🚀 Starting complete collection export to: {output_dir}/")
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Export different aspects of collections
        self._export_collection_metadata(os.path.join(output_dir, "collections_metadata.csv"))
        self._export_collection_products(os.path.join(output_dir, "collections_products.csv"))
        self._export_collection_seo(os.path.join(output_dir, "collections_seo.csv"))
        self._export_collection_images(os.path.join(output_dir, "collections_images.csv"))
        self._export_collection_summary(os.path.join(output_dir, "collections_summary.csv"))
        
        # Also export as JSON for complete data preservation
        self._export_collections_json(os.path.join(output_dir, "collections_complete.json"))
        
        print(f"\n✅ Export completed successfully!")
        print(f"📁 Files saved in: {output_dir}/")
        
    def _export_collection_metadata(self, output_file: str) -> None:
        """Export core collection metadata."""
        print("\n📊 Exporting collection metadata...")
        
        fieldnames = [
            'collection_id', 'collection_handle', 'collection_title',
            'description', 'description_html', 'sort_order', 
            'template_suffix', 'products_count', 'updated_at'
        ]
        
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            collections = self._fetch_all_collections()
            
            for collection in collections:
                # Count products
                products_count = len(collection.get('products', {}).get('edges', []))
                
                writer.writerow({
                    'collection_id': collection.get('id'),
                    'collection_handle': collection.get('handle'),
                    'collection_title': collection.get('title'),
                    'description': collection.get('description', ''),
                    'description_html': collection.get('descriptionHtml', ''),
                    'sort_order': collection.get('sortOrder', ''),
                    'template_suffix': collection.get('templateSuffix', ''),
                    'products_count': products_count,
                    'updated_at': collection.get('updatedAt')
                })
        
        print(f"   ✓ Exported metadata for {len(collections)} collections")
        
    def _export_collection_products(self, output_file: str) -> None:
        """Export collection-product relationships with full product details."""
        print("\n📦 Exporting collection products...")
        
        fieldnames = [
            'collection_handle', 'collection_title',
            'product_id', 'product_handle', 'product_title', 
            'product_status', 'vendor', 'product_type', 'tags', 'position'
        ]
        
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            collections = self._fetch_all_collections()
            total_relationships = 0
            
            for collection in collections:
                # Get all products in collection
                products_edges = collection.get('products', {}).get('edges', [])
                
                for position, product_edge in enumerate(products_edges, 1):
                    product = product_edge['node']
                    writer.writerow({
                        'collection_handle': collection.get('handle'),
                        'collection_title': collection.get('title'),
                        'product_id': product.get('id'),
                        'product_handle': product.get('handle'),
                        'product_title': product.get('title'),
                        'product_status': product.get('status'),
                        'vendor': product.get('vendor'),
                        'product_type': product.get('productType'),
                        'tags': ', '.join(product.get('tags', [])),
                        'position': position
                    })
                    total_relationships += 1
        
        print(f"   ✓ Exported {total_relationships} product-collection relationships")
        
    def _export_collection_seo(self, output_file: str) -> None:
        """Export collection SEO data."""
        print("\n🔍 Exporting collection SEO data...")
        
        fieldnames = [
            'collection_handle', 'collection_title',
            'seo_title', 'seo_description', 'url_handle'
        ]
        
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            collections = self._fetch_all_collections()
            
            for collection in collections:
                seo = collection.get('seo', {})
                writer.writerow({
                    'collection_handle': collection.get('handle'),
                    'collection_title': collection.get('title'),
                    'seo_title': seo.get('title', ''),
                    'seo_description': seo.get('description', ''),
                    'url_handle': collection.get('handle')
                })
        
        print(f"   ✓ Exported SEO data for {len(collections)} collections")
        
    def _export_collection_images(self, output_file: str) -> None:
        """Export collection image data."""
        print("\n🖼️  Exporting collection images...")
        
        fieldnames = [
            'collection_handle', 'collection_title',
            'image_url', 'image_alt_text'
        ]
        
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            collections = self._fetch_all_collections()
            images_count = 0
            
            for collection in collections:
                image = collection.get('image', {})
                if image and image.get('url'):
                    writer.writerow({
                        'collection_handle': collection.get('handle'),
                        'collection_title': collection.get('title'),
                        'image_url': image.get('url', ''),
                        'image_alt_text': image.get('altText', '')
                    })
                    images_count += 1
        
        print(f"   ✓ Exported {images_count} collection images")
        
    def _export_collection_summary(self, output_file: str) -> None:
        """Export a summary view with key collection info."""
        print("\n📋 Exporting collection summary...")
        
        fieldnames = [
            'collection_handle', 'collection_title', 'products_count',
            'has_image', 'has_seo', 'has_description', 'sort_order'
        ]
        
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            collections = self._fetch_all_collections()
            
            for collection in collections:
                products_count = len(collection.get('products', {}).get('edges', []))
                image = collection.get('image') or {}
                has_image = bool(image.get('url'))
                seo = collection.get('seo') or {}
                has_seo = bool(seo.get('title') or seo.get('description'))
                has_description = bool(collection.get('description'))
                
                writer.writerow({
                    'collection_handle': collection.get('handle'),
                    'collection_title': collection.get('title'),
                    'products_count': products_count,
                    'has_image': has_image,
                    'has_seo': has_seo,
                    'has_description': has_description,
                    'sort_order': collection.get('sortOrder', '')
                })
        
        print(f"   ✓ Exported summary for {len(collections)} collections")
        
    def _export_collections_json(self, output_file: str) -> None:
        """Export complete collection data as JSON."""
        print("\n💾 Exporting complete collection data as JSON...")
        
        collections = self._fetch_all_collections()
        
        # Clean up GraphQL specific fields
        for collection in collections:
            if 'products' in collection and 'edges' in collection['products']:
                collection['products'] = [
                    edge['node'] for edge in collection['products']['edges']
                ]
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(collections, f, indent=2, ensure_ascii=False)
        
        print(f"   ✓ Exported complete data for {len(collections)} collections")
        
    def _fetch_all_collections(self) -> List[Dict[str, Any]]:
        """Fetch all collections with pagination."""
        collections = []
        has_next_page = True
        cursor = None
        
        while has_next_page:
            variables = {'first': 50}
            if cursor:
                variables['after'] = cursor
                
            result = self.execute_graphql(COMPLETE_COLLECTIONS_QUERY, variables)
            
            if 'errors' in result:
                raise Exception(f"GraphQL errors: {result['errors']}")
                
            collections_data = result.get('data', {}).get('collections', {})
            edges = collections_data.get('edges', [])
            
            for edge in edges:
                collections.append(edge['node'])
                
            page_info = collections_data.get('pageInfo', {})
            has_next_page = page_info.get('hasNextPage', False)
            cursor = page_info.get('endCursor')
            
            print(f"   Fetched {len(collections)} collections so far...")
            
        return collections


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description='Export complete Shopify collection data for recreation'
    )
    parser.add_argument('--shop-url', required=True, help='Shopify store URL')
    parser.add_argument('--access-token', required=True, help='Shopify access token')
    parser.add_argument('--output-dir', default='collection_export', 
                       help='Output directory (default: collection_export)')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # Create exporter and run export
        exporter = ShopifyCompleteCollectionExporter(
            shop_url=args.shop_url,
            access_token=args.access_token,
            debug=args.debug
        )
        
        exporter.export_collections(args.output_dir)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Export interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {str(e)}")
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()