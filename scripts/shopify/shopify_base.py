"""
Shopify Base Classes and Utilities

This module contains base classes, constants, and utility functions
shared across the Shopify integration scripts.
"""

import os
import time
import json
import logging
import requests
import random
from typing import Dict, Optional, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# GraphQL mutations and queries
CREATE_PRODUCT_MUTATION = """
mutation createProduct($input: ProductInput!) {
  productCreate(input: $input) {
    product {
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

UPDATE_PRODUCT_MUTATION = """
mutation updateProduct($input: ProductInput!) {
  productUpdate(input: $input) {
    product {
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

CREATE_MEDIA_MUTATION = """
mutation productCreateMedia($media: [CreateMediaInput!]!, $productId: ID!) {
  productCreateMedia(media: $media, productId: $productId) {
    media {
      mediaContentType
      status
    }
    mediaUserErrors {
      field
      message
    }
  }
}
"""

# GraphQL mutations for product variants
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

# Ultra-fast update mutations - only update essential fields
ULTRA_FAST_PRODUCT_UPDATE = """
mutation ultraFastProductUpdate($input: ProductInput!) {
  productUpdate(input: $input) {
    product {
      id
      publishedAt
    }
    userErrors {
      field
      message
    }
  }
}
"""

# Mutation to publish/unpublish products from sales channels
PUBLISH_PRODUCT_MUTATION = """
mutation publishProduct($id: ID!, $input: [PublicationInput!]!) {
  publishablePublish(id: $id, input: $input) {
    publishable {
      ... on Product {
        id
      }
    }
    userErrors {
      field
      message
    }
  }
}
"""

UNPUBLISH_PRODUCT_MUTATION = """
mutation unpublishProduct($id: ID!, $input: [PublicationInput!]!) {
  publishableUnpublish(id: $id, input: $input) {
    publishable {
      ... on Product {
        id
      }
    }
    userErrors {
      field
      message
    }
  }
}
"""

ULTRA_FAST_VARIANT_UPDATE = """
mutation ultraFastVariantUpdate($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
  productVariantsBulkUpdate(productId: $productId, variants: $variants) {
    productVariants {
      id
      inventoryPolicy
    }
    userErrors {
      field
      message
    }
  }
}
"""

# Mutation to update inventory tracking
INVENTORY_ITEM_UPDATE = """
mutation inventoryItemUpdate($id: ID!, $input: InventoryItemInput!) {
  inventoryItemUpdate(id: $id, input: $input) {
    inventoryItem {
      id
      tracked
    }
    userErrors {
      field
      message
    }
  }
}
"""

# Column mappings for different data sources
COLUMN_MAPPINGS = {
    'default': {
        'title': 'Title',
        'handle': 'URL handle',
        'description': 'Description',
        'vendor': 'Vendor',
        'type': 'Type',
        'tags': 'Tags',
        'published': 'Published',
        'status': 'Status',
        'sku': 'SKU',
        'price': 'Price',
        'image_url': 'Product image URL'
    },
    'etilize': {
        'title': 'Title',
        'handle': 'URL handle',
        'description': 'Description',
        'vendor': 'Vendor',
        'type': 'Type',
        'tags': 'Tags',
        'published': 'Published',
        'status': 'Status',
        'sku': 'SKU',
        'price': 'Price',
        'image_url': 'Product image URL'
    }
}

class RateLimiter:
    """Manages API rate limiting for Shopify requests."""
    
    def __init__(self, turbo: bool = False, hyper: bool = False):
        self.last_request_time = 0
        self.bucket_size = 40  # Shopify bucket size
        self.leak_rate = 2     # Requests per second
        self.current_calls = 0
        self.consecutive_rate_limits = 0
        # Delay settings: normal=0.5s, turbo=0.1s, hyper=0.05s
        self.hyper = hyper
        if hyper:
            self.base_delay = 0.05  # 20 requests/second theoretical max
        elif turbo:
            self.base_delay = 0.1   # 10 requests/second theoretical max
        else:
            self.base_delay = 0.5   # 2 requests/second safe mode
        
    def calculate_delay(self) -> float:
        """Calculate the delay needed before next request."""
        now = time.time()
        time_since_last = now - self.last_request_time
        
        # Decrease current calls based on leak rate
        leaked_calls = time_since_last * self.leak_rate
        self.current_calls = max(0, self.current_calls - leaked_calls)
        
        # If we're near the bucket limit, add extra delay
        if self.hyper:
            # In hyper mode, be more aggressive
            if self.current_calls >= self.bucket_size * 0.9:  # 90% threshold
                return self.base_delay * 1.5
            else:
                return self.base_delay
        else:
            # Normal/turbo mode thresholds
            if self.current_calls >= self.bucket_size * 0.8:  # 80% threshold
                return self.base_delay * 2
            elif self.current_calls >= self.bucket_size * 0.6:  # 60% threshold
                return self.base_delay * 1.5
            else:
                return self.base_delay
    
    def wait(self) -> None:
        """Wait appropriate amount of time before next request."""
        delay = self.calculate_delay()
        
        # Add extra delay if we've hit rate limits recently
        if self.consecutive_rate_limits > 0:
            delay *= (1 + self.consecutive_rate_limits * 0.5)
        
        if delay > 0:
            logging.getLogger(__name__).debug(f"Rate limiting delay: {delay:.1f}s")
            time.sleep(delay)
        
        self.last_request_time = time.time()
        self.current_calls += 1
    
    def record_success(self) -> None:
        """Record a successful request."""
        self.consecutive_rate_limits = 0
    
    def record_rate_limit(self) -> None:
        """Record a rate limit hit."""
        self.consecutive_rate_limits += 1

class ShopifyAPIBase:
    """Base class for Shopify API operations."""
    
    def __init__(self, shop_url: str, access_token: str, debug: bool = False, turbo: bool = False, hyper: bool = False):
        """Initialize Shopify API client."""
        self.shop_url = shop_url.strip()
        self.access_token = access_token.strip()
        self.debug = debug
        self.turbo = turbo
        self.hyper = hyper
        
        # Ensure proper URL format
        if not self.shop_url.startswith('https://'):
            self.shop_url = f"https://{self.shop_url}"
        if not self.shop_url.endswith('.myshopify.com'):
            if '.' not in self.shop_url.split('://')[-1]:
                self.shop_url += '.myshopify.com'
        
        self.graphql_url = f"{self.shop_url}/admin/api/2024-10/graphql.json"
        self.rate_limiter = RateLimiter(turbo, hyper)
        self.logger = logging.getLogger(self.__class__.__name__)
        
        if debug:
            self.logger.setLevel(logging.DEBUG)
        
        self.logger.debug(f"Initialized with shop URL: {self.shop_url}")
        self.logger.debug(f"GraphQL URL: {self.graphql_url}")
        self.logger.debug(f"API Version: 2024-10")
    
    def execute_graphql(self, query: str, variables: Dict, retry: bool = True) -> Dict:
        """Execute a GraphQL query with rate limiting and error handling."""
        headers = {
            'Content-Type': 'application/json',
            'X-Shopify-Access-Token': self.access_token
        }
        
        payload = {
            'query': query,
            'variables': variables
        }
        
        max_retries = 3 if retry else 1
        
        for attempt in range(max_retries):
            try:
                self.rate_limiter.wait()
                
                response = requests.post(
                    self.graphql_url,
                    headers=headers,
                    json=payload,
                    timeout=30
                )
                
                if response.status_code == 429:
                    self.rate_limiter.record_rate_limit()
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt + random.uniform(0, 1)
                        self.logger.warning(f"Rate limited, waiting {wait_time:.1f}s...")
                        time.sleep(wait_time)
                        continue
                    else:
                        raise Exception("Rate limited after all retries")
                
                response.raise_for_status()
                self.rate_limiter.record_success()
                
                result = response.json()
                
                if 'errors' in result:
                    self.logger.error(f"GraphQL errors: {result['errors']}")
                
                return result
                
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt + random.uniform(0, 1)
                    self.logger.warning(f"Request failed, retrying in {wait_time:.1f}s: {str(e)}")
                    time.sleep(wait_time)
                    continue
                else:
                    self.logger.error(f"Request failed after {max_retries} attempts: {str(e)}")
                    raise Exception(f"Request failed: {str(e)}")
        
        raise Exception("Max retries exceeded")
    
    def test_auth(self) -> None:
        """Test if the API credentials are valid."""
        test_query = """
        query {
          shop {
            name
          }
        }
        """
        
        try:
            result = self.execute_graphql(test_query, {})
            if 'errors' in result:
                raise Exception(f"Authentication failed: {result['errors']}")
            
            shop_name = result.get('data', {}).get('shop', {}).get('name', 'Unknown')
            self.logger.info(f"Successfully authenticated with shop: {shop_name}")
            
        except Exception as e:
            raise Exception(f"Authentication test failed: {str(e)}")