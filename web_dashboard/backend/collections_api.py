"""Collections API endpoints for managing product collections."""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from services.supabase_auth import supabase_jwt_required, get_current_user_id
from marshmallow import Schema, fields, validate, ValidationError
from datetime import datetime
from typing import List, Dict, Any
import logging

from database import db_session_scope
from repositories.collection_repository import CollectionRepository
from repositories.product_repository import ProductRepository
from services.shopify_sync_service import ShopifySyncService
from shopify_collections import ShopifyCollectionsManager
from config import Config

# Configure logging
logger = logging.getLogger(__name__)

# Create Blueprint
collections_bp = Blueprint('collections', __name__, url_prefix='/api/collections')


# Schemas
class CollectionSchema(Schema):
    """Schema for collection validation."""
    id = fields.Integer(dump_only=True)
    name = fields.String(required=True, validate=validate.Length(min=1, max=255))
    handle = fields.String(required=True, validate=validate.Length(min=1, max=255))
    description = fields.String(allow_none=True)
    sort_order = fields.String(validate=validate.OneOf(['manual', 'alphabetical', 'price_ascending', 'price_descending', 'created_descending']))
    status = fields.String(validate=validate.OneOf(['draft', 'active', 'archived']))
    rules_type = fields.String(validate=validate.OneOf(['manual', 'automatic']))
    rules_conditions = fields.List(fields.Dict(), allow_none=True)
    disjunctive = fields.Boolean(default=False)
    seo_title = fields.String(allow_none=True)
    seo_description = fields.String(allow_none=True)
    products_count = fields.Integer(dump_only=True)
    shopify_collection_id = fields.String(dump_only=True)
    shopify_synced_at = fields.DateTime(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)


class ProductTypeSchema(Schema):
    """Schema for product type summary."""
    name = fields.String(required=True)
    product_count = fields.Integer(required=True)
    avg_price = fields.Float(required=True)
    vendors = fields.List(fields.String())
    categories = fields.List(fields.Integer())


class CollectionProductSchema(Schema):
    """Schema for adding/removing products from collections."""
    product_ids = fields.List(fields.Integer(), required=True)
    position_start = fields.Integer(default=0)


class AICollectionSuggestionSchema(Schema):
    """Schema for AI collection suggestions."""
    product_types = fields.List(fields.String(), required=True)


# Initialize schemas
collection_schema = CollectionSchema()
collections_schema = CollectionSchema(many=True)
product_type_schema = ProductTypeSchema()
product_types_schema = ProductTypeSchema(many=True)


@collections_bp.route('/', methods=['GET'])
@collections_bp.route('', methods=['GET'])
@supabase_jwt_required
def get_collections():
    """Get all collections with statistics."""
    try:
        status = request.args.get('status')
        include_archived = request.args.get('include_archived', 'false').lower() == 'true'
        
        with db_session_scope() as session:
            repo = CollectionRepository(session)
            collections = repo.get_all_with_stats(status=status, include_archived=include_archived)
        
        return jsonify({
            'collections': collections,
            'total': len(collections)
        }), 200
    
    except Exception as e:
        logger.error(f"Error fetching collections: {str(e)}")
        return jsonify({'error': 'Failed to fetch collections'}), 500


@collections_bp.route('/<int:collection_id>', methods=['GET'])
@supabase_jwt_required
def get_collection(collection_id: int):
    """Get a single collection with its products."""
    try:
        with db_session_scope() as session:
            repo = CollectionRepository(session)
            collection = repo.get_with_products(collection_id)
            
            if not collection:
                return jsonify({'error': 'Collection not found'}), 404
            
            result = collection_schema.dump(collection)
            # Add products list
            result['products'] = [
                {
                    'id': p.id,
                    'sku': p.sku,
                    'name': p.name,
                    'price': p.price,
                    'status': p.status
                }
                for p in collection.products
            ]
        
        return jsonify(result), 200
    
    except Exception as e:
        logger.error(f"Error fetching collection {collection_id}: {str(e)}")
        return jsonify({'error': 'Failed to fetch collection'}), 500


@collections_bp.route('/create', methods=['POST'])
@supabase_jwt_required
def create_collection():
    """Create a new collection."""
    try:
        # Validate input
        data = request.get_json()
        errors = collection_schema.validate(data)
        if errors:
            return jsonify({'errors': errors}), 400
        
        user_id = get_jwt_identity()
        
        with db_session_scope() as session:
            repo = CollectionRepository(session)
            
            # Check if handle already exists
            if repo.get_by_handle(data['handle']):
                return jsonify({'error': 'Collection with this handle already exists'}), 409
            
            # Create collection
            collection = repo.create_collection(
                name=data['name'],
                handle=data['handle'],
                description=data.get('description'),
                created_by=user_id,
                rules_type=data.get('rules_type', 'manual'),
                rules_conditions=data.get('rules_conditions'),
                disjunctive=data.get('disjunctive', False),
                status=data.get('status', 'draft'),
                sort_order=data.get('sort_order', 'manual'),
                seo_title=data.get('seo_title'),
                seo_description=data.get('seo_description')
            )
            
            # If automatic collection, populate products
            if collection.rules_type == 'automatic' and collection.rules_conditions:
                repo.update_automatic_collection(collection.id)
            
            result = collection_schema.dump(collection)
        
        return jsonify({
            'message': 'Collection created successfully',
            'collection': result
        }), 201
    
    except Exception as e:
        logger.error(f"Error creating collection: {str(e)}")
        return jsonify({'error': 'Failed to create collection'}), 500


@collections_bp.route('/<int:collection_id>', methods=['PUT'])
@supabase_jwt_required
def update_collection(collection_id: int):
    """Update a collection."""
    try:
        data = request.get_json()
        user_id = get_jwt_identity()
        
        with db_session_scope() as session:
            repo = CollectionRepository(session)
            
            # Check if collection exists
            collection = repo.get(collection_id)
            if not collection:
                return jsonify({'error': 'Collection not found'}), 404
            
            # Update collection
            updated_collection = repo.update_collection(
                collection_id=collection_id,
                updated_by=user_id,
                **data
            )
            
            # If rules changed and it's automatic, update products
            if updated_collection.rules_type == 'automatic' and 'rules_conditions' in data:
                repo.update_automatic_collection(collection_id)
            
            result = collection_schema.dump(updated_collection)
        
        return jsonify({
            'message': 'Collection updated successfully',
            'collection': result
        }), 200
    
    except Exception as e:
        logger.error(f"Error updating collection {collection_id}: {str(e)}")
        return jsonify({'error': 'Failed to update collection'}), 500


@collections_bp.route('/<int:collection_id>/products', methods=['POST'])
@supabase_jwt_required
def add_products_to_collection(collection_id: int):
    """Add products to a collection."""
    try:
        data = request.get_json()
        product_ids = data.get('product_ids', [])
        position_start = data.get('position_start', 0)
        
        if not product_ids:
            return jsonify({'error': 'No product IDs provided'}), 400
        
        with db_session_scope() as session:
            repo = CollectionRepository(session)
            
            # Check if collection exists
            collection = repo.get(collection_id)
            if not collection:
                return jsonify({'error': 'Collection not found'}), 404
            
            # Add products
            added_count = repo.add_products_to_collection(
                collection_id=collection_id,
                product_ids=product_ids,
                position_start=position_start
            )
        
        return jsonify({
            'message': f'Added {added_count} products to collection',
            'added_count': added_count
        }), 200
    
    except Exception as e:
        logger.error(f"Error adding products to collection {collection_id}: {str(e)}")
        return jsonify({'error': 'Failed to add products to collection'}), 500


@collections_bp.route('/<int:collection_id>/products', methods=['DELETE'])
@supabase_jwt_required
def remove_products_from_collection(collection_id: int):
    """Remove products from a collection."""
    try:
        data = request.get_json()
        product_ids = data.get('product_ids', [])
        
        if not product_ids:
            return jsonify({'error': 'No product IDs provided'}), 400
        
        with db_session_scope() as session:
            repo = CollectionRepository(session)
            
            # Check if collection exists
            collection = repo.get(collection_id)
            if not collection:
                return jsonify({'error': 'Collection not found'}), 404
            
            # Remove products
            removed_count = repo.remove_products_from_collection(
                collection_id=collection_id,
                product_ids=product_ids
            )
        
        return jsonify({
            'message': f'Removed {removed_count} products from collection',
            'removed_count': removed_count
        }), 200
    
    except Exception as e:
        logger.error(f"Error removing products from collection {collection_id}: {str(e)}")
        return jsonify({'error': 'Failed to remove products from collection'}), 500


@collections_bp.route('/<int:collection_id>/sync-to-shopify', methods=['POST'])
@supabase_jwt_required
def sync_collection_to_shopify(collection_id: int):
    """Sync a collection to Shopify."""
    try:
        with db_session_scope() as session:
            repo = CollectionRepository(session)
            collection = repo.get_with_products(collection_id)
            
            if not collection:
                return jsonify({'error': 'Collection not found'}), 404
            
            # Initialize Shopify manager
            shopify_manager = ShopifyCollectionsManager(
                shop_url=Config.SHOPIFY_SHOP_URL,
                access_token=Config.SHOPIFY_ACCESS_TOKEN
            )
            
            # Create or update collection in Shopify
            if collection.shopify_collection_id:
                # Update existing collection
                result = shopify_manager.update_collection(
                    collection_id=collection.shopify_collection_id,
                    title=collection.name,
                    description=collection.description,
                    sort_order=collection.sort_order
                )
            else:
                # Create new collection
                result = shopify_manager.create_collection(
                    title=collection.name,
                    handle=collection.handle,
                    description=collection.description,
                    sort_order=collection.sort_order
                )
                
                if result and 'collection' in result:
                    shopify_id = result['collection']['id']
                    shopify_handle = result['collection']['handle']
                    
                    # Update local collection with Shopify info
                    repo.sync_with_shopify(
                        collection_id=collection.id,
                        shopify_collection_id=shopify_id,
                        shopify_handle=shopify_handle
                    )
            
            # Sync products if manual collection
            if collection.rules_type == 'manual' and collection.products:
                product_ids = [f"gid://shopify/Product/{p.shopify_product_id}" 
                             for p in collection.products if p.shopify_product_id]
                
                if product_ids:
                    shopify_manager.add_products_to_collection(
                        collection_id=collection.shopify_collection_id,
                        product_ids=product_ids
                    )
        
        return jsonify({
            'message': 'Collection synced to Shopify successfully',
            'shopify_collection_id': collection.shopify_collection_id
        }), 200
    
    except Exception as e:
        logger.error(f"Error syncing collection {collection_id} to Shopify: {str(e)}")
        return jsonify({'error': 'Failed to sync collection to Shopify'}), 500


@collections_bp.route('/product-types-summary', methods=['GET'])
@supabase_jwt_required
def get_product_types_summary():
    """Get summary of product types for collection creation."""
    try:
        with db_session_scope() as session:
            repo = CollectionRepository(session)
            product_types = repo.get_product_types_summary()
            
            # Get sample products for each type
            product_repo = ProductRepository(session)
            for pt in product_types:
                sample_products = product_repo.get_by_product_type(
                    pt['name'], 
                    limit=5
                )
                pt['sample_products'] = [p.name for p in sample_products]
        
        return jsonify({
            'product_types': product_types,
            'total': len(product_types)
        }), 200
    
    except Exception as e:
        logger.error(f"Error fetching product types summary: {str(e)}")
        return jsonify({'error': 'Failed to fetch product types summary'}), 500


@collections_bp.route('/ai-suggestions', methods=['POST'])
@supabase_jwt_required
def get_ai_collection_suggestions():
    """Get AI-powered collection suggestions based on product types."""
    try:
        data = request.get_json()
        product_types = data.get('product_types', [])
        
        if not product_types:
            return jsonify({'error': 'No product types provided'}), 400
        
        # For now, return simple suggestions
        # In production, this would use OpenAI or similar service
        suggestions = []
        for product_type in product_types:
            # Create a suggested collection name and description
            collection_name = f"{product_type} Collection"
            description = f"Browse our selection of {product_type.lower()} products"
            
            # Make the name more appealing
            if 'pen' in product_type.lower():
                collection_name = "Premium Writing Instruments"
                description = "Discover our curated selection of professional pens and writing tools"
            elif 'paper' in product_type.lower():
                collection_name = "Paper & Stationery Essentials"
                description = "Quality paper products for all your office and creative needs"
            elif 'folder' in product_type.lower() or 'binder' in product_type.lower():
                collection_name = "Organization & Filing Solutions"
                description = "Keep your documents organized with our filing and storage products"
            
            suggestions.append({
                'product_type': product_type,
                'collection_name': collection_name,
                'description': description,
                'handle': collection_name.lower().replace(' ', '-').replace('&', 'and')
            })
        
        return jsonify({
            'suggestions': suggestions
        }), 200
    
    except Exception as e:
        logger.error(f"Error generating AI suggestions: {str(e)}")
        return jsonify({'error': 'Failed to generate AI suggestions'}), 500


@collections_bp.route('/managed', methods=['GET'])
@supabase_jwt_required
def get_managed_collections():
    """Get collections managed by this system (not from Shopify)."""
    try:
        with db_session_scope() as session:
            repo = CollectionRepository(session)
            collections = repo.get_all_with_stats(include_archived=False)
            
            # Format for frontend
            formatted_collections = []
            for col in collections:
                formatted_collections.append({
                    'id': col['id'],
                    'name': col['name'],
                    'description': col['description'],
                    'handle': col['handle'],
                    'product_count': col['products_count'],
                    'product_types': [],  # TODO: Extract from products
                    'created_locally': True,
                    'shopify_collection_id': col['shopify_collection_id'],
                    'shopify_synced_at': col['shopify_synced_at'],
                    'status': col['status'],
                    'ai_generated': False,  # TODO: Track this in DB
                    'rules': {
                        'type': col['rules_type'],
                        'conditions': col.get('rules_conditions', [])
                    }
                })
        
        return jsonify({
            'collections': formatted_collections
        }), 200
    
    except Exception as e:
        logger.error(f"Error fetching managed collections: {str(e)}")
        return jsonify({'error': 'Failed to fetch managed collections'}), 500


@collections_bp.route('/bulk-create', methods=['POST'])
@supabase_jwt_required
def bulk_create_collections():
    """Create multiple collections from product types in one operation."""
    try:
        data = request.get_json()
        product_types = data.get('product_types', [])
        
        if not product_types:
            return jsonify({'error': 'No product types provided'}), 400
        
        created_collections = []
        errors = []
        
        with db_session_scope() as session:
            repo = CollectionRepository(session)
            
            for pt in product_types:
                try:
                    # Get product type details
                    product_type = pt.get('name')
                    suggested_name = pt.get('suggested_collection_name', f"{product_type} Collection")
                    suggested_description = pt.get('suggested_description', f"Browse our selection of {product_type.lower()} products")
                    
                    # Create handle
                    handle = suggested_name.lower().replace(' ', '-').replace('&', 'and')
                    
                    # Create collection
                    collection_data = {
                        'name': suggested_name,
                        'handle': handle,
                        'description': suggested_description,
                        'rules_type': 'automatic',
                        'rules_conditions': [{
                            'field': 'product_type',
                            'operator': 'equals',
                            'value': product_type
                        }],
                        'disjunctive': False,
                        'status': 'active',
                        'created_by': get_current_user_id()
                    }
                    
                    collection = repo.create(collection_data)
                    
                    # Update automatic collection to assign products
                    repo.update_automatic_collection(collection.id)
                    
                    created_collections.append({
                        'id': collection.id,
                        'name': collection.name,
                        'handle': collection.handle,
                        'product_type': product_type,
                        'products_count': collection.products_count or 0
                    })
                    
                except Exception as e:
                    logger.error(f"Error creating collection for {product_type}: {str(e)}")
                    errors.append({
                        'product_type': product_type,
                        'error': str(e)
                    })
        
        return jsonify({
            'message': f'Created {len(created_collections)} collections',
            'created': created_collections,
            'errors': errors
        }), 200
    
    except Exception as e:
        logger.error(f"Error in bulk collection creation: {str(e)}")
        return jsonify({'error': 'Failed to create collections'}), 500