#!/usr/bin/env python3
"""
Fix Missing Collection Associations

This script identifies and fixes collections that are missing products.

Usage:
    python fix_missing_associations.py --shop-url store.myshopify.com --access-token TOKEN
"""

import os
import sys
import csv
import argparse
import logging
import time
from typing import Dict, List, Optional

try:
    from .shopify_base import ShopifyAPIBase
except ImportError:
    from shopify_base import ShopifyAPIBase

# Query to check if a product exists
CHECK_PRODUCT_QUERY = """
query checkProduct($handle: String!) {
  productByHandle(handle: $handle) {
    id
    handle
    title
  }
}
"""

# Mutation to add products to collection
ADD_PRODUCTS_MUTATION = """
mutation addProductsToCollection($id: ID!, $productIds: [ID!]!) {
  collectionAddProducts(id: $id, productIds: $productIds) {
    collection {
      id
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

class AssociationFixer(ShopifyAPIBase):
    """Fixes missing product-collection associations."""
    
    def __init__(self, shop_url: str, access_token: str, debug: bool = False):
        """Initialize the fixer."""
        super().__init__(shop_url, access_token, debug)
        self.logger = logging.getLogger(__name__)
        
    def fix_missing_associations(self, target_collections: List[str] = None) -> None:
        """Fix missing associations for specified collections."""
        # Load associations
        associations = self._load_associations()
        
        # Group by collection
        collections_map = {}
        for assoc in associations:
            handle = assoc['collection_handle']
            if target_collections is None or handle in target_collections:
                if handle not in collections_map:
                    collections_map[handle] = []
                collections_map[handle].append(assoc)
        
        print(f"🔧 Fixing associations for {len(collections_map)} collections...")
        
        for idx, (collection_handle, products) in enumerate(collections_map.items(), 1):
            print(f"\n[{idx}/{len(collections_map)}] {collection_handle}")
            print(f"   Expected products: {len(products)}")
            
            # Check which products exist
            existing_products = []
            missing_products = []
            
            for product in products:
                product_handle = product['product_handle']
                if self._product_exists(product_handle):
                    existing_products.append(product)
                else:
                    missing_products.append(product_handle)
            
            print(f"   Existing products: {len(existing_products)}")
            if missing_products:
                print(f"   Missing products: {len(missing_products)}")
                if len(missing_products) <= 5:
                    for handle in missing_products:
                        print(f"     - {handle}")
                else:
                    for handle in missing_products[:3]:
                        print(f"     - {handle}")
                    print(f"     ... and {len(missing_products) - 3} more")
            
            # Add existing products to collection
            if existing_products:
                collection_id = existing_products[0]['collection_id']
                product_ids = [self._get_product_id(p['product_handle']) for p in existing_products]
                product_ids = [pid for pid in product_ids if pid]  # Filter out None values
                
                if product_ids:
                    success = self._add_products_to_collection(collection_id, product_ids)
                    if success:
                        print(f"   ✅ Added {len(product_ids)} products")
                    else:
                        print(f"   ❌ Failed to add products")
                        
                    time.sleep(1)  # Rate limiting
            
    def _load_associations(self) -> List[Dict]:
        """Load product-collection associations."""
        associations = []
        with open('product_collection_associations.csv', 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                associations.append(row)
        return associations
    
    def _product_exists(self, handle: str) -> bool:
        """Check if a product exists."""
        try:
            result = self.execute_graphql(CHECK_PRODUCT_QUERY, {'handle': handle})
            return result.get('data', {}).get('productByHandle') is not None
        except:
            return False
    
    def _get_product_id(self, handle: str) -> Optional[str]:
        """Get product ID by handle."""
        try:
            result = self.execute_graphql(CHECK_PRODUCT_QUERY, {'handle': handle})
            product = result.get('data', {}).get('productByHandle')
            return product['id'] if product else None
        except:
            return None
    
    def _add_products_to_collection(self, collection_id: str, product_ids: List[str]) -> bool:
        """Add products to collection."""
        try:
            # Add one by one to avoid API limits and identify which products are problematic
            success_count = 0
            for product_id in product_ids:
                result = self.execute_graphql(ADD_PRODUCTS_MUTATION, {
                    'id': collection_id,
                    'productIds': [product_id]
                })
                
                if 'errors' in result:
                    self.logger.error(f"GraphQL errors for {product_id}: {result['errors']}")
                    continue
                
                add_result = result.get('data', {}).get('collectionAddProducts', {})
                user_errors = add_result.get('userErrors', [])
                
                if user_errors:
                    # Check if it's a duplicate error (product already in collection)
                    error_msg = user_errors[0].get('message', '')
                    if 'already' in error_msg.lower():
                        self.logger.debug(f"Product {product_id} already in collection")
                        success_count += 1
                    else:
                        self.logger.warning(f"Failed to add {product_id}: {error_msg}")
                else:
                    success_count += 1
                
                time.sleep(0.2)  # Rate limit between products
            
            return success_count > 0
            
        except Exception as e:
            self.logger.error(f"Error adding products: {str(e)}")
            return False


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description='Fix missing product-collection associations'
    )
    parser.add_argument('--shop-url', required=True, help='Shopify store URL')
    parser.add_argument('--access-token', required=True, help='Shopify access token')
    parser.add_argument('--collections', nargs='*', help='Specific collections to fix')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # Create fixer and run
        fixer = AssociationFixer(
            shop_url=args.shop_url,
            access_token=args.access_token,
            debug=args.debug
        )
        
        fixer.fix_missing_associations(args.collections)
        
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