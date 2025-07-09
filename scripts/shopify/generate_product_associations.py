#!/usr/bin/env python3
"""
Generate Product Collection Associations

This script generates the product_collection_associations.csv file
from the exported data and existing collections on the new store.

Usage:
    python generate_product_associations.py --shop-url store.myshopify.com --access-token TOKEN --input-dir old_shopify_complete_collections
"""

import os
import sys
import csv
import json
import argparse
import logging
from typing import Dict, List

try:
    from .shopify_base import ShopifyAPIBase
except ImportError:
    from shopify_base import ShopifyAPIBase

# Query to get all collections
GET_ALL_COLLECTIONS_QUERY = """
query getCollections($first: Int!, $after: String) {
  collections(first: $first, after: $after) {
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

class ProductAssociationGenerator(ShopifyAPIBase):
    """Generates product-collection association file."""
    
    def __init__(self, shop_url: str, access_token: str, debug: bool = False):
        """Initialize the generator."""
        super().__init__(shop_url, access_token, debug)
        self.logger = logging.getLogger(__name__)
        
    def generate_associations(self, input_dir: str) -> None:
        """Generate product association CSV from existing data."""
        print(f"📄 Generating product-collection associations...")
        
        # First, get all collections from the new store
        print("🔍 Fetching collections from new store...")
        collections = self._fetch_all_collections()
        
        # Create handle to ID mapping
        collection_mapping = {c['handle']: c['id'] for c in collections}
        
        # Save mapping
        with open('collection_mapping.json', 'w') as f:
            json.dump(collection_mapping, f, indent=2)
        print(f"   ✅ Found {len(collections)} collections")
        print(f"   💾 Saved collection_mapping.json")
        
        # Load product-collection relationships from export
        products_file = os.path.join(input_dir, "collections_products.csv")
        if not os.path.exists(products_file):
            print(f"❌ Error: {products_file} not found!")
            return
        
        # Read and process relationships
        associations = []
        missing_collections = set()
        
        with open(products_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                collection_handle = row['collection_handle']
                
                # Check if collection exists in new store
                if collection_handle in collection_mapping:
                    associations.append({
                        'product_handle': row['product_handle'],
                        'collection_handle': collection_handle,
                        'collection_id': collection_mapping[collection_handle],
                        'position': row.get('position', '')
                    })
                else:
                    missing_collections.add(collection_handle)
        
        # Write associations file
        with open('product_collection_associations.csv', 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['product_handle', 'collection_handle', 'collection_id', 'position'])
            writer.writeheader()
            writer.writerows(associations)
        
        print(f"\n✅ Generated product_collection_associations.csv")
        print(f"   📊 Total associations: {len(associations)}")
        print(f"   ⚠️  Missing collections: {len(missing_collections)}")
        
        if missing_collections:
            print(f"\n⚠️  Collections not found in new store:")
            for handle in sorted(missing_collections)[:10]:
                print(f"   - {handle}")
            if len(missing_collections) > 10:
                print(f"   ... and {len(missing_collections) - 10} more")
    
    def _fetch_all_collections(self) -> List[Dict]:
        """Fetch all collections from the store."""
        collections = []
        has_next_page = True
        cursor = None
        
        while has_next_page:
            variables = {'first': 250}
            if cursor:
                variables['after'] = cursor
            
            result = self.execute_graphql(GET_ALL_COLLECTIONS_QUERY, variables)
            
            if 'errors' in result:
                raise Exception(f"GraphQL errors: {result['errors']}")
            
            data = result.get('data', {}).get('collections', {})
            edges = data.get('edges', [])
            
            for edge in edges:
                collections.append(edge['node'])
            
            page_info = data.get('pageInfo', {})
            has_next_page = page_info.get('hasNextPage', False)
            cursor = page_info.get('endCursor')
        
        return collections


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description='Generate product-collection associations file'
    )
    parser.add_argument('--shop-url', required=True, help='Shopify store URL')
    parser.add_argument('--access-token', required=True, help='Shopify access token')
    parser.add_argument('--input-dir', required=True, help='Directory with exported data')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # Create generator and run
        generator = ProductAssociationGenerator(
            shop_url=args.shop_url,
            access_token=args.access_token,
            debug=args.debug
        )
        
        generator.generate_associations(args.input_dir)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Process interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {str(e)}")
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()