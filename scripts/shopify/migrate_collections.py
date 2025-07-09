#!/usr/bin/env python3
"""
Shopify Collections Migration Script

This script creates collections on a new Shopify site using exported data,
including downloading and uploading images, setting SEO data, and all metadata.

Usage:
    python migrate_collections.py --shop-url new-store.myshopify.com --access-token TOKEN --input-dir old_shopify_complete_collections
"""

import os
import sys
import csv
import json
import argparse
import logging
import requests
import time
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

try:
    from .shopify_base import ShopifyAPIBase
except ImportError:
    from shopify_base import ShopifyAPIBase

# GraphQL mutations for creating collections
CREATE_COLLECTION_MUTATION = """
mutation createCollection($input: CollectionInput!) {
  collectionCreate(input: $input) {
    collection {
      id
      handle
      title
    }
    userErrors {
      field
      message
    }
  }
}
"""

UPDATE_COLLECTION_IMAGE_MUTATION = """
mutation updateCollectionImage($input: CollectionInput!) {
  collectionUpdate(input: $input) {
    collection {
      id
      image {
        url
      }
    }
    userErrors {
      field
      message
    }
  }
}
"""

class ShopifyCollectionMigrator(ShopifyAPIBase):
    """Migrates collections to a new Shopify store."""
    
    def __init__(self, shop_url: str, access_token: str, debug: bool = False):
        """Initialize the migrator."""
        super().__init__(shop_url, access_token, debug)
        self.logger = logging.getLogger(__name__)
        self.collection_mapping = {}  # old_handle -> new_id mapping
        
    def migrate_collections(self, input_dir: str, images_dir: str = "collection_images") -> None:
        """Migrate all collections from exported data."""
        print(f"🚀 Starting collection migration from: {input_dir}/")
        
        # Create images directory
        os.makedirs(images_dir, exist_ok=True)
        
        # Load all data files
        metadata = self._load_csv(os.path.join(input_dir, "collections_metadata.csv"))
        seo_data = self._load_csv(os.path.join(input_dir, "collections_seo.csv"))
        images_data = self._load_csv(os.path.join(input_dir, "collections_images.csv"))
        
        # Create lookup dictionaries
        seo_lookup = {row['collection_handle']: row for row in seo_data}
        images_lookup = {row['collection_handle']: row for row in images_data}
        
        # Process each collection
        total = len(metadata)
        created = 0
        errors = 0
        
        print(f"\n📊 Found {total} collections to migrate")
        
        for idx, collection in enumerate(metadata, 1):
            try:
                handle = collection['collection_handle']
                print(f"\n[{idx}/{total}] Processing: {handle}")
                
                # Get SEO and image data
                seo = seo_lookup.get(handle, {})
                image = images_lookup.get(handle, {})
                
                # Create the collection
                new_collection = self._create_collection(collection, seo)
                
                if new_collection:
                    created += 1
                    self.collection_mapping[handle] = new_collection['id']
                    
                    # Download and attach image if exists
                    if image.get('image_url'):
                        self._attach_collection_image(
                            new_collection['id'], 
                            image['image_url'],
                            image.get('image_alt_text', ''),
                            images_dir
                        )
                    
                    print(f"   ✅ Created: {new_collection['handle']} (ID: {new_collection['id']})")
                else:
                    errors += 1
                    print(f"   ❌ Failed to create collection")
                    
                # Rate limiting
                time.sleep(0.5)  # Be gentle with the API
                
            except Exception as e:
                errors += 1
                self.logger.error(f"Error processing {collection.get('collection_handle')}: {str(e)}")
                print(f"   ❌ Error: {str(e)}")
        
        # Save mapping for product associations
        self._save_collection_mapping()
        
        # Generate product association CSV
        self._generate_product_association_csv(input_dir)
        
        print(f"\n✅ Migration Summary:")
        print(f"   📦 Collections created: {created}/{total}")
        print(f"   ❌ Errors: {errors}")
        print(f"   💾 Collection mapping saved: collection_mapping.json")
        print(f"   📄 Product associations saved: product_collection_associations.csv")
        
    def _create_collection(self, metadata: Dict, seo: Dict) -> Optional[Dict]:
        """Create a single collection."""
        try:
            # Prepare collection input
            collection_input = {
                'title': metadata['collection_title'],
                'handle': metadata['collection_handle'],
            }
            
            # Add description if exists
            if metadata.get('description'):
                collection_input['descriptionHtml'] = metadata.get('description_html', metadata['description'])
            
            # Add SEO if exists
            if seo.get('seo_title') or seo.get('seo_description'):
                collection_input['seo'] = {}
                if seo.get('seo_title'):
                    collection_input['seo']['title'] = seo['seo_title']
                if seo.get('seo_description'):
                    collection_input['seo']['description'] = seo['seo_description']
            
            # Add sort order
            if metadata.get('sort_order'):
                # The sort order from export is already in the correct format
                # Just pass it through directly
                valid_sort_orders = [
                    'ALPHA_ASC', 'ALPHA_DESC', 'BEST_SELLING',
                    'CREATED', 'CREATED_DESC', 'MANUAL',
                    'PRICE_ASC', 'PRICE_DESC'
                ]
                
                sort_order = metadata['sort_order']
                if sort_order in valid_sort_orders:
                    collection_input['sortOrder'] = sort_order
                else:
                    # Default to MANUAL for unknown values
                    collection_input['sortOrder'] = 'MANUAL'
            
            # Add template suffix if exists
            if metadata.get('template_suffix'):
                collection_input['templateSuffix'] = metadata['template_suffix']
            
            # Execute mutation
            variables = {'input': collection_input}
            result = self.execute_graphql(CREATE_COLLECTION_MUTATION, variables)
            
            if 'errors' in result:
                raise Exception(f"GraphQL errors: {result['errors']}")
            
            collection_result = result.get('data', {}).get('collectionCreate', {})
            
            # Check for user errors
            user_errors = collection_result.get('userErrors', [])
            if user_errors:
                # Check if collection already exists
                if any('already been taken' in err.get('message', '') for err in user_errors):
                    print(f"   ⚠️  Collection already exists, skipping...")
                    # Try to get existing collection ID
                    return self._get_existing_collection(metadata['collection_handle'])
                else:
                    raise Exception(f"User errors: {user_errors}")
            
            return collection_result.get('collection')
            
        except Exception as e:
            self.logger.error(f"Error creating collection: {str(e)}")
            return None
    
    def _get_existing_collection(self, handle: str) -> Optional[Dict]:
        """Get existing collection by handle."""
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
            collection = result.get('data', {}).get('collectionByHandle')
            return collection
        except:
            return None
    
    def _attach_collection_image(self, collection_id: str, image_url: str, alt_text: str, images_dir: str) -> None:
        """Download and attach image to collection."""
        try:
            print(f"   📸 Downloading image...")
            
            # Extract filename from URL
            filename = image_url.split('/')[-1].split('?')[0]
            if not filename:
                filename = f"{collection_id.split('/')[-1]}.jpg"
            
            filepath = os.path.join(images_dir, filename)
            
            # Download image
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()
            
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            print(f"   📤 Uploading image to Shopify...")
            
            # Upload to Shopify (using staged upload)
            image_url = self._upload_image_to_shopify(filepath)
            
            if image_url:
                # Update collection with image
                variables = {
                    'input': {
                        'id': collection_id,
                        'image': {
                            'src': image_url,
                            'altText': alt_text
                        }
                    }
                }
                
                result = self.execute_graphql(UPDATE_COLLECTION_IMAGE_MUTATION, variables)
                
                if 'errors' not in result:
                    print(f"   ✅ Image attached successfully")
                else:
                    print(f"   ⚠️  Failed to attach image: {result['errors']}")
            
        except Exception as e:
            print(f"   ⚠️  Image processing failed: {str(e)}")
    
    def _upload_image_to_shopify(self, filepath: str) -> Optional[str]:
        """Upload image to Shopify and return URL."""
        # This is a simplified version - in production you'd use staged uploads
        # For now, we'll note that the image needs to be uploaded
        print(f"   ℹ️  Image saved locally: {filepath}")
        print(f"   ℹ️  Manual upload required for now")
        return None
    
    def _load_csv(self, filepath: str) -> List[Dict]:
        """Load CSV file into list of dictionaries."""
        data = []
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                data.append(row)
        return data
    
    def _save_collection_mapping(self) -> None:
        """Save collection handle to ID mapping."""
        with open('collection_mapping.json', 'w') as f:
            json.dump(self.collection_mapping, f, indent=2)
    
    def _generate_product_association_csv(self, input_dir: str) -> None:
        """Generate CSV for product-collection associations."""
        print("\n📄 Generating product association CSV...")
        
        # Load product data
        products_data = self._load_csv(os.path.join(input_dir, "collections_products.csv"))
        
        # Create simplified CSV
        with open('product_collection_associations.csv', 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['product_handle', 'collection_handle', 'collection_id', 'position'])
            
            for row in products_data:
                collection_handle = row['collection_handle']
                new_collection_id = self.collection_mapping.get(collection_handle, '')
                
                if new_collection_id:
                    writer.writerow([
                        row['product_handle'],
                        collection_handle,
                        new_collection_id,
                        row.get('position', '')
                    ])
        
        print(f"   ✅ Generated associations for {len(products_data)} product-collection pairs")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description='Migrate Shopify collections to a new store'
    )
    parser.add_argument('--shop-url', required=True, help='New Shopify store URL')
    parser.add_argument('--access-token', required=True, help='New store access token')
    parser.add_argument('--input-dir', required=True, help='Directory with exported collection data')
    parser.add_argument('--images-dir', default='collection_images', help='Directory for downloaded images')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # Create migrator and run migration
        migrator = ShopifyCollectionMigrator(
            shop_url=args.shop_url,
            access_token=args.access_token,
            debug=args.debug
        )
        
        migrator.migrate_collections(args.input_dir, args.images_dir)
        
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