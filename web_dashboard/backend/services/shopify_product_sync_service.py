"""
Shopify Product Sync Service

Handles comprehensive synchronization of products from Shopify including:
- Active and draft products
- Product details, pricing, inventory
- Variants, metafields, images
- Categories/collections mapping
- Full bi-directional sync capabilities
"""

import os
import logging
import requests
import json
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone
import time
from decimal import Decimal
import base64

from repositories.product_repository import ProductRepository
from repositories.category_repository import CategoryRepository
from models import Product, Category, ProductStatus, SyncStatus

logger = logging.getLogger(__name__)


class ShopifyProductSyncService:
    """Service for comprehensive Shopify product synchronization."""
    
    def __init__(self, db_session=None):
        """Initialize the service with database session."""
        self.db_session = db_session
        self.product_repo = ProductRepository(db_session)
        self.category_repo = CategoryRepository(db_session)
        
        # Get Shopify credentials from environment
        self.shop_url = os.getenv('SHOPIFY_SHOP_URL')
        self.access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
        
        if not self.shop_url or not self.access_token:
            logger.warning("Shopify credentials not found in environment variables")
        
        # API configuration
        self.api_version = "2024-10"
        self.rate_limit_delay = 0.5  # 500ms between requests
        self.max_retries = 3
        self.products_per_page = 250  # Shopify max is 250
    
    def _make_graphql_request(self, query: str, variables: dict = None, retry_count: int = 0) -> Dict[str, Any]:
        """
        Make a GraphQL request to the Shopify Admin API with exponential backoff for rate limiting.
        
        Args:
            query: GraphQL query string
            variables: Query variables
            retry_count: Current retry attempt (for internal use)
            
        Returns:
            Response data or error information
        """
        if not self.shop_url or not self.access_token:
            return {
                'success': False,
                'error': 'Shopify credentials not configured',
                'error_code': 'MISSING_CREDENTIALS'
            }
        
        # Ensure shop URL format is correct
        shop_url = self.shop_url.strip()
        
        # Remove any trailing slashes
        shop_url = shop_url.rstrip('/')
        
        # Add https:// if not present
        if not shop_url.startswith('https://'):
            shop_url = f"https://{shop_url}"
        
        # The shop_url should already include .myshopify.com
        if '.myshopify.com' not in shop_url:
            logger.error(f"Invalid shop URL format: {shop_url} - must include .myshopify.com")
            shop_url += '.myshopify.com'
        
        url = f"{shop_url}/admin/api/{self.api_version}/graphql.json"
        
        headers = {
            'X-Shopify-Access-Token': self.access_token,
            'Content-Type': 'application/json'
        }
        
        request_data = {
            'query': query,
            'variables': variables or {}
        }
        
        try:
            response = requests.post(url, headers=headers, json=request_data, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                if 'errors' in data:
                    # Check for rate limit errors
                    errors = data.get('errors', [])
                    is_throttled = any(
                        err.get('extensions', {}).get('code') == 'THROTTLED' 
                        for err in errors if isinstance(err, dict)
                    )
                    
                    if is_throttled and retry_count < self.max_retries:
                        # Exponential backoff: 2^retry_count seconds (2s, 4s, 8s)
                        wait_time = 2 ** (retry_count + 1)
                        logger.warning(f"GraphQL rate limited, waiting {wait_time} seconds before retry {retry_count + 1}/{self.max_retries}")
                        time.sleep(wait_time)
                        
                        # Recursive retry with incremented count
                        logger.info(f"Retrying GraphQL request after {wait_time}s wait...")
                        return self._make_graphql_request(query, variables, retry_count + 1)
                    
                    return {
                        'success': False,
                        'error': 'GraphQL errors',
                        'error_code': 'GRAPHQL_ERROR',
                        'error_details': errors
                    }
                return {
                    'success': True,
                    'data': data['data'],
                    'status_code': response.status_code,
                    'extensions': data.get('extensions', {})  # Include cost info
                }
            elif response.status_code == 429:
                # HTTP rate limit (shouldn't happen with GraphQL but handle anyway)
                if retry_count < self.max_retries:
                    retry_after = int(response.headers.get('Retry-After', 2))
                    logger.warning(f"HTTP 429 rate limit, waiting {retry_after} seconds before retry {retry_count + 1}/{self.max_retries}")
                    time.sleep(retry_after)
                    return self._make_graphql_request(query, variables, retry_count + 1)
                
                return {
                    'success': False,
                    'error': 'Rate limited',
                    'error_code': 'RATE_LIMITED',
                    'status_code': response.status_code
                }
            else:
                return {
                    'success': False,
                    'error': f'API request failed: {response.status_code}',
                    'error_code': 'API_ERROR',
                    'status_code': response.status_code
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f'Unexpected error: {str(e)}',
                'error_code': 'UNEXPECTED_ERROR'
            }
    
    def _make_shopify_request(self, endpoint: str, method: str = 'GET', data: dict = None, params: dict = None) -> Dict[str, Any]:
        """
        Make a request to the Shopify Admin API with rate limiting and error handling.
        
        Args:
            endpoint: API endpoint (without domain and version)
            method: HTTP method
            data: Request data for POST/PUT requests
            params: Query parameters
            
        Returns:
            Response data or error information
        """
        if not self.shop_url or not self.access_token:
            return {
                'success': False,
                'error': 'Shopify credentials not configured',
                'error_code': 'MISSING_CREDENTIALS'
            }
        
        # Ensure shop URL format is correct
        shop_url = self.shop_url.strip()
        
        # Remove any trailing slashes
        shop_url = shop_url.rstrip('/')
        
        # Add https:// if not present
        if not shop_url.startswith('https://'):
            shop_url = f"https://{shop_url}"
        
        # The shop_url should already include .myshopify.com
        # Don't append it again if it's already there
        if '.myshopify.com' not in shop_url:
            logger.error(f"Invalid shop URL format: {shop_url} - must include .myshopify.com")
            shop_url += '.myshopify.com'
        
        url = f"{shop_url}/admin/api/{self.api_version}/{endpoint}"
        
        # Log the URL being called for debugging
        logger.info(f"Making Shopify API request to: {url}")
        logger.debug(f"Shop URL from env: {self.shop_url}")
        logger.debug(f"Processed shop URL: {shop_url}")
        
        headers = {
            'X-Shopify-Access-Token': self.access_token,
            'Content-Type': 'application/json'
        }
        
        # Rate limiting
        time.sleep(self.rate_limit_delay)
        
        for attempt in range(self.max_retries):
            try:
                if method == 'GET':
                    response = requests.get(url, headers=headers, params=params, timeout=30)
                elif method == 'POST':
                    response = requests.post(url, headers=headers, json=data, params=params, timeout=30)
                elif method == 'PUT':
                    response = requests.put(url, headers=headers, json=data, params=params, timeout=30)
                elif method == 'DELETE':
                    response = requests.delete(url, headers=headers, params=params, timeout=30)
                else:
                    return {
                        'success': False,
                        'error': f'Unsupported HTTP method: {method}',
                        'error_code': 'INVALID_METHOD'
                    }
                
                if response.status_code in [200, 201]:
                    return {
                        'success': True,
                        'data': response.json(),
                        'status_code': response.status_code,
                        'headers': dict(response.headers)
                    }
                elif response.status_code == 404:
                    return {
                        'success': False,
                        'error': 'Resource not found',
                        'error_code': 'NOT_FOUND',
                        'status_code': response.status_code
                    }
                elif response.status_code == 429:
                    # Rate limited - exponential backoff
                    retry_after = int(response.headers.get('Retry-After', 2))
                    logger.warning(f"Rate limited, waiting {retry_after} seconds (attempt {attempt + 1})")
                    time.sleep(retry_after)
                    continue
                elif response.status_code == 422:
                    error_data = {}
                    try:
                        error_data = response.json()
                    except:
                        pass
                    return {
                        'success': False,
                        'error': 'Validation error',
                        'error_code': 'VALIDATION_ERROR',
                        'status_code': response.status_code,
                        'error_details': error_data
                    }
                else:
                    error_data = {}
                    try:
                        error_data = response.json()
                    except:
                        pass
                        
                    return {
                        'success': False,
                        'error': f'API request failed: {response.status_code}',
                        'error_code': 'API_ERROR',
                        'status_code': response.status_code,
                        'error_details': error_data
                    }
                    
            except requests.exceptions.Timeout:
                if attempt == self.max_retries - 1:
                    return {
                        'success': False,
                        'error': 'Request timeout',
                        'error_code': 'TIMEOUT'
                    }
                time.sleep(2 ** attempt)  # Exponential backoff
                
            except requests.exceptions.ConnectionError:
                if attempt == self.max_retries - 1:
                    return {
                        'success': False,
                        'error': 'Connection error',
                        'error_code': 'CONNECTION_ERROR'
                    }
                time.sleep(2 ** attempt)  # Exponential backoff
                
            except Exception as e:
                if attempt == self.max_retries - 1:
                    return {
                        'success': False,
                        'error': f'Unexpected error: {str(e)}',
                        'error_code': 'UNEXPECTED_ERROR'
                    }
                time.sleep(2 ** attempt)  # Exponential backoff
        
        return {
            'success': False,
            'error': 'Max retries exceeded',
            'error_code': 'MAX_RETRIES_EXCEEDED'
        }
    
    def _make_graphql_request(self, query: str, variables: dict = None) -> Dict[str, Any]:
        """
        Make a request to the Shopify GraphQL API.
        
        Args:
            query: GraphQL query string
            variables: Variables for the query
            
        Returns:
            Response data or error information
        """
        if not self.shop_url or not self.access_token:
            return {
                'success': False,
                'error': 'Shopify credentials not configured',
                'error_code': 'MISSING_CREDENTIALS'
            }
        
        # Ensure shop URL format is correct
        shop_url = self.shop_url.strip().rstrip('/')
        if not shop_url.startswith('https://'):
            shop_url = f"https://{shop_url}"
        
        # GraphQL endpoint
        url = f"{shop_url}/admin/api/{self.api_version}/graphql.json"
        
        headers = {
            'X-Shopify-Access-Token': self.access_token,
            'Content-Type': 'application/json'
        }
        
        payload = {
            'query': query,
            'variables': variables or {}
        }
        
        logger.info(f"Making Shopify GraphQL request to: {url}")
        
        # Rate limiting
        time.sleep(self.rate_limit_delay)
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                if 'errors' in data:
                    return {
                        'success': False,
                        'error': 'GraphQL errors',
                        'error_details': data['errors'],
                        'data': data.get('data')
                    }
                return {
                    'success': True,
                    'data': data.get('data', {}),
                    'extensions': data.get('extensions', {})
                }
            else:
                return {
                    'success': False,
                    'error': f'GraphQL request failed: {response.status_code}',
                    'error_code': 'GRAPHQL_ERROR',
                    'status_code': response.status_code,
                    'response_text': response.text
                }
                
        except Exception as e:
            logger.error(f"GraphQL request error: {str(e)}")
            return {
                'success': False,
                'error': f'GraphQL request exception: {str(e)}',
                'error_code': 'GRAPHQL_EXCEPTION'
            }
    
    def _get_all_paginated(self, endpoint: str, params: dict = None) -> List[Dict[str, Any]]:
        """
        Get all items from a paginated Shopify endpoint.
        
        Args:
            endpoint: API endpoint
            params: Query parameters
            
        Returns:
            List of all items across all pages
        """
        all_items = []
        page_params = params.copy() if params else {}
        page_params['limit'] = self.products_per_page
        
        while True:
            result = self._make_shopify_request(endpoint, params=page_params)
            
            if not result['success']:
                logger.error(f"Failed to fetch paginated data: {result['error']}")
                break
            
            data = result['data']
            items_key = list(data.keys())[0]  # Usually 'products', 'collections', etc.
            items = data.get(items_key, [])
            
            if not items:
                break
            
            all_items.extend(items)
            
            # Check for pagination link in headers
            link_header = result.get('headers', {}).get('link', '')
            if 'rel="next"' not in link_header:
                break
            
            # Extract next page info from link header
            next_link = None
            for link in link_header.split(','):
                if 'rel="next"' in link:
                    next_link = link.split(';')[0].strip('<> ')
                    break
            
            if not next_link:
                break
            
            # Extract page_info from next link
            try:
                page_info = next_link.split('page_info=')[1].split('&')[0]
                page_params = {'limit': self.products_per_page, 'page_info': page_info}
            except (IndexError, ValueError):
                logger.error("Failed to parse pagination link")
                break
        
        return all_items
    
    def fetch_products_graphql(self, limit: int = 10) -> Dict[str, Any]:
        """
        Fetch products using GraphQL API.
        
        Args:
            limit: Number of products to fetch
            
        Returns:
            Products data or error
        """
        query = """
        query getProducts($first: Int!) {
            products(first: $first) {
                edges {
                    node {
                        id
                        title
                        handle
                        status
                        vendor
                        productType
                        createdAt
                        updatedAt
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
                        images(first: 1) {
                            edges {
                                node {
                                    url
                                    altText
                                }
                            }
                        }
                    }
                }
                pageInfo {
                    hasNextPage
                    endCursor
                }
            }
        }
        """
        
        variables = {
            'first': limit
        }
        
        result = self._make_graphql_request(query, variables)
        
        if result['success']:
            products_data = result['data'].get('products', {})
            products = []
            
            for edge in products_data.get('edges', []):
                node = edge.get('node', {})
                # Extract variant info
                variant_edges = node.get('variants', {}).get('edges', [])
                variant = variant_edges[0]['node'] if variant_edges else {}
                
                # Extract image info  
                image_edges = node.get('images', {}).get('edges', [])
                image = image_edges[0]['node'] if image_edges else {}
                
                products.append({
                    'id': node.get('id'),
                    'title': node.get('title'),
                    'handle': node.get('handle'),
                    'status': node.get('status'),
                    'vendor': node.get('vendor'),
                    'product_type': node.get('productType'),
                    'created_at': node.get('createdAt'),
                    'updated_at': node.get('updatedAt'),
                    'tags': node.get('tags', []),
                    'sku': variant.get('sku'),
                    'price': variant.get('price'),
                    'inventory_quantity': variant.get('inventoryQuantity'),
                    'image_url': image.get('url')
                })
            
            return {
                'success': True,
                'products': products,
                'total': len(products),
                'has_next_page': products_data.get('pageInfo', {}).get('hasNextPage', False)
            }
        else:
            return result
    
    def sync_all_products(self, include_draft: bool = True, resume_cursor: str = None) -> Dict[str, Any]:
        """
        Sync all products from Shopify to local database using GraphQL.
        
        Args:
            include_draft: Whether to include draft products
            resume_cursor: Optional cursor to resume sync from (for continuing after rate limits)
            
        Returns:
            Sync result summary
        """
        try:
            logger.info("Starting comprehensive Shopify product sync using GraphQL")
            
            # First, get a count of products to set expectations
            count_query = """
            query GetProductCount {
                productsCount {
                    count
                }
            }
            """
            count_result = self._make_graphql_request(count_query)
            
            total_store_products = 0
            if count_result['success']:
                total_store_products = count_result['data'].get('productsCount', {}).get('count', 0)
                logger.info(f"Store has {total_store_products} products total")
            
            sync_results = {
                'total_products': 0,
                'created': 0,
                'updated': 0,
                'skipped': 0,
                'errors': 0,
                'error_details': [],
                'store_total': total_store_products
            }
            
            # GraphQL query for products with all details
            query = """
            query getProducts($first: Int!, $after: String, $query: String) {
                products(first: $first, after: $after, query: $query) {
                    edges {
                        cursor
                        node {
                            id
                            title
                            handle
                            descriptionHtml
                            vendor
                            productType
                            status
                            tags
                            createdAt
                            updatedAt
                            seo {
                                title
                                description
                            }
                            variants(first: 250) {
                                edges {
                                    node {
                                        id
                                        sku
                                        price
                                        compareAtPrice
                                        inventoryQuantity
                                        inventoryPolicy
                                        barcode
                                        position
                                        selectedOptions {
                                            name
                                            value
                                        }
                                    }
                                }
                            }
                            images(first: 250) {
                                edges {
                                    node {
                                        id
                                        url
                                        altText
                                    }
                                }
                            }
                            metafields(first: 100) {
                                edges {
                                    node {
                                        namespace
                                        key
                                        value
                                        type
                                    }
                                }
                            }
                        }
                    }
                    pageInfo {
                        hasNextPage
                        endCursor
                    }
                }
            }
            """
            
            # Build query filter - GraphQL doesn't use 'ANY' like REST
            query_filter = None  # No filter means get all products regardless of status
            
            # Paginate through all products
            has_next_page = True
            cursor = resume_cursor  # Start from resume point if provided
            
            if resume_cursor:
                logger.info(f"Resuming sync from cursor: {resume_cursor}")
            
            while has_next_page:
                variables = {
                    'first': 100  # Max 250 per request
                }
                if query_filter:
                    variables['query'] = query_filter
                if cursor:
                    variables['after'] = cursor
                
                logger.info(f"Making Shopify GraphQL request to: {self.shop_url}/admin/api/{self.api_version}/graphql.json")
                result = self._make_graphql_request(query, variables)
                
                if not result['success']:
                    logger.error(f"GraphQL request failed: {result.get('error')}")
                    if 'error_details' in result:
                        logger.error(f"GraphQL error details: {result.get('error_details')}")
                    
                    # Check if it's a rate limit error after all retries
                    error_details = result.get('error_details', [])
                    is_rate_limited = any(
                        err.get('extensions', {}).get('code') == 'THROTTLED' 
                        for err in error_details if isinstance(err, dict)
                    )
                    
                    if is_rate_limited:
                        # Return partial success for rate limit after retries exhausted
                        logger.info(f"Rate limited after processing {sync_results['total_products']} products (all retries exhausted)")
                        progress_pct = (sync_results['total_products'] / total_store_products * 100) if total_store_products > 0 else 0
                        return {
                            'success': True,
                            'message': f'Sync partially completed. Processed {sync_results["total_products"]} of {total_store_products} products ({progress_pct:.1f}%) before hitting rate limits. Please run sync again to continue.',
                            'results': sync_results,
                            'rate_limited': True,
                            'progress': {
                                'processed': sync_results['total_products'],
                                'total': total_store_products,
                                'percentage': progress_pct
                            },
                            'resume_cursor': cursor  # Provide cursor for resuming
                        }
                    
                    return {
                        'success': False,
                        'error': f"Failed to fetch products: {result.get('error')}",
                        'error_details': result.get('error_details'),
                        'error_code': 'GRAPHQL_ERROR'
                    }
                
                # Log GraphQL cost if available
                extensions = result.get('extensions', {})
                if 'cost' in extensions:
                    cost = extensions['cost']
                    logger.debug(f"GraphQL query cost: {cost.get('requestedQueryCost')}/{cost.get('throttleStatus', {}).get('maximumAvailable')}")
                    logger.debug(f"Restore rate: {cost.get('throttleStatus', {}).get('restoreRate')} points/second")
                
                products_data = result['data'].get('products', {})
                edges = products_data.get('edges', [])
                page_info = products_data.get('pageInfo', {})
                
                sync_results['total_products'] += len(edges)
                
                # Process each product
                for edge in edges:
                    try:
                        node = edge['node']
                        # Transform GraphQL data to match expected format
                        shopify_product = self._transform_graphql_product(node)
                        
                        result = self._sync_single_product(shopify_product)
                        
                        if result['success']:
                            if result['action'] == 'created':
                                sync_results['created'] += 1
                            elif result['action'] == 'updated':
                                sync_results['updated'] += 1
                            else:
                                sync_results['skipped'] += 1
                        else:
                            sync_results['errors'] += 1
                            sync_results['error_details'].append({
                                'product_id': node.get('id'),
                                'title': node.get('title'),
                                'error': result['error']
                            })
                            
                    except Exception as e:
                        sync_results['errors'] += 1
                        sync_results['error_details'].append({
                            'product_id': edge.get('node', {}).get('id'),
                            'title': edge.get('node', {}).get('title'),
                            'error': str(e)
                        })
                        logger.error(f"Error processing product: {str(e)}")
                
                # Progress logging
                logger.info(f"Processed {sync_results['total_products']} products so far...")
                
                # Check for next page
                has_next_page = page_info.get('hasNextPage', False)
                cursor = page_info.get('endCursor')
            
            # Sync collections using GraphQL
            self._sync_collections_graphql() if hasattr(self, '_sync_collections_graphql') else self._sync_collections()
            
            logger.info(f"Product sync completed: {sync_results}")
            
            return {
                'success': True,
                'message': 'Product sync completed successfully',
                'results': sync_results
            }
            
        except Exception as e:
            logger.error(f"Error in product sync: {str(e)}")
            return {
                'success': False,
                'error': f'Product sync failed: {str(e)}',
                'error_code': 'SYNC_ERROR'
            }
    
    def _transform_graphql_product(self, node: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform GraphQL product node to REST-like format.
        
        Args:
            node: GraphQL product node
            
        Returns:
            Product data in REST format
        """
        # Extract Shopify ID from GraphQL ID (format: gid://shopify/Product/123)
        gid = node.get('id', '')
        shopify_id = gid.split('/')[-1] if gid else ''
        
        # Transform variants
        variants = []
        variant_edges = node.get('variants', {}).get('edges', [])
        for v_edge in variant_edges:
            v_node = v_edge['node']
            variant_gid = v_node.get('id', '')
            variant_id = variant_gid.split('/')[-1] if variant_gid else ''
            
            # Extract options
            options = []
            for opt in v_node.get('selectedOptions', []):
                options.append(opt.get('value'))
            
            variants.append({
                'id': variant_id,
                'sku': v_node.get('sku'),
                'price': v_node.get('price'),
                'compare_at_price': v_node.get('compareAtPrice'),
                'inventory_quantity': v_node.get('inventoryQuantity'),
                'inventory_policy': v_node.get('inventoryPolicy'),
                'barcode': v_node.get('barcode'),
                'position': v_node.get('position'),
                'option1': options[0] if len(options) > 0 else None,
                'option2': options[1] if len(options) > 1 else None,
                'option3': options[2] if len(options) > 2 else None
            })
        
        # Transform images
        images = []
        image_edges = node.get('images', {}).get('edges', [])
        for i_edge in image_edges:
            i_node = i_edge['node']
            images.append({
                'id': i_node.get('id'),
                'src': i_node.get('url'),
                'alt': i_node.get('altText')
            })
        
        # Transform metafields
        metafields = []
        metafield_edges = node.get('metafields', {}).get('edges', [])
        for m_edge in metafield_edges:
            m_node = m_edge['node']
            metafields.append({
                'namespace': m_node.get('namespace'),
                'key': m_node.get('key'),
                'value': m_node.get('value'),
                'type': m_node.get('type')
            })
        
        # Build REST-like product object
        return {
            'id': shopify_id,
            'title': node.get('title'),
            'handle': node.get('handle'),
            'body_html': node.get('descriptionHtml'),
            'vendor': node.get('vendor'),
            'product_type': node.get('productType'),
            'status': node.get('status', '').lower(),  # GraphQL returns uppercase
            'tags': ', '.join(node.get('tags', [])) if isinstance(node.get('tags'), list) else node.get('tags', ''),
            'created_at': node.get('createdAt'),
            'updated_at': node.get('updatedAt'),
            'seo_title': node.get('seo', {}).get('title'),
            'seo_description': node.get('seo', {}).get('description'),
            'variants': variants,
            'images': images,
            'metafields': metafields
        }
    
    def _sync_single_product(self, shopify_product: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sync a single product from Shopify data.
        
        Args:
            shopify_product: Product data from Shopify API
            
        Returns:
            Sync result for this product
        """
        try:
            shopify_id = str(shopify_product['id'])
            
            # Check if product already exists
            existing_product = self.product_repo.get_by_shopify_id(shopify_id)
            
            # Extract product data
            product_data = self._extract_product_data(shopify_product)
            
            if existing_product:
                # Update existing product
                updated_product = self.product_repo.update_product(
                    existing_product.id, 
                    product_data
                )
                
                if updated_product:
                    return {
                        'success': True,
                        'action': 'updated',
                        'product_id': updated_product.id,
                        'shopify_id': shopify_id
                    }
                else:
                    return {
                        'success': False,
                        'error': 'Failed to update product in database'
                    }
            else:
                # Create new product
                new_product = self.product_repo.create_product(product_data)
                
                if new_product:
                    return {
                        'success': True,
                        'action': 'created',
                        'product_id': new_product.id,
                        'shopify_id': shopify_id
                    }
                else:
                    return {
                        'success': False,
                        'error': 'Failed to create product in database'
                    }
                    
        except Exception as e:
            return {
                'success': False,
                'error': f'Error syncing product: {str(e)}'
            }
    
    def _extract_product_data(self, shopify_product: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract and transform Shopify product data for database storage.
        
        Args:
            shopify_product: Raw Shopify product data
            
        Returns:
            Transformed product data for database
        """
        try:
            # Basic product information
            data = {
                'shopify_product_id': str(shopify_product['id']),
                'shopify_handle': shopify_product.get('handle'),
                'name': shopify_product.get('title', ''),
                'description': shopify_product.get('body_html', ''),
                'brand': shopify_product.get('vendor', ''),  # Shopify vendor maps to brand
                'manufacturer': shopify_product.get('vendor', ''),  # Also use as manufacturer
                'status': ProductStatus.ACTIVE.value if shopify_product.get('status') == 'active' else ProductStatus.DRAFT.value,
                'shopify_synced_at': datetime.now(timezone.utc),
                'shopify_sync_status': SyncStatus.SUCCESS.value
            }
            
            # Handle variants (use first variant for main product data)
            variants = shopify_product.get('variants', [])
            if variants:
                main_variant = variants[0]
                
                data.update({
                    'shopify_variant_id': str(main_variant['id']),
                    'sku': main_variant.get('sku', ''),
                    'price': Decimal(str(main_variant.get('price', 0))),
                    'compare_at_price': Decimal(str(main_variant.get('compare_at_price', 0))) if main_variant.get('compare_at_price') else None,
                    'cost_price': Decimal(str(main_variant.get('cost', 0))) if main_variant.get('cost') else None,
                    'inventory_quantity': main_variant.get('inventory_quantity', 0),
                    'track_inventory': main_variant.get('inventory_management') == 'shopify',
                    'continue_selling_when_out_of_stock': main_variant.get('inventory_policy') == 'continue',
                    'weight': main_variant.get('weight', 0),
                    'weight_unit': main_variant.get('weight_unit', 'kg'),
                    'upc': main_variant.get('barcode', ''),  # Shopify barcode maps to UPC
                })
                
                # Handle variant options - store in custom_attributes or metafields
                variant_options = {}
                if main_variant.get('option1'):
                    variant_options['option1'] = main_variant['option1']
                if main_variant.get('option2'):
                    variant_options['option2'] = main_variant['option2']
                if main_variant.get('option3'):
                    variant_options['option3'] = main_variant['option3']
                
                if variant_options:
                    data['custom_attributes'] = variant_options
            
            # Handle images
            images = shopify_product.get('images', [])
            if images:
                data['featured_image_url'] = images[0].get('src')
                # Store additional images as JSON
                additional_images = [img.get('src') for img in images[1:] if img.get('src')]
                if additional_images:
                    data['additional_images'] = additional_images
            
            # Handle SEO
            data.update({
                'seo_title': shopify_product.get('seo_title') or shopify_product.get('title', ''),
                'seo_description': shopify_product.get('seo_description', '')
            })
            
            # Handle metafields if present
            metafields = shopify_product.get('metafields', [])
            if metafields:
                metafields_dict = {}
                for metafield in metafields:
                    key = f"{metafield.get('namespace', 'custom')}.{metafield.get('key', 'field')}"
                    metafields_dict[key] = metafield.get('value')
                data['metafields'] = metafields_dict
            
            # Map to category based on product_type or create default
            product_type = shopify_product.get('product_type', '')
            if product_type:
                category = self._find_or_create_category(product_type)
                if category:
                    data['category_id'] = category.id
            else:
                # Create or get a default category for uncategorized products
                category = self._find_or_create_category('Uncategorized')
                if category:
                    data['category_id'] = category.id
            
            return data
            
        except Exception as e:
            logger.error(f"Error extracting product data: {str(e)}")
            raise
    
    def _find_or_create_category(self, product_type: str) -> Optional[Category]:
        """
        Find existing category or create new one based on product type.
        
        Args:
            product_type: Shopify product type
            
        Returns:
            Category object or None
        """
        try:
            # Try to find existing category by name
            category = self.category_repo.get_by_name(product_type)
            
            if not category:
                # Create new category
                category_data = {
                    'name': product_type,
                    'slug': product_type.lower().replace(' ', '-').replace('&', 'and'),
                    'description': f'Products of type: {product_type}',
                    'is_active': True
                }
                category = self.category_repo.create_category(category_data)
                
                if category:
                    logger.info(f"Created new category: {product_type}")
            
            return category
            
        except Exception as e:
            logger.error(f"Error finding/creating category '{product_type}': {str(e)}")
            return None
    
    def _sync_collections(self) -> Dict[str, Any]:
        """
        Sync Shopify collections and map them to categories.
        
        Returns:
            Collection sync results
        """
        try:
            logger.info("Syncing Shopify collections")
            
            # Get all collections
            collections = self._get_all_paginated('collections.json')
            
            results = {
                'total_collections': len(collections),
                'synced': 0,
                'errors': 0
            }
            
            for collection in collections:
                try:
                    # Find or create category for this collection
                    category = self._find_or_create_category(collection.get('title', ''))
                    
                    if category:
                        # Update category with Shopify collection info
                        update_data = {
                            'shopify_collection_id': str(collection['id']),
                            'shopify_handle': collection.get('handle'),
                            'shopify_synced_at': datetime.now(timezone.utc)
                        }
                        
                        if collection.get('description'):
                            update_data['description'] = collection['description']
                        
                        self.category_repo.update_category(category.id, update_data)
                        results['synced'] += 1
                    else:
                        results['errors'] += 1
                        
                except Exception as e:
                    logger.error(f"Error syncing collection {collection.get('id')}: {str(e)}")
                    results['errors'] += 1
            
            logger.info(f"Collection sync completed: {results}")
            return results
            
        except Exception as e:
            logger.error(f"Error syncing collections: {str(e)}")
            return {'error': str(e)}
    
    def get_sync_status(self) -> Dict[str, Any]:
        """
        Get current sync status and statistics.
        
        Returns:
            Sync status information
        """
        try:
            # Get product counts
            total_products = self.product_repo.count_all()
            synced_products = self.product_repo.count_by_sync_status(SyncStatus.SUCCESS.value)
            
            # Get recent sync activities
            recent_syncs = self.product_repo.get_recently_synced(limit=10)
            
            # Get categories with Shopify mapping
            categories_with_shopify = self.category_repo.count_with_shopify_mapping()
            
            return {
                'success': True,
                'statistics': {
                    'total_products': total_products,
                    'synced_products': synced_products,
                    'sync_percentage': round((synced_products / total_products * 100) if total_products > 0 else 0, 2),
                    'categories_with_shopify': categories_with_shopify
                },
                'recent_syncs': [
                    {
                        'id': product.id,
                        'name': product.name,
                        'sku': product.sku,
                        'synced_at': product.shopify_synced_at.isoformat() if product.shopify_synced_at else None
                    }
                    for product in recent_syncs
                ]
            }
            
        except Exception as e:
            logger.error(f"Error getting sync status: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def sync_single_product_by_id(self, shopify_product_id: str) -> Dict[str, Any]:
        """
        Sync a single product by its Shopify ID.
        
        Args:
            shopify_product_id: Shopify product ID
            
        Returns:
            Sync result
        """
        try:
            # Fetch product from Shopify
            result = self._make_shopify_request(f'products/{shopify_product_id}.json')
            
            if not result['success']:
                return result
            
            shopify_product = result['data']['product']
            
            # Sync the product
            sync_result = self._sync_single_product(shopify_product)
            
            return sync_result
            
        except Exception as e:
            logger.error(f"Error syncing single product {shopify_product_id}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }