"""
Shopify Product Management Module

This module handles all product-related operations including:
- Product creation and updates
- Product data transformation and validation
- Product comparison and change detection
- Data mapping from CSV to Shopify format
"""

import hashlib
import html
import json
import logging
from typing import Dict, Optional, Any, List

try:
    from .shopify_base import ShopifyAPIBase, CREATE_PRODUCT_MUTATION, UPDATE_PRODUCT_MUTATION, COLUMN_MAPPINGS
except ImportError:
    from shopify_base import ShopifyAPIBase, CREATE_PRODUCT_MUTATION, UPDATE_PRODUCT_MUTATION, COLUMN_MAPPINGS

# GraphQL queries for product operations
GET_PRODUCT_BY_HANDLE = """
query getProductByHandle($handle: String!) {
  productByHandle(handle: $handle) {
    id
    handle
  }
}
"""

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

class ShopifyProductManager(ShopifyAPIBase):
    """Manages product operations for Shopify."""
    
    def __init__(self, shop_url: str, access_token: str, debug: bool = False, 
                 data_source: str = 'default'):
        """Initialize the product manager."""
        super().__init__(shop_url, access_token, debug)
        self.logger = logging.getLogger(__name__)
        self.data_source = data_source
        self.column_mapping = COLUMN_MAPPINGS.get(data_source, COLUMN_MAPPINGS['default'])
    
    def get_product_by_handle(self, handle: str) -> Optional[str]:
        """Get product ID by handle."""
        try:
            result = self.execute_graphql(GET_PRODUCT_BY_HANDLE, {'handle': handle})
            
            if 'errors' in result:
                self.logger.error(f"GraphQL errors: {result['errors']}")
                return None
            
            product = result.get('data', {}).get('productByHandle')
            return product['id'] if product else None
            
        except Exception as e:
            self.logger.error(f"Failed to get product by handle: {str(e)}")
            return None
    
    def get_existing_product_hash(self, handle: str) -> str:
        """Get hash of existing product data for comparison."""
        try:
            result = self.execute_graphql(GET_PRODUCT_DETAILS, {'handle': handle})
            
            if 'errors' in result:
                self.logger.debug(f"GraphQL errors getting product details: {result['errors']}")
                return ""
            
            product = result.get('data', {}).get('productByHandle')
            if not product:
                self.logger.debug(f"Product not found: {handle}")
                return ""
            
            # Create hash data from existing product
            variant_data = {}
            variants = product.get('variants', {}).get('edges', [])
            if variants:
                variant = variants[0]['node']
                variant_data = {
                    'sku': variant.get('sku', ''),
                    'price': variant.get('price', ''),
                    'inventoryQuantity': variant.get('inventoryQuantity', 0)
                }
            
            # Extract metafields
            metafields = {}
            metafield_edges = product.get('metafields', {}).get('edges', [])
            for edge in metafield_edges:
                node = edge['node']
                metafields[f"{node['namespace']}.{node['key']}"] = node['value']
            
            hash_data = {
                'title': product.get('title', ''),
                'bodyHtml': product.get('bodyHtml', ''),
                'vendor': product.get('vendor', ''),
                'productType': product.get('productType', ''),
                'tags': sorted(product.get('tags', [])),
                'variants': [variant_data] if variant_data else [],
                'metafields': metafields
            }
            
            # Create hash
            hash_string = json.dumps(hash_data, sort_keys=True, separators=(',', ':'))
            return hashlib.md5(hash_string.encode()).hexdigest()
            
        except Exception as e:
            self.logger.debug(f"Failed to get existing product hash: {str(e)}")
            return ""
    
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
            
            # Add variant data (assuming single variant for now)
            variants = input_data.get('variants', [])
            if variants:
                variant = variants[0]
                hash_data['variants'] = [{
                    'sku': variant.get('sku', ''),
                    'price': variant.get('price', ''),
                    'inventoryQuantity': variant.get('inventoryQuantity', 0)
                }]
            
            # Add metafields
            metafields = input_data.get('metafields', [])
            metafields_dict = {}
            for metafield in metafields:
                key = f"{metafield.get('namespace', '')}.{metafield.get('key', '')}"
                metafields_dict[key] = metafield.get('value', '')
            hash_data['metafields'] = metafields_dict
            
            # Create hash
            hash_string = json.dumps(hash_data, sort_keys=True, separators=(',', ':'))
            return hashlib.md5(hash_string.encode()).hexdigest()
            
        except Exception as e:
            self.logger.debug(f"Failed to create product hash: {str(e)}")
            return ""
    
    def has_product_changed(self, product_data: Dict[str, Any], handle: str) -> bool:
        """Check if product data has changed compared to existing product."""
        try:
            new_hash = self.create_product_hash(product_data)
            existing_hash = self.get_existing_product_hash(handle)
            
            if not existing_hash:
                # If we can't get existing hash, assume it has changed
                return True
            
            changed = new_hash != existing_hash
            self.logger.debug(f"Product {handle} changed: {changed} (new: {new_hash[:8]}, existing: {existing_hash[:8]})")
            return changed
            
        except Exception as e:
            self.logger.debug(f"Failed to compare product hashes: {str(e)}")
            return True  # If comparison fails, assume it has changed
    
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
            
            # Map basic fields using column mapping with fallbacks
            def get_mapped_value(field_key: str, default: str = '') -> str:
                mapped_column = self.column_mapping.get(field_key, field_key)
                # Try multiple variations of the column name
                for variation in [mapped_column, mapped_column.lower(), mapped_column.title()]:
                    if variation in row:
                        value = row[variation].strip() if row[variation] else default
                        return self.decode_html_entities(value) if value else default
                return default
            
            description = get_mapped_value('description')
            vendor = get_mapped_value('vendor')
            product_type = get_mapped_value('type')
            tags_str = get_mapped_value('tags')
            published_str = get_mapped_value('published', 'true').lower()
            status_str = get_mapped_value('status', 'active').upper()
            
            # Parse tags
            tags = []
            if tags_str:
                tags = [tag.strip() for tag in tags_str.split(',') if tag.strip()]
            
            # Parse published status
            published = published_str in ['true', '1', 'yes', 'active']
            
            # Parse status
            status = 'ACTIVE' if status_str in ['ACTIVE', 'TRUE', '1', 'YES'] else 'DRAFT'
            
            # Get variant data
            sku = get_mapped_value('sku')
            price_str = get_mapped_value('price', '0')
            
            # Parse price
            try:
                # Remove currency symbols and clean up price
                price_clean = ''.join(c for c in price_str if c.isdigit() or c == '.')
                price = float(price_clean) if price_clean else 0.0
            except (ValueError, TypeError):
                self.logger.warning(f"Invalid price '{price_str}' for product {title}, using 0.0")
                price = 0.0
            
            # Build product input
            product_input = {
                'title': title,
                'bodyHtml': description,
                'vendor': vendor,
                'productType': product_type,
                'tags': tags,
                'published': published,
                'status': status,
                'variants': [{
                    'sku': sku,
                    'price': str(price),
                    'inventoryQuantity': 0,
                    'requiresShipping': True,
                    'taxable': True
                }]
            }
            
            # Add handle if provided
            if handle:
                product_input['handle'] = handle
            
            # Process metafields (custom fields)
            metafields = []
            for column_name, value in row.items():
                if column_name.startswith('Metafield:') and value and value.strip():
                    # Parse metafield format: "Metafield: namespace.key[type]"
                    try:
                        metafield_def = column_name.replace('Metafield:', '').strip()
                        if '[' in metafield_def and ']' in metafield_def:
                            namespace_key, type_def = metafield_def.split('[', 1)
                            type_def = type_def.rstrip(']')
                            
                            if '.' in namespace_key:
                                namespace, key = namespace_key.split('.', 1)
                                
                                metafields.append({
                                    'namespace': namespace.strip(),
                                    'key': key.strip(),
                                    'value': value.strip(),
                                    'type': type_def.strip()
                                })
                    except Exception as e:
                        self.logger.warning(f"Failed to parse metafield '{column_name}': {str(e)}")
            
            if metafields:
                product_input['metafields'] = metafields
            
            return {
                'input': product_input
            }
            
        except Exception as e:
            self.logger.error(f"Failed to map row to product: {str(e)}")
            raise ValueError(f"Failed to map CSV row to product: {str(e)}")
    
    def upload_product(self, product_data: Dict, product_id: Optional[str] = None) -> str:
        """Upload or update a product."""
        try:
            mutation = UPDATE_PRODUCT_MUTATION if product_id else CREATE_PRODUCT_MUTATION
            
            # Add product ID for updates
            if product_id:
                product_data['input']['id'] = product_id
            
            result = self.execute_graphql(mutation, product_data)
            
            if 'errors' in result:
                raise Exception(f"GraphQL errors: {result['errors']}")
            
            operation = 'productUpdate' if product_id else 'productCreate'
            product_result = result.get('data', {}).get(operation, {})
            
            if product_result.get('userErrors'):
                raise Exception(f"User errors: {product_result['userErrors']}")
            
            created_product = product_result.get('product', {})
            return created_product.get('id', '')
            
        except Exception as e:
            self.logger.error(f"Failed to upload product: {str(e)}")
            raise Exception(f"Failed to upload product: {str(e)}")
    
    def extract_images_from_rows(self, product_rows: List[Dict]) -> List[str]:
        """Extract image URLs from product rows."""
        image_urls = []
        
        for row in product_rows:
            # Try different possible column names for image URL
            image_url = None
            for col_name in ['Product image URL', 'product image url', 'Image URL', 'image_url']:
                if col_name in row and row[col_name]:
                    image_url = row[col_name].strip()
                    break
            
            if image_url and image_url.startswith('http'):
                image_urls.append(image_url)
        
        return image_urls
    
    def validate_product_data(self, product_data: Dict) -> bool:
        """Validate product data before upload."""
        try:
            input_data = product_data.get('input', {})
            
            # Check required fields
            if not input_data.get('title'):
                self.logger.error("Product title is required")
                return False
            
            # Validate variants
            variants = input_data.get('variants', [])
            if not variants:
                self.logger.error("At least one variant is required")
                return False
            
            for variant in variants:
                price = variant.get('price', '0')
                try:
                    float(price)
                except (ValueError, TypeError):
                    self.logger.error(f"Invalid price: {price}")
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Product validation failed: {str(e)}")
            return False