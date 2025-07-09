#!/usr/bin/env python3
"""
Enhanced Shopify Collections Migration Script

This script creates collections with proper image uploads and descriptions.

Usage:
    python migrate_collections_with_uploads.py --shop-url new-store.myshopify.com --access-token TOKEN --input-dir old_shopify_complete_collections
"""

import os
import sys
import csv
import json
import argparse
import logging
import requests
import time
import base64
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

try:
    from .shopify_base import ShopifyAPIBase
except ImportError:
    from shopify_base import ShopifyAPIBase

# GraphQL mutations
CREATE_COLLECTION_MUTATION = """
mutation createCollection($input: CollectionInput!) {
  collectionCreate(input: $input) {
    collection {
      id
      handle
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

# Staged upload mutations for images
STAGED_UPLOADS_CREATE_MUTATION = """
mutation stagedUploadsCreate($input: [StagedUploadInput!]!) {
  stagedUploadsCreate(input: $input) {
    stagedTargets {
      url
      resourceUrl
      parameters {
        name
        value
      }
    }
    userErrors {
      field
      message
    }
  }
}
"""

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

class ShopifyCollectionMigratorEnhanced(ShopifyAPIBase):
    """Enhanced migrator with proper image uploads."""
    
    def __init__(self, shop_url: str, access_token: str, debug: bool = False):
        """Initialize the migrator."""
        super().__init__(shop_url, access_token, debug)
        self.logger = logging.getLogger(__name__)
        self.collection_mapping = {}
        
    def migrate_collections(self, input_dir: str) -> None:
        """Migrate all collections with images and descriptions."""
        print(f"🚀 Starting enhanced collection migration from: {input_dir}/")
        
        # Load all data files
        metadata = self._load_csv(os.path.join(input_dir, "collections_metadata.csv"))
        seo_data = self._load_csv(os.path.join(input_dir, "collections_seo.csv"))
        images_data = self._load_csv(os.path.join(input_dir, "collections_images.csv"))
        
        # Create lookup dictionaries
        seo_lookup = {row['collection_handle']: row for row in seo_data}
        images_lookup = {row['collection_handle']: row for row in images_data}
        
        # Download all images first
        print("\n📸 Downloading all collection images...")
        self._download_all_images(images_data)
        
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
                
                # Create the collection with description
                new_collection = self._create_collection_with_description(collection, seo)
                
                if new_collection:
                    created += 1
                    self.collection_mapping[handle] = new_collection['id']
                    
                    # Upload image if exists
                    if image.get('image_url'):
                        success = self._upload_collection_image(
                            new_collection['id'],
                            handle,
                            image.get('image_alt_text', ''),
                            image['image_url']
                        )
                        if success:
                            print(f"   ✅ Image uploaded successfully")
                    
                    print(f"   ✅ Created: {new_collection['handle']} (ID: {new_collection['id']})")
                    
                    # Show description status
                    if new_collection.get('description'):
                        print(f"   📝 Description: {new_collection['description'][:50]}...")
                else:
                    errors += 1
                    
                # Rate limiting
                time.sleep(0.5)
                
            except Exception as e:
                errors += 1
                self.logger.error(f"Error processing {collection.get('collection_handle')}: {str(e)}")
                print(f"   ❌ Error: {str(e)}")
        
        # Save mapping
        self._save_collection_mapping()
        
        # Generate product association CSV
        self._generate_product_association_csv(input_dir)
        
        print(f"\n✅ Migration Summary:")
        print(f"   📦 Collections created: {created}/{total}")
        print(f"   ❌ Errors: {errors}")
        print(f"   💾 Collection mapping saved: collection_mapping.json")
        print(f"   📄 Product associations saved: product_collection_associations.csv")
        
    def _create_collection_with_description(self, metadata: Dict, seo: Dict) -> Optional[Dict]:
        """Create a collection ensuring description is included."""
        try:
            # Prepare collection input
            collection_input = {
                'title': metadata['collection_title'],
                'handle': metadata['collection_handle'],
            }
            
            # IMPORTANT: Add description - check both fields
            description = metadata.get('description') or metadata.get('description_html', '')
            if description and description.strip():
                # Use HTML description if available, otherwise plain text
                if metadata.get('description_html'):
                    collection_input['descriptionHtml'] = metadata['description_html']
                else:
                    collection_input['descriptionHtml'] = f"<p>{description}</p>"
                
                print(f"   📝 Adding description: {description[:50]}...")
            
            # Add SEO
            if seo.get('seo_title') or seo.get('seo_description'):
                collection_input['seo'] = {}
                if seo.get('seo_title'):
                    collection_input['seo']['title'] = seo['seo_title']
                if seo.get('seo_description'):
                    collection_input['seo']['description'] = seo['seo_description']
            
            # Add sort order
            if metadata.get('sort_order'):
                valid_sort_orders = [
                    'ALPHA_ASC', 'ALPHA_DESC', 'BEST_SELLING',
                    'CREATED', 'CREATED_DESC', 'MANUAL',
                    'PRICE_ASC', 'PRICE_DESC'
                ]
                
                sort_order = metadata['sort_order']
                if sort_order in valid_sort_orders:
                    collection_input['sortOrder'] = sort_order
            
            # Add template suffix
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
                if any('already been taken' in err.get('message', '') for err in user_errors):
                    print(f"   ⚠️  Collection already exists, getting existing...")
                    return self._get_existing_collection(metadata['collection_handle'])
                else:
                    raise Exception(f"User errors: {user_errors}")
            
            return collection_result.get('collection')
            
        except Exception as e:
            self.logger.error(f"Error creating collection: {str(e)}")
            print(f"   ❌ Failed to create: {str(e)}")
            return None
    
    def _download_all_images(self, images_data: List[Dict]) -> None:
        """Download all images before processing."""
        os.makedirs('collection_images', exist_ok=True)
        
        for image_data in images_data:
            if image_data.get('image_url'):
                handle = image_data['collection_handle']
                image_path = f"collection_images/{handle}.jpg"
                
                if not os.path.exists(image_path):
                    try:
                        response = requests.get(image_data['image_url'], timeout=30)
                        response.raise_for_status()
                        
                        with open(image_path, 'wb') as f:
                            f.write(response.content)
                        
                        print(f"   ✅ Downloaded: {handle}")
                    except Exception as e:
                        print(f"   ⚠️  Failed to download {handle}: {str(e)}")
    
    def _upload_collection_image(self, collection_id: str, handle: str, alt_text: str, original_url: str) -> bool:
        """Upload image to Shopify using staged uploads."""
        try:
            # Check if local file exists
            local_path = f"collection_images/{handle}.jpg"
            if not os.path.exists(local_path):
                print(f"   ⚠️  Local image not found: {local_path}")
                return False
            
            print(f"   📤 Uploading image...")
            
            # Step 1: Create staged upload
            file_size = os.path.getsize(local_path)
            staged_input = [{
                'resource': 'COLLECTION_IMAGE',
                'filename': f"{handle}.jpg",
                'mimeType': 'image/jpeg',
                'fileSize': str(file_size)
            }]
            
            staged_result = self.execute_graphql(STAGED_UPLOADS_CREATE_MUTATION, {'input': staged_input})
            
            if 'errors' in staged_result:
                print(f"   ❌ Staged upload error: {staged_result['errors']}")
                return False
            
            staged_targets = staged_result.get('data', {}).get('stagedUploadsCreate', {}).get('stagedTargets', [])
            if not staged_targets:
                print(f"   ❌ No staged target returned")
                return False
            
            target = staged_targets[0]
            upload_url = target['url']
            resource_url = target['resourceUrl']
            parameters = {param['name']: param['value'] for param in target['parameters']}
            
            # Step 2: Upload file to staged URL
            with open(local_path, 'rb') as f:
                files = {'file': (f"{handle}.jpg", f, 'image/jpeg')}
                response = requests.post(upload_url, data=parameters, files=files)
                
                if response.status_code != 201:
                    print(f"   ❌ Upload failed: {response.status_code}")
                    return False
            
            # Step 3: Update collection with the uploaded image
            update_input = {
                'id': collection_id,
                'image': {
                    'src': resource_url,
                    'altText': alt_text or f"{handle} collection"
                }
            }
            
            update_result = self.execute_graphql(UPDATE_COLLECTION_IMAGE_MUTATION, {'input': update_input})
            
            if 'errors' in update_result:
                print(f"   ❌ Update error: {update_result['errors']}")
                return False
            
            return True
            
        except Exception as e:
            print(f"   ❌ Image upload error: {str(e)}")
            return False
    
    def _get_existing_collection(self, handle: str) -> Optional[Dict]:
        """Get existing collection by handle."""
        query = """
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
        
        try:
            result = self.execute_graphql(query, {'handle': handle})
            collection = result.get('data', {}).get('collectionByHandle')
            return collection
        except:
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
        
        products_data = self._load_csv(os.path.join(input_dir, "collections_products.csv"))
        
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


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description='Migrate Shopify collections with proper image uploads'
    )
    parser.add_argument('--shop-url', required=True, help='New Shopify store URL')
    parser.add_argument('--access-token', required=True, help='New store access token')
    parser.add_argument('--input-dir', required=True, help='Directory with exported collection data')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # Create migrator and run migration
        migrator = ShopifyCollectionMigratorEnhanced(
            shop_url=args.shop_url,
            access_token=args.access_token,
            debug=args.debug
        )
        
        migrator.migrate_collections(args.input_dir)
        
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