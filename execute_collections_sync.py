#!/usr/bin/env python3
"""
Collections Sync Coordinator Script
Executes full collections sync from Shopify to local database
"""

import os
import sys
import logging
import json
from datetime import datetime
from typing import Dict, List, Optional, Any

# Add paths for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web_dashboard', 'backend'))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scripts'))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import required modules
from web_dashboard.backend.shopify_collections import ShopifyCollectionsManager
from web_dashboard.backend.database import db_session_scope, db_manager
from web_dashboard.backend.models import Product, Category, ProductCollection
from web_dashboard.backend.repositories.collection_repository import CollectionRepository
from scripts.shopify.shopify_base import ShopifyAPIBase

# Extended query for complete collection data including rules
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
        sortOrder
        templateSuffix
        
        image {
          id
          url
          altText
          width
          height
        }
        
        seo {
          title
          description
        }
        
        # Rules for smart collections
        ruleSet {
          appliedDisjunctively
          rules {
            column
            relation
            condition
          }
        }
        
        products(first: 10) {
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
        
        productsCount {
          count
        }
        
        metafields(first: 10) {
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
      cursor
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""

class CollectionsSyncCoordinator:
    """Coordinates the full collections sync from Shopify"""
    
    def __init__(self):
        self.shop_url = os.getenv('SHOPIFY_SHOP_URL')
        self.access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
        
        if not self.shop_url or not self.access_token:
            raise ValueError("Shopify credentials not configured in environment")
        
        self.shopify_client = ShopifyAPIBase(self.shop_url, self.access_token, debug=True)
        self.collections_manager = ShopifyCollectionsManager(self.shop_url, self.access_token, debug=True)
        
        # Track sync statistics
        self.stats = {
            'collections_synced': 0,
            'smart_collections': 0,
            'custom_collections': 0,
            'products_associated': 0,
            'rules_synced': 0,
            'errors': []
        }
    
    def execute_sync(self):
        """Execute the full collections sync"""
        logger.info("🚀 Starting Collections Sync from Shopify")
        logger.info(f"📍 Shop URL: {self.shop_url}")
        
        try:
            # Step 1: Fetch all collections from Shopify
            logger.info("\n📊 Step 1: Fetching collections from Shopify...")
            shopify_collections = self._fetch_all_collections()
            logger.info(f"✅ Fetched {len(shopify_collections)} collections from Shopify")
            
            # Step 2: Process and store collections
            logger.info("\n💾 Step 2: Processing and storing collections...")
            self._process_collections(shopify_collections)
            
            # Step 3: Sync collection-product associations
            logger.info("\n🔗 Step 3: Syncing collection-product associations...")
            self._sync_product_associations(shopify_collections)
            
            # Step 4: Generate sync report
            logger.info("\n📈 Step 4: Generating sync report...")
            self._generate_sync_report()
            
            logger.info("\n✅ Collections sync completed successfully!")
            
        except Exception as e:
            logger.error(f"❌ Error during collections sync: {str(e)}")
            self.stats['errors'].append(str(e))
            raise
    
    def _fetch_all_collections(self) -> List[Dict[str, Any]]:
        """Fetch all collections from Shopify with pagination"""
        collections = []
        has_next_page = True
        cursor = None
        
        while has_next_page:
            variables = {'first': 50}
            if cursor:
                variables['after'] = cursor
            
            result = self.shopify_client.execute_graphql(COMPLETE_COLLECTIONS_QUERY, variables)
            
            if 'errors' in result:
                raise Exception(f"GraphQL errors: {result['errors']}")
            
            collections_data = result.get('data', {}).get('collections', {})
            edges = collections_data.get('edges', [])
            
            for edge in edges:
                collection = edge['node']
                # Extract numeric ID from GraphQL ID
                collection['numeric_id'] = collection['id'].split('/')[-1]
                collections.append(collection)
            
            page_info = collections_data.get('pageInfo', {})
            has_next_page = page_info.get('hasNextPage', False)
            cursor = page_info.get('endCursor')
            
            logger.info(f"   Fetched {len(collections)} collections so far...")
        
        return collections
    
    def _process_collections(self, shopify_collections: List[Dict[str, Any]]):
        """Process and store collections in the database"""
        with db_session_scope() as session:
            repo = CollectionRepository(session)
            
            for shopify_collection in shopify_collections:
                try:
                    # Determine collection type
                    has_rules = shopify_collection.get('ruleSet') is not None
                    collection_type = 'automatic' if has_rules else 'manual'
                    
                    if has_rules:
                        self.stats['smart_collections'] += 1
                    else:
                        self.stats['custom_collections'] += 1
                    
                    # Prepare collection data
                    collection_data = {
                        'name': shopify_collection['title'],
                        'handle': shopify_collection['handle'],
                        'description': shopify_collection.get('description', ''),
                        'shopify_collection_id': shopify_collection['id'],
                        'status': 'active',  # Default to active since we can't check publication status
                        'sort_order': shopify_collection.get('sortOrder', 'MANUAL').lower(),
                        'rules_type': collection_type,
                        'disjunctive': False,
                        'seo_title': shopify_collection.get('seo', {}).get('title', ''),
                        'seo_description': shopify_collection.get('seo', {}).get('description', ''),
                        'shopify_synced_at': datetime.utcnow()
                    }
                    
                    # Handle rules for smart collections
                    if has_rules:
                        rule_set = shopify_collection['ruleSet']
                        collection_data['disjunctive'] = rule_set.get('appliedDisjunctively', False)
                        
                        # Convert rules to our format
                        rules = []
                        for rule in rule_set.get('rules', []):
                            rules.append({
                                'column': rule['column'],
                                'relation': rule['relation'],
                                'condition': rule['condition']
                            })
                            self.stats['rules_synced'] += 1
                        
                        collection_data['rules_conditions'] = rules
                    
                    # Check if collection exists
                    existing_collection = repo.get_by_handle(shopify_collection['handle'])
                    
                    if existing_collection:
                        # Update existing collection
                        updated_collection = repo.update_collection(
                            collection_id=existing_collection.id,
                            updated_by=1,  # System user ID
                            **collection_data
                        )
                        logger.info(f"   ✅ Updated collection: {shopify_collection['title']}")
                    else:
                        # Create new collection
                        new_collection = repo.create_collection(
                            created_by=1,  # System user ID
                            **collection_data
                        )
                        logger.info(f"   ✅ Created collection: {shopify_collection['title']}")
                    
                    self.stats['collections_synced'] += 1
                    
                except Exception as e:
                    logger.error(f"   ❌ Error processing collection {shopify_collection['handle']}: {str(e)}")
                    self.stats['errors'].append(f"Collection {shopify_collection['handle']}: {str(e)}")
    
    def _sync_product_associations(self, shopify_collections: List[Dict[str, Any]]):
        """Sync product associations for manual collections"""
        with db_session_scope() as session:
            repo = CollectionRepository(session)
            product_repo = session.query(Product)
            
            for shopify_collection in shopify_collections:
                try:
                    # Skip smart collections (they manage their own products)
                    if shopify_collection.get('ruleSet'):
                        continue
                    
                    # Get local collection
                    local_collection = repo.get_by_handle(shopify_collection['handle'])
                    if not local_collection:
                        logger.warning(f"   ⚠️  Collection not found locally: {shopify_collection['handle']}")
                        continue
                    
                    # Get product IDs from Shopify collection
                    shopify_product_ids = []
                    products_data = shopify_collection.get('products', {})
                    
                    for edge in products_data.get('edges', []):
                        product = edge['node']
                        shopify_product_ids.append(product['id'])
                    
                    # Note if there are more products to fetch
                    if products_data.get('pageInfo', {}).get('hasNextPage'):
                        logger.warning(f"   ⚠️  Collection '{shopify_collection['handle']}' has more than 10 products. Full sync needed.")
                    
                    # Find matching local products
                    local_product_ids = []
                    for shopify_id in shopify_product_ids:
                        local_product = product_repo.filter_by(shopify_product_id=shopify_id).first()
                        if local_product:
                            local_product_ids.append(local_product.id)
                    
                    if local_product_ids:
                        # Clear existing associations and add new ones
                        # First remove all existing products
                        existing_products = session.query(ProductCollection).filter_by(
                            collection_id=local_collection.id
                        ).all()
                        for ep in existing_products:
                            session.delete(ep)
                        session.flush()
                        
                        # Then add new ones
                        added_count = repo.add_products_to_collection(
                            collection_id=local_collection.id,
                            product_ids=local_product_ids
                        )
                        self.stats['products_associated'] += added_count
                        logger.info(f"   ✅ Associated {added_count} products with collection: {shopify_collection['title']}")
                    
                except Exception as e:
                    logger.error(f"   ❌ Error syncing products for collection {shopify_collection['handle']}: {str(e)}")
                    self.stats['errors'].append(f"Product sync for {shopify_collection['handle']}: {str(e)}")
    
    def _generate_sync_report(self):
        """Generate and display sync report"""
        logger.info("\n" + "=" * 60)
        logger.info("📊 COLLECTIONS SYNC REPORT")
        logger.info("=" * 60)
        logger.info(f"Total Collections Synced: {self.stats['collections_synced']}")
        logger.info(f"  - Smart Collections: {self.stats['smart_collections']}")
        logger.info(f"  - Custom Collections: {self.stats['custom_collections']}")
        logger.info(f"Rules Synced: {self.stats['rules_synced']}")
        logger.info(f"Products Associated: {self.stats['products_associated']}")
        
        if self.stats['errors']:
            logger.info(f"\nErrors Encountered: {len(self.stats['errors'])}")
            for error in self.stats['errors']:
                logger.error(f"  - {error}")
        else:
            logger.info("\n✅ No errors encountered!")
        
        logger.info("=" * 60)
        
        # Save report to file
        report_file = f"collections_sync_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump({
                'sync_timestamp': datetime.utcnow().isoformat(),
                'shop_url': self.shop_url,
                'statistics': self.stats
            }, f, indent=2)
        
        logger.info(f"\n📄 Report saved to: {report_file}")


def main():
    """Main execution function"""
    try:
        # Initialize database
        logger.info("Initializing database connection...")
        db_manager.initialize()
        
        # Initialize and run sync
        coordinator = CollectionsSyncCoordinator()
        coordinator.execute_sync()
        
    except KeyboardInterrupt:
        logger.warning("\n⚠️  Sync interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n❌ Fatal error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()