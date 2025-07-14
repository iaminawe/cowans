#!/usr/bin/env python3
"""
Clean migration script for ALL products including drafts
"""
import os
import sys
import csv
import json
import time
from typing import Dict, List, Any
from collections import defaultdict

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.shopify.shopify_base import ShopifyAPIBase

# GraphQL Queries
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

GET_COLLECTION_BY_HANDLE_QUERY = """
query getCollection($handle: String!) {
  collectionByHandle(handle: $handle) {
    id
    handle
    title
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

class AllProductsMigrator(ShopifyAPIBase):
    """Migrates ALL products to new hierarchy."""
    
    def __init__(self, shop_url: str, access_token: str):
        super().__init__(shop_url, access_token)
        self.product_types_to_collections = {}
        
    def load_hierarchy_mapping(self, hierarchy_file: str):
        """Load product type mappings from hierarchy CSV."""
        print(f"📥 Loading hierarchy mappings from: {hierarchy_file}")
        
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
        
        print(f"✅ Loaded {len(self.product_types_to_collections)} product type mappings")
    
    def get_all_products(self):
        """Get all products including drafts."""
        products = []
        cursor = None
        
        print("📦 Fetching all products (including drafts)...")
        
        while True:
            variables = {"first": 250, "after": cursor}
            result = self.execute_graphql(GET_ALL_PRODUCTS_QUERY, variables)
            
            if 'errors' in result:
                print(f"❌ GraphQL errors: {result['errors']}")
                break
            
            products_data = result.get('data', {}).get('products', {})
            edges = products_data.get('edges', [])
            page_info = products_data.get('pageInfo', {})
            
            for edge in edges:
                products.append(edge['node'])
            
            if not page_info.get('hasNextPage'):
                break
                
            cursor = page_info.get('endCursor')
            
            if len(products) % 500 == 0:
                print(f"   Fetched {len(products)} products...")
        
        print(f"✅ Found {len(products)} total products")
        return products
    
    def determine_new_collections(self, product):
        """Determine which collections a product should belong to."""
        new_collections = set()
        
        # Check product type mapping
        product_type = product.get('productType', '')
        if product_type in self.product_types_to_collections:
            new_collections.update(self.product_types_to_collections[product_type])
        
        # Check tags for additional hints
        tags = product.get('tags', [])
        for tag in tags:
            tag_lower = tag.lower()
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
    
    def get_collection_by_handle(self, handle):
        """Get collection data by handle."""
        try:
            result = self.execute_graphql(GET_COLLECTION_BY_HANDLE_QUERY, {'handle': handle})
            return result.get('data', {}).get('collectionByHandle')
        except Exception as e:
            print(f"❌ Error getting collection {handle}: {e}")
            return None
    
    def migrate_all_products(self):
        """Migrate ALL products to new hierarchy."""
        print("\n🔄 Starting migration of ALL products to new hierarchy...")
        
        # Get all products
        all_products = self.get_all_products()
        
        stats = {
            'total_products': len(all_products),
            'migrated': 0,
            'errors': 0,
            'no_mapping': 0,
            'draft_products': 0
        }
        
        product_migrations = defaultdict(set)
        
        print(f"\n📋 Processing {len(all_products)} products...")
        
        # Process each product
        for i, product in enumerate(all_products):
            if i % 100 == 0:
                print(f"   Progress: {i}/{len(all_products)} ({i/len(all_products)*100:.1f}%)")
            
            if product.get('status') == 'DRAFT':
                stats['draft_products'] += 1
            
            new_collections = self.determine_new_collections(product)
            
            if new_collections:
                product_id = product['id']
                product_migrations[product_id].update(new_collections)
                if i < 10:
                    print(f"   - {product['title'][:50]}... → {', '.join(new_collections)}")
            else:
                stats['no_mapping'] += 1
                if i < 10:
                    print(f"   - {product['title'][:50]}... → ⚠️  No mapping found")
        
        print(f"\n📊 Product Analysis:")
        print(f"   📄 Total products: {stats['total_products']}")
        print(f"   📝 Draft products: {stats['draft_products']}")
        print(f"   ✅ Products with mappings: {len(product_migrations)}")
        print(f"   ❌ Products without mappings: {stats['no_mapping']}")
        
        # Apply migrations
        print("\n📤 Applying product migrations...")
        
        collection_products = defaultdict(list)
        for product_id, collection_handles in product_migrations.items():
            for handle in collection_handles:
                collection_products[handle].append(product_id)
        
        # Add products to collections
        for collection_handle, product_ids in collection_products.items():
            print(f"\n📁 Adding {len(product_ids)} products to: {collection_handle}")
            
            collection_data = self.get_collection_by_handle(collection_handle)
            if not collection_data:
                print(f"   ❌ Collection not found: {collection_handle}")
                stats['errors'] += len(product_ids)
                continue
            
            # Process in batches of 10
            for i in range(0, len(product_ids), 10):
                batch = product_ids[i:i+10]
                
                try:
                    result = self.execute_graphql(
                        ADD_PRODUCTS_TO_COLLECTION_MUTATION,
                        {
                            'id': collection_data['id'],
                            'productIds': batch
                        }
                    )
                    
                    if 'errors' in result:
                        print(f"   ❌ GraphQL errors: {result['errors']}")
                        stats['errors'] += len(batch)
                    else:
                        collection_result = result.get('data', {}).get('collectionAddProducts', {})
                        user_errors = collection_result.get('userErrors', [])
                        
                        if user_errors:
                            print(f"   ❌ User errors: {user_errors}")
                            stats['errors'] += len(batch)
                        else:
                            stats['migrated'] += len(batch)
                            print(f"   ✅ Added batch of {len(batch)} products")
                    
                except Exception as e:
                    print(f"   ❌ Error adding products: {e}")
                    stats['errors'] += len(batch)
                
                time.sleep(0.8)
        
        # Print summary
        print("\n📊 Migration Summary:")
        print(f"   📄 Total products processed: {stats['total_products']}")
        print(f"   📝 Draft products included: {stats['draft_products']}")
        print(f"   ✅ Products migrated: {stats['migrated']}")
        print(f"   ❌ Products without mapping: {stats['no_mapping']}")
        print(f"   💥 Migration errors: {stats['errors']}")
        
        # Save report
        with open('all_products_migration_report.json', 'w') as f:
            json.dump({
                'stats': stats,
                'product_migrations': {
                    product_id: list(collections)
                    for product_id, collections in product_migrations.items()
                }
            }, f, indent=2)
        
        print("\n💾 Migration report saved to: all_products_migration_report.json")

def main():
    shop_url = os.environ.get('SHOPIFY_SHOP_URL')
    access_token = os.environ.get('SHOPIFY_ACCESS_TOKEN')
    
    if not shop_url or not access_token:
        print("Error: SHOPIFY_SHOP_URL and SHOPIFY_ACCESS_TOKEN must be set")
        sys.exit(1)
    
    print("🚀 Starting migration of ALL products (including drafts) to hierarchy...")
    
    migrator = AllProductsMigrator(shop_url, access_token)
    
    try:
        migrator.test_auth()
    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        sys.exit(1)
    
    migrator.load_hierarchy_mapping('data/collection_hierarchy_3_levels.csv')
    migrator.migrate_all_products()
    
    print("\n✅ Product migration complete!")

if __name__ == '__main__':
    main()