#!/usr/bin/env python3
"""
Add Products to Collections Script

This script adds products to collections using the association CSV generated
by the migration script. It handles both adding products and setting their
position in manual collections.

Usage:
    python add_products_to_collections.py --shop-url store.myshopify.com --access-token TOKEN --associations product_collection_associations.csv
"""

import os
import sys
import csv
import json
import argparse
import logging
import time
from typing import Dict, List, Optional, Any
from collections import defaultdict

try:
    from .shopify_base import ShopifyAPIBase
except ImportError:
    from shopify_base import ShopifyAPIBase

# GraphQL mutations
ADD_PRODUCTS_TO_COLLECTION_MUTATION = """
mutation addProductsToCollection($id: ID!, $productIds: [ID!]!) {
  collectionAddProducts(id: $id, productIds: $productIds) {
    collection {
      id
      handle
      productsCount {
        count
      }
    }
    userErrors {
      field
      message
    }
  }
}
"""

REORDER_PRODUCTS_IN_COLLECTION_MUTATION = """
mutation reorderProductsInCollection($id: ID!, $moves: [MoveInput!]!) {
  collectionReorderProducts(id: $id, moves: $moves) {
    userErrors {
      field
      message
    }
  }
}
"""

GET_PRODUCT_BY_HANDLE_QUERY = """
query getProductByHandle($handle: String!) {
  productByHandle(handle: $handle) {
    id
    handle
    title
  }
}
"""

class ShopifyProductCollectionAssociator(ShopifyAPIBase):
    """Associates products with collections."""
    
    def __init__(self, shop_url: str, access_token: str, debug: bool = False):
        """Initialize the associator."""
        super().__init__(shop_url, access_token, debug)
        self.logger = logging.getLogger(__name__)
        self.product_cache = {}  # handle -> id cache
        
    def add_products_to_collections(self, associations_file: str, batch_size: int = 100) -> None:
        """Add products to collections from association CSV."""
        print(f"🚀 Starting product-collection associations from: {associations_file}")
        
        # Load associations
        associations = self._load_associations(associations_file)
        
        # Group by collection for batch processing
        collections_map = defaultdict(list)
        for assoc in associations:
            collections_map[assoc['collection_id']].append(assoc)
        
        print(f"\n📊 Found {len(associations)} associations across {len(collections_map)} collections")
        
        # Process each collection
        total_collections = len(collections_map)
        processed_collections = 0
        total_added = 0
        total_errors = 0
        
        for collection_id, products in collections_map.items():
            processed_collections += 1
            collection_handle = products[0]['collection_handle']
            
            print(f"\n[{processed_collections}/{total_collections}] Processing collection: {collection_handle}")
            print(f"   📦 Products to add: {len(products)}")
            
            # Get product IDs
            product_ids = []
            positions = {}
            
            for product in products:
                product_id = self._get_product_id(product['product_handle'])
                if product_id:
                    product_ids.append(product_id)
                    if product.get('position'):
                        positions[product_id] = int(product['position'])
                else:
                    total_errors += 1
                    print(f"   ⚠️  Product not found: {product['product_handle']}")
            
            if product_ids:
                # Add products in batches
                for i in range(0, len(product_ids), batch_size):
                    batch = product_ids[i:i + batch_size]
                    success = self._add_products_batch(collection_id, batch)
                    
                    if success:
                        total_added += len(batch)
                        print(f"   ✅ Added batch of {len(batch)} products")
                    else:
                        total_errors += len(batch)
                        print(f"   ❌ Failed to add batch")
                    
                    # Rate limiting
                    time.sleep(0.5)
                
                # Reorder products if positions are specified
                if positions and any(positions.values()):
                    print(f"   🔄 Setting product positions...")
                    self._reorder_products(collection_id, product_ids, positions)
            
            # Progress update
            print(f"   ✅ Completed: {total_added} products added so far")
        
        print(f"\n✅ Association Summary:")
        print(f"   📦 Products added: {total_added}")
        print(f"   ❌ Errors: {total_errors}")
        print(f"   📂 Collections processed: {processed_collections}")
        
    def _load_associations(self, filepath: str) -> List[Dict]:
        """Load association CSV."""
        associations = []
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('collection_id'):  # Skip if no collection ID
                    associations.append(row)
        return associations
    
    def _get_product_id(self, handle: str) -> Optional[str]:
        """Get product ID by handle (with caching)."""
        # Check cache first
        if handle in self.product_cache:
            return self.product_cache[handle]
        
        try:
            result = self.execute_graphql(GET_PRODUCT_BY_HANDLE_QUERY, {'handle': handle})
            
            if 'errors' in result:
                return None
            
            product = result.get('data', {}).get('productByHandle')
            if product:
                product_id = product['id']
                self.product_cache[handle] = product_id
                return product_id
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting product {handle}: {str(e)}")
            return None
    
    def _add_products_batch(self, collection_id: str, product_ids: List[str]) -> bool:
        """Add a batch of products to a collection."""
        try:
            variables = {
                'id': collection_id,
                'productIds': product_ids
            }
            
            result = self.execute_graphql(ADD_PRODUCTS_TO_COLLECTION_MUTATION, variables)
            
            if 'errors' in result:
                self.logger.error(f"GraphQL errors: {result['errors']}")
                return False
            
            add_result = result.get('data', {}).get('collectionAddProducts', {})
            user_errors = add_result.get('userErrors', [])
            
            if user_errors:
                self.logger.error(f"User errors: {user_errors}")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error adding products: {str(e)}")
            return False
    
    def _reorder_products(self, collection_id: str, product_ids: List[str], positions: Dict[str, int]) -> bool:
        """Reorder products in a collection based on positions."""
        try:
            # Create moves list
            moves = []
            for product_id, position in positions.items():
                if product_id in product_ids:
                    # Shopify uses 0-based positioning
                    moves.append({
                        'id': product_id,
                        'newPosition': str(position - 1)  # Convert to 0-based
                    })
            
            if not moves:
                return True
            
            # Sort by position to avoid conflicts
            moves.sort(key=lambda x: int(x['newPosition']))
            
            variables = {
                'id': collection_id,
                'moves': moves
            }
            
            result = self.execute_graphql(REORDER_PRODUCTS_IN_COLLECTION_MUTATION, variables)
            
            if 'errors' in result:
                self.logger.error(f"Reorder errors: {result['errors']}")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error reordering products: {str(e)}")
            return False


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description='Add products to Shopify collections'
    )
    parser.add_argument('--shop-url', required=True, help='Shopify store URL')
    parser.add_argument('--access-token', required=True, help='Shopify access token')
    parser.add_argument('--associations', default='product_collection_associations.csv',
                       help='CSV file with product-collection associations')
    parser.add_argument('--batch-size', type=int, default=100,
                       help='Number of products to add per batch (default: 100)')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # Create associator and run
        associator = ShopifyProductCollectionAssociator(
            shop_url=args.shop_url,
            access_token=args.access_token,
            debug=args.debug
        )
        
        associator.add_products_to_collections(args.associations, args.batch_size)
        
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