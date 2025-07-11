#!/usr/bin/env python3
"""
Shopify Sync API - Supabase version
Handles Shopify integration and synchronization using Supabase
"""

import json
from flask import Blueprint, request, jsonify
from flask_cors import CORS
from services.supabase_database import get_supabase_db
from services.supabase_auth import supabase_jwt_required
from datetime import datetime
import logging
import os
import sys
import traceback

# Import Shopify client
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from scripts.shopify.shopify_base import ShopifyAPIBase, CREATE_PRODUCT_MUTATION

logger = logging.getLogger(__name__)

# Create blueprint
shopify_sync_bp = Blueprint('shopify_sync', __name__, url_prefix='/api/shopify')
CORS(shopify_sync_bp)

def get_shopify_client():
    """Get configured Shopify API client."""
    shop_url = os.getenv('SHOPIFY_SHOP_URL')
    access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
    
    if not shop_url or not access_token:
        raise ValueError("Shopify credentials not configured")
    
    return ShopifyAPIBase(shop_url, access_token, debug=True)

@shopify_sync_bp.route('/products', methods=['POST'])
@supabase_jwt_required
def create_product():
    """Create a new product in Shopify and local database."""
    try:
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate required fields
        required_fields = ['title', 'description', 'vendor', 'productType']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        # Get Shopify client
        try:
            shopify_client = get_shopify_client()
        except ValueError as e:
            return jsonify({'error': str(e)}), 500
        
        # Prepare product data for Shopify GraphQL API
        product_input = {
            'title': data['title'],
            'description': data['description'],
            'vendor': data['vendor'],
            'productType': data['productType'],
            'status': data.get('status', 'DRAFT'),
            'tags': data.get('tags', []),
            'handle': data.get('handle', ''),
            'seo': {
                'title': data.get('seoTitle', ''),
                'description': data.get('seoDescription', '')
            }
        }
        
        # Add variants if provided
        variants = []
        if data.get('price') or data.get('sku'):
            variant = {}
            if data.get('price'):
                variant['price'] = str(data['price'])
            if data.get('compareAtPrice'):
                variant['compareAtPrice'] = str(data['compareAtPrice'])
            if data.get('sku'):
                variant['sku'] = data['sku']
            if data.get('barcode'):
                variant['barcode'] = data['barcode']
            if data.get('inventoryQuantity'):
                variant['inventoryQuantities'] = [{
                    'availableQuantity': int(data['inventoryQuantity']),
                    'locationId': 'gid://shopify/Location/1'  # Default location
                }]
            if data.get('weight'):
                variant['weight'] = float(data['weight'])
                variant['weightUnit'] = data.get('weightUnit', 'POUNDS')
            if data.get('inventoryPolicy'):
                variant['inventoryPolicy'] = data['inventoryPolicy']
            if data.get('inventoryTracked') is not None:
                variant['inventoryManagement'] = 'SHOPIFY' if data['inventoryTracked'] else 'NOT_MANAGED'
            if data.get('requiresShipping') is not None:
                variant['requiresShipping'] = data['requiresShipping']
            if data.get('taxable') is not None:
                variant['taxable'] = data['taxable']
            
            variants.append(variant)
        
        if variants:
            product_input['variants'] = variants
        
        # Create product in Shopify
        variables = {'input': product_input}
        
        logger.info(f"Creating product in Shopify with data: {json.dumps(variables, indent=2)}")
        
        result = shopify_client.execute_graphql(CREATE_PRODUCT_MUTATION, variables)
        
        if 'errors' in result:
            logger.error(f"Shopify GraphQL errors: {result['errors']}")
            return jsonify({'error': 'Shopify API error', 'details': result['errors']}), 500
        
        # Check for user errors
        product_create = result.get('data', {}).get('productCreate', {})
        if product_create.get('userErrors'):
            logger.error(f"Shopify user errors: {product_create['userErrors']}")
            return jsonify({'error': 'Product creation failed', 'details': product_create['userErrors']}), 400
        
        # Get created product data
        created_product = product_create.get('product')
        if not created_product:
            return jsonify({'error': 'Product creation failed - no product returned'}), 500
        
        shopify_product_id = created_product['id']
        shopify_handle = created_product['handle']
        
        logger.info(f"Product created in Shopify: {shopify_product_id}")
        
        # Store product in Supabase
        supabase = get_supabase_db()
        
        # Find or create Uncategorized category
        category_result = supabase.client.table('categories')\
            .select('id')\
            .eq('name', 'Uncategorized')\
            .single()\
            .execute()
        
        if not category_result.data:
            # Create Uncategorized category
            category_data = {
                'name': 'Uncategorized',
                'slug': 'uncategorized',
                'description': 'Default category for new products',
                'level': 0,
                'path': 'uncategorized',
                'is_active': True,
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            category_result = supabase.client.table('categories').insert(category_data).execute()
            category_id = category_result.data[0]['id']
        else:
            category_id = category_result.data['id']
        
        # Create local product record
        local_product_data = {
            'name': data['title'],
            'description': data['description'],
            'brand': data['vendor'],
            'sku': data.get('sku', ''),
            'price': float(data['price']) if data.get('price') else None,
            'compare_at_price': float(data['compareAtPrice']) if data.get('compareAtPrice') else None,
            'inventory_quantity': int(data.get('inventoryQuantity', 0)),
            'weight': float(data['weight']) if data.get('weight') else None,
            'category_id': category_id,
            'shopify_product_id': shopify_product_id,
            'shopify_sync_status': 'synced',
            'shopify_synced_at': datetime.utcnow().isoformat(),
            'product_type': data['productType'],
            'tags': data.get('tags', []),
            'handle': shopify_handle,
            'status': data.get('status', 'DRAFT').lower(),
            'seo_title': data.get('seoTitle', ''),
            'seo_description': data.get('seoDescription', ''),
            'weight_unit': data.get('weightUnit', 'POUNDS'),
            'requires_shipping': data.get('requiresShipping', True),
            'taxable': data.get('taxable', True),
            'inventory_policy': data.get('inventoryPolicy', 'DENY'),
            'inventory_tracked': data.get('inventoryTracked', True),
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }
        
        product_result = supabase.client.table('products').insert(local_product_data).execute()
        
        if not product_result.data:
            logger.error("Failed to create local product record")
            return jsonify({'error': 'Failed to create local product record'}), 500
        
        local_product_id = product_result.data[0]['id']
        
        logger.info(f"Product stored locally with ID: {local_product_id}")
        
        return jsonify({
            'success': True,
            'shopify_product_id': shopify_product_id,
            'local_product_id': local_product_id,
            'handle': shopify_handle,
            'message': 'Product created successfully'
        }), 201
        
    except Exception as e:
        logger.error(f"Error creating product: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@shopify_sync_bp.route('/products/types', methods=['GET'])
@supabase_jwt_required
def get_product_types():
    """Get available product types for dropdown selection."""
    try:
        supabase = get_supabase_db()
        
        # Get product types from existing products
        products_result = supabase.client.table('products')\
            .select('product_type')\
            .not_.is_('product_type', 'null')\
            .execute()
        
        product_types = set()
        
        if products_result.data:
            for product in products_result.data:
                product_type = product.get('product_type')
                if product_type and product_type.strip():
                    product_types.add(product_type.strip())
        
        # Also get categories as potential product types
        categories_result = supabase.client.table('categories')\
            .select('name')\
            .neq('name', 'Uncategorized')\
            .execute()
        
        if categories_result.data:
            for category in categories_result.data:
                if category.get('name'):
                    product_types.add(category['name'])
        
        # Add some common product types if database is empty
        if not product_types:
            product_types = {
                'Office Supplies', 'Electronics', 'Furniture', 'Stationery',
                'Computers', 'Accessories', 'Books', 'Art Supplies'
            }
        
        return jsonify({
            'success': True,
            'product_types': sorted(list(product_types))
        })
        
    except Exception as e:
        logger.error(f"Error getting product types: {str(e)}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@shopify_sync_bp.route('/products/vendors', methods=['GET'])
@supabase_jwt_required
def get_vendors():
    """Get available vendors for dropdown selection."""
    try:
        supabase = get_supabase_db()
        
        # Get unique vendors from existing products
        products_result = supabase.client.table('products')\
            .select('brand')\
            .not_.is_('brand', 'null')\
            .neq('brand', '')\
            .execute()
        
        vendors = set()
        
        if products_result.data:
            for product in products_result.data:
                brand = product.get('brand')
                if brand and brand.strip():
                    vendors.add(brand.strip())
        
        # Add some common vendors if database is empty
        if not vendors:
            vendors = [
                'Generic', 'House Brand', 'Private Label', 'Manufacturer Direct'
            ]
        else:
            vendors = sorted(list(vendors))
        
        return jsonify({
            'success': True,
            'vendors': vendors
        })
        
    except Exception as e:
        logger.error(f"Error getting vendors: {str(e)}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@shopify_sync_bp.route('/test-connection', methods=['GET'])
@supabase_jwt_required
def test_shopify_connection():
    """Test Shopify API connection."""
    try:
        shopify_client = get_shopify_client()
        shopify_client.test_auth()
        
        # Get shop info
        shop_query = """
        query {
          shop {
            name
            email
            domain
            currencyCode
            plan {
              displayName
            }
          }
        }
        """
        
        result = shopify_client.execute_graphql(shop_query, {})
        shop_data = result.get('data', {}).get('shop', {})
        
        return jsonify({
            'connected': True,
            'shop': {
                'name': shop_data.get('name'),
                'email': shop_data.get('email'),
                'domain': shop_data.get('domain'),
                'currency': shop_data.get('currencyCode'),
                'plan': shop_data.get('plan', {}).get('displayName')
            }
        })
        
    except Exception as e:
        logger.error(f"Shopify connection test failed: {str(e)}")
        return jsonify({
            'connected': False,
            'error': str(e)
        }), 500

@shopify_sync_bp.route('/approved-products', methods=['GET'])
@supabase_jwt_required
def get_approved_products():
    """Get products that have been approved for sync."""
    try:
        supabase = get_supabase_db()
        
        # Get query parameters
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        status = request.args.get('status', 'approved')
        
        # Calculate offset
        offset = (page - 1) * per_page
        
        # Build query for approved products
        query = supabase.client.table('products').select('*, categories(*)')
        
        # Add status filter if provided
        if status == 'approved':
            query = query.not_.is_('shopify_product_id', 'null')
        elif status == 'pending':
            query = query.is_('shopify_product_id', 'null')
        
        # Get total count
        count_result = supabase.client.table('products').select('id', count='exact')
        if status == 'approved':
            count_result = count_result.not_.is_('shopify_product_id', 'null')
        elif status == 'pending':
            count_result = count_result.is_('shopify_product_id', 'null')
        
        count_result = count_result.execute()
        total = count_result.count if hasattr(count_result, 'count') else 0
        
        # Get paginated results
        result = query.order('updated_at', desc=True)\
            .range(offset, offset + per_page - 1)\
            .execute()
        
        products = result.data if result.data else []
        
        # Format response
        items = []
        for product in products:
            items.append({
                'id': product.get('id'),
                'sku': product.get('sku', ''),
                'name': product.get('name', ''),
                'description': product.get('description', ''),
                'price': product.get('price'),
                'brand': product.get('brand', ''),
                'category': product['categories']['name'] if product.get('categories') else None,
                'inventory_quantity': product.get('inventory_quantity', 0),
                'shopify_product_id': product.get('shopify_product_id'),
                'status': product.get('status', ''),
                'sync_status': 'synced' if product.get('shopify_product_id') else 'pending',
                'updated_at': product.get('updated_at')
            })
        
        return jsonify({
            'success': True,
            'products': items,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'total_pages': (total + per_page - 1) // per_page
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting approved products: {str(e)}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@shopify_sync_bp.route('/collections', methods=['GET'])
@supabase_jwt_required
def get_collections():
    """Get Shopify collections."""
    try:
        # Try to get Shopify client
        try:
            shopify_client = get_shopify_client()
        except ValueError as e:
            logger.warning(f"Shopify not configured: {e}")
            # Return empty collections with 200 OK status if Shopify is not configured
            return jsonify({
                'success': True,
                'collections': [],
                'total': 0,
                'message': 'Shopify integration not configured'
            }), 200
        
        # GraphQL query to get collections
        collections_query = """
        query GetCollections($first: Int!) {
          collections(first: $first) {
            edges {
              node {
                id
                handle
                title
                description
                image {
                  url
                  altText
                }
                productsCount
                updatedAt
                sortOrder
                templateSuffix
                seo {
                  title
                  description
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
        
        # Get collections from Shopify
        variables = {'first': 50}
        result = shopify_client.execute_graphql(collections_query, variables)
        
        if result.get('errors'):
            logger.error(f"Shopify GraphQL errors: {result['errors']}")
            # Return empty array instead of 500 error
            return jsonify({
                'success': True,
                'error': 'Failed to fetch collections from Shopify',
                'collections': [],
                'total': 0,
                'message': 'Unable to fetch collections from Shopify'
            }), 200
        
        collections_data = result.get('data', {}).get('collections', {}).get('edges', [])
        
        # Format collections
        collections = []
        for edge in collections_data:
            collection = edge['node']
            collections.append({
                'id': collection['id'],
                'handle': collection['handle'],
                'title': collection['title'],
                'description': collection.get('description', ''),
                'image': {
                    'url': collection.get('image', {}).get('url'),
                    'alt': collection.get('image', {}).get('altText')
                } if collection.get('image') else None,
                'products_count': collection.get('productsCount', 0),
                'updated_at': collection.get('updatedAt'),
                'sort_order': collection.get('sortOrder'),
                'template_suffix': collection.get('templateSuffix'),
                'seo': {
                    'title': collection.get('seo', {}).get('title', ''),
                    'description': collection.get('seo', {}).get('description', '')
                }
            })
        
        return jsonify({
            'success': True,
            'collections': collections,
            'total': len(collections)
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting collections: {str(e)}")
        logger.error(traceback.format_exc())
        # Return empty collections instead of 500 error
        return jsonify({
            'success': True,
            'error': 'Internal server error',
            'collections': [],
            'total': 0,
            'message': 'Unable to fetch collections'
        }), 200

@shopify_sync_bp.route('/product-types', methods=['GET'])
@supabase_jwt_required
def get_shopify_product_types():
    """Get product types from Shopify."""
    try:
        shopify_client = get_shopify_client()
        
        # GraphQL query to get product types
        product_types_query = """
        query GetProductTypes($first: Int!) {
          products(first: $first) {
            edges {
              node {
                productType
              }
            }
            pageInfo {
              hasNextPage
              endCursor
            }
          }
        }
        """
        
        # Get product types from Shopify
        variables = {'first': 250}
        result = shopify_client.execute_graphql(product_types_query, variables)
        
        if result.get('errors'):
            return jsonify({'error': 'Failed to fetch product types from Shopify'}), 500
        
        products_data = result.get('data', {}).get('products', {}).get('edges', [])
        
        # Extract unique product types
        product_types = set()
        for edge in products_data:
            product_type = edge['node'].get('productType')
            if product_type and product_type.strip():
                product_types.add(product_type.strip())
        
        # Also get types from local database
        supabase = get_supabase_db()
        local_result = supabase.client.table('products')\
            .select('brand')\
            .not_.is_('brand', 'null')\
            .neq('brand', '')\
            .execute()
        
        if local_result.data:
            for product in local_result.data:
                brand = product.get('brand')
                if brand and brand.strip():
                    product_types.add(brand.strip())
        
        return jsonify({
            'success': True,
            'product_types': sorted(list(product_types))
        })
        
    except Exception as e:
        logger.error(f"Error getting product types: {str(e)}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

# Sync status endpoints
@shopify_sync_bp.route('/sync-status', methods=['GET'])
@supabase_jwt_required
def get_sync_status():
    """Get synchronization status between local and Shopify."""
    try:
        supabase = get_supabase_db()
        
        # Get sync statistics
        total_result = supabase.client.table('products').select('id', count='exact').execute()
        total_products = total_result.count if hasattr(total_result, 'count') else 0
        
        synced_result = supabase.client.table('products')\
            .select('id', count='exact')\
            .not_.is_('shopify_product_id', 'null')\
            .execute()
        synced_products = synced_result.count if hasattr(synced_result, 'count') else 0
        
        pending_sync = total_products - synced_products
        
        # Get recent sync activity
        recent_result = supabase.client.table('products')\
            .select('name, shopify_synced_at')\
            .not_.is_('shopify_synced_at', 'null')\
            .order('shopify_synced_at', desc=True)\
            .limit(5)\
            .execute()
        
        recent_syncs = recent_result.data if recent_result.data else []
        
        return jsonify({
            'success': True,
            'sync_status': {
                'total_products': total_products,
                'synced_products': synced_products,
                'pending_sync': pending_sync,
                'sync_percentage': (synced_products / total_products * 100) if total_products > 0 else 0,
                'recent_syncs': recent_syncs
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting sync status: {str(e)}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500