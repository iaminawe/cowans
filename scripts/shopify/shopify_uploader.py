"""
Shopify Uploader Module using GraphQL API

This module handles uploading transformed product data to Shopify using the GraphQL Admin API.
Implements batched mutations, rate limiting, and smart error handling.
"""

import os
import time
import json
import logging
from typing import Dict, Optional, Any, List, Tuple
import requests
import random
import argparse
import csv
import sys
import hashlib
import html
from collections import defaultdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# GraphQL query to look up product by handle
GET_PRODUCT_BY_HANDLE = """
query getProductByHandle($handle: String!) {
  productByHandle(handle: $handle) {
    id
    handle
  }
}
"""

# GraphQL query to get detailed product data for comparison
GET_PRODUCT_DETAILS = """
query getProductDetails($handle: String!) {
  productByHandle(handle: $handle) {
    id
    handle
    title
    bodyHtml
    vendor
    productType
    tags
    variants(first: 1) {
      edges {
        node {
          id
          sku
          price
          inventoryQuantity
        }
      }
    }
    metafields(first: 10, namespace: "custom") {
      edges {
        node {
          namespace
          key
          value
        }
      }
    }
  }
}
"""

# GraphQL query to get product images
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

# GraphQL mutation to delete product media
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

# GraphQL mutation for creating/updating products
CREATE_PRODUCTS_MUTATION = """
mutation productCreate($input: ProductInput!) {
  productCreate(input: $input) {
    product {
      id
      title
      handle
      status
      variants(first: 1) {
        edges {
          node {
            id
            sku
          }
        }
      }
    }
    userErrors {
      field
      message
    }
  }
}
"""

UPDATE_PRODUCT_MUTATION = """
mutation productUpdate($input: ProductInput!) {
  productUpdate(input: $input) {
    product {
      id
      title
      handle
      status
      variants(first: 1) {
        edges {
          node {
            id
            sku
          }
        }
      }
    }
    userErrors {
      field
      message
    }
  }
}
"""

# GraphQL mutation for creating product variants
CREATE_VARIANT_MUTATION = """
mutation productVariantCreate($input: ProductVariantInput!) {
  productVariantCreate(input: $input) {
    productVariant {
      id
      sku
      price
    }
    userErrors {
      field
      message
    }
  }
}
"""

# GraphQL mutation for updating product variants
UPDATE_VARIANT_MUTATION = """
mutation productVariantUpdate($input: ProductVariantInput!) {
  productVariantUpdate(input: $input) {
    productVariant {
      id
      sku
      price
    }
    userErrors {
      field
      message
    }
  }
}
"""
# GraphQL mutation for adding images to products
CREATE_MEDIA_MUTATION = """
mutation productCreateMedia($media: [CreateMediaInput!]!, $productId: ID!) {
  productCreateMedia(media: $media, productId: $productId) {
    media {
      ... on MediaImage {
        id
        image {
          originalSrc
        }
      }
    }
    product {
      id
    }
    mediaUserErrors {
      field
      message
    }
  }
}
"""
# Column mappings for different data sources
# Map CSV column names to Shopify GraphQL fields
COLUMN_MAPPINGS = {
    'etilize': {
        'title': 'title',
        'url handle': 'handle',  # Match CSV column name
        'body_html': 'bodyHtml',
        'vendor': 'vendor',
        'product_type': 'productType',
        'tags': 'tags',
        'sku': 'newsku',  # Use newsku field (lowercase)
        'product image url': 'images',
        'price': 'price',
        'inventory_quantity': 'inventoryQuantity',
        'metafields': 'metafields'
    },
    'default': {
        'title': 'title',
        'url handle': 'handle',  # Match CSV column name
        'body_html': 'bodyHtml',
        'vendor': 'vendor',
        'product_type': 'productType',
        'tags': 'tags',
        'sku': 'newsku',  # Use newsku field (lowercase)
        'product image url': 'images',
        'price': 'price',
        'inventory_quantity': 'inventoryQuantity'
    }
}

class RateLimiter:
    """Advanced rate limiter for GraphQL API requests."""
    def __init__(self):
        self.calls_per_second = 2.0  # Two requests per second (Shopify allows 2/sec for GraphQL)
        self.min_delay = 0.5  # Minimum 0.5 seconds between requests
        self.backoff_factor = 1.5  # More gradual backoff
        self.max_backoff = 30.0  # Maximum 30 seconds backoff
        self.jitter_range = 0.2  # Reduced jitter for faster processing
        self.last_call_time = 0.0
        self.consecutive_429s = 0
        self.logger = logging.getLogger(__name__)

    def calculate_delay(self) -> float:
        """Calculate delay needed based on rate limits and backoff."""
        current_time = time.time()
        elapsed = current_time - self.last_call_time
        
        if self.consecutive_429s > 0:
            backoff = min(
                self.min_delay * (self.backoff_factor ** self.consecutive_429s),
                self.max_backoff
            )
        else:
            backoff = self.min_delay

        jitter = random.uniform(0, self.jitter_range)
        return max(backoff - elapsed + jitter, 0)

    def wait(self) -> None:
        """Wait appropriate time between API calls."""
        delay = self.calculate_delay()
        if delay > 0:
            if self.consecutive_429s > 0:
                self.logger.warning(f"Rate limited. Waiting {delay:.1f}s (attempt {self.consecutive_429s})...")
            else:
                self.logger.debug(f"Rate limiting delay: {delay:.1f}s")
            time.sleep(delay)
        self.last_call_time = time.time()

    def record_success(self) -> None:
        """Record successful API call."""
        self.consecutive_429s = 0

    def record_rate_limit(self) -> None:
        """Record rate limit hit."""
        self.consecutive_429s += 1

class ShopifyUploader:
    """Handles product data uploads to Shopify using GraphQL."""

    def __init__(
        self,
        shop_url: str,
        access_token: str,
        api_version: str = "2024-10",
        batch_size: int = 25,
        max_workers: int = 1,
        timeout: float = 30.0,
        logger: Optional[logging.Logger] = None,
        rate_limiter: Optional[RateLimiter] = None,
        debug: bool = False,
        data_source: str = 'default',
        cleanup_duplicates: bool = False
    ):
        """Initialize Shopify uploader with API credentials."""
        if not all([shop_url, access_token]):
            raise ValueError("shop_url and access_token are required")
            
        self.shop_url = shop_url.strip()
        self.access_token = access_token.strip()  # Ensure token is stripped
        self.api_version = api_version.strip()
        
        # Clean up shop URL
        if not self.shop_url.endswith('myshopify.com'):
            if '.' not in self.shop_url:
                self.shop_url += '.myshopify.com'
            elif not self.shop_url.endswith('myshopify.com'):
                raise ValueError("shop_url must be a myshopify.com domain")
            
        # Ensure URL starts with https://
        if not self.shop_url.startswith('https://'):
            self.shop_url = f"https://{self.shop_url}"
            
        self.graphql_url = f"{self.shop_url}/admin/api/{self.api_version}/graphql.json"
        self.headers = {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": self.access_token
        }
        
        self.batch_size = batch_size
        self.logger = logger or logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG if debug else logging.INFO)
        
        # Debug: Log the constructed URL
        self.logger.debug(f"GraphQL URL: {self.graphql_url}")
        self.logger.debug(f"Shop URL: {self.shop_url}")
        self.logger.debug(f"API Version: {self.api_version}")
        self.rate_limiter = rate_limiter or RateLimiter()
        self.max_workers = max_workers
        self.timeout = timeout
        self.column_mapping = COLUMN_MAPPINGS.get(data_source, COLUMN_MAPPINGS['default'])
        self.cleanup_duplicates = cleanup_duplicates
        
        self.upload_metrics = {
            'total_products': 0,
            'successful_uploads': 0,
            'failed_uploads': 0,
            'skipped_uploads': 0,
            'retry_count': 0,
            'duplicates_cleaned': 0
        }

    def execute_graphql(self, query: str, variables: Dict, retry: bool = True) -> Dict:
        """Execute a GraphQL query/mutation with retry on auth failure."""
        self.rate_limiter.wait()
        
        try:
            response = requests.post(
                self.graphql_url,
                headers=self.headers,
                json={'query': query, 'variables': variables},
                timeout=self.timeout
            )
            
            if response.status_code == 429:
                self.rate_limiter.record_rate_limit()
                self.logger.warning("Rate limited by GraphQL API")
                time.sleep(int(response.headers.get('Retry-After', '5')))
                return self.execute_graphql(query, variables, retry)

            # Check for authentication errors and retry once
            if response.status_code == 401 and retry:
                self.logger.warning("Authentication failed. Please provide a valid Shopify access token and try again.")
                return {'errors': [{'message': 'Invalid Shopify access token.'}]}  # Return error
            
            response.raise_for_status()
            self.rate_limiter.record_success()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 404:
                self.logger.error(f"GraphQL endpoint not found. Please check your shop URL and API version.")
                return {'errors': [{'message': 'GraphQL endpoint not found. Please check your shop URL and API version.'}]}
            if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 401:
                 self.logger.error("Please provide a valid Shopify access token and try again.")
                 return {'errors': [{'message': 'Invalid Shopify access token.'}]}  # Return error
            self.logger.error(f"GraphQL request failed: {str(e)}")
            raise

    def get_product_by_handle(self, handle: str) -> Optional[str]:
        """Look up a product by its handle and return its ID if found."""
        try:
            result = self.execute_graphql(GET_PRODUCT_BY_HANDLE, {'handle': handle})
            
            if 'errors' in result:
                self.logger.error(f"GraphQL errors: {result['errors']}")
                return None

            product = result.get('data', {}).get('productByHandle')
            return product['id'] if product else None

        except Exception as e:
            self.logger.error(f"Failed to look up product by handle: {str(e)}")
            return None

    def get_product_images(self, product_id: str) -> List[Dict[str, str]]:
        """Get existing images for a product."""
        try:
            result = self.execute_graphql(GET_PRODUCT_IMAGES, {'id': product_id})
            
            if 'errors' in result:
                self.logger.error(f"GraphQL errors: {result['errors']}")
                return []

            product = result.get('data', {}).get('product', {})
            media_edges = product.get('media', {}).get('edges', [])
            
            images = []
            for edge in media_edges:
                node = edge.get('node', {})
                if 'image' in node:
                    images.append({
                        'id': node['id'],
                        'originalSrc': node['image']['originalSrc'],
                        'url': node['image']['url']
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

    def create_product_hash(self, product_data: Dict[str, Any]) -> str:
        """Create a hash of the core product data for change detection."""
        try:
            # Extract the core data that we care about for change detection
            input_data = product_data.get('input', {})
            
            hash_data = {
                'title': input_data.get('title', ''),
                'bodyHtml': input_data.get('bodyHtml', ''),
                'vendor': input_data.get('vendor', ''),
                'productType': input_data.get('productType', ''),
                'tags': sorted(input_data.get('tags', [])),  # Sort for consistent hashing
            }
            
            # Add metafields data
            metafields = input_data.get('metafields', [])
            if metafields:
                # Sort metafields by namespace+key for consistent hashing
                sorted_metafields = sorted(metafields, key=lambda x: f"{x.get('namespace', '')}.{x.get('key', '')}")
                hash_data['metafields'] = [
                    {
                        'namespace': mf.get('namespace', ''),
                        'key': mf.get('key', ''),
                        'value': mf.get('value', ''),
                        'type': mf.get('type', '')
                    }
                    for mf in sorted_metafields
                ]
            
            # Create hash from the data
            hash_string = json.dumps(hash_data, sort_keys=True, separators=(',', ':'))
            return hashlib.sha256(hash_string.encode()).hexdigest()[:16]  # Use first 16 chars
            
        except Exception as e:
            self.logger.debug(f"Failed to create product hash: {str(e)}")
            return ""

    def get_existing_product_hash(self, handle: str) -> str:
        """Get hash of existing product data in Shopify."""
        try:
            result = self.execute_graphql(GET_PRODUCT_DETAILS, {'handle': handle})
            
            if 'errors' in result:
                self.logger.debug(f"GraphQL errors getting product details: {result['errors']}")
                return ""

            product = result.get('data', {}).get('productByHandle')
            if not product:
                return ""
            
            # Create comparable hash data from existing product
            hash_data = {
                'title': product.get('title', ''),
                'bodyHtml': product.get('bodyHtml', ''),
                'vendor': product.get('vendor', ''),
                'productType': product.get('productType', ''),
                'tags': sorted(product.get('tags', [])),
            }
            
            # Add variant data
            variant_edges = product.get('variants', {}).get('edges', [])
            if variant_edges:
                variant_node = variant_edges[0].get('node', {})
                hash_data['variant'] = {
                    'sku': variant_node.get('sku', ''),
                    'price': variant_node.get('price', ''),
                    'inventoryQuantity': variant_node.get('inventoryQuantity', 0)
                }
            
            # Add metafields data
            metafield_edges = product.get('metafields', {}).get('edges', [])
            if metafield_edges:
                metafields = []
                for edge in metafield_edges:
                    node = edge.get('node', {})
                    metafields.append({
                        'namespace': node.get('namespace', ''),
                        'key': node.get('key', ''),
                        'value': node.get('value', ''),
                        'type': 'json' if node.get('key') == 'metadata' else 'single_line_text'
                    })
                # Sort metafields for consistent hashing
                hash_data['metafields'] = sorted(metafields, key=lambda x: f"{x['namespace']}.{x['key']}")
            
            # Create hash from the data
            hash_string = json.dumps(hash_data, sort_keys=True, separators=(',', ':'))
            return hashlib.sha256(hash_string.encode()).hexdigest()[:16]  # Use first 16 chars
            
        except Exception as e:
            self.logger.debug(f"Failed to get existing product hash: {str(e)}")
            return ""

    def has_product_changed(self, product_data: Dict[str, Any], handle: str) -> bool:
        """Check if product data has changed by comparing hashes."""
        try:
            new_hash = self.create_product_hash(product_data)
            existing_hash = self.get_existing_product_hash(handle)
            
            if not new_hash or not existing_hash:
                # If we can't generate hashes, assume it has changed
                return True
            
            changed = new_hash != existing_hash
            
            if self.logger.isEnabledFor(logging.DEBUG):
                self.logger.debug(f"Product {handle} hash comparison:")
                self.logger.debug(f"  New hash: {new_hash}")
                self.logger.debug(f"  Existing hash: {existing_hash}")
                self.logger.debug(f"  Changed: {changed}")
            
            return changed
            
        except Exception as e:
            self.logger.debug(f"Failed to compare product hashes: {str(e)}")
            return True  # If comparison fails, assume it has changed

    def manage_product_images(self, product_id: str, product_rows: List[Dict], handle: str, force_update: bool = False, cleanup_only: bool = False) -> None:
        """Manage images for a product - avoid duplicates and handle updates."""
        try:
            # Get current images
            existing_images = self.get_product_images(product_id)
            # Create a set of normalized URLs for comparison (remove query params and normalize)
            existing_urls = set()
            for img in existing_images:
                # Use both originalSrc and url for comparison, normalized
                original_url = img['originalSrc'].split('?')[0] if img['originalSrc'] else ''
                display_url = img['url'].split('?')[0] if img.get('url') else ''
                if original_url:
                    existing_urls.add(original_url)
                if display_url and display_url != original_url:
                    existing_urls.add(display_url)
            
            if self.logger.level <= logging.DEBUG:
                print(f"    🔍 Current images on product:")
                for i, img in enumerate(existing_images, 1):
                    print(f"    📸 Existing {i}: {img['originalSrc']}")
            
            # Extract unique new image URLs
            new_image_urls = []
            if not cleanup_only:
                for row in product_rows:
                    image_url = row.get('Product image URL', row.get('product image url', ''))
                    if image_url:
                        # Normalize the URL for comparison (remove query params)
                        normalized_url = image_url.split('?')[0]
                        if normalized_url not in existing_urls and image_url not in new_image_urls:
                            new_image_urls.append(image_url)
                            print(f"    📸 Found new image URL: {image_url}")
                        elif normalized_url in existing_urls:
                            print(f"    ⏭️  Skipping existing image URL: {image_url}")
                
                print(f"    📊 Total unique new images found: {len(new_image_urls)}")
            
            # If cleanup_only mode, we only care about removing duplicates
            if cleanup_only:
                print(f"    🧹 Cleanup mode: only checking for duplicate images")
                new_image_urls = []  # Don't add any new images in cleanup mode
            elif not new_image_urls:
                print(f"    🖼️  No images to process")
                return

            # If not forcing update and not in cleanup mode, check if we actually have new images to add
            if not force_update and not cleanup_only:
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

            # Create smarter mappings that distinguish between duplicates and legitimate alternate views
            existing_by_path = {}
            existing_by_filename = {}
            
            for img in existing_images:
                full_url = img['originalSrc'].split('?')[0]  # Remove query params
                filename = full_url.split('/')[-1]
                
                # Map by full path (to detect exact duplicates)
                existing_by_path[full_url] = img
                
                # Map by filename for alternate view detection
                if filename in existing_by_filename:
                    if not isinstance(existing_by_filename[filename], list):
                        existing_by_filename[filename] = [existing_by_filename[filename]]
                    existing_by_filename[filename].append(img)
                else:
                    existing_by_filename[filename] = img

            new_by_path = {}
            new_by_filename = {}
            
            for url in new_image_urls:
                normalized_url = url.split('?')[0]  # Remove query params
                filename = normalized_url.split('/')[-1]
                
                # Map by full path (to detect exact duplicates)
                new_by_path[normalized_url] = url
                
                # Map by filename but preserve path info for alternate views
                if filename in new_by_filename:
                    if not isinstance(new_by_filename[filename], list):
                        new_by_filename[filename] = [new_by_filename[filename]]
                    new_by_filename[filename].append(url)
                else:
                    new_by_filename[filename] = url

            # Find images to add using smarter duplicate detection
            images_to_add = []
            images_to_skip = []
            
            print(f"    🔍 Analyzing {len(new_by_path)} new images against {len(existing_by_path)} existing...")
            
            # Check each new image
            for normalized_url, url in new_by_path.items():
                filename = normalized_url.split('/')[-1]
                
                # First check: exact URL match (definite duplicate)
                if normalized_url in existing_by_path:
                    images_to_skip.append(url)
                    print(f"    ⏭️  Skipping: {filename} (exact URL already exists)")
                    continue
                
                # Second check: same filename with different paths (might be alternate views)
                filename_matches = existing_by_filename.get(filename, [])
                if not isinstance(filename_matches, list):
                    filename_matches = [filename_matches] if filename_matches else []
                
                if filename_matches:
                    # We have existing images with the same filename
                    existing_paths = [img['originalSrc'].split('?')[0] for img in filename_matches]
                    
                    # Check if this is a legitimate alternate view
                    is_alternate_view = self.is_legitimate_alternate_view(normalized_url, existing_paths)
                    
                    if is_alternate_view:
                        # Additional check: compare file sizes to ensure it's not the exact same image
                        new_file_size = self.get_image_file_size(url)
                        is_size_duplicate = False
                        
                        if new_file_size is not None:
                            for existing_match in filename_matches:
                                existing_size = self.get_image_file_size(existing_match['originalSrc'])
                                if existing_size == new_file_size:
                                    is_size_duplicate = True
                                    break
                        
                        if is_size_duplicate:
                            images_to_skip.append(url)
                            print(f"    ⏭️  Skipping: {filename} (same file size as existing image)")
                        else:
                            images_to_add.append(url)
                            path_type = self.get_image_path_type(normalized_url)
                            print(f"    ➕ Will add alternate view: {filename} ({path_type})")
                    else:
                        # Same filename but not a clear alternate view - skip to be safe
                        images_to_skip.append(url)
                        print(f"    ⏭️  Skipping: {filename} (potential duplicate, being conservative)")
                else:
                    # Completely new filename - check against all existing images by file size
                    new_file_size = self.get_image_file_size(url)
                    is_size_duplicate = False
                    
                    if new_file_size is not None:
                        for existing_img in existing_images:
                            existing_size = self.get_image_file_size(existing_img['originalSrc'])
                            if existing_size == new_file_size:
                                is_size_duplicate = True
                                existing_filename = existing_img['originalSrc'].split('/')[-1].split('?')[0]
                                print(f"    ⏭️  Skipping: {filename} (same file size as {existing_filename})")
                                break
                    
                    if not is_size_duplicate:
                        images_to_add.append(url)
                        print(f"    ➕ Will add new image: {filename}")
                    else:
                        images_to_skip.append(url)
            
            print(f"    📊 Result: {len(images_to_add)} to add, {len(images_to_skip)} to skip")

            # Find duplicate existing images (same filename, multiple instances)
            duplicates_to_remove = []
            for filename, existing_item in existing_by_filename.items():
                if isinstance(existing_item, list) and len(existing_item) > 1:
                    # Keep the first one, remove the rest
                    for img in existing_item[1:]:
                        duplicates_to_remove.append(img['id'])
                    print(f"    🗑️  Found {len(existing_item)-1} filename duplicate(s) of: {filename}")
                    self.upload_metrics['duplicates_cleaned'] += len(existing_item) - 1

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
                            self.upload_metrics['duplicates_cleaned'] += 1

            # Find images to remove (existing but filename not in new set) - skip in cleanup_only mode
            # For additional images mode, don't remove existing images - only add missing ones
            images_to_remove = []
            if not cleanup_only and force_update:
                # Only remove images if this is a full product update, not additional images
                # Check if we have titles - if no titles, this is additional images only
                has_titles = any(row.get('Title', row.get('title', '')).strip() for row in product_rows)
                if has_titles:
                    # This is a full product update - proceed with removal logic
                    new_by_filename_for_removal = {}
                    for url in new_image_urls:
                        filename = url.split('/')[-1].split('?')[0]  # Extract filename
                        new_by_filename_for_removal[filename] = url
                        
                    for filename, existing_item in existing_by_filename.items():
                        if filename not in new_by_filename_for_removal:
                            if isinstance(existing_item, list):
                                for img in existing_item:
                                    images_to_remove.append(img['id'])
                            else:
                                images_to_remove.append(existing_item['id'])
                # For additional images (no titles), don't remove any existing images

            # Remove duplicates and unwanted images
            all_removals = images_to_remove + duplicates_to_remove
            if all_removals:
                print(f"    🗑️  Removing {len(all_removals)} images...")
                success = self.delete_product_media(product_id, all_removals)
                if success:
                    print(f"    ✅ Successfully removed {len(all_removals)} images")
                else:
                    print(f"    ❌ Failed to remove some images")

            # Add new images (skip in cleanup_only mode)
            if images_to_add and not cleanup_only:
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
                        self.logger.debug(f"Successfully added image to product {handle}: {image_url}")
                    except Exception as e:
                        print(f"    ❌ Failed to add image {idx}: {str(e)}")
                        self.logger.error(f"Failed to add image to product {handle}: {e}")
                        continue
            elif not cleanup_only:
                print(f"    ✅ All images already exist, no new images to add")
            else:
                print(f"    🖼️  In cleanup-only mode, skipping image additions")

            # Summary
            if cleanup_only:
                if duplicates_to_remove:
                    print(f"    🧹 Cleanup complete: {len(duplicates_to_remove)} duplicates removed")
                else:
                    print(f"    🧹 Cleanup complete: no duplicates found")
            else:
                if images_to_add:
                    print(f"    📊 Summary: {len(images_to_add)} images added, {len(images_to_skip)} already existed")
                elif images_to_skip:
                    print(f"    ✅ All {len(images_to_skip)} additional images already exist on this product")
                else:
                    print(f"    📊 No additional images to process for this product")

        except Exception as e:
            print(f"    ❌ Failed to manage images: {str(e)}")
            self.logger.error(f"Failed to manage images for product {handle}: {str(e)}")

    def decode_html_entities(self, text: str) -> str:
        """Decode HTML entities in text to proper unicode characters."""
        if not text:
            return text
        return html.unescape(text)

    def map_row_to_product(self, row: Dict[str, str], row_num: int = 0) -> Dict[str, Any]:
        """Map CSV row to GraphQL product input."""
        try:
            # Get title and handle using exact CSV column names
            title = self.decode_html_entities(row.get('Title', row.get('title', '')).strip())
            handle = row.get('URL handle', row.get('url handle', '')).strip()  # Match CSV column name
            
            if not title:
                raise ValueError(f"Product title is required (row {row_num})")
            
            # Debug log available columns
            self.logger.debug(f"CSV columns: {list(row.keys())}")
            self.logger.debug(f"Using column mapping: {self.column_mapping}")
            
            # Map product data using exact CSV column names
            self.logger.debug("Mapping product data from CSV columns...")
            
            product_input = {
                'title': title,
                'bodyHtml': self.decode_html_entities(row.get('body_html', '')),
                'vendor': self.decode_html_entities(row.get('vendor', '')),
                'productType': self.decode_html_entities(row.get('product_type', '')),
                'tags': [self.decode_html_entities(t.strip()) for t in row.get('tags', '').split(',') if t.strip()]
            }
            
            # Always include handle for product identification
            if handle:
                product_input['handle'] = handle

            metafields_col = self.column_mapping.get('metafields')
            if metafields_col and metafields_col in row:
                try:
                    # Try to parse JSON, but don't fail if it's invalid
                    metafields_str = self.decode_html_entities(row[metafields_col].strip())
                    if metafields_str.startswith('{') and metafields_str.endswith('}'): 
                        try:
                            # Try JSON first, then evaluate as Python dict if needed
                            try:
                                metafields_data = json.loads(metafields_str)
                            except json.JSONDecodeError:
                                # If JSON fails, try to evaluate as Python dict (handles single quotes)
                                import ast
                                metafields_data = ast.literal_eval(metafields_str)
                            if isinstance(metafields_data, dict):
                                # Decode HTML entities in metafield values
                                decoded_metafields = {}
                                for k, v in metafields_data.items():
                                    if isinstance(v, str):
                                        decoded_metafields[k] = self.decode_html_entities(v)
                                    else:
                                        decoded_metafields[k] = v
                                # Map to custom.metadata field for the combined metafield
                                product_input['metafields'] = [
                                    {
                                        'namespace': 'custom',
                                        'key': 'metadata',
                                        'value': json.dumps(decoded_metafields),
                                        'type': 'json'
                                    }
                                ]
                                self.logger.info(f"Added custom.metadata JSON metafield for row {row_num}")
                        except (json.JSONDecodeError, ValueError, SyntaxError) as e:
                            self.logger.debug(f"Skipping invalid metafields data for row {row_num}: {str(e)}")
                except Exception as e:
                    self.logger.debug(f"Skipping metafields for row {row_num}: {str(e)}")
                    
            # Check for metafield columns and insert into product.metadata JSON
            metafield_columns = [
                'Metafield: custom.CWS_A[list.single_line_text]',
                'Metafield: custom.CWS_Catalog[list.single_line_text]', 
                'Metafield: custom.SPRC[list.single_line_text]'
            ]
            
            metadata_object = {}
            for col in metafield_columns:
                if col in row and row[col].strip():
                    # Extract the key name from the column (e.g., CWS_A from 'Metafield: custom.CWS_A[list.single_line_text]')
                    key = col.split('.')[1].split('[')[0]
                    metadata_object[key] = self.decode_html_entities(row[col].strip())
            
            # Also check for direct custom.metadata field in the CSV
            metadata_col = 'Metafield: custom.metadata[json]'
            if metadata_col in row and row[metadata_col].strip():
                try:
                    metadata_str = self.decode_html_entities(row[metadata_col].strip())
                    # Parse existing JSON and merge with our metafield data
                    existing_metadata = json.loads(metadata_str)
                    if isinstance(existing_metadata, dict):
                        # Decode HTML entities in the existing metadata values
                        decoded_metadata = {}
                        for k, v in existing_metadata.items():
                            if isinstance(v, str):
                                decoded_metadata[k] = self.decode_html_entities(v)
                            else:
                                decoded_metadata[k] = v
                        metadata_object.update(decoded_metadata)
                except json.JSONDecodeError:
                    self.logger.warning(f"Invalid JSON in custom.metadata field for row {row_num}, using metafield data only")
                except Exception as e:
                    self.logger.debug(f"Error processing custom.metadata: {str(e)}")
            
            # Add the combined metadata if we have any data
            if metadata_object:
                if 'metafields' not in product_input:
                    product_input['metafields'] = []
                    
                product_input['metafields'].append({
                    'namespace': 'custom',
                    'key': 'metadata',
                    'value': json.dumps(metadata_object),
                    'type': 'json'
                })
                self.logger.info(f"Added custom.metadata with metafield data for row {row_num}: {list(metadata_object.keys())}")

            
            # Extract variant data separately
            variant_data = {
                'price': row.get('price', '0.00'),
                'sku': row.get(self.column_mapping.get('sku', 'sku'), row.get('sku', '')),
                'inventory_quantity': row.get('inventory_quantity', 0)
            }
            
            return {
                'input': product_input,
                'variant_data': variant_data
            }
        
        except Exception as e:
            self.logger.error(f"Error mapping row {row_num}: {str(e)}")
            raise

    
    def upload_product(self, product_data: Dict, product_id: Optional[str] = None, variant_data: Optional[Dict] = None) -> str:
        """Upload or update a single product using GraphQL mutation."""
        if product_id:
            # Update existing product
            product_data['input']['id'] = product_id
            result = self.execute_graphql(UPDATE_PRODUCT_MUTATION, product_data)
            operation = 'productUpdate'
        else:
            # Create new product
            result = self.execute_graphql(CREATE_PRODUCTS_MUTATION, product_data)
            operation = 'productCreate'

        if 'errors' in result:
            self.logger.error(f"GraphQL errors: {result['errors']}")
            raise Exception(f"GraphQL errors: {result['errors']}")

        product_result = result.get('data', {}).get(operation, {})
        if product_result.get('userErrors'):
            self.logger.error(f"Product {operation} errors: {product_result['userErrors']}")
            raise Exception(f"Product {operation} errors: {product_result['userErrors']}")

        created_product_id = product_result['product']['id']
        
        # Handle variant if provided
        if variant_data:
            try:
                self.manage_product_variant(created_product_id, variant_data, product_result['product'])
            except Exception as e:
                self.logger.warning(f"Failed to manage variant: {str(e)}")

        return created_product_id

    def manage_product_variant(self, product_id: str, variant_data: Dict, product_info: Dict) -> str:
        """Create or update a product variant."""
        try:
            # Check if product already has variants
            existing_variants = product_info.get('variants', {}).get('edges', [])
            
            if existing_variants:
                # Update existing variant
                variant_id = existing_variants[0]['node']['id']
                variant_input = {
                    'id': variant_id,
                    'price': variant_data.get('price', '0.00'),
                    'sku': variant_data.get('sku', ''),
                    'inventoryQuantities': [{
                        'availableQuantity': int(variant_data.get('inventory_quantity', 0)),
                        'locationId': "gid://shopify/Location/72344797441"
                    }]
                }
                result = self.execute_graphql(UPDATE_VARIANT_MUTATION, {'input': variant_input})
                operation = 'productVariantUpdate'
            else:
                # Create new variant
                variant_input = {
                    'productId': product_id,
                    'price': variant_data.get('price', '0.00'),
                    'sku': variant_data.get('sku', ''),
                    'inventoryQuantities': [{
                        'availableQuantity': int(variant_data.get('inventory_quantity', 0)),
                        'locationId': "gid://shopify/Location/72344797441"
                    }]
                }
                result = self.execute_graphql(CREATE_VARIANT_MUTATION, {'input': variant_input})
                operation = 'productVariantCreate'

            if 'errors' in result:
                raise Exception(f"GraphQL errors: {result['errors']}")

            variant_result = result.get('data', {}).get(operation, {})
            if variant_result.get('userErrors'):
                raise Exception(f"Variant {operation} errors: {variant_result['userErrors']}")

            return variant_result['productVariant']['id']
            
        except Exception as e:
            self.logger.error(f"Failed to manage variant: {str(e)}")
            raise

    def process_csv(self, csv_path: str, batch_size: int = 25, limit: Optional[int] = None, start_from: Optional[int] = None) -> None:
        """Process product data from CSV file and upload to Shopify."""
        try:
            if not os.path.exists(csv_path):
                raise FileNotFoundError(f"CSV file not found: {csv_path}")

            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                if not reader.fieldnames:
                    raise ValueError("CSV file is empty or has no headers")
                self.logger.debug(f"Found CSV headers: {', '.join(reader.fieldnames)}")
                
                # Filter out empty rows and validate as we read
                rows = []
                seen_handles = set()
                product_count = 0
                
                for idx, row in enumerate(reader, 1):
                    # Check if row has any non-empty values
                    if any(v.strip() for v in row.values()):
                        handle = row.get('URL handle', row.get('url handle', '')).strip()
                        title = row.get('Title', row.get('title', '')).strip()
                        
                        # For additional images, title might be empty but handle should exist
                        if not title and not handle:
                            self.logger.warning(f"Skipping row {idx}: Missing both title and handle")
                            self.upload_metrics['failed_uploads'] += 1
                            continue
                        elif not title and handle:
                            # This is likely an additional image for an existing product
                            self.logger.debug(f"Row {idx}: Additional image for product handle '{handle}'")
                        
                        # Count unique products for start_from logic
                        if handle not in seen_handles:
                            product_count += 1
                            seen_handles.add(handle)
                            
                            # Apply start_from filter - skip products before start_from
                            if start_from and product_count < start_from:
                                continue
                        
                        # If we already processed this handle and it was skipped due to start_from, continue skipping
                        if start_from and handle in seen_handles and product_count < start_from:
                            continue
                            
                        rows.append(row)
                    else:
                        self.logger.debug(f"Skipping empty row {idx}")
                
                if not rows:
                    raise ValueError("No valid product data found in CSV file")
                
                # Apply limit if specified (after start_from)
                if limit:
                    self.logger.info(f"Limiting import to {limit} products")
                    # Group by handle first to apply limit correctly
                    handle_groups = {}
                    for row in rows:
                        handle = row.get('URL handle', row.get('url handle', '')).strip()
                        if handle not in handle_groups:
                            handle_groups[handle] = []
                        handle_groups[handle].append(row)
                    
                    # Take only the first 'limit' unique products
                    limited_handles = list(handle_groups.keys())[:limit]
                    rows = []
                    for handle in limited_handles:
                        rows.extend(handle_groups[handle])
                
                # Recalculate unique handles after filtering
                final_handles = set()
                for row in rows:
                    handle = row.get('URL handle', row.get('url handle', '')).strip()
                    final_handles.add(handle)
                
                total_products = len(final_handles)
                self.logger.info(f"Processing {total_products} unique products from CSV")
                if start_from:
                    self.logger.info(f"Starting from product {start_from}")
                self.upload_metrics['total_products'] = total_products

                # Process in batches
                processed_products = 0
                for i in range(0, len(rows), batch_size):
                    batch = rows[i:i + batch_size]
                    batch_num = i//batch_size + 1
                    total_batches = (len(rows) + batch_size - 1)//batch_size
                    
                    print(f"\n📦 Processing batch {batch_num}/{total_batches} ({len(batch)} rows)", flush=True)
                    self.logger.info(f"Processing batch {batch_num}/{total_batches}")
                    
                    # Group rows by handle
                    handle_groups = {}
                    for row in batch:
                        handle = row.get('URL handle', row.get('url handle', '')).strip()
                        if handle in handle_groups:
                            handle_groups[handle].append(row)
                        else:
                            handle_groups[handle] = [row]
                    
                    # Process each unique product
                    batch_processed = 0
                    batch_total = len(handle_groups)
                    for handle, product_rows in handle_groups.items():
                        try:
                            batch_processed += 1
                            processed_products += 1
                            
                            # Progress indicator
                            progress_pct = (processed_products / total_products) * 100
                            print(f"  🔄 [{batch_processed}/{batch_total}] Processing '{handle}' (Overall: {processed_products}/{total_products} - {progress_pct:.1f}%)", flush=True)
                            
                            # Check if product exists
                            print(f"    🔍 Checking if product exists...")
                            product_id = self.get_product_by_handle(handle)
                            
                            # Check if this is only additional images (no title in any row)
                            has_title = any(row.get('Title', row.get('title', '')).strip() for row in product_rows)
                            
                            if not has_title:
                                # This is additional images only - no product data to update
                                print(f"    🖼️  This is additional images only for product {handle}")
                                print(f"    📸 Found {len(product_rows)} image rows")
                                
                                # Debug: show what image URLs we're finding
                                for i, row in enumerate(product_rows, 1):
                                    image_url = row.get('Product image URL', row.get('product image url', ''))
                                    print(f"    📸 Image {i}: {image_url}")
                                
                                if product_id:
                                    print(f"    🖼️  Adding additional images to existing product...")
                                    self.logger.info(f"Adding {len(product_rows)} additional images to existing product {handle}")
                                    # For additional images, don't force update - let it check for changes
                                    self.manage_product_images(product_id, product_rows, handle, force_update=False)
                                    self.upload_metrics['successful_uploads'] += 1
                                    print(f"    ✅ Successfully processed additional images!")
                                else:
                                    print(f"    ❌ Cannot add images: Product {handle} not found")
                                    self.logger.warning(f"Cannot add additional images: Product {handle} not found in Shopify")
                                    self.upload_metrics['failed_uploads'] += 1
                                continue
                            
                            # Get product data from first row with title
                            main_row = next((row for row in product_rows if row.get('Title', row.get('title', '')).strip()), product_rows[0])
                            mapped_data = self.map_row_to_product(main_row, i + 1)
                            product_data = {'input': mapped_data['input']}
                            variant_data = mapped_data.get('variant_data')
                            
                            if product_id:
                                # Product exists - check if it has changed
                                print(f"    🔍 Checking for changes...")
                                has_changed = self.has_product_changed(product_data, handle)
                                
                                if has_changed:
                                    print(f"    ✏️  Changes detected, updating product...")
                                    self.logger.info(f"Product {handle} has changes, updating")
                                    product_id = self.upload_product(product_data, product_id, variant_data)
                                    self.upload_metrics['successful_uploads'] += 1
                                    print(f"    ✅ Successfully updated product!")
                                    self.logger.debug(f"Successfully updated product with ID: {product_id}")
                                    
                                    # Manage images for updated product
                                    self.manage_product_images(product_id, product_rows, handle, force_update=True)
                                else:
                                    print(f"    ⏭️  No changes detected, skipping update")
                                    self.logger.debug(f"Product {handle} unchanged, skipping")
                                    self.upload_metrics['skipped_uploads'] += 1
                                    
                                    # Run duplicate cleanup for unchanged products if requested
                                    if self.cleanup_duplicates:
                                        print(f"    🧹 Running duplicate cleanup for unchanged product...")
                                        self.manage_product_images(product_id, product_rows, handle, force_update=False, cleanup_only=True)
                                    else:
                                        print(f"    🖼️  Skipping image processing (product unchanged)")
                            else:
                                print(f"    ➕ Creating new product...")
                                # Create new product
                                product_id = self.upload_product(product_data, None, variant_data)
                                self.upload_metrics['successful_uploads'] += 1
                                print(f"    ✅ Successfully created product!")
                                self.logger.debug(f"Successfully created product with ID: {product_id}")
                                
                                # Manage images for new product
                                if product_id:
                                    self.manage_product_images(product_id, product_rows, handle, force_update=True)
                        except Exception as e:
                            print(f"    ❌ Failed to process product '{handle}': {str(e)}")
                            self.logger.error(f"Failed to process product {handle}: {str(e)}")
                            self.upload_metrics['failed_uploads'] += 1
                            continue
                    
                    # Progress summary after batch
                    success_rate = (self.upload_metrics['successful_uploads'] / max(processed_products, 1)) * 100
                    print(f"  📊 Batch {batch_num} complete: {self.upload_metrics['successful_uploads']} updated, {self.upload_metrics['skipped_uploads']} skipped, {self.upload_metrics['failed_uploads']} failed ({success_rate:.1f}% update rate)")
                    
                    # Add delay between batches
                    if i + batch_size < len(rows):
                        print(f"  ⏱️  Waiting before next batch...")
                        self.rate_limiter.wait()
                
                # Final summary
                final_success_rate = (self.upload_metrics['successful_uploads'] / max(self.upload_metrics['total_products'], 1)) * 100
                efficiency_rate = ((self.upload_metrics['successful_uploads'] + self.upload_metrics['skipped_uploads']) / max(self.upload_metrics['total_products'], 1)) * 100
                print(f"\n🎉 Import Complete!")
                print(f"📊 Final Results:")
                print(f"   Total products: {self.upload_metrics['total_products']}")
                print(f"   ✅ Updated: {self.upload_metrics['successful_uploads']}")
                print(f"   ⏭️  Skipped (no changes): {self.upload_metrics['skipped_uploads']}")
                print(f"   ❌ Failed: {self.upload_metrics['failed_uploads']}")
                print(f"   🧹 Duplicates cleaned: {self.upload_metrics['duplicates_cleaned']}")
                print(f"   📈 Update rate: {final_success_rate:.1f}%")
                print(f"   ⚡ Efficiency rate: {efficiency_rate:.1f}% (updated + skipped)")
                print(f"   🔄 Retries: {self.upload_metrics['retry_count']}")
                
                self.logger.info(
                    f"Import complete. Metrics:\n"
                    f"Total products: {self.upload_metrics['total_products']}\n"
                    f"Updated: {self.upload_metrics['successful_uploads']}\n"
                    f"Skipped: {self.upload_metrics['skipped_uploads']}\n"
                    f"Failed: {self.upload_metrics['failed_uploads']}\n"
                    f"Duplicates cleaned: {self.upload_metrics['duplicates_cleaned']}\n"
                    f"Retries: {self.upload_metrics['retry_count']}"
                )
        except Exception as e:
            self.logger.error(f"Fatal error processing CSV: {str(e)}")
            raise

    def create_product_media(self, media_input: Dict) -> None:
        """Create media for a product using GraphQL mutation."""
        try:
            result = self.execute_graphql(CREATE_MEDIA_MUTATION, media_input)

            if 'errors' in result:
                self.logger.error(f"GraphQL errors: {result['errors']}")
                raise Exception(f"GraphQL errors: {result['errors']}")

            media_result = result.get('data', {}).get('productCreateMedia', {})
            if media_result.get('mediaUserErrors'):
                self.logger.error(f"Media creation errors: {media_result['mediaUserErrors']}")
                raise Exception(f"Media creation errors: {media_result['mediaUserErrors']}")

        except Exception as e:
            self.logger.error(f"Failed to create product media: {str(e)}")
            raise

    def test_auth(self) -> None:
        """Test Shopify API authentication."""
        try:
            response = requests.get(
                f"{self.shop_url}/admin/api/{self.api_version}/shop.json",
                headers=self.headers,
                timeout=self.timeout
            )
            response.raise_for_status()
            print("Token is valid")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Token validation failed: {e}")

def main() -> None:
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description='Upload products to Shopify from CSV using GraphQL API',
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    parser.add_argument('csv_file', type=str, help='Path to CSV file containing product data', nargs='?')
    parser.add_argument('--shop-url', required=True, help='Shopify shop URL (*.myshopify.com)')
    parser.add_argument('--access-token', required=True, help='Shopify Admin API access token')
    parser.add_argument('--batch-size', type=int, default=25, help='Batch size for uploads (default: 25)')
    parser.add_argument('--max-workers', type=int, default=1, help='Maximum number of concurrent uploads (default: 1)')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--data-source', choices=list(COLUMN_MAPPINGS.keys()), default='default',
                      help='Data source format (affects column mapping)')
    parser.add_argument('--limit', type=int, help='Limit number of products to import (for testing)')
    parser.add_argument('--start-from', type=int, help='Start processing from a specific product number (for resuming interrupted uploads)')
    parser.add_argument('--validate-token', action='store_true', help='Validate Shopify access token')
    parser.add_argument('--cleanup-duplicates', action='store_true', help='Force cleanup of duplicate images even for unchanged products')
    
    if len(sys.argv) == 1 or '--help' in sys.argv or '-h' in sys.argv:
        print("\nExample usage:")
        print("python shopify_uploader.py data/products.csv --shop-url store.myshopify.com --access-token TOKEN")
        print("python shopify_uploader.py data/products.csv --shop-url store.myshopify.com --access-token TOKEN --data-source etilize")
        print("python shopify_uploader.py data/products.csv --shop-url store.myshopify.com --access-token TOKEN --limit 10 --debug")
        print("python shopify_uploader.py data/products.csv --shop-url store.myshopify.com --access-token TOKEN --start-from 50")
        print("python shopify_uploader.py data/products.csv --shop-url store.myshopify.com --access-token TOKEN --start-from 100 --limit 50")
        print("python shopify_uploader.py --shop-url store.myshopify.com --access-token TOKEN --validate-token")
        sys.exit(1)
    
    args = parser.parse_args()
    
    try:
        # Format shop URL consistently
        shop_url = args.shop_url.strip().lower()
        if not shop_url.startswith('https://'):
            shop_url = f"https://{shop_url}"
        if '.' not in shop_url and not shop_url.endswith('myshopify.com'):
            shop_url += '.myshopify.com'
            
        uploader = ShopifyUploader(
            shop_url=shop_url,
            access_token=args.access_token.strip(),
            batch_size=args.batch_size,
            max_workers=args.max_workers,
            debug=args.debug,
            data_source=args.data_source,
            cleanup_duplicates=args.cleanup_duplicates
        )
        
        if args.validate_token:
            try:
                uploader.test_auth()
            except Exception as e:
                print(f"Shopify access token is invalid: {e}")
        elif args.csv_file:
            uploader.process_csv(args.csv_file, batch_size=args.batch_size, limit=args.limit, start_from=args.start_from)
        else:
            print("Error: CSV file is required unless --validate-token is used.")
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()