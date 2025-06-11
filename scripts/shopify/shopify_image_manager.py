"""
Shopify Image Management Module

This module handles all image-related operations including:
- Image upload, download, and deletion
- Duplicate detection (filename, size, content-based)
- Image analysis and validation
- File size comparison and deduplication
"""

import requests
import logging
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

try:
    from .shopify_base import ShopifyAPIBase, CREATE_MEDIA_MUTATION
except ImportError:
    from shopify_base import ShopifyAPIBase, CREATE_MEDIA_MUTATION

# GraphQL queries for image operations
GET_PRODUCT_IMAGES = """
query getProductImages($id: ID!) {
  product(id: $id) {
    id
    media(first: 50) {
      edges {
        node {
          ... on MediaImage {
            id
            image {
              originalSrc
              url
            }
          }
        }
      }
    }
  }
}
"""

DELETE_PRODUCT_MEDIA = """
mutation productDeleteMedia($productId: ID!, $mediaIds: [ID!]!) {
  productDeleteMedia(productId: $productId, mediaIds: $mediaIds) {
    deletedMediaIds
    deletedProductImageIds
    mediaUserErrors {
      field
      message
    }
  }
}
"""

class ShopifyImageManager(ShopifyAPIBase):
    """Manages image operations for Shopify products."""
    
    def __init__(self, shop_url: str, access_token: str, debug: bool = False):
        """Initialize the image manager."""
        super().__init__(shop_url, access_token, debug)
        self.logger = logging.getLogger(__name__)
    
    def get_product_images(self, product_id: str) -> List[Dict[str, str]]:
        """Get all images for a product."""
        try:
            result = self.execute_graphql(GET_PRODUCT_IMAGES, {'id': product_id})
            
            if 'errors' in result:
                self.logger.error(f"GraphQL errors: {result['errors']}")
                return []
            
            product_data = result.get('data', {}).get('product', {})
            if not product_data:
                self.logger.warning(f"Product not found: {product_id}")
                return []
            
            images = []
            media_edges = product_data.get('media', {}).get('edges', [])
            
            for edge in media_edges:
                node = edge.get('node', {})
                if 'image' in node:
                    image_data = node['image']
                    images.append({
                        'id': node['id'],
                        'originalSrc': image_data.get('originalSrc', image_data.get('url', ''))
                    })
            
            return images
            
        except Exception as e:
            self.logger.error(f"Failed to get product images: {str(e)}")
            return []
    
    def delete_product_media(self, product_id: str, media_ids: List[str]) -> bool:
        """Delete product media by IDs."""
        try:
            result = self.execute_graphql(DELETE_PRODUCT_MEDIA, {
                'productId': product_id,
                'mediaIds': media_ids
            })
            
            if 'errors' in result:
                self.logger.error(f"GraphQL errors: {result['errors']}")
                return False

            media_result = result.get('data', {}).get('productDeleteMedia', {})
            if media_result.get('mediaUserErrors'):
                self.logger.error(f"Media deletion errors: {media_result['mediaUserErrors']}")
                return False

            return True

        except Exception as e:
            self.logger.error(f"Failed to delete product media: {str(e)}")
            return False
    
    def create_product_media(self, media_input: Dict) -> bool:
        """Create media for a product using GraphQL mutation."""
        try:
            result = self.execute_graphql(CREATE_MEDIA_MUTATION, media_input)

            if 'errors' in result:
                self.logger.error(f"GraphQL errors: {result['errors']}")
                return False

            media_result = result.get('data', {}).get('productCreateMedia', {})
            if media_result.get('mediaUserErrors'):
                self.logger.error(f"Media creation errors: {media_result['mediaUserErrors']}")
                return False

            return True

        except Exception as e:
            self.logger.error(f"Failed to create product media: {str(e)}")
            return False
    
    def get_image_path_type(self, url: str) -> str:
        """Extract the path type from an image URL to identify the view type."""
        if 'etilize.com' in url:
            # Extract path component before filename
            path_parts = url.split('/')
            if len(path_parts) >= 2:
                path_type = path_parts[-2]  # e.g., "Front", "Left", "Alternate-Image1"
                return path_type
        return "unknown"
    
    def get_image_file_size(self, url: str) -> Optional[int]:
        """Get the file size of an image from its URL."""
        try:
            # Make a HEAD request to get file size without downloading the full image
            response = requests.head(url, timeout=10, allow_redirects=True)
            if response.status_code == 200:
                content_length = response.headers.get('content-length')
                if content_length:
                    return int(content_length)
            return None
        except Exception as e:
            self.logger.debug(f"Failed to get file size for {url}: {str(e)}")
            return None
    
    def get_image_id_from_url(self, url: str) -> str:
        """Extract image ID from Etilize URL to identify same image content."""
        if 'etilize.com' in url:
            # Extract the numeric ID from URLs like: https://content.etilize.com/Front/1066665382.jpg
            parts = url.split('/')
            if len(parts) >= 1:
                filename = parts[-1].split('?')[0]  # Remove query params
                # Extract numeric part (without extension)
                base_name = filename.split('.')[0]
                # Handle cases like "1066665382" or other patterns
                if base_name.isdigit():
                    return base_name
        return url.split('/')[-1].split('?')[0]  # Fallback to filename
    
    def is_legitimate_alternate_view(self, new_url: str, existing_urls: List[str]) -> bool:
        """
        Determine if a new image URL represents a legitimate alternate view
        vs a duplicate of an existing image.
        """
        # First check: if exact URL already exists, it's definitely a duplicate
        new_normalized = new_url.split('?')[0]
        existing_normalized = [url.split('?')[0] for url in existing_urls]
        if new_normalized in existing_normalized:
            return False
        
        # Second check: same image content (same image ID from Etilize)
        new_image_id = self.get_image_id_from_url(new_url)
        existing_image_ids = [self.get_image_id_from_url(url) for url in existing_urls]
        
        # If this image ID already exists, check if it's a different view
        if new_image_id in existing_image_ids:
            new_path_type = self.get_image_path_type(new_url)
            existing_path_types = [self.get_image_path_type(url) for url in existing_urls 
                                 if self.get_image_id_from_url(url) == new_image_id]
            
            # If it's the same image ID but different path type, it's a legitimate alternate view
            if new_path_type not in existing_path_types:
                # Known legitimate path types for product images
                legitimate_paths = {
                    'Front', 'Left', 'Right', 'Back', 'Top', 'Bottom',
                    'Life-Style', 'Lifestyle', 'Detail', 'Close-up',
                    'Alternate-Image1', 'Alternate-Image2', 'Alternate-Image3', 
                    'Alternate-Image4', 'Alternate-Image5', 'Alternate-Image6',
                    'Alternate-Image7', 'Alternate-Image8', 'Alternate-Image9'
                }
                
                if new_path_type in legitimate_paths:
                    return True
            
            # Same image ID and same (or unknown) path type = duplicate
            return False
        
        # Different image ID = definitely a different image
        return True
    
    def find_duplicate_images_by_size(self, images: List[Dict]) -> List[List[Dict]]:
        """Find duplicate images by comparing file sizes."""
        print(f"    🔍 Analyzing {len(images)} images for size-based duplicates...")
        
        # Group images by file size
        size_groups = defaultdict(list)
        
        for img in images:
            url = img['originalSrc']
            file_size = self.get_image_file_size(url)
            
            if file_size is not None:
                size_groups[file_size].append(img)
            else:
                self.logger.debug(f"Could not get file size for: {url}")
        
        # Find groups with multiple images (potential duplicates)
        duplicate_groups = []
        for file_size, imgs in size_groups.items():
            if len(imgs) > 1:
                # Further validation: check if these are likely the same image
                validated_duplicates = []
                for img in imgs:
                    filename = img['originalSrc'].split('/')[-1].split('?')[0]
                    # Additional checks can be added here (e.g., similar filenames)
                    validated_duplicates.append(img)
                
                if len(validated_duplicates) > 1:
                    duplicate_groups.append(validated_duplicates)
                    print(f"    📸 Found {len(validated_duplicates)} images with identical size: {file_size} bytes")
        
        return duplicate_groups
    
    def manage_product_images(self, product_id: str, new_image_urls: List[str], 
                            handle: str, force_update: bool = False, 
                            cleanup_only: bool = False) -> None:
        """
        Manage images for a product - avoid duplicates and handle updates.
        
        Args:
            product_id: Shopify product ID
            new_image_urls: List of new image URLs to potentially add
            handle: Product handle for logging
            force_update: Force image processing even if no changes detected
            cleanup_only: Only run cleanup, don't add new images
        """
        try:
            # Get current images
            existing_images = self.get_product_images(product_id)
            existing_urls = {img['originalSrc'].split('?')[0] for img in existing_images}
            
            print(f"    🖼️  Managing images for product: {handle}")
            print(f"    📊 Current images: {len(existing_images)}")
            
            if cleanup_only:
                print(f"    🧹 Cleanup mode: processing existing images only")
            elif not new_image_urls:
                print(f"    🖼️  No new images to process")
                if len(existing_images) <= 1:
                    return
            
            # If not forcing update and not in cleanup mode, check if we actually have new images to add
            if not force_update and not cleanup_only and new_image_urls:
                print(f"    🔍 Checking for new images to add:")
                print(f"    📊 Existing images: {len(existing_images)}")
                print(f"    📊 New images from CSV: {len(new_image_urls)}")
                
                # Check each new image to see if it's truly new/different
                has_new_content = False
                for new_url in new_image_urls:
                    new_normalized = new_url.split('?')[0]
                    
                    # Check if exact URL already exists
                    if new_normalized in existing_urls:
                        continue
                    
                    # Check if this represents new image content
                    existing_urls_list = list(existing_urls)
                    if self.is_legitimate_alternate_view(new_normalized, existing_urls_list):
                        has_new_content = True
                        break
                
                if not has_new_content:
                    print(f"    🖼️  No new images to add, skipping image processing")
                    return
                else:
                    print(f"    🖼️  Found new images to add, proceeding with update")

            # Process images for duplicates and determine what to add/remove
            self._process_images(product_id, existing_images, new_image_urls or [], 
                               handle, cleanup_only)

        except Exception as e:
            print(f"    ❌ Failed to manage images: {str(e)}")
            self.logger.error(f"Failed to manage images for product {handle}: {str(e)}")
    
    def _process_images(self, product_id: str, existing_images: List[Dict], 
                       new_image_urls: List[str], handle: str, cleanup_only: bool) -> None:
        """Process images for duplicates and handle additions/removals."""
        # Find duplicates to remove
        duplicates_to_remove = []
        
        # Find filename-based duplicates
        existing_by_filename = {}
        for img in existing_images:
            filename = img['originalSrc'].split('/')[-1].split('?')[0]
            if filename in existing_by_filename:
                if not isinstance(existing_by_filename[filename], list):
                    existing_by_filename[filename] = [existing_by_filename[filename]]
                existing_by_filename[filename].append(img)
            else:
                existing_by_filename[filename] = img
        
        for filename, existing_item in existing_by_filename.items():
            if isinstance(existing_item, list) and len(existing_item) > 1:
                # Keep the first one, remove the rest
                for img in existing_item[1:]:
                    duplicates_to_remove.append(img['id'])
                print(f"    🗑️  Found {len(existing_item)-1} filename duplicate(s) of: {filename}")

        # Always check for size-based duplicates among existing images
        if len(existing_images) > 1:  # Only check if there are multiple images
            size_duplicate_groups = self.find_duplicate_images_by_size(existing_images)
            for duplicate_group in size_duplicate_groups:
                # Keep the first image (usually oldest), remove the rest
                for img in duplicate_group[1:]:
                    if img['id'] not in duplicates_to_remove:  # Avoid duplicate removals
                        duplicates_to_remove.append(img['id'])
                        filename = img['originalSrc'].split('/')[-1].split('?')[0]
                        print(f"    🗑️  Found size-based duplicate: {filename}")

        # Remove duplicates
        if duplicates_to_remove:
            print(f"    🗑️  Removing {len(duplicates_to_remove)} duplicate images...")
            success = self.delete_product_media(product_id, duplicates_to_remove)
            if success:
                print(f"    ✅ Successfully removed {len(duplicates_to_remove)} duplicates")
            else:
                print(f"    ❌ Failed to remove some duplicates")

        # Add new images (skip in cleanup_only mode)
        if new_image_urls and not cleanup_only:
            images_to_add = self._filter_new_images(new_image_urls, existing_images)
            
            if images_to_add:
                print(f"    🖼️  Adding {len(images_to_add)} new images...")
                for idx, image_url in enumerate(images_to_add, 1):
                    try:
                        filename = image_url.split('/')[-1].split('?')[0]
                        print(f"    🖼️  Adding image {idx}/{len(images_to_add)}: {filename}")
                        media_input = {
                            'media': [{
                                'alt': 'Product Image',
                                'mediaContentType': 'IMAGE',
                                'originalSource': image_url
                            }],
                            'productId': product_id
                        }
                        self.create_product_media(media_input)
                        print(f"    ✅ Image {idx} added successfully")
                    except Exception as e:
                        print(f"    ❌ Failed to add image {idx}: {str(e)}")
                        self.logger.error(f"Failed to add image to product {handle}: {e}")
                        continue
            else:
                print(f"    ✅ All images already exist, no new images to add")
        elif cleanup_only:
            print(f"    🧹 Cleanup complete")
    
    def _filter_new_images(self, new_image_urls: List[str], 
                          existing_images: List[Dict]) -> List[str]:
        """Filter new image URLs to only include truly new/different images."""
        existing_urls = {img['originalSrc'].split('?')[0] for img in existing_images}
        images_to_add = []
        
        for url in new_image_urls:
            normalized_url = url.split('?')[0]
            
            # Skip exact URL matches
            if normalized_url in existing_urls:
                continue
            
            # Check file size to prevent duplicates
            new_file_size = self.get_image_file_size(url)
            is_size_duplicate = False
            
            if new_file_size is not None:
                for existing_img in existing_images:
                    existing_size = self.get_image_file_size(existing_img['originalSrc'])
                    if existing_size == new_file_size:
                        is_size_duplicate = True
                        existing_filename = existing_img['originalSrc'].split('/')[-1].split('?')[0]
                        filename = normalized_url.split('/')[-1]
                        print(f"    ⏭️  Skipping: {filename} (same file size as {existing_filename})")
                        break
            
            if not is_size_duplicate:
                images_to_add.append(url)
                filename = normalized_url.split('/')[-1]
                print(f"    ➕ Will add new image: {filename}")
        
        return images_to_add