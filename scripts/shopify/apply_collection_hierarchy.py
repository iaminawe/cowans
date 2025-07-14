#!/usr/bin/env python3
"""
Apply 3-Level Collection Hierarchy to Shopify

This script applies the new 3-level collection hierarchy to Shopify while:
- Checking for existing collections to avoid duplicates
- Updating existing collections instead of creating new ones
- Setting up proper parent-child relationships
- Preserving existing product associations

Usage:
    python apply_collection_hierarchy.py --shop-url YOUR_SHOP --access-token YOUR_TOKEN
"""

import os
import sys
import csv
import json
import argparse
import logging
import time
from typing import Dict, List, Optional, Any, Set, Tuple
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from scripts.shopify.shopify_base import ShopifyAPIBase
except ImportError:
    from shopify_base import ShopifyAPIBase

# Configure logging
logger = logging.getLogger(__name__)

# GraphQL Queries and Mutations
GET_ALL_COLLECTIONS_QUERY = """
query getCollections($first: Int!, $after: String) {
  collections(first: $first, after: $after) {
    edges {
      node {
        id
        handle
        title
        description
        descriptionHtml
        productsCount {
          count
        }
        metafields(first: 10) {
          edges {
            node {
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

CREATE_COLLECTION_MUTATION = """
mutation createCollection($input: CollectionInput!) {
  collectionCreate(input: $input) {
    collection {
      id
      handle
      title
      description
    }
    userErrors {
      field
      message
    }
  }
}
"""

UPDATE_COLLECTION_MUTATION = """
mutation updateCollection($input: CollectionInput!) {
  collectionUpdate(input: $input) {
    collection {
      id
      handle
      title
      description
    }
    userErrors {
      field
      message
    }
  }
}
"""

class CollectionHierarchyManager(ShopifyAPIBase):
    """Manages the application of 3-level collection hierarchy to Shopify."""
    
    def __init__(self, shop_url: str, access_token: str, debug: bool = False):
        """Initialize the hierarchy manager."""
        super().__init__(shop_url, access_token, debug)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.existing_collections = {}  # handle -> collection dict
        self.hierarchy_collections = {}  # (level, handle) -> hierarchy entry
        self.collection_mapping = {}  # old_handle -> new_handle
        
    def load_existing_collections(self) -> None:
        """Load all existing collections from Shopify."""
        print("📥 Loading existing collections from Shopify...")
        collections = []
        cursor = None
        
        while True:
            variables = {
                "first": 250,
                "after": cursor
            }
            
            result = self.execute_graphql(GET_ALL_COLLECTIONS_QUERY, variables)
            
            if 'errors' in result:
                self.logger.error(f"GraphQL errors: {result['errors']}")
                break
            
            edges = result.get('data', {}).get('collections', {}).get('edges', [])
            page_info = result.get('data', {}).get('collections', {}).get('pageInfo', {})
            
            for edge in edges:
                collection = edge['node']
                handle = collection['handle']
                self.existing_collections[handle] = collection
            
            if not page_info.get('hasNextPage'):
                break
                
            cursor = page_info.get('endCursor')
        
        print(f"✅ Loaded {len(self.existing_collections)} existing collections")
        
    def load_hierarchy_data(self, hierarchy_file: str) -> None:
        """Load the 3-level hierarchy data from CSV."""
        print(f"📥 Loading hierarchy data from: {hierarchy_file}")
        
        with open(hierarchy_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Store by level and handle for easy lookup
                for level in ['1', '2', '3']:
                    handle = row.get(f'collection_handle_l{level}', '')
                    if handle:
                        key = (int(level), handle)
                        self.hierarchy_collections[key] = row
        
        print(f"✅ Loaded {len(self.hierarchy_collections)} hierarchy entries")
    
    def analyze_matches(self) -> Dict[str, List[Dict[str, Any]]]:
        """Analyze which existing collections match new hierarchy."""
        matches = {
            'exact': [],      # Exact handle matches
            'similar': [],    # Similar names/handles
            'update': [],     # Need updating
            'create': []      # Need creating
        }
        
        # Get unique collection handles from hierarchy
        hierarchy_handles = set()
        for (level, handle) in self.hierarchy_collections.keys():
            hierarchy_handles.add(handle)
        
        # Check each hierarchy collection
        for handle in hierarchy_handles:
            if handle in self.existing_collections:
                matches['exact'].append({
                    'handle': handle,
                    'existing': self.existing_collections[handle],
                    'action': 'update'
                })
            else:
                # Check for similar matches
                similar = self._find_similar_collection(handle)
                if similar:
                    matches['similar'].append({
                        'new_handle': handle,
                        'existing_handle': similar['handle'],
                        'existing': similar,
                        'action': 'update'
                    })
                else:
                    matches['create'].append({
                        'handle': handle,
                        'action': 'create'
                    })
        
        return matches
    
    def _find_similar_collection(self, handle: str) -> Optional[Dict[str, Any]]:
        """Find similar existing collection by handle variations."""
        # Common variations to check
        variations = [
            handle.replace('-', '_'),
            handle.replace('_', '-'),
            handle.replace('-and-', '-'),
            handle.replace('-supplies', ''),
            handle.replace('-products', ''),
            handle + 's',  # plural
            handle.rstrip('s')  # singular
        ]
        
        # Also check specific known mappings
        known_mappings = {
            'paints-painting': ['painting-tools', 'acrylic-paints', 'watercolour-paints', 'oil-paints'],
            'drawing-sketching': ['drawing-tools', 'graphite', 'coloured-pencils'],
            'canvas-surfaces': ['stretched-canvas', 'canvas-boards', 'birch-boards'],
            'writing-instruments': ['pen-ink', 'markers', 'pencils'],
            'office-furniture': ['office-stuff', 'furniture'],
            'printing-imaging': ['ink-cartridges', 'toner-cartridges']
        }
        
        # Check variations
        for variation in variations:
            if variation in self.existing_collections:
                return self.existing_collections[variation]
        
        # Check known mappings
        for new_handle, old_handles in known_mappings.items():
            if handle == new_handle:
                for old_handle in old_handles:
                    if old_handle in self.existing_collections:
                        return self.existing_collections[old_handle]
        
        return None
    
    def create_or_update_collection(self, handle: str, level: int, parent_handle: Optional[str] = None) -> Optional[str]:
        """Create or update a collection based on hierarchy data."""
        # Get hierarchy data
        hierarchy_key = (level, handle)
        hierarchy_data = None
        
        # Find the hierarchy data for this handle at this level
        for (h_level, h_handle), data in self.hierarchy_collections.items():
            if h_level == level and h_handle == handle:
                hierarchy_data = data
                break
        
        if not hierarchy_data:
            self.logger.warning(f"No hierarchy data found for {handle} at level {level}")
            return None
        
        # Determine title and description based on level
        if level == 1:
            title = hierarchy_data['level_1']
            description = f"Browse our complete selection of {hierarchy_data['level_1'].lower()}"
        elif level == 2:
            title = hierarchy_data['level_2']
            description = hierarchy_data.get('description', f"{hierarchy_data['level_2']} in {hierarchy_data['level_1']}")
        else:  # level 3
            title = hierarchy_data['level_3']
            description = hierarchy_data.get('description', f"{hierarchy_data['level_3']} - {hierarchy_data['product_types_included']}")
        
        # Prepare collection data
        collection_input = {
            'title': title,
            'handle': handle,
            'descriptionHtml': f'<p>{description}</p>',
            'sortOrder': 'BEST_SELLING',
            'metafields': [
                {
                    'namespace': 'hierarchy',
                    'key': 'level',
                    'value': str(level),
                    'type': 'single_line_text_field'
                },
                {
                    'namespace': 'hierarchy',
                    'key': 'synced_at',
                    'value': datetime.utcnow().isoformat(),
                    'type': 'single_line_text_field'
                }
            ]
        }
        
        # Add parent reference if applicable
        if parent_handle and level > 1:
            collection_input['metafields'].append({
                'namespace': 'hierarchy',
                'key': 'parent_handle',
                'value': parent_handle,
                'type': 'single_line_text_field'
            })
        
        # Check if collection exists
        existing = self.existing_collections.get(handle)
        if not existing:
            # Check for similar collection
            existing = self._find_similar_collection(handle)
        
        try:
            if existing:
                # Update existing collection
                collection_input['id'] = existing['id']
                print(f"  📝 Updating: {existing['handle']} → {handle} ({title})")
                
                result = self.execute_graphql(UPDATE_COLLECTION_MUTATION, {'input': collection_input})
                
                if 'errors' in result:
                    self.logger.error(f"GraphQL errors: {result['errors']}")
                    return None
                
                collection_result = result.get('data', {}).get('collectionUpdate', {})
            else:
                # Create new collection
                print(f"  ✨ Creating: {handle} ({title})")
                
                result = self.execute_graphql(CREATE_COLLECTION_MUTATION, {'input': collection_input})
                
                if 'errors' in result:
                    self.logger.error(f"GraphQL errors: {result['errors']}")
                    return None
                
                collection_result = result.get('data', {}).get('collectionCreate', {})
            
            # Check for user errors
            user_errors = collection_result.get('userErrors', [])
            if user_errors:
                self.logger.error(f"User errors: {user_errors}")
                return None
            
            collection = collection_result.get('collection')
            if collection:
                return collection['id']
            
        except Exception as e:
            self.logger.error(f"Error processing collection {handle}: {str(e)}")
            
        return None
    
    def apply_hierarchy(self) -> None:
        """Apply the complete 3-level hierarchy."""
        print("\n🔄 Applying 3-level collection hierarchy...")
        
        # Track created/updated collections
        stats = {
            'created': 0,
            'updated': 0,
            'errors': 0,
            'level_1': 0,
            'level_2': 0,
            'level_3': 0
        }
        
        # Get unique collections by level
        level_1_collections = set()
        level_2_collections = set()
        level_3_collections = set()
        
        for (level, handle) in self.hierarchy_collections.keys():
            if level == 1:
                level_1_collections.add(handle)
            elif level == 2:
                level_2_collections.add(handle)
            elif level == 3:
                level_3_collections.add(handle)
        
        # Process Level 1 collections first
        print("\n📁 Processing Level 1 Collections (Top Level)...")
        for handle in sorted(level_1_collections):
            result = self.create_or_update_collection(handle, 1)
            if result:
                stats['level_1'] += 1
                if handle in self.existing_collections:
                    stats['updated'] += 1
                else:
                    stats['created'] += 1
            else:
                stats['errors'] += 1
            time.sleep(0.5)  # Rate limiting
        
        # Process Level 2 collections
        print("\n📁 Processing Level 2 Collections (Categories)...")
        for handle in sorted(level_2_collections):
            # Find parent handle
            parent_handle = None
            for (level, h), data in self.hierarchy_collections.items():
                if level == 2 and h == handle:
                    parent_handle = data.get('collection_handle_l1')
                    break
            
            result = self.create_or_update_collection(handle, 2, parent_handle)
            if result:
                stats['level_2'] += 1
                if handle in self.existing_collections or self._find_similar_collection(handle):
                    stats['updated'] += 1
                else:
                    stats['created'] += 1
            else:
                stats['errors'] += 1
            time.sleep(0.5)  # Rate limiting
        
        # Process Level 3 collections
        print("\n📁 Processing Level 3 Collections (Subcategories)...")
        for handle in sorted(level_3_collections):
            # Find parent handle
            parent_handle = None
            for (level, h), data in self.hierarchy_collections.items():
                if level == 3 and h == handle:
                    parent_handle = data.get('collection_handle_l2')
                    break
            
            result = self.create_or_update_collection(handle, 3, parent_handle)
            if result:
                stats['level_3'] += 1
                if handle in self.existing_collections or self._find_similar_collection(handle):
                    stats['updated'] += 1
                else:
                    stats['created'] += 1
            else:
                stats['errors'] += 1
            time.sleep(0.5)  # Rate limiting
        
        # Print summary
        print("\n📊 Hierarchy Application Summary:")
        print(f"   ✨ Collections created: {stats['created']}")
        print(f"   📝 Collections updated: {stats['updated']}")
        print(f"   ❌ Errors: {stats['errors']}")
        print(f"\n   📁 Level 1: {stats['level_1']} collections")
        print(f"   📁 Level 2: {stats['level_2']} collections")
        print(f"   📁 Level 3: {stats['level_3']} collections")
        
        # Save mapping for reference
        self._save_collection_mapping()
    
    def _save_collection_mapping(self) -> None:
        """Save the collection mapping for future reference."""
        mapping_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'existing_collections': len(self.existing_collections),
            'hierarchy_collections': len(self.hierarchy_collections),
            'mapping': self.collection_mapping
        }
        
        with open('collection_hierarchy_mapping.json', 'w') as f:
            json.dump(mapping_data, f, indent=2)
        
        print("\n💾 Collection mapping saved to: collection_hierarchy_mapping.json")
    
    def generate_analysis_report(self, matches: Dict[str, List[Dict[str, Any]]]) -> None:
        """Generate a detailed analysis report."""
        print("\n📊 Collection Hierarchy Analysis Report")
        print("=" * 50)
        
        print(f"\n📥 Existing Collections: {len(self.existing_collections)}")
        print(f"📋 Hierarchy Collections: {len(set(h for _, h in self.hierarchy_collections.keys()))}")
        
        print(f"\n✅ Exact Matches: {len(matches['exact'])}")
        if matches['exact']:
            print("   Examples:")
            for match in matches['exact'][:5]:
                print(f"   - {match['handle']} → Update existing")
        
        print(f"\n🔄 Similar Matches: {len(matches['similar'])}")
        if matches['similar']:
            print("   Examples:")
            for match in matches['similar'][:5]:
                print(f"   - {match['new_handle']} → Update {match['existing_handle']}")
        
        print(f"\n✨ New Collections: {len(matches['create'])}")
        if matches['create']:
            print("   Examples:")
            for match in matches['create'][:5]:
                print(f"   - {match['handle']} → Create new")
        
        # Save detailed report
        report = {
            'timestamp': datetime.utcnow().isoformat(),
            'summary': {
                'existing_collections': len(self.existing_collections),
                'hierarchy_collections': len(set(h for _, h in self.hierarchy_collections.keys())),
                'exact_matches': len(matches['exact']),
                'similar_matches': len(matches['similar']),
                'new_collections': len(matches['create'])
            },
            'matches': matches
        }
        
        with open('collection_hierarchy_analysis.json', 'w') as f:
            json.dump(report, f, indent=2)
        
        print("\n💾 Detailed analysis saved to: collection_hierarchy_analysis.json")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description='Apply 3-level collection hierarchy to Shopify'
    )
    parser.add_argument('--shop-url', required=True, help='Shopify store URL')
    parser.add_argument('--access-token', required=True, help='Shopify access token')
    parser.add_argument('--hierarchy-file', default='collection_hierarchy_3_levels.csv', 
                       help='Path to hierarchy CSV file')
    parser.add_argument('--analyze-only', action='store_true', 
                       help='Only analyze, do not apply changes')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # Create manager
        manager = CollectionHierarchyManager(
            shop_url=args.shop_url,
            access_token=args.access_token,
            debug=args.debug
        )
        
        # Test authentication
        manager.test_auth()
        
        # Load existing collections
        manager.load_existing_collections()
        
        # Load hierarchy data
        manager.load_hierarchy_data(args.hierarchy_file)
        
        # Analyze matches
        matches = manager.analyze_matches()
        manager.generate_analysis_report(matches)
        
        if not args.analyze_only:
            # Apply hierarchy
            confirm = input("\n⚠️  Ready to apply hierarchy. Continue? (yes/no): ")
            if confirm.lower() == 'yes':
                manager.apply_hierarchy()
            else:
                print("❌ Operation cancelled")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Operation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {str(e)}")
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()