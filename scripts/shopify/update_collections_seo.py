#!/usr/bin/env python3
"""
Update Collections SEO Script

This script updates existing collections with SEO titles and descriptions.

Usage:
    python update_collections_seo.py --shop-url store.myshopify.com --access-token TOKEN --input-file old_shopify_complete_collections/collections_seo.csv
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

# GraphQL mutation for updating collection SEO
UPDATE_COLLECTION_SEO_MUTATION = """
mutation collectionUpdate($input: CollectionInput!) {
  collectionUpdate(input: $input) {
    collection {
      id
      title
      seo {
        title
        description
      }
    }
    userErrors {
      field
      message
    }
  }
}
"""

# Query to get collection with SEO
GET_COLLECTION_SEO_QUERY = """
query getCollection($handle: String!) {
  collectionByHandle(handle: $handle) {
    id
    handle
    title
    seo {
      title
      description
    }
  }
}
"""

class ShopifyCollectionSEOUpdater(ShopifyAPIBase):
    """Updates collection SEO data."""
    
    def __init__(self, shop_url: str, access_token: str, debug: bool = False):
        """Initialize the updater."""
        super().__init__(shop_url, access_token, debug)
        self.logger = logging.getLogger(__name__)
        
    def update_collection_seo(self, seo_csv: str) -> None:
        """Update collections with SEO data from CSV."""
        print(f"🔍 Starting collection SEO updates from: {seo_csv}")
        
        # Load SEO data
        seo_data = []
        with open(seo_csv, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            seo_data = list(reader)
        
        # Filter collections with SEO data
        collections_with_seo = [
            row for row in seo_data 
            if row.get('seo_title') or row.get('seo_description')
        ]
        
        print(f"📊 Found {len(collections_with_seo)} collections with SEO data")
        
        updated = 0
        skipped = 0
        errors = 0
        
        for idx, seo_row in enumerate(collections_with_seo, 1):
            handle = seo_row['collection_handle']
            title = seo_row['collection_title']
            seo_title = seo_row.get('seo_title', '').strip()
            seo_description = seo_row.get('seo_description', '').strip()
            
            print(f"\n[{idx}/{len(collections_with_seo)}] {handle}")
            
            try:
                # Get collection
                collection = self._get_collection(handle)
                if not collection:
                    print(f"   ⚠️  Collection not found")
                    errors += 1
                    continue
                
                # Check if already has same SEO
                existing_seo = collection.get('seo', {})
                if (existing_seo.get('title') == seo_title and 
                    existing_seo.get('description') == seo_description):
                    print(f"   ⏭️  SEO already up to date")
                    skipped += 1
                    continue
                
                # Update SEO
                success = self._update_collection_seo(
                    collection['id'],
                    seo_title,
                    seo_description
                )
                
                if success:
                    updated += 1
                    print(f"   ✅ SEO updated successfully")
                    if seo_title:
                        print(f"      Title: {seo_title[:50]}...")
                    if seo_description:
                        print(f"      Desc: {seo_description[:50]}...")
                else:
                    errors += 1
                    print(f"   ❌ Failed to update SEO")
                
                # Rate limiting
                time.sleep(0.5)
                
            except Exception as e:
                errors += 1
                print(f"   ❌ Error: {str(e)}")
        
        print(f"\n✅ SEO Update Summary:")
        print(f"   🔍 Updated: {updated}")
        print(f"   ⏭️  Skipped: {skipped}")
        print(f"   ❌ Errors: {errors}")
    
    def _get_collection(self, handle: str) -> Optional[Dict]:
        """Get collection by handle."""
        try:
            result = self.execute_graphql(GET_COLLECTION_SEO_QUERY, {'handle': handle})
            
            if 'errors' in result:
                return None
            
            return result.get('data', {}).get('collectionByHandle')
            
        except Exception as e:
            self.logger.error(f"Error getting collection {handle}: {str(e)}")
            return None
    
    def _update_collection_seo(self, collection_id: str, seo_title: str, seo_description: str) -> bool:
        """Update collection SEO data."""
        try:
            # Prepare update input
            update_input = {
                'id': collection_id,
                'seo': {}
            }
            
            # Only include non-empty values
            if seo_title:
                update_input['seo']['title'] = seo_title
            if seo_description:
                update_input['seo']['description'] = seo_description
                
            # Skip if no SEO data
            if not update_input['seo']:
                return True
            
            result = self.execute_graphql(UPDATE_COLLECTION_SEO_MUTATION, {'input': update_input})
            
            if 'errors' in result:
                self.logger.error(f"GraphQL errors: {result['errors']}")
                return False
            
            update_result = result.get('data', {}).get('collectionUpdate', {})
            user_errors = update_result.get('userErrors', [])
            
            if user_errors:
                self.logger.error(f"User errors: {user_errors}")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating SEO: {str(e)}")
            return False


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description='Update Shopify collections with SEO data'
    )
    parser.add_argument('--shop-url', required=True, help='Shopify store URL')
    parser.add_argument('--access-token', required=True, help='Shopify access token')
    parser.add_argument('--input-file', required=True, help='CSV file with SEO data')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # Create updater and run
        updater = ShopifyCollectionSEOUpdater(
            shop_url=args.shop_url,
            access_token=args.access_token,
            debug=args.debug
        )
        
        updater.update_collection_seo(args.input_file)
        
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