#!/usr/bin/env python3
"""
Collections API - Supabase version
Handles all collection-related operations using Supabase
"""

from flask import Blueprint, jsonify, request
from flask_cors import CORS
from services.supabase_database import get_supabase_db
from services.supabase_auth import supabase_jwt_required
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

collections_bp = Blueprint('collections', __name__)
CORS(collections_bp)

@collections_bp.route('/api/collections', methods=['GET'])
@supabase_jwt_required
def get_collections():
    """Get all collections with optional filtering"""
    try:
        supabase = get_supabase_db()
        
        # Get query parameters
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        is_active = request.args.get('is_active', None)
        
        # Build query
        query = supabase.client.table('collections').select('*')
        
        if is_active is not None:
            query = query.eq('is_active', is_active.lower() == 'true')
        
        # Execute query with pagination
        result = query.range(offset, offset + limit - 1).order('created_at', desc=True).execute()
        
        collections = result.data if result.data else []
        
        return jsonify({
            'collections': collections,
            'total': len(collections),
            'limit': limit,
            'offset': offset
        })
        
    except Exception as e:
        logger.error(f"Error fetching collections: {str(e)}")
        return jsonify({
            'collections': [],
            'total': 0,
            'error': 'Failed to fetch collections'
        }), 200

@collections_bp.route('/api/collections/<int:collection_id>', methods=['GET'])
@supabase_jwt_required
def get_collection(collection_id):
    """Get a specific collection by ID"""
    try:
        supabase = get_supabase_db()
        
        # Get collection
        result = supabase.client.table('collections')\
            .select('*')\
            .eq('id', collection_id)\
            .single()\
            .execute()
        
        if result.data:
            # Get products in this collection
            products_result = supabase.client.table('product_collections')\
                .select('product_id, products(*)')\
                .eq('collection_id', collection_id)\
                .execute()
            
            collection = result.data
            collection['products'] = [pc['products'] for pc in (products_result.data or []) if pc.get('products')]
            
            return jsonify(collection)
        else:
            return jsonify({'error': 'Collection not found'}), 404
            
    except Exception as e:
        logger.error(f"Error fetching collection {collection_id}: {str(e)}")
        return jsonify({'error': 'Failed to fetch collection'}), 500

@collections_bp.route('/api/collections', methods=['POST'])
@supabase_jwt_required
def create_collection():
    """Create a new collection"""
    try:
        supabase = get_supabase_db()
        data = request.get_json()
        
        # Validate required fields
        if not data.get('title'):
            return jsonify({'error': 'Title is required'}), 400
        
        # Create collection
        collection_data = {
            'title': data['title'],
            'handle': data.get('handle', data['title'].lower().replace(' ', '-')),
            'description': data.get('description', ''),
            'is_active': data.get('is_active', True),
            'shopify_collection_id': data.get('shopify_collection_id'),
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }
        
        result = supabase.client.table('collections').insert(collection_data).execute()
        
        if result.data:
            return jsonify(result.data[0]), 201
        else:
            return jsonify({'error': 'Failed to create collection'}), 500
            
    except Exception as e:
        logger.error(f"Error creating collection: {str(e)}")
        return jsonify({'error': 'Failed to create collection'}), 500

@collections_bp.route('/api/collections/<int:collection_id>', methods=['PUT'])
@supabase_jwt_required
def update_collection(collection_id):
    """Update a collection"""
    try:
        supabase = get_supabase_db()
        data = request.get_json()
        
        # Update only provided fields
        update_data = {}
        if 'title' in data:
            update_data['title'] = data['title']
        if 'handle' in data:
            update_data['handle'] = data['handle']
        if 'description' in data:
            update_data['description'] = data['description']
        if 'is_active' in data:
            update_data['is_active'] = data['is_active']
        
        update_data['updated_at'] = datetime.utcnow().isoformat()
        
        result = supabase.client.table('collections')\
            .update(update_data)\
            .eq('id', collection_id)\
            .execute()
        
        if result.data:
            return jsonify(result.data[0])
        else:
            return jsonify({'error': 'Collection not found'}), 404
            
    except Exception as e:
        logger.error(f"Error updating collection {collection_id}: {str(e)}")
        return jsonify({'error': 'Failed to update collection'}), 500

@collections_bp.route('/api/collections/<int:collection_id>', methods=['DELETE'])
@supabase_jwt_required
def delete_collection(collection_id):
    """Delete a collection"""
    try:
        supabase = get_supabase_db()
        
        # First remove all product associations
        supabase.client.table('product_collections')\
            .delete()\
            .eq('collection_id', collection_id)\
            .execute()
        
        # Then delete the collection
        result = supabase.client.table('collections')\
            .delete()\
            .eq('id', collection_id)\
            .execute()
        
        return jsonify({'message': 'Collection deleted successfully'}), 200
        
    except Exception as e:
        logger.error(f"Error deleting collection {collection_id}: {str(e)}")
        return jsonify({'error': 'Failed to delete collection'}), 500

@collections_bp.route('/api/collections/summary', methods=['GET'])
@supabase_jwt_required
def get_collections_summary():
    """Get collections summary statistics"""
    try:
        supabase = get_supabase_db()
        
        # Get total collections
        collections_result = supabase.client.table('collections').select('id, is_active').execute()
        collections = collections_result.data if collections_result.data else []
        
        total_collections = len(collections)
        active_collections = len([c for c in collections if c.get('is_active')])
        
        # Get synced collections (those with shopify_collection_id)
        synced_result = supabase.client.table('collections')\
            .select('id')\
            .not_.is_('shopify_collection_id', 'null')\
            .execute()
        synced_collections = len(synced_result.data) if synced_result.data else 0
        
        return jsonify({
            'total_collections': total_collections,
            'active_collections': active_collections,
            'synced_collections': synced_collections,
            'pending_sync': total_collections - synced_collections,
            'collection_stats': []  # TODO: Add more detailed stats if needed
        })
        
    except Exception as e:
        logger.error(f"Error fetching collections summary: {str(e)}")
        return jsonify({
            'total_collections': 0,
            'active_collections': 0,
            'synced_collections': 0,
            'pending_sync': 0,
            'collection_stats': []
        }), 200

@collections_bp.route('/api/collections/<int:collection_id>/products', methods=['POST'])
@supabase_jwt_required
def add_products_to_collection(collection_id):
    """Add products to a collection"""
    try:
        supabase = get_supabase_db()
        data = request.get_json()
        
        product_ids = data.get('product_ids', [])
        if not product_ids:
            return jsonify({'error': 'No product IDs provided'}), 400
        
        # Add products to collection
        associations = []
        for idx, product_id in enumerate(product_ids):
            associations.append({
                'collection_id': collection_id,
                'product_id': product_id,
                'position': idx
            })
        
        # Insert all associations
        result = supabase.client.table('product_collections')\
            .upsert(associations, on_conflict='product_id,collection_id')\
            .execute()
        
        return jsonify({
            'message': f'Added {len(product_ids)} products to collection',
            'added': len(result.data) if result.data else 0
        })
        
    except Exception as e:
        logger.error(f"Error adding products to collection {collection_id}: {str(e)}")
        return jsonify({'error': 'Failed to add products to collection'}), 500

@collections_bp.route('/api/collections/<int:collection_id>/products/<int:product_id>', methods=['DELETE'])
@supabase_jwt_required
def remove_product_from_collection(collection_id, product_id):
    """Remove a product from a collection"""
    try:
        supabase = get_supabase_db()
        
        result = supabase.client.table('product_collections')\
            .delete()\
            .eq('collection_id', collection_id)\
            .eq('product_id', product_id)\
            .execute()
        
        return jsonify({'message': 'Product removed from collection'}), 200
        
    except Exception as e:
        logger.error(f"Error removing product {product_id} from collection {collection_id}: {str(e)}")
        return jsonify({'error': 'Failed to remove product from collection'}), 500

# Additional endpoints that were referenced in the frontend
@collections_bp.route('/api/collections/managed', methods=['GET'])
@supabase_jwt_required
def get_managed_collections():
    """Get collections that are managed (not from Shopify)"""
    try:
        supabase = get_supabase_db()
        
        # Get collections without shopify_collection_id
        result = supabase.client.table('collections')\
            .select('*')\
            .is_('shopify_collection_id', 'null')\
            .order('created_at', desc=True)\
            .execute()
        
        return jsonify({
            'collections': result.data if result.data else []
        })
        
    except Exception as e:
        logger.error(f"Error fetching managed collections: {str(e)}")
        return jsonify({'collections': []}), 200

@collections_bp.route('/api/collections/product-types-summary', methods=['GET'])
@supabase_jwt_required
def get_product_types_summary():
    """Get summary of product types for collection creation"""
    try:
        supabase = get_supabase_db()
        
        # Get all unique product types
        products_result = supabase.client.table('products')\
            .select('product_type')\
            .not_.is_('product_type', 'null')\
            .execute()
        
        if products_result.data:
            # Count products by type
            type_counts = {}
            for product in products_result.data:
                ptype = product.get('product_type', 'Unknown')
                type_counts[ptype] = type_counts.get(ptype, 0) + 1
            
            # Format response
            product_types = []
            for ptype, count in type_counts.items():
                product_types.append({
                    'name': ptype,
                    'product_count': count,
                    'collection_status': 'available'  # TODO: Check if collection exists
                })
            
            return jsonify({
                'product_types': sorted(product_types, key=lambda x: x['product_count'], reverse=True)
            })
        
        return jsonify({'product_types': []})
        
    except Exception as e:
        logger.error(f"Error fetching product types summary: {str(e)}")
        return jsonify({'product_types': []}), 200