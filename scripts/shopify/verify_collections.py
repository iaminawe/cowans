#!/usr/bin/env python3
"""
Verify Collections and Product Associations

This script checks which collections have products and reports on the status.

Usage:
    python verify_collections.py --shop-url store.myshopify.com --access-token TOKEN
"""

import os
import sys
import argparse
import logging
import json
from typing import Dict, List

try:
    from .shopify_base import ShopifyAPIBase
except ImportError:
    from shopify_base import ShopifyAPIBase

# Query to get collections with product counts
GET_COLLECTIONS_WITH_COUNTS_QUERY = """
query getCollectionsWithCounts($first: Int!, $after: String) {
  collections(first: $first, after: $after) {
    edges {
      node {
        id
        handle
        title
        productsCount {
          count
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

class CollectionVerifier(ShopifyAPIBase):
    """Verifies collection product associations."""
    
    def __init__(self, shop_url: str, access_token: str, debug: bool = False):
        """Initialize the verifier."""
        super().__init__(shop_url, access_token, debug)
        self.logger = logging.getLogger(__name__)
        
    def verify_collections(self) -> None:
        """Verify all collections and their product counts."""
        print(f"🔍 Verifying collections and product associations...")
        
        # Get all collections
        collections = self._fetch_all_collections()
        
        # Load expected associations
        expected_counts = {}
        if os.path.exists('product_collection_associations.csv'):
            with open('product_collection_associations.csv', 'r') as f:
                next(f)  # Skip header
                for line in f:
                    if line.strip():
                        parts = line.strip().split(',')
                        if len(parts) >= 2:
                            collection_handle = parts[1]
                            expected_counts[collection_handle] = expected_counts.get(collection_handle, 0) + 1
        
        print(f"\n📊 Collection Status Report:")
        print(f"{'Handle':<30} {'Title':<30} {'Expected':<10} {'Actual':<10} {'Status'}")
        print("=" * 90)
        
        total_collections = len(collections)
        collections_with_products = 0
        total_expected = 0
        total_actual = 0
        
        for collection in sorted(collections, key=lambda x: x['handle']):
            handle = collection['handle']
            title = collection['title'][:28]
            actual_count = collection['productsCount']['count']
            expected_count = expected_counts.get(handle, 0)
            
            if actual_count > 0:
                collections_with_products += 1
            
            total_expected += expected_count
            total_actual += actual_count
            
            # Status
            if expected_count == 0 and actual_count == 0:
                status = "✓ No products expected"
            elif expected_count > 0 and actual_count == expected_count:
                status = "✅ Complete"
            elif expected_count > 0 and actual_count > 0 and actual_count != expected_count:
                status = f"⚠️  Partial ({actual_count}/{expected_count})"
            elif expected_count > 0 and actual_count == 0:
                status = "❌ Missing products"
            else:
                status = "🔍 Extra products"
            
            print(f"{handle:<30} {title:<30} {expected_count:<10} {actual_count:<10} {status}")
        
        print("=" * 90)
        print(f"Summary:")
        print(f"  Total collections: {total_collections}")
        print(f"  Collections with products: {collections_with_products}")
        print(f"  Expected product associations: {total_expected}")
        print(f"  Actual product associations: {total_actual}")
        print(f"  Completion rate: {(total_actual/total_expected*100) if total_expected > 0 else 0:.1f}%")
        
        # Find collections that need attention
        needs_attention = []
        for collection in collections:
            handle = collection['handle']
            actual_count = collection['productsCount']['count']
            expected_count = expected_counts.get(handle, 0)
            
            if expected_count > 0 and actual_count < expected_count:
                needs_attention.append((handle, expected_count, actual_count))
        
        if needs_attention:
            print(f"\n⚠️  Collections needing attention:")
            for handle, expected, actual in needs_attention[:10]:
                print(f"  {handle}: Expected {expected}, has {actual}")
            if len(needs_attention) > 10:
                print(f"  ... and {len(needs_attention) - 10} more")
    
    def _fetch_all_collections(self) -> List[Dict]:
        """Fetch all collections with product counts."""
        collections = []
        has_next_page = True
        cursor = None
        
        while has_next_page:
            variables = {'first': 250}
            if cursor:
                variables['after'] = cursor
            
            result = self.execute_graphql(GET_COLLECTIONS_WITH_COUNTS_QUERY, variables)
            
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
        description='Verify collection product associations'
    )
    parser.add_argument('--shop-url', required=True, help='Shopify store URL')
    parser.add_argument('--access-token', required=True, help='Shopify access token')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # Create verifier and run
        verifier = CollectionVerifier(
            shop_url=args.shop_url,
            access_token=args.access_token,
            debug=args.debug
        )
        
        verifier.verify_collections()
        
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