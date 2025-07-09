"""
API Response Transformer Module

Specialized module for handling different types of API responses from Shopify
and transforming them into standardized data structures.
"""

import json
import logging
from typing import Dict, List, Any, Optional, Iterator
from datetime import datetime

class APIResponseTransformer:
    """
    Handles transformation of various API response formats.
    """
    
    def __init__(self, debug: bool = False):
        self.debug = debug
        self.logger = logging.getLogger(self.__class__.__name__)
        
        if debug:
            self.logger.setLevel(logging.DEBUG)
    
    def transform_products_response(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Transform products API response.
        
        Args:
            response: Raw API response
            
        Returns:
            List of standardized product data
        """
        products = []
        
        if 'data' not in response:
            return products
        
        # Handle different response structures
        if 'products' in response['data']:
            # Standard products query
            edges = response['data']['products'].get('edges', [])
            for edge in edges:
                product = self._standardize_product(edge['node'])
                if product:
                    products.append(product)
        
        return products
    
    def transform_collections_response(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Transform collections API response.
        
        Args:
            response: Raw API response
            
        Returns:
            List of standardized collection data
        """
        collections = []
        
        if 'data' not in response:
            return collections
        
        if 'collections' in response['data']:
            edges = response['data']['collections'].get('edges', [])
            for edge in edges:
                collection = self._standardize_collection(edge['node'])
                if collection:
                    collections.append(collection)
        
        return collections
    
    def transform_collection_products_response(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Transform collections with products API response.
        
        Args:
            response: Raw API response containing collections with their products
            
        Returns:
            List of product-collection relationship data
        """
        relationships = []
        
        if 'data' not in response or 'collections' not in response['data']:
            return relationships
        
        for collection_edge in response['data']['collections']['edges']:
            collection = collection_edge['node']
            collection_data = self._standardize_collection(collection)
            
            if 'products' in collection and collection_data:
                product_edges = collection['products'].get('edges', [])
                for product_edge in product_edges:
                    product = self._standardize_product(product_edge['node'])
                    if product:
                        # Create relationship record
                        relationship = {
                            'product': product,
                            'collection': collection_data,
                            'source': 'collections_with_products_api'
                        }
                        relationships.append(relationship)
        
        return relationships
    
    def _standardize_product(self, product_node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Standardize product data structure.
        
        Args:
            product_node: Raw product node from API
            
        Returns:
            Standardized product data or None if invalid
        """
        if not product_node or not product_node.get('handle'):
            return None
        
        standardized = {
            'id': product_node.get('id', ''),
            'handle': product_node.get('handle', ''),
            'title': product_node.get('title', ''),
            'description': product_node.get('description', ''),
            'productType': product_node.get('productType', ''),
            'vendor': product_node.get('vendor', ''),
            'tags': product_node.get('tags', []),
            'status': product_node.get('status', 'ACTIVE'),
            'publishedAt': product_node.get('publishedAt'),
            'createdAt': product_node.get('createdAt'),
            'updatedAt': product_node.get('updatedAt'),
            'collections': [],
            'variants': [],
            'images': []
        }
        
        # Extract collections
        if 'collections' in product_node:
            collections_data = product_node['collections']
            if 'edges' in collections_data:
                for edge in collections_data['edges']:
                    collection = self._standardize_collection(edge['node'])
                    if collection:
                        standardized['collections'].append(collection)
        
        # Extract variants
        if 'variants' in product_node:
            variants_data = product_node['variants']
            if 'edges' in variants_data:
                for edge in variants_data['edges']:
                    variant = self._standardize_variant(edge['node'])
                    if variant:
                        standardized['variants'].append(variant)
        
        # Extract images
        if 'images' in product_node:
            images_data = product_node['images']
            if 'edges' in images_data:
                for edge in images_data['edges']:
                    image = self._standardize_image(edge['node'])
                    if image:
                        standardized['images'].append(image)
        
        return standardized
    
    def _standardize_collection(self, collection_node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Standardize collection data structure.
        
        Args:
            collection_node: Raw collection node from API
            
        Returns:
            Standardized collection data or None if invalid
        """
        if not collection_node or not collection_node.get('handle'):
            return None
        
        standardized = {
            'id': collection_node.get('id', ''),
            'handle': collection_node.get('handle', ''),
            'title': collection_node.get('title', ''),
            'description': collection_node.get('description', ''),
            'sortOrder': collection_node.get('sortOrder', 'MANUAL'),
            'ruleSet': collection_node.get('ruleSet'),
            'productsCount': 0,
            'updatedAt': collection_node.get('updatedAt'),
            'image': None
        }
        
        # Extract products count
        if 'products' in collection_node:
            products_data = collection_node['products']
            if isinstance(products_data, dict) and 'edges' in products_data:
                standardized['productsCount'] = len(products_data['edges'])
        
        # Extract image
        if 'image' in collection_node and collection_node['image']:
            standardized['image'] = self._standardize_image(collection_node['image'])
        
        return standardized
    
    def _standardize_variant(self, variant_node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Standardize variant data structure.
        
        Args:
            variant_node: Raw variant node from API
            
        Returns:
            Standardized variant data or None if invalid
        """
        if not variant_node:
            return None
        
        return {
            'id': variant_node.get('id', ''),
            'sku': variant_node.get('sku', ''),
            'title': variant_node.get('title', ''),
            'price': variant_node.get('price', '0.00'),
            'compareAtPrice': variant_node.get('compareAtPrice'),
            'availableForSale': variant_node.get('availableForSale', True),
            'inventoryQuantity': variant_node.get('inventoryQuantity', 0),
            'weight': variant_node.get('weight', 0),
            'weightUnit': variant_node.get('weightUnit', 'GRAMS'),
            'requiresShipping': variant_node.get('requiresShipping', True),
            'taxable': variant_node.get('taxable', True)
        }
    
    def _standardize_image(self, image_node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Standardize image data structure.
        
        Args:
            image_node: Raw image node from API
            
        Returns:
            Standardized image data or None if invalid
        """
        if not image_node:
            return None
        
        return {
            'id': image_node.get('id', ''),
            'url': image_node.get('url', ''),
            'altText': image_node.get('altText', ''),
            'width': image_node.get('width'),
            'height': image_node.get('height')
        }
    
    def batch_transform_responses(self, responses: List[Dict[str, Any]], 
                                response_type: str = 'products') -> Iterator[Dict[str, Any]]:
        """
        Transform multiple API responses in batches.
        
        Args:
            responses: List of API responses
            response_type: Type of response ('products', 'collections', 'collection_products')
            
        Yields:
            Transformed data items
        """
        transform_map = {
            'products': self.transform_products_response,
            'collections': self.transform_collections_response,
            'collection_products': self.transform_collection_products_response
        }
        
        transform_func = transform_map.get(response_type, self.transform_products_response)
        
        for response in responses:
            try:
                transformed_items = transform_func(response)
                for item in transformed_items:
                    yield item
            except Exception as e:
                self.logger.error(f"Error transforming response: {e}")
                continue
    
    def validate_response_structure(self, response: Dict[str, Any], 
                                  expected_type: str = 'products') -> bool:
        """
        Validate that API response has expected structure.
        
        Args:
            response: API response to validate
            expected_type: Expected response type
            
        Returns:
            True if valid, False otherwise
        """
        if not isinstance(response, dict) or 'data' not in response:
            self.logger.warning("Response missing 'data' field")
            return False
        
        data = response['data']
        
        if expected_type == 'products':
            return 'products' in data and 'edges' in data['products']
        elif expected_type == 'collections':
            return 'collections' in data and 'edges' in data['collections']
        elif expected_type == 'collection_products':
            if 'collections' not in data:
                return False
            # Check that at least one collection has products
            for edge in data['collections'].get('edges', []):
                if 'products' in edge['node']:
                    return True
            return False
        
        return False
    
    def extract_pagination_info(self, response: Dict[str, Any], 
                              data_type: str = 'products') -> Dict[str, Any]:
        """
        Extract pagination information from API response.
        
        Args:
            response: API response
            data_type: Type of data being paginated
            
        Returns:
            Pagination info dictionary
        """
        pagination_info = {
            'hasNextPage': False,
            'hasPreviousPage': False,
            'startCursor': None,
            'endCursor': None,
            'totalCount': None
        }
        
        if 'data' not in response:
            return pagination_info
        
        data_section = response['data'].get(data_type, {})
        page_info = data_section.get('pageInfo', {})
        
        pagination_info.update({
            'hasNextPage': page_info.get('hasNextPage', False),
            'hasPreviousPage': page_info.get('hasPreviousPage', False),
            'startCursor': page_info.get('startCursor'),
            'endCursor': page_info.get('endCursor')
        })
        
        # Extract total count if available
        if 'totalCount' in data_section:
            pagination_info['totalCount'] = data_section['totalCount']
        
        return pagination_info