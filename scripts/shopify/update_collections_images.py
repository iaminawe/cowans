#!/usr/bin/env python3
"""
Update Collections with Images Script

This script updates existing collections with images using direct URLs.

Usage:
    python update_collections_images.py --shop-url store.myshopify.com --access-token TOKEN --input-file old_shopify_complete_collections/collections_images.csv
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

# GraphQL mutation for updating collection with image URL
UPDATE_COLLECTION_IMAGE_MUTATION = """
mutation collectionUpdate($input: CollectionInput!) {
  collectionUpdate(input: $input) {
    collection {
      id
      title
      image {
        url
        altText
      }
    }
    userErrors {
      field
      message
    }
  }
}
"""

# Query to get collection by handle
GET_COLLECTION_QUERY = """
query getCollection($handle: String!) {
  collectionByHandle(handle: $handle) {
    id
    handle
    title
    image {
      url
    }
  }
}
"""

class ShopifyCollectionImageUpdater(ShopifyAPIBase):
    """Updates collection images using direct URLs."""
    
    def __init__(self, shop_url: str, access_token: str, debug: bool = False):
        """Initialize the updater."""
        super().__init__(shop_url, access_token, debug)
        self.logger = logging.getLogger(__name__)
        
    def update_collection_images(self, images_csv: str) -> None:
        """Update collections with images from CSV."""
        print(f"🖼️  Starting collection image updates from: {images_csv}")
        
        # Load image data
        images = []
        with open(images_csv, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            images = list(reader)
        
        print(f"📊 Found {len(images)} collections with images")
        
        updated = 0
        skipped = 0
        errors = 0
        
        for idx, image_data in enumerate(images, 1):
            handle = image_data['collection_handle']
            title = image_data['collection_title']
            image_url = image_data['image_url']
            alt_text = image_data.get('image_alt_text', '')
            
            if not image_url:
                skipped += 1
                continue
            
            print(f"\n[{idx}/{len(images)}] {handle}")
            
            try:
                # Get collection ID
                collection = self._get_collection(handle)
                if not collection:
                    print(f"   ⚠️  Collection not found")
                    errors += 1
                    continue
                
                # Check if already has image
                if collection.get('image') and collection['image'].get('url'):
                    print(f"   ⏭️  Already has image")
                    skipped += 1
                    continue
                
                # Update with image
                success = self._update_collection_image(
                    collection['id'],
                    image_url,
                    alt_text or f"{title} collection"
                )
                
                if success:
                    updated += 1
                    print(f"   ✅ Image updated successfully")
                else:
                    errors += 1
                    print(f"   ❌ Failed to update image")
                
                # Rate limiting
                time.sleep(0.5)
                
            except Exception as e:
                errors += 1
                print(f"   ❌ Error: {str(e)}")
        
        print(f"\n✅ Update Summary:")
        print(f"   🖼️  Updated: {updated}")
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
    
    def _update_collection_image(self, collection_id: str, image_url: str, alt_text: str) -> bool:
        """Update collection with image URL."""
        try:
            # Prepare update input
            update_input = {
                'id': collection_id,
                'image': {
                    'src': image_url,
                    'altText': alt_text
                }
            }
            
            result = self.execute_graphql(UPDATE_COLLECTION_IMAGE_MUTATION, {'input': update_input})
            
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
            self.logger.error(f"Error updating image: {str(e)}")
            return False


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description='Update Shopify collections with images'
    )
    parser.add_argument('--shop-url', required=True, help='Shopify store URL')
    parser.add_argument('--access-token', required=True, help='Shopify access token')
    parser.add_argument('--input-file', required=True, help='CSV file with image URLs')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # Create updater and run
        updater = ShopifyCollectionImageUpdater(
            shop_url=args.shop_url,
            access_token=args.access_token,
            debug=args.debug
        )
        
        updater.update_collection_images(args.input_file)
        
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