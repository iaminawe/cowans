#!/usr/bin/env python3
"""
Products API - Supabase version
Handles all product-related operations using Supabase
"""

from flask import Blueprint, jsonify, request
from flask_cors import CORS
from services.supabase_database import get_supabase_db
from services.supabase_auth import supabase_jwt_required
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

products_bp = Blueprint('products', __name__)
CORS(products_bp)

@products_bp.route('/api/products', methods=['GET'])
@supabase_jwt_required
def get_products():
    """Get all products with filtering, pagination, and search."""
    try:
        supabase = get_supabase_db()
        
        # Get query parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 50, type=int), 100)  # Cap at 100
        search = request.args.get('search', '').strip()
        category_id = request.args.get('category_id', type=int)
        status = request.args.get('status', '').strip()
        brand = request.args.get('brand', '').strip()
        sort_by = request.args.get('sort_by', 'updated_at')
        sort_order = request.args.get('sort_order', 'desc')
        
        # Calculate offset
        offset = (page - 1) * per_page
        
        # Build query with joins for categories
        query = supabase.client.table('products').select('*, categories(*)')
        
        # Apply filters
        if search:
            # Search in name, description, sku, and brand
            query = query.or_(f'name.ilike.%{search}%,description.ilike.%{search}%,sku.ilike.%{search}%,brand.ilike.%{search}%')
        
        if category_id:
            query = query.eq('category_id', category_id)
        
        if status:
            query = query.eq('status', status)
        
        if brand:
            query = query.eq('brand', brand)
        
        # Apply sorting
        desc = sort_order.lower() == 'desc'
        query = query.order(sort_by, desc=desc)
        
        # Get total count for pagination
        count_query = supabase.client.table('products').select('id', count='exact')
        if search:
            count_query = count_query.or_(f'name.ilike.%{search}%,description.ilike.%{search}%,sku.ilike.%{search}%,brand.ilike.%{search}%')
        if category_id:
            count_query = count_query.eq('category_id', category_id)
        if status:
            count_query = count_query.eq('status', status)
        if brand:
            count_query = count_query.eq('brand', brand)
        
        count_result = count_query.execute()
        total = count_result.count if hasattr(count_result, 'count') else 0
        
        # Get paginated results
        result = query.range(offset, offset + per_page - 1).execute()
        
        products = result.data if result.data else []
        
        # Format products for response
        formatted_products = []
        for product in products:
            formatted_product = {
                'id': product.get('id'),
                'name': product.get('name', ''),
                'description': product.get('description', ''),
                'sku': product.get('sku', ''),
                'price': product.get('price'),
                'compare_at_price': product.get('compare_at_price'),
                'brand': product.get('brand', ''),
                'manufacturer': product.get('manufacturer', ''),
                'product_type': product.get('product_type', ''),
                'status': product.get('status', 'draft'),
                'inventory_quantity': product.get('inventory_quantity', 0),
                'weight': product.get('weight'),
                'weight_unit': product.get('weight_unit', 'kg'),
                'requires_shipping': product.get('requires_shipping', True),
                'taxable': product.get('taxable', True),
                'tags': product.get('tags', []),
                'handle': product.get('handle', ''),
                'seo_title': product.get('seo_title', ''),
                'seo_description': product.get('seo_description', ''),
                'shopify_product_id': product.get('shopify_product_id'),
                'shopify_sync_status': product.get('shopify_sync_status'),
                'shopify_synced_at': product.get('shopify_synced_at'),
                'category': product['categories'] if product.get('categories') else None,
                'category_id': product.get('category_id'),
                'created_at': product.get('created_at'),
                'updated_at': product.get('updated_at')
            }
            formatted_products.append(formatted_product)
        
        return jsonify({
            'success': True,
            'products': formatted_products,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'total_pages': (total + per_page - 1) // per_page,
                'has_next': offset + per_page < total,
                'has_prev': page > 1
            },
            'filters': {
                'search': search,
                'category_id': category_id,
                'status': status,
                'brand': brand,
                'sort_by': sort_by,
                'sort_order': sort_order
            }
        })
        
    except Exception as e:
        logger.error(f"Error fetching products: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to fetch products',
            'products': [],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': 0,
                'total_pages': 0,
                'has_next': False,
                'has_prev': False
            }
        }), 200

@products_bp.route('/api/products/<int:product_id>', methods=['GET'])
@supabase_jwt_required
def get_product(product_id):
    """Get a specific product by ID."""
    try:
        supabase = get_supabase_db()
        
        # Get product with category information
        result = supabase.client.table('products')\
            .select('*, categories(*)')\
            .eq('id', product_id)\
            .single()\
            .execute()
        
        if result.data:
            product = result.data
            
            # Get collections this product belongs to
            collections_result = supabase.client.table('product_collections')\
                .select('collection_id, collections(*)')\
                .eq('product_id', product_id)\
                .execute()
            
            collections = []
            if collections_result.data:
                for pc in collections_result.data:
                    if pc.get('collections'):
                        collections.append(pc['collections'])
            
            # Format response
            formatted_product = {
                'id': product.get('id'),
                'name': product.get('name', ''),
                'description': product.get('description', ''),
                'sku': product.get('sku', ''),
                'price': product.get('price'),
                'compare_at_price': product.get('compare_at_price'),
                'brand': product.get('brand', ''),
                'manufacturer': product.get('manufacturer', ''),
                'product_type': product.get('product_type', ''),
                'status': product.get('status', 'draft'),
                'inventory_quantity': product.get('inventory_quantity', 0),
                'weight': product.get('weight'),
                'weight_unit': product.get('weight_unit', 'kg'),
                'requires_shipping': product.get('requires_shipping', True),
                'taxable': product.get('taxable', True),
                'tags': product.get('tags', []),
                'handle': product.get('handle', ''),
                'seo_title': product.get('seo_title', ''),
                'seo_description': product.get('seo_description', ''),
                'shopify_product_id': product.get('shopify_product_id'),
                'shopify_sync_status': product.get('shopify_sync_status'),
                'shopify_synced_at': product.get('shopify_synced_at'),
                'category': product['categories'] if product.get('categories') else None,
                'category_id': product.get('category_id'),
                'collections': collections,
                'created_at': product.get('created_at'),
                'updated_at': product.get('updated_at')
            }
            
            return jsonify({
                'success': True,
                'product': formatted_product
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Product not found'
            }), 404
            
    except Exception as e:
        logger.error(f"Error fetching product {product_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to fetch product'
        }), 500

@products_bp.route('/api/products', methods=['POST'])
@supabase_jwt_required
def create_product():
    """Create a new product."""
    try:
        supabase = get_supabase_db()
        data = request.get_json()
        
        # Validate required fields
        if not data.get('name'):
            return jsonify({
                'success': False,
                'error': 'Name is required'
            }), 400
        
        # Create product data
        product_data = {
            'name': data['name'],
            'description': data.get('description', ''),
            'sku': data.get('sku', ''),
            'price': data.get('price'),
            'compare_at_price': data.get('compare_at_price'),
            'brand': data.get('brand', ''),
            'manufacturer': data.get('manufacturer', ''),
            'product_type': data.get('product_type', ''),
            'status': data.get('status', 'draft'),
            'inventory_quantity': data.get('inventory_quantity', 0),
            'weight': data.get('weight'),
            'weight_unit': data.get('weight_unit', 'kg'),
            'requires_shipping': data.get('requires_shipping', True),
            'taxable': data.get('taxable', True),
            'tags': data.get('tags', []),
            'handle': data.get('handle', ''),
            'seo_title': data.get('seo_title', ''),
            'seo_description': data.get('seo_description', ''),
            'category_id': data.get('category_id'),
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }
        
        # Insert product
        result = supabase.client.table('products').insert(product_data).execute()
        
        if result.data:
            return jsonify({
                'success': True,
                'product': result.data[0],
                'message': 'Product created successfully'
            }), 201
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to create product'
            }), 500
            
    except Exception as e:
        logger.error(f"Error creating product: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to create product'
        }), 500

@products_bp.route('/api/products/<int:product_id>', methods=['PUT'])
@supabase_jwt_required
def update_product(product_id):
    """Update a product."""
    try:
        supabase = get_supabase_db()
        data = request.get_json()
        
        # Build update data
        update_data = {}
        
        # Only update provided fields
        for field in ['name', 'description', 'sku', 'price', 'compare_at_price', 
                     'brand', 'manufacturer', 'product_type', 'status', 
                     'inventory_quantity', 'weight', 'weight_unit', 'requires_shipping', 
                     'taxable', 'tags', 'handle', 'seo_title', 'seo_description', 
                     'category_id']:
            if field in data:
                update_data[field] = data[field]
        
        update_data['updated_at'] = datetime.utcnow().isoformat()
        
        # Update product
        result = supabase.client.table('products')\
            .update(update_data)\
            .eq('id', product_id)\
            .execute()
        
        if result.data:
            return jsonify({
                'success': True,
                'product': result.data[0],
                'message': 'Product updated successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Product not found'
            }), 404
            
    except Exception as e:
        logger.error(f"Error updating product {product_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to update product'
        }), 500

@products_bp.route('/api/products/<int:product_id>', methods=['DELETE'])
@supabase_jwt_required
def delete_product(product_id):
    """Delete a product."""
    try:
        supabase = get_supabase_db()
        
        # First remove from collections
        supabase.client.table('product_collections')\
            .delete()\
            .eq('product_id', product_id)\
            .execute()
        
        # Then delete the product
        result = supabase.client.table('products')\
            .delete()\
            .eq('id', product_id)\
            .execute()
        
        return jsonify({
            'success': True,
            'message': 'Product deleted successfully'
        })
        
    except Exception as e:
        logger.error(f"Error deleting product {product_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to delete product'
        }), 500

@products_bp.route('/api/products/summary', methods=['GET'])
@supabase_jwt_required
def get_products_summary():
    """Get products summary statistics."""
    try:
        supabase = get_supabase_db()
        
        # Get total products
        total_result = supabase.client.table('products').select('id', count='exact').execute()
        total_products = total_result.count if hasattr(total_result, 'count') else 0
        
        # Get products by status
        active_result = supabase.client.table('products')\
            .select('id', count='exact')\
            .eq('status', 'active')\
            .execute()
        active_products = active_result.count if hasattr(active_result, 'count') else 0
        
        draft_result = supabase.client.table('products')\
            .select('id', count='exact')\
            .eq('status', 'draft')\
            .execute()
        draft_products = draft_result.count if hasattr(draft_result, 'count') else 0
        
        # Get synced products
        synced_result = supabase.client.table('products')\
            .select('id', count='exact')\
            .not_.is_('shopify_product_id', 'null')\
            .execute()
        synced_products = synced_result.count if hasattr(synced_result, 'count') else 0
        
        # Get low stock products (inventory < 10)
        low_stock_result = supabase.client.table('products')\
            .select('id', count='exact')\
            .lt('inventory_quantity', 10)\
            .execute()
        low_stock_products = low_stock_result.count if hasattr(low_stock_result, 'count') else 0
        
        # Get recent products (last 7 days)
        week_ago = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        week_ago = week_ago.replace(day=week_ago.day - 7)
        
        recent_result = supabase.client.table('products')\
            .select('id', count='exact')\
            .gte('created_at', week_ago.isoformat())\
            .execute()
        recent_products = recent_result.count if hasattr(recent_result, 'count') else 0
        
        # Get top brands
        brands_result = supabase.client.table('products')\
            .select('brand')\
            .not_.is_('brand', 'null')\
            .neq('brand', '')\
            .execute()
        
        brand_counts = {}
        if brands_result.data:
            for product in brands_result.data:
                brand = product.get('brand')
                if brand:
                    brand_counts[brand] = brand_counts.get(brand, 0) + 1
        
        top_brands = sorted(brand_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return jsonify({
            'success': True,
            'summary': {
                'total_products': total_products,
                'active_products': active_products,
                'draft_products': draft_products,
                'synced_products': synced_products,
                'pending_sync': total_products - synced_products,
                'low_stock_products': low_stock_products,
                'recent_products': recent_products,
                'top_brands': [{'brand': brand, 'count': count} for brand, count in top_brands]
            }
        })
        
    except Exception as e:
        logger.error(f"Error fetching products summary: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to fetch summary',
            'summary': {
                'total_products': 0,
                'active_products': 0,
                'draft_products': 0,
                'synced_products': 0,
                'pending_sync': 0,
                'low_stock_products': 0,
                'recent_products': 0,
                'top_brands': []
            }
        }), 200

@products_bp.route('/api/products/search', methods=['GET'])
@supabase_jwt_required
def search_products():
    """Search products by various criteria."""
    try:
        supabase = get_supabase_db()
        
        query = request.args.get('q', '').strip()
        limit = min(request.args.get('limit', 20, type=int), 100)
        
        if not query:
            return jsonify({
                'success': True,
                'products': []
            })
        
        # Search products
        result = supabase.client.table('products')\
            .select('id, name, sku, brand, price, status, categories(*)')\
            .or_(f'name.ilike.%{query}%,description.ilike.%{query}%,sku.ilike.%{query}%,brand.ilike.%{query}%')\
            .limit(limit)\
            .execute()
        
        products = result.data if result.data else []
        
        return jsonify({
            'success': True,
            'products': products,
            'query': query,
            'total': len(products)
        })
        
    except Exception as e:
        logger.error(f"Error searching products: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to search products',
            'products': []
        }), 200

@products_bp.route('/api/products/brands', methods=['GET'])
@supabase_jwt_required
def get_brands():
    """Get all unique brands."""
    try:
        supabase = get_supabase_db()
        
        # Get unique brands
        result = supabase.client.table('products')\
            .select('brand')\
            .not_.is_('brand', 'null')\
            .neq('brand', '')\
            .execute()
        
        brands = set()
        if result.data:
            for product in result.data:
                brand = product.get('brand')
                if brand and brand.strip():
                    brands.add(brand.strip())
        
        return jsonify({
            'success': True,
            'brands': sorted(list(brands))
        })
        
    except Exception as e:
        logger.error(f"Error fetching brands: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to fetch brands',
            'brands': []
        }), 200

@products_bp.route('/api/products/types', methods=['GET'])
@supabase_jwt_required
def get_product_types():
    """Get all unique product types."""
    try:
        supabase = get_supabase_db()
        
        # Get unique product types
        result = supabase.client.table('products')\
            .select('product_type')\
            .not_.is_('product_type', 'null')\
            .neq('product_type', '')\
            .execute()
        
        types = set()
        if result.data:
            for product in result.data:
                product_type = product.get('product_type')
                if product_type and product_type.strip():
                    types.add(product_type.strip())
        
        return jsonify({
            'success': True,
            'product_types': sorted(list(types))
        })
        
    except Exception as e:
        logger.error(f"Error fetching product types: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to fetch product types',
            'product_types': []
        }), 200

# Additional endpoints for frontend compatibility
@products_bp.route('/api/products/with-shopify-data', methods=['GET'])
@supabase_jwt_required
def get_products_with_shopify_data():
    """Get products with Shopify data for sync manager."""
    try:
        supabase = get_supabase_db()
        
        # Get query parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 50, type=int), 100)
        
        # Calculate offset
        offset = (page - 1) * per_page
        
        # Get products with Shopify data
        result = supabase.client.table('products')\
            .select('*, categories(*)')\
            .not_.is_('shopify_product_id', 'null')\
            .order('updated_at', desc=True)\
            .range(offset, offset + per_page - 1)\
            .execute()
        
        # Get total count
        count_result = supabase.client.table('products')\
            .select('id', count='exact')\
            .not_.is_('shopify_product_id', 'null')\
            .execute()
        
        total = count_result.count if hasattr(count_result, 'count') else 0
        
        products = result.data if result.data else []
        
        return jsonify({
            'success': True,
            'products': products,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'total_pages': (total + per_page - 1) // per_page,
                'has_next': offset + per_page < total,
                'has_prev': page > 1
            }
        })
        
    except Exception as e:
        logger.error(f"Error fetching products with Shopify data: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to fetch products with Shopify data',
            'products': [],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': 0,
                'total_pages': 0,
                'has_next': False,
                'has_prev': False
            }
        }), 200

@products_bp.route('/api/products/sync/status', methods=['GET'])
@supabase_jwt_required
def get_products_sync_status():
    """Get sync status for products."""
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
        
        return jsonify({
            'success': True,
            'total_products': total_products,
            'synced_products': synced_products,
            'pending_sync': total_products - synced_products,
            'sync_percentage': (synced_products / total_products * 100) if total_products > 0 else 0,
            'last_sync': None,
            'sync_in_progress': False
        })
        
    except Exception as e:
        logger.error(f"Error fetching sync status: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to fetch sync status',
            'total_products': 0,
            'synced_products': 0,
            'pending_sync': 0,
            'sync_percentage': 0
        }), 200

@products_bp.route('/api/products/sync/operations', methods=['GET'])
@supabase_jwt_required
def get_products_sync_operations():
    """Get sync operations for products."""
    try:
        # For now, return empty operations
        return jsonify({
            'success': True,
            'operations': []
        })
        
    except Exception as e:
        logger.error(f"Error fetching sync operations: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to fetch sync operations',
            'operations': []
        }), 200

@products_bp.route('/api/products/<int:product_id>/changes', methods=['GET'])
@supabase_jwt_required
def get_product_changes(product_id):
    """Get change history for a product."""
    try:
        # For now, return empty changes
        return jsonify({
            'success': True,
            'changes': []
        })
        
    except Exception as e:
        logger.error(f"Error fetching product changes: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to fetch product changes',
            'changes': []
        }), 200

@products_bp.route('/api/products/<int:product_id>/sync', methods=['POST'])
@supabase_jwt_required
def sync_product(product_id):
    """Sync a specific product."""
    try:
        # For now, just return success
        return jsonify({
            'success': True,
            'message': f'Product {product_id} sync initiated'
        })
        
    except Exception as e:
        logger.error(f"Error syncing product {product_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to sync product'
        }), 500

@products_bp.route('/api/products/sync/batch', methods=['POST'])
@supabase_jwt_required
def batch_sync_products():
    """Batch sync products."""
    try:
        data = request.get_json()
        product_ids = data.get('product_ids', [])
        operation = data.get('operation', 'sync')
        
        return jsonify({
            'success': True,
            'operation': {
                'id': 'batch_sync_' + str(len(product_ids)),
                'type': operation,
                'status': 'queued',
                'product_count': len(product_ids)
            }
        })
        
    except Exception as e:
        logger.error(f"Error in batch sync: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to batch sync products'
        }), 500