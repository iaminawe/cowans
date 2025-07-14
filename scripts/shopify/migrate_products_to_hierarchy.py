#!/usr/bin/env python3
"""
Migrate Products to New Collection Hierarchy

This script migrates products from old collections to the new 3-level hierarchy:
- Maps products from old collections to appropriate new collections
- Handles products that need to be in multiple collections
- Preserves existing product-collection relationships where appropriate

Usage:
    python migrate_products_to_hierarchy.py --shop-url YOUR_SHOP --access-token YOUR_TOKEN
"""

import os
import sys
import csv
import json
import argparse
import logging
import time
from typing import Dict, List, Optional, Any, Set
from datetime import datetime
from collections import defaultdict

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from scripts.shopify.shopify_base import ShopifyAPIBase
except ImportError:
    from shopify_base import ShopifyAPIBase

# Configure logging
logger = logging.getLogger(__name__)

# GraphQL Queries and Mutations

GET_ALL_PRODUCTS_QUERY = """
query getAllProducts($first: Int!, $after: String) {
  products(first: $first, after: $after) {
    edges {
      node {
        id
        handle
        title
        productType
        tags
        status
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

GET_COLLECTION_PRODUCTS_QUERY = """
query getCollectionProducts($handle: String!, $first: Int!, $after: String) {
  collectionByHandle(handle: $handle) {
    id
    handle
    title
    products(first: $first, after: $after) {
      edges {
        node {
          id
          handle
          title
          productType
          tags
        }
        cursor
      }
      pageInfo {
        hasNextPage
        endCursor
      }
    }
  }
}
"""

ADD_PRODUCTS_TO_COLLECTION_MUTATION = """
mutation addProductsToCollection($id: ID!, $productIds: [ID!]!) {
  collectionAddProducts(id: $id, productIds: $productIds) {
    collection {
      id
      handle
      title
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

REMOVE_PRODUCTS_FROM_COLLECTION_MUTATION = """
mutation removeProductsFromCollection($id: ID!, $productIds: [ID!]!) {
  collectionRemoveProducts(id: $id, productIds: $productIds) {
    collection {
      id
      handle
      title
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

class ProductHierarchyMigrator(ShopifyAPIBase):
    """Manages product migration to new collection hierarchy."""
    
    def __init__(self, shop_url: str, access_token: str, debug: bool = False):
        """Initialize the migrator."""
        super().__init__(shop_url, access_token, debug)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.old_to_new_mapping = {}  # old_handle -> [new_handles]
        self.product_types_to_collections = {}  # product_type -> [collection_handles]
        
    def load_hierarchy_mapping(self, hierarchy_file: str) -> None:
        """Load hierarchy data and create mappings."""
        print(f"📥 Loading hierarchy mappings from: {hierarchy_file}")
        
        # Define manual mappings for common cases
        self.old_to_new_mapping = {
            # Art Supplies mappings
            'acrylic-paints': ['acrylic-paints'],
            'acrylic-mediums': ['acrylic-paints'],
            'oil-paints': ['oil-specialty-paints'],
            'watercolour-paints': ['watercolor-supplies'],
            'watercolour-tubes': ['watercolor-supplies'],
            'wet-media': ['watercolor-supplies'],
            
            # Drawing mappings
            'graphite': ['pencils-charcoal'],
            'coloured-pencils': ['pencils-charcoal'],
            'drawing-tools': ['drawing-tools'],
            'markers': ['markers-art-pens'],
            'pen-ink': ['markers-art-pens'],
            
            # Canvas mappings
            'stretched-canvas': ['stretched-canvas'],
            'canvas-boards': ['canvas-rolls-boards'],
            'birch-boards': ['canvas-rolls-boards'],
            
            # Brushes and tools
            'brush-sets': ['paint-tools-accessories'],
            'brush-sets-synthetic': ['paint-tools-accessories'],
            'oil-acrylic-synthetic-filbert-brushes': ['paint-tools-accessories'],
            'watercolour-natural-mop-brushes': ['paint-tools-accessories'],
            'palette-knives': ['paint-tools-accessories'],
            'painting-tools': ['paint-tools-accessories'],
            
            # Kids/Crafts
            'kids-activity': ['school-kids-crafts'],
            'kids-markers': ['school-kids-crafts'],
            'kids-paints': ['school-kids-crafts'],
            'kids-pencils-crayons': ['school-kids-crafts'],
            'crafts': ['general-crafting'],
            
            # Office supplies
            'office-stuff': ['office-supplies'],  # General mapping
        }
        
        # Load product type mappings from hierarchy
        with open(hierarchy_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                product_types = row.get('product_types_included', '').split(',')
                collection_l3 = row.get('collection_handle_l3', '')
                
                if collection_l3:
                    for product_type in product_types:
                        pt = product_type.strip()
                        if pt:
                            if pt not in self.product_types_to_collections:
                                self.product_types_to_collections[pt] = []
                            self.product_types_to_collections[pt].append(collection_l3)
        
        print(f"✅ Loaded {len(self.old_to_new_mapping)} direct mappings")
        print(f"✅ Loaded {len(self.product_types_to_collections)} product type mappings")
    
    def get_collection_products(self, handle: str) -> List[Dict[str, Any]]:
        """Get all products from a collection."""
        products = []
        cursor = None
        
        while True:
            variables = {
                "handle": handle,
                "first": 250,
                "after": cursor
            }
            
            result = self.execute_graphql(GET_COLLECTION_PRODUCTS_QUERY, variables)
            
            if 'errors' in result:
                self.logger.error(f"GraphQL errors: {result['errors']}")
                break
            
            collection = result.get('data', {}).get('collectionByHandle')
            if not collection:
                self.logger.warning(f"Collection not found: {handle}")
                break
            
            edges = collection.get('products', {}).get('edges', [])
            page_info = collection.get('products', {}).get('pageInfo', {})
            
            for edge in edges:
                products.append(edge['node'])
            
            if not page_info.get('hasNextPage'):
                break
                
            cursor = page_info.get('endCursor')
        
        return products
    
    def get_all_products(self) -> List[Dict[str, Any]]:
        """Get all products from the store, including drafts."""
        products = []
        cursor = None
        
        print("📦 Fetching all products (including drafts)...")
        
        while True:
            variables = {
                "first": 250,
                "after": cursor
            }
            
            result = self.execute_graphql(GET_ALL_PRODUCTS_QUERY, variables)
            
            if 'errors' in result:
                self.logger.error(f"GraphQL errors: {result['errors']}")
                break
            
            products_data = result.get('data', {}).get('products', {})
            edges = products_data.get('edges', [])
            page_info = products_data.get('pageInfo', {})
            
            for edge in edges:
                products.append(edge['node'])
            
            if not page_info.get('hasNextPage'):
                break
                
            cursor = page_info.get('endCursor')
            
            # Progress indicator
            if len(products) % 500 == 0:
                print(f"   Fetched {len(products)} products...")
        
        print(f"✅ Found {len(products)} total products")
        return products
    
    def determine_new_collections(self, product: Dict[str, Any], old_collection_handle: str = None) -> List[str]:
        """Determine which new collections a product should belong to."""
        new_collections = set()
        
        # 1. Check direct mapping from old collection
        if old_collection_handle in self.old_to_new_mapping:
            new_collections.update(self.old_to_new_mapping[old_collection_handle])
        
        # 2. Check product type mapping
        product_type = product.get('productType', '')
        if product_type in self.product_types_to_collections:
            new_collections.update(self.product_types_to_collections[product_type])
        
        # 3. Check tags for additional hints
        tags = product.get('tags', [])
        for tag in tags:
            tag_lower = tag.lower()
            # Map common tags to collections
            if 'acrylic' in tag_lower:
                new_collections.add('acrylic-paints')
            elif 'watercolor' in tag_lower or 'watercolour' in tag_lower:
                new_collections.add('watercolor-supplies')
            elif 'oil paint' in tag_lower:
                new_collections.add('oil-specialty-paints')
            elif 'marker' in tag_lower:
                new_collections.add('markers-art-pens')
            elif 'pencil' in tag_lower:
                new_collections.add('pencils-charcoal')
            elif 'canvas' in tag_lower:
                new_collections.add('stretched-canvas')
            elif 'brush' in tag_lower:
                new_collections.add('paint-tools-accessories')
        
        return list(new_collections)
    
    def migrate_products(self, old_collections_file: str = None) -> None:
        """Migrate products from old collections to new hierarchy."""
        print("\n🔄 Starting product migration to new hierarchy...")
        
        # Load old collections list
        old_collections = []
        if old_collections_file and os.path.exists(old_collections_file):
            with open(old_collections_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    old_collections.append(row['collection_handle'])
        else:
            # Use default list of known old collections
            old_collections = list(self.old_to_new_mapping.keys())
        
        # Track migration stats
        stats = {
            'total_products': 0,
            'migrated': 0,
            'errors': 0,
            'collections_processed': 0
        }
        
        # Track products and their new collections
        product_migrations = defaultdict(set)  # product_id -> set of new collection handles
        
        # Process each old collection
        for old_handle in old_collections:
            print(f"\n📦 Processing collection: {old_handle}")
            stats['collections_processed'] += 1
            
            # Get products from old collection
            products = self.get_collection_products(old_handle)
            stats['total_products'] += len(products)
            
            print(f"   Found {len(products)} products")
            
            # Determine new collections for each product
            for product in products:
                new_collections = self.determine_new_collections(product, old_handle)
                
                if new_collections:
                    product_id = product['id']
                    product_migrations[product_id].update(new_collections)
                    print(f"   - {product['title'][:50]}... → {', '.join(new_collections)}")
                else:
                    print(f"   - {product['title'][:50]}... → ⚠️  No mapping found")
            
            time.sleep(0.5)  # Rate limiting
        
        # Apply migrations
        print("\n📤 Applying product migrations...")
        
        # Group by target collection for efficiency
        collection_products = defaultdict(list)  # collection_handle -> [product_ids]
        
        for product_id, collection_handles in product_migrations.items():
            for handle in collection_handles:
                collection_products[handle].append(product_id)
        
        # Add products to new collections
        for collection_handle, product_ids in collection_products.items():
            print(f"\n📁 Adding {len(product_ids)} products to: {collection_handle}")
            
            # First, get the collection ID
            collection_data = self._get_collection_by_handle(collection_handle)
            if not collection_data:
                print(f"   ❌ Collection not found: {collection_handle}")
                stats['errors'] += len(product_ids)
                continue
            
            # Add products in batches of 20 to avoid API errors
            for i in range(0, len(product_ids), 20):
                batch = product_ids[i:i+20]
                
                try:
                    result = self.execute_graphql(
                        ADD_PRODUCTS_TO_COLLECTION_MUTATION,
                        {
                            'id': collection_data['id'],
                            'productIds': batch
                        }
                    )
                    
                    if 'errors' in result:
                        self.logger.error(f"GraphQL errors: {result['errors']}")
                        stats['errors'] += len(batch)
                    else:
                        collection_result = result.get('data', {}).get('collectionAddProducts', {})
                        user_errors = collection_result.get('userErrors', [])
                        
                        if user_errors:
                            self.logger.error(f"User errors: {user_errors}")
                            stats['errors'] += len(batch)
                        else:
                            stats['migrated'] += len(batch)
                            print(f"   ✅ Added batch of {len(batch)} products")
                    
                except Exception as e:
                    self.logger.error(f"Error adding products: {str(e)}")
                    stats['errors'] += len(batch)
                
                time.sleep(0.5)  # Rate limiting
        
        # Print summary
        print("\n📊 Migration Summary:")
        print(f"   📦 Collections processed: {stats['collections_processed']}")
        print(f"   📄 Total products found: {stats['total_products']}")
        print(f"   ✅ Products migrated: {stats['migrated']}")
        print(f"   ❌ Errors: {stats['errors']}")
        
        # Save migration report
        self._save_migration_report(product_migrations, stats)
    
    def migrate_all_products(self) -> None:
        """Migrate ALL products (including drafts) to new hierarchy based on product types."""
        print("\n🔄 Starting migration of ALL products to new hierarchy...")\n        \n        # Get all products from the store\n        all_products = self.get_all_products()\n        \n        # Track migration stats\n        stats = {\n            'total_products': len(all_products),\n            'migrated': 0,\n            'errors': 0,\n            'no_mapping': 0,\n            'draft_products': 0\n        }\n        \n        # Track products and their new collections\n        product_migrations = defaultdict(set)  # product_id -> set of new collection handles\n        \n        print(f\"\\n📋 Processing {len(all_products)} products...\")\n        \n        # Process each product\n        for i, product in enumerate(all_products):\n            if i % 100 == 0:\n                print(f\"   Progress: {i}/{len(all_products)} ({i/len(all_products)*100:.1f}%)\")\n            \n            # Track draft products\n            if product.get('status') == 'DRAFT':\n                stats['draft_products'] += 1\n            \n            # Determine new collections for this product\n            new_collections = self.determine_new_collections(product)\n            \n            if new_collections:\n                product_id = product['id']\n                product_migrations[product_id].update(new_collections)\n                if i < 10:  # Show first 10 for debugging\n                    print(f\"   - {product['title'][:50]}... → {', '.join(new_collections)}\")\n            else:\n                stats['no_mapping'] += 1\n                if i < 10:  # Show first 10 for debugging\n                    print(f\"   - {product['title'][:50]}... → ⚠️  No mapping found\")\n        \n        print(f\"\\n📊 Product Analysis:\")\n        print(f\"   📄 Total products: {stats['total_products']}\")\n        print(f\"   📝 Draft products: {stats['draft_products']}\")\n        print(f\"   ✅ Products with mappings: {len(product_migrations)}\")\n        print(f\"   ❌ Products without mappings: {stats['no_mapping']}\")\n        \n        # Apply migrations\n        print(\"\\n📤 Applying product migrations...\")\n        \n        # Group by target collection for efficiency\n        collection_products = defaultdict(list)  # collection_handle -> [product_ids]\n        \n        for product_id, collection_handles in product_migrations.items():\n            for handle in collection_handles:\n                collection_products[handle].append(product_id)\n        \n        # Add products to new collections\n        for collection_handle, product_ids in collection_products.items():\n            print(f\"\\n📁 Adding {len(product_ids)} products to: {collection_handle}\")\n            \n            # First, get the collection ID\n            collection_data = self._get_collection_by_handle(collection_handle)\n            if not collection_data:\n                print(f\"   ❌ Collection not found: {collection_handle}\")\n                stats['errors'] += len(product_ids)\n                continue\n            \n            # Add products in batches of 10 to be more conservative\n            for i in range(0, len(product_ids), 10):\n                batch = product_ids[i:i+10]\n                \n                try:\n                    result = self.execute_graphql(\n                        ADD_PRODUCTS_TO_COLLECTION_MUTATION,\n                        {\n                            'id': collection_data['id'],\n                            'productIds': batch\n                        }\n                    )\n                    \n                    if 'errors' in result:\n                        print(f\"   ❌ GraphQL errors: {result['errors']}\")\n                        stats['errors'] += len(batch)\n                    else:\n                        collection_result = result.get('data', {}).get('collectionAddProducts', {})\n                        user_errors = collection_result.get('userErrors', [])\n                        \n                        if user_errors:\n                            print(f\"   ❌ User errors: {user_errors}\")\n                            stats['errors'] += len(batch)\n                        else:\n                            stats['migrated'] += len(batch)\n                            print(f\"   ✅ Added batch of {len(batch)} products\")\n                    \n                except Exception as e:\n                    print(f\"   ❌ Error adding products {batch}: {str(e)}\")\n                    stats['errors'] += len(batch)\n                \n                time.sleep(0.8)  # More conservative rate limiting\n        \n        # Print summary\n        print(\"\\n📊 Migration Summary:\")\n        print(f\"   📄 Total products processed: {stats['total_products']}\")\n        print(f\"   📝 Draft products included: {stats['draft_products']}\")\n        print(f\"   ✅ Products migrated: {stats['migrated']}\")\n        print(f\"   ❌ Products without mapping: {stats['no_mapping']}\")\n        print(f\"   💥 Migration errors: {stats['errors']}\")\n        \n        # Save migration report\n        self._save_migration_report(product_migrations, stats)\n    
    def _get_collection_by_handle(self, handle: str) -> Optional[Dict[str, Any]]:
        """Get collection data by handle."""
        query = """
        query getCollection($handle: String!) {
          collectionByHandle(handle: $handle) {
            id
            handle
            title
          }
        }
        """
        
        try:
            result = self.execute_graphql(query, {'handle': handle})
            return result.get('data', {}).get('collectionByHandle')
        except Exception as e:
            self.logger.error(f"Error getting collection {handle}: {str(e)}")
            return None
    
    def _save_migration_report(self, product_migrations: Dict[str, Set[str]], stats: Dict[str, int]) -> None:
        """Save migration report for reference."""
        report = {
            'timestamp': datetime.utcnow().isoformat(),
            'stats': stats,
            'product_migrations': {
                product_id: list(collections)
                for product_id, collections in product_migrations.items()
            }
        }
        
        with open('product_migration_report.json', 'w') as f:
            json.dump(report, f, indent=2)
        
        print("\n💾 Migration report saved to: product_migration_report.json")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description='Migrate products to new collection hierarchy'
    )
    parser.add_argument('--shop-url', required=True, help='Shopify store URL')
    parser.add_argument('--access-token', required=True, help='Shopify access token')
    parser.add_argument('--hierarchy-file', default='collection_hierarchy_3_levels.csv', 
                       help='Path to hierarchy CSV file')
    parser.add_argument('--old-collections', help='CSV file with old collection handles')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # Create migrator
        migrator = ProductHierarchyMigrator(
            shop_url=args.shop_url,
            access_token=args.access_token,
            debug=args.debug
        )
        
        # Test authentication
        migrator.test_auth()
        
        # Load hierarchy mapping
        migrator.load_hierarchy_mapping(args.hierarchy_file)
        
        # Run migration
        confirm = input("\n⚠️  Ready to migrate products. Continue? (yes/no): ")
        if confirm.lower() == 'yes':
            migrator.migrate_products(args.old_collections)
        else:
            print("❌ Operation cancelled")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Migration interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {str(e)}")
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()