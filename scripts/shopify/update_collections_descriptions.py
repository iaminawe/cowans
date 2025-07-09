#!/usr/bin/env python3
"""
Update Collections Descriptions Script

This script updates existing collections with descriptions from the export data.

Usage:
    python update_collections_descriptions.py --shop-url store.myshopify.com --access-token TOKEN --input-file old_shopify_complete_collections/collections_metadata.csv
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

# GraphQL mutation for updating collection description
UPDATE_COLLECTION_DESCRIPTION_MUTATION = """
mutation collectionUpdate($input: CollectionInput!) {
  collectionUpdate(input: $input) {
    collection {
      id
      title
      description
      descriptionHtml
    }
    userErrors {
      field
      message
    }
  }
}
"""

# Query to get collection
GET_COLLECTION_QUERY = """
query getCollection($handle: String!) {
  collectionByHandle(handle: $handle) {
    id
    handle
    title
    description
    descriptionHtml
  }
}
"""

class ShopifyCollectionDescriptionUpdater(ShopifyAPIBase):
    """Updates collection descriptions."""
    
    def __init__(self, shop_url: str, access_token: str, debug: bool = False):
        """Initialize the updater."""
        super().__init__(shop_url, access_token, debug)
        self.logger = logging.getLogger(__name__)
        
    def update_collection_descriptions(self, metadata_csv: str) -> None:
        """Update collections with descriptions from CSV."""
        print(f"📝 Starting collection description updates from: {metadata_csv}")
        
        # Load metadata
        metadata = []
        with open(metadata_csv, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            metadata = list(reader)
        
        # Filter collections with descriptions
        collections_with_desc = [
            row for row in metadata 
            if row.get('description') or row.get('description_html')
        ]
        
        print(f"📊 Found {len(collections_with_desc)} collections with descriptions")
        
        updated = 0
        skipped = 0
        errors = 0
        
        for idx, meta_row in enumerate(collections_with_desc, 1):
            handle = meta_row['collection_handle']
            title = meta_row['collection_title']
            description = meta_row.get('description', '').strip()
            description_html = meta_row.get('description_html', '').strip()
            
            print(f"\n[{idx}/{len(collections_with_desc)}] {handle}")
            
            try:
                # Get collection
                collection = self._get_collection(handle)
                if not collection:
                    print(f"   ⚠️  Collection not found")
                    errors += 1
                    continue
                
                # Check if already has description
                existing_desc = collection.get('description', '').strip()
                if existing_desc and (existing_desc == description or existing_desc == description_html):
                    print(f"   ⏭️  Description already set")
                    skipped += 1
                    continue
                
                # Update description
                success = self._update_collection_description(
                    collection['id'],
                    description,
                    description_html
                )
                
                if success:
                    updated += 1
                    print(f"   ✅ Description updated successfully")
                    print(f"      {description[:80]}...")
                else:
                    errors += 1
                    print(f"   ❌ Failed to update description")
                
                # Rate limiting
                time.sleep(0.5)
                
            except Exception as e:
                errors += 1
                print(f"   ❌ Error: {str(e)}")
        
        print(f"\n✅ Description Update Summary:")
        print(f"   📝 Updated: {updated}")
        print(f"   ⏭️  Skipped: {skipped}")
        print(f"   ❌ Errors: {errors}")
    
    def _get_collection(self, handle: str) -> Optional[Dict]:
        """Get collection by handle."""
        try:
            result = self.execute_graphql(GET_COLLECTION_QUERY, {'handle': handle})
            
            if 'errors' in result:
                return None
            
            return result.get('data', {}).get('collectionByHandle')
            
        except Exception as e:
            self.logger.error(f"Error getting collection {handle}: {str(e)}")
            return None
    
    def _update_collection_description(self, collection_id: str, description: str, description_html: str) -> bool:
        """Update collection description."""
        try:
            # Prepare update input
            update_input = {
                'id': collection_id
            }
            
            # Use HTML description if available, otherwise plain text
            if description_html:
                update_input['descriptionHtml'] = description_html
            elif description:
                # Convert plain text to HTML
                update_input['descriptionHtml'] = f"<p>{description}</p>"
            else:
                return True  # Nothing to update
            
            result = self.execute_graphql(UPDATE_COLLECTION_DESCRIPTION_MUTATION, {'input': update_input})
            
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
            self.logger.error(f"Error updating description: {str(e)}")
            return False


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description='Update Shopify collections with descriptions'
    )
    parser.add_argument('--shop-url', required=True, help='Shopify store URL')
    parser.add_argument('--access-token', required=True, help='Shopify access token')
    parser.add_argument('--input-file', required=True, help='CSV file with metadata')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # Create updater and run
        updater = ShopifyCollectionDescriptionUpdater(
            shop_url=args.shop_url,
            access_token=args.access_token,
            debug=args.debug
        )
        
        updater.update_collection_descriptions(args.input_file)
        
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