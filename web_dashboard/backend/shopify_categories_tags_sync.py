#!/usr/bin/env python3
"""
Shopify Categories & Tags Sync Coordinator

This script performs a full sync of categories (product types) and tags from Shopify.
It builds a comprehensive taxonomy for organization and navigation.
"""

import os
import sys
import json
import logging
from datetime import datetime
from collections import defaultdict, Counter
from typing import Dict, List, Set, Tuple, Optional
import time

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from database import db_session_scope
from models import Product, Category, Collection, SyncHistory
from sync_models import SyncPerformanceMetrics
from scripts.shopify.shopify_base import ShopifyAPIBase
from sqlalchemy import func, and_, or_

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/categories_tags_sync.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class CategoriesTagsSyncCoordinator:
    """Coordinates the sync of categories and tags from Shopify."""
    
    def __init__(self):
        """Initialize the sync coordinator."""
        self.shop_url = os.getenv('SHOPIFY_SHOP_URL')
        self.access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
        
        if not self.shop_url or not self.access_token:
            raise ValueError("Shopify credentials not configured")
        
        self.shopify_client = ShopifyAPIBase(self.shop_url, self.access_token, debug=True)
        self.start_time = datetime.utcnow()
        self.metrics = {
            'products_processed': 0,
            'categories_created': 0,
            'categories_updated': 0,
            'tags_extracted': 0,
            'product_types_found': 0,
            'vendors_found': 0,
            'api_calls': 0,
            'errors': []
        }
        self.coordination_memory = {}
        
    def execute_full_sync(self) -> Dict:
        """Execute a full categories and tags sync from Shopify."""
        logger.info("🐝 Categories & Tags Sync Coordinator starting...")
        
        try:
            # Store coordination start in memory
            self._store_coordination_memory('sync_start', {
                'timestamp': self.start_time.isoformat(),
                'coordinator': 'Categories & Tags Sync',
                'status': 'initializing'
            })
            
            # Step 1: Extract all product data from Shopify
            logger.info("📊 Step 1: Extracting product taxonomy from Shopify...")
            taxonomy_data = self._extract_shopify_taxonomy()
            
            # Step 2: Analyze and organize the taxonomy
            logger.info("🧠 Step 2: Analyzing taxonomy patterns...")
            organized_taxonomy = self._analyze_taxonomy(taxonomy_data)
            
            # Step 3: Build category hierarchy
            logger.info("🏗️ Step 3: Building category hierarchy...")
            category_mapping = self._build_category_hierarchy(organized_taxonomy)
            
            # Step 4: Store tag analytics
            logger.info("🏷️ Step 4: Storing tag analytics...")
            tag_analytics = self._store_tag_analytics(organized_taxonomy)
            
            # Step 5: Update products with category assignments
            logger.info("🔄 Step 5: Updating product category assignments...")
            self._update_product_categories(category_mapping)
            
            # Step 6: Generate sync report
            logger.info("📈 Step 6: Generating sync report...")
            sync_report = self._generate_sync_report(organized_taxonomy, tag_analytics)
            
            # Store final results in coordination memory
            self._store_coordination_memory('sync_complete', {
                'timestamp': datetime.utcnow().isoformat(),
                'metrics': self.metrics,
                'report': sync_report,
                'status': 'completed'
            })
            
            logger.info("✅ Categories & Tags sync completed successfully!")
            return sync_report
            
        except Exception as e:
            logger.error(f"❌ Error during sync: {str(e)}")
            self.metrics['errors'].append(str(e))
            self._store_coordination_memory('sync_error', {
                'timestamp': datetime.utcnow().isoformat(),
                'error': str(e),
                'status': 'failed'
            })
            raise
            
    def _extract_shopify_taxonomy(self) -> Dict:
        """Extract all taxonomy data from Shopify products."""
        taxonomy_data = {
            'product_types': Counter(),
            'vendors': Counter(),
            'tags': Counter(),
            'tag_associations': defaultdict(set),
            'type_vendor_map': defaultdict(set),
            'products_by_type': defaultdict(list),
            'products_by_vendor': defaultdict(list),
            'products_by_tag': defaultdict(list)
        }
        
        try:
            # GraphQL query to get all products with taxonomy data
            query = """
            query GetProductTaxonomy($cursor: String) {
                products(first: 250, after: $cursor) {
                    pageInfo {
                        hasNextPage
                        endCursor
                    }
                    nodes {
                        id
                        title
                        handle
                        productType
                        vendor
                        tags
                        status
                        createdAt
                        updatedAt
                        variants(first: 1) {
                            nodes {
                                sku
                            }
                        }
                    }
                }
            }
            """
            
            cursor = None
            page = 0
            
            while True:
                page += 1
                logger.info(f"Fetching products page {page}...")
                
                variables = {'cursor': cursor} if cursor else {}
                result = self.shopify_client.execute_graphql(query, variables)
                self.metrics['api_calls'] += 1
                
                if 'errors' in result:
                    raise Exception(f"GraphQL errors: {result['errors']}")
                
                products_data = result.get('data', {}).get('products', {})
                products = products_data.get('nodes', [])
                
                for product in products:
                    self.metrics['products_processed'] += 1
                    
                    # Extract product type
                    product_type = product.get('productType', '').strip()
                    if product_type:
                        taxonomy_data['product_types'][product_type] += 1
                        taxonomy_data['products_by_type'][product_type].append({
                            'id': product['id'],
                            'title': product['title'],
                            'handle': product['handle'],
                            'sku': product['variants']['nodes'][0]['sku'] if product['variants']['nodes'] else None
                        })
                    
                    # Extract vendor
                    vendor = product.get('vendor', '').strip()
                    if vendor:
                        taxonomy_data['vendors'][vendor] += 1
                        taxonomy_data['products_by_vendor'][vendor].append(product['id'])
                        
                        # Map vendor to product type
                        if product_type:
                            taxonomy_data['type_vendor_map'][product_type].add(vendor)
                    
                    # Extract tags
                    tags = product.get('tags', [])
                    for tag in tags:
                        tag = tag.strip()
                        if tag:
                            taxonomy_data['tags'][tag] += 1
                            taxonomy_data['products_by_tag'][tag].append(product['id'])
                            
                            # Associate tags with product types
                            if product_type:
                                taxonomy_data['tag_associations'][product_type].add(tag)
                
                # Check for more pages
                page_info = products_data.get('pageInfo', {})
                if not page_info.get('hasNextPage'):
                    break
                    
                cursor = page_info.get('endCursor')
                time.sleep(0.5)  # Rate limiting
                
            self.metrics['product_types_found'] = len(taxonomy_data['product_types'])
            self.metrics['vendors_found'] = len(taxonomy_data['vendors'])
            self.metrics['tags_extracted'] = len(taxonomy_data['tags'])
            
            logger.info(f"Extracted {self.metrics['products_processed']} products")
            logger.info(f"Found {self.metrics['product_types_found']} product types")
            logger.info(f"Found {self.metrics['vendors_found']} vendors")
            logger.info(f"Found {self.metrics['tags_extracted']} unique tags")
            
            return taxonomy_data
            
        except Exception as e:
            logger.error(f"Error extracting taxonomy: {str(e)}")
            raise
            
    def _analyze_taxonomy(self, taxonomy_data: Dict) -> Dict:
        """Analyze taxonomy data to identify patterns and hierarchies."""
        organized = {
            'categories': {},
            'tag_frequency': taxonomy_data['tags'].most_common(),
            'type_frequency': taxonomy_data['product_types'].most_common(),
            'vendor_frequency': taxonomy_data['vendors'].most_common(),
            'tag_clusters': {},
            'suggested_hierarchy': {}
        }
        
        # Analyze product types as main categories
        for product_type, count in taxonomy_data['product_types'].items():
            organized['categories'][product_type] = {
                'name': product_type,
                'product_count': count,
                'vendors': list(taxonomy_data['type_vendor_map'].get(product_type, [])),
                'common_tags': list(taxonomy_data['tag_associations'].get(product_type, [])),
                'products': taxonomy_data['products_by_type'].get(product_type, [])
            }
        
        # Identify tag clusters (tags that often appear together)
        tag_cooccurrence = defaultdict(lambda: defaultdict(int))
        for product_type, tags in taxonomy_data['tag_associations'].items():
            tag_list = list(tags)
            for i in range(len(tag_list)):
                for j in range(i + 1, len(tag_list)):
                    tag_cooccurrence[tag_list[i]][tag_list[j]] += 1
                    tag_cooccurrence[tag_list[j]][tag_list[i]] += 1
        
        # Find strong tag relationships
        for tag, related_tags in tag_cooccurrence.items():
            if len(related_tags) > 0:
                organized['tag_clusters'][tag] = sorted(
                    related_tags.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:10]  # Top 10 related tags
        
        # Suggest category hierarchy based on patterns
        # (This is a simplified version - could be enhanced with ML)
        organized['suggested_hierarchy'] = self._suggest_hierarchy(taxonomy_data)
        
        return organized
        
    def _suggest_hierarchy(self, taxonomy_data: Dict) -> Dict:
        """Suggest a category hierarchy based on naming patterns."""
        hierarchy = {}
        
        # Look for patterns in product types
        type_names = list(taxonomy_data['product_types'].keys())
        
        # Group by common prefixes or patterns
        for type_name in type_names:
            parts = type_name.split(' - ')
            if len(parts) > 1:
                # Multi-level category
                parent = parts[0].strip()
                child = ' - '.join(parts[1:]).strip()
                
                if parent not in hierarchy:
                    hierarchy[parent] = {
                        'name': parent,
                        'children': [],
                        'is_parent': True
                    }
                
                hierarchy[parent]['children'].append({
                    'name': child,
                    'full_name': type_name,
                    'count': taxonomy_data['product_types'][type_name]
                })
            else:
                # Single level category
                if type_name not in hierarchy:
                    hierarchy[type_name] = {
                        'name': type_name,
                        'children': [],
                        'is_parent': False,
                        'count': taxonomy_data['product_types'][type_name]
                    }
        
        return hierarchy
        
    def _build_category_hierarchy(self, organized_taxonomy: Dict) -> Dict:
        """Build or update category hierarchy in the database."""
        category_mapping = {}
        
        with db_session_scope() as session:
            # Process suggested hierarchy
            for parent_name, parent_data in organized_taxonomy['suggested_hierarchy'].items():
                # Create or update parent category
                parent_category = session.query(Category).filter_by(
                    name=parent_name
                ).first()
                
                if not parent_category:
                    parent_category = Category(
                        name=parent_name,
                        slug=self._generate_slug(parent_name),
                        description=f"Product category: {parent_name}",
                        level=0,
                        path=parent_name,
                        is_active=True
                    )
                    session.add(parent_category)
                    session.flush()
                    self.metrics['categories_created'] += 1
                else:
                    self.metrics['categories_updated'] += 1
                
                # Store mapping
                if parent_data['is_parent']:
                    # Has children
                    for child_data in parent_data['children']:
                        full_name = child_data['full_name']
                        category_mapping[full_name] = parent_category.id
                        
                        # Create child category
                        child_category = session.query(Category).filter_by(
                            name=child_data['name'],
                            parent_id=parent_category.id
                        ).first()
                        
                        if not child_category:
                            child_category = Category(
                                name=child_data['name'],
                                slug=self._generate_slug(child_data['name']),
                                description=f"Product subcategory: {child_data['name']}",
                                parent_id=parent_category.id,
                                level=1,
                                path=f"{parent_name}/{child_data['name']}",
                                is_active=True
                            )
                            session.add(child_category)
                            session.flush()
                            self.metrics['categories_created'] += 1
                        
                        category_mapping[full_name] = child_category.id
                else:
                    # No children
                    category_mapping[parent_name] = parent_category.id
            
            session.commit()
            
        logger.info(f"Created {self.metrics['categories_created']} new categories")
        logger.info(f"Updated {self.metrics['categories_updated']} existing categories")
        
        return category_mapping
        
    def _store_tag_analytics(self, organized_taxonomy: Dict) -> Dict:
        """Store tag analytics for future use."""
        tag_analytics = {
            'total_tags': len(organized_taxonomy['tag_frequency']),
            'top_tags': organized_taxonomy['tag_frequency'][:50],  # Top 50 tags
            'tag_clusters': organized_taxonomy['tag_clusters'],
            'tags_per_category': {}
        }
        
        # Calculate tags per category
        for category, data in organized_taxonomy['categories'].items():
            tag_analytics['tags_per_category'][category] = {
                'tags': data['common_tags'],
                'count': len(data['common_tags'])
            }
        
        # Store in coordination memory
        self._store_coordination_memory('tag_analytics', tag_analytics)
        
        return tag_analytics
        
    def _update_product_categories(self, category_mapping: Dict):
        """Update products with their appropriate categories."""
        updated_count = 0
        
        with db_session_scope() as session:
            for product_type, category_id in category_mapping.items():
                # Update products with this product type
                products = session.query(Product).filter(
                    func.json_extract(Product.custom_attributes, '$.product_type') == product_type
                ).all()
                
                for product in products:
                    if product.category_id != category_id:
                        product.category_id = category_id
                        updated_count += 1
                
                session.commit()
        
        logger.info(f"Updated {updated_count} products with new category assignments")
        
    def _generate_sync_report(self, organized_taxonomy: Dict, tag_analytics: Dict) -> Dict:
        """Generate a comprehensive sync report."""
        duration = (datetime.utcnow() - self.start_time).total_seconds()
        
        report = {
            'sync_type': 'categories_tags_sync',
            'started_at': self.start_time.isoformat(),
            'completed_at': datetime.utcnow().isoformat(),
            'duration_seconds': duration,
            'metrics': self.metrics,
            'summary': {
                'total_products_processed': self.metrics['products_processed'],
                'total_product_types': self.metrics['product_types_found'],
                'total_vendors': self.metrics['vendors_found'],
                'total_tags': self.metrics['tags_extracted'],
                'categories_created': self.metrics['categories_created'],
                'categories_updated': self.metrics['categories_updated'],
                'api_calls_made': self.metrics['api_calls']
            },
            'top_categories': organized_taxonomy['type_frequency'][:20],
            'top_vendors': organized_taxonomy['vendor_frequency'][:20],
            'top_tags': tag_analytics['top_tags'][:20],
            'errors': self.metrics['errors']
        }
        
        # Store sync history
        with db_session_scope() as session:
            sync_history = SyncHistory(
                sync_type='categories_tags_sync',
                sync_source='shopify',
                sync_target='local',
                status='success' if not self.metrics['errors'] else 'partial',
                started_at=self.start_time,
                completed_at=datetime.utcnow(),
                duration=int(duration),
                total_items=self.metrics['products_processed'],
                items_processed=self.metrics['products_processed'],
                items_successful=self.metrics['products_processed'] - len(self.metrics['errors']),
                items_failed=len(self.metrics['errors']),
                message='Categories and tags sync completed',
                meta_data=report,
                user_id=1  # System user
            )
            session.add(sync_history)
            
            # Store performance metrics
            perf_metric = SyncPerformanceMetrics(
                metric_name='categories_tags_sync_duration',
                metric_type='timer',
                value=duration,
                unit='seconds',
                operation='categories_tags_sync',
                entity_type='taxonomy',
                duration=duration,
                api_calls=self.metrics['api_calls'],
                success_rate=100.0 if not self.metrics['errors'] else (
                    (self.metrics['products_processed'] - len(self.metrics['errors'])) / 
                    self.metrics['products_processed'] * 100.0
                ),
                error_count=len(self.metrics['errors']),
                time_bucket='day',
                tags={
                    'products_processed': self.metrics['products_processed'],
                    'categories_created': self.metrics['categories_created'],
                    'tags_extracted': self.metrics['tags_extracted']
                }
            )
            session.add(perf_metric)
            session.commit()
        
        return report
        
    def _generate_slug(self, name: str) -> str:
        """Generate a URL-friendly slug from a name."""
        import re
        slug = name.lower()
        slug = re.sub(r'[^a-z0-9\s-]', '', slug)
        slug = re.sub(r'[\s]+', '-', slug)
        slug = slug.strip('-')
        return slug
        
    def _store_coordination_memory(self, key: str, data: Dict):
        """Store data in coordination memory for other agents."""
        self.coordination_memory[key] = {
            'timestamp': datetime.utcnow().isoformat(),
            'data': data
        }
        
        # Also log to file for persistence
        memory_file = f"logs/coordination_memory_categories_{self.start_time.strftime('%Y%m%d_%H%M%S')}.json"
        try:
            with open(memory_file, 'w') as f:
                json.dump(self.coordination_memory, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not write coordination memory: {str(e)}")


def main():
    """Main execution function."""
    try:
        coordinator = CategoriesTagsSyncCoordinator()
        report = coordinator.execute_full_sync()
        
        # Print summary
        print("\n" + "="*60)
        print("🐝 CATEGORIES & TAGS SYNC COMPLETE")
        print("="*60)
        print(f"Duration: {report['duration_seconds']:.2f} seconds")
        print(f"Products Processed: {report['summary']['total_products_processed']}")
        print(f"Product Types Found: {report['summary']['total_product_types']}")
        print(f"Vendors Found: {report['summary']['total_vendors']}")
        print(f"Tags Extracted: {report['summary']['total_tags']}")
        print(f"Categories Created: {report['summary']['categories_created']}")
        print(f"Categories Updated: {report['summary']['categories_updated']}")
        print(f"API Calls: {report['summary']['api_calls_made']}")
        
        if report['errors']:
            print(f"\n⚠️ Errors: {len(report['errors'])}")
            for error in report['errors'][:5]:
                print(f"  - {error}")
        
        print("\n📊 Top 10 Product Types:")
        for product_type, count in report['top_categories'][:10]:
            print(f"  - {product_type}: {count} products")
            
        print("\n🏷️ Top 10 Tags:")
        for tag, count in report['top_tags'][:10]:
            print(f"  - {tag}: {count} products")
            
        print("\n✅ Sync completed successfully!")
        
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        print(f"\n❌ Sync failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()