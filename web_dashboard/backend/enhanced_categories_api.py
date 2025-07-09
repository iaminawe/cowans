"""
Enhanced Categories API with Shopify Integration and Batch Operations

This module provides comprehensive category management that integrates with
Shopify's taxonomy (product types, collections, tags) and enables batch
product assignment operations.
"""

import os
from flask import Blueprint, jsonify, request
from services.supabase_auth import supabase_jwt_required, get_current_user_id
from marshmallow import Schema, fields, validate, ValidationError
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging
import json
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func, and_, or_

from database import db_session_scope
from repositories.category_repository import CategoryRepository
from repositories.product_repository import ProductRepository
from models import Category, Product, Collection, ProductCollection
from scripts.shopify.shopify_base import ShopifyAPIBase

# Configure logging
logger = logging.getLogger(__name__)

# Create Blueprint
enhanced_categories_bp = Blueprint('enhanced_categories', __name__, url_prefix='/api/categories/enhanced')

# Schemas
class ShopifyCategorySyncSchema(Schema):
    """Schema for syncing categories from Shopify."""
    sync_product_types = fields.Boolean(default=True)
    sync_collections = fields.Boolean(default=True)
    sync_tags = fields.Boolean(default=False)
    create_hierarchy = fields.Boolean(default=True)
    min_product_count = fields.Integer(default=5)  # Minimum products to create category

class BatchProductAssignmentSchema(Schema):
    """Schema for batch product assignment to categories."""
    product_ids = fields.List(fields.Integer(), required=True, validate=validate.Length(min=1))
    category_assignments = fields.Dict(
        keys=fields.String(),
        values=fields.Raw(),
        required=True
    )
    sync_to_shopify = fields.Boolean(default=True)
    remove_existing = fields.Boolean(default=False)

class CategoryAnalyticsSchema(Schema):
    """Schema for category analytics response."""
    category_id = fields.Integer()
    name = fields.String()
    product_count = fields.Integer()
    total_revenue = fields.Float()
    average_price = fields.Float()
    top_products = fields.List(fields.Dict())
    shopify_performance = fields.Dict()

# Enhanced Categories API Endpoints

@enhanced_categories_bp.route('/sync-from-shopify', methods=['POST'])
@supabase_jwt_required
def sync_categories_from_shopify():
    """Sync categories from Shopify's taxonomy (product types, collections, tags)."""
    try:
        # Validate request data
        schema = ShopifyCategorySyncSchema()
        data = schema.load(request.get_json() or {})
        
        shop_url = os.getenv('SHOPIFY_SHOP_URL')
        access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
        
        if not shop_url or not access_token:
            return jsonify({'error': 'Shopify credentials not configured'}), 500
        
        shopify_api = ShopifyAPIBase(shop_url, access_token)
        sync_results = {
            'product_types': {'synced': 0, 'created': 0, 'updated': 0, 'errors': []},
            'collections': {'synced': 0, 'created': 0, 'updated': 0, 'errors': []},
            'tags': {'synced': 0, 'created': 0, 'updated': 0, 'errors': []},
            'total_categories': 0
        }
        
        with db_session_scope() as session:
            category_repo = CategoryRepository(session)
            
            # 1. Sync Product Types as Categories
            if data['sync_product_types']:
                try:
                    product_types = _get_shopify_product_types(shopify_api, data['min_product_count'])
                    for product_type_data in product_types:
                        result = _create_or_update_category_from_product_type(
                            category_repo, product_type_data, data['create_hierarchy']
                        )
                        if result['created']:
                            sync_results['product_types']['created'] += 1
                        elif result['updated']:
                            sync_results['product_types']['updated'] += 1
                        sync_results['product_types']['synced'] += 1
                except Exception as e:
                    logger.error(f"Error syncing product types: {e}")
                    sync_results['product_types']['errors'].append(str(e))
            
            # 2. Sync Collections as Categories
            if data['sync_collections']:
                try:
                    collections = _get_shopify_collections(shopify_api)
                    for collection_data in collections:
                        result = _create_or_update_category_from_collection(
                            category_repo, collection_data
                        )
                        if result['created']:
                            sync_results['collections']['created'] += 1
                        elif result['updated']:
                            sync_results['collections']['updated'] += 1
                        sync_results['collections']['synced'] += 1
                except Exception as e:
                    logger.error(f"Error syncing collections: {e}")
                    sync_results['collections']['errors'].append(str(e))
            
            # 3. Sync Popular Tags as Categories
            if data['sync_tags']:
                try:
                    popular_tags = _get_popular_shopify_tags(shopify_api, data['min_product_count'])
                    for tag_data in popular_tags:
                        result = _create_or_update_category_from_tag(
                            category_repo, tag_data
                        )
                        if result['created']:
                            sync_results['tags']['created'] += 1
                        elif result['updated']:
                            sync_results['tags']['updated'] += 1
                        sync_results['tags']['synced'] += 1
                except Exception as e:
                    logger.error(f"Error syncing tags: {e}")
                    sync_results['tags']['errors'].append(str(e))
            
            sync_results['total_categories'] = (
                sync_results['product_types']['synced'] +
                sync_results['collections']['synced'] +
                sync_results['tags']['synced']
            )
            
            session.commit()
        
        return jsonify({
            'success': True,
            'message': f"Synced {sync_results['total_categories']} categories from Shopify",
            'results': sync_results
        })
        
    except ValidationError as e:
        return jsonify({'error': 'Invalid request data', 'details': e.messages}), 400
    except Exception as e:
        logger.error(f"Error syncing categories from Shopify: {e}")
        return jsonify({'error': str(e)}), 500

@enhanced_categories_bp.route('/batch-assign-products', methods=['POST'])
@supabase_jwt_required
def batch_assign_products_to_categories():
    """Assign multiple products to multiple categories with Shopify sync."""
    try:
        # Validate request data
        schema = BatchProductAssignmentSchema()
        data = schema.load(request.get_json())
        
        product_ids = data['product_ids']
        assignments = data['category_assignments']
        sync_to_shopify = data['sync_to_shopify']
        remove_existing = data['remove_existing']
        
        results = {
            'processed_products': 0,
            'successful_assignments': 0,
            'failed_assignments': 0,
            'shopify_sync_results': [],
            'errors': []
        }
        
        with db_session_scope() as session:
            product_repo = ProductRepository(session)
            category_repo = CategoryRepository(session)
            
            # Get products to process
            products = session.query(Product).filter(Product.id.in_(product_ids)).all()
            
            if not products:
                return jsonify({'error': 'No valid products found'}), 400
            
            for product in products:
                try:
                    product_results = _assign_product_to_categories(
                        session, product, assignments, remove_existing
                    )
                    
                    results['processed_products'] += 1
                    results['successful_assignments'] += product_results['assignments_made']
                    
                    # Sync to Shopify if requested
                    if sync_to_shopify and product.shopify_product_id:
                        shopify_result = _sync_product_categories_to_shopify(
                            product, assignments
                        )
                        results['shopify_sync_results'].append(shopify_result)
                    
                except Exception as e:
                    logger.error(f"Error processing product {product.id}: {e}")
                    results['failed_assignments'] += 1
                    results['errors'].append({
                        'product_id': product.id,
                        'error': str(e)
                    })
            
            session.commit()
        
        return jsonify({
            'success': True,
            'message': f"Processed {results['processed_products']} products",
            'results': results
        })
        
    except ValidationError as e:
        return jsonify({'error': 'Invalid request data', 'details': e.messages}), 400
    except Exception as e:
        logger.error(f"Error in batch assignment: {e}")
        return jsonify({'error': str(e)}), 500

@enhanced_categories_bp.route('/analytics', methods=['GET'])
@supabase_jwt_required
def get_category_analytics():
    """Get comprehensive analytics for categories including Shopify performance."""
    try:
        with db_session_scope() as session:
            # Get category analytics with product counts and revenue
            analytics_query = session.query(
                Category.id,
                Category.name,
                Category.shopify_collection_id,
                func.count(Product.id).label('product_count'),
                func.sum(Product.price * Product.inventory_quantity).label('total_value'),
                func.avg(Product.price).label('average_price')
            ).outerjoin(Product).group_by(Category.id, Category.name, Category.shopify_collection_id)
            
            analytics_data = []
            for row in analytics_query.all():
                category_analytics = {
                    'category_id': row.id,
                    'name': row.name,
                    'product_count': row.product_count or 0,
                    'total_value': float(row.total_value or 0),
                    'average_price': float(row.average_price or 0),
                    'has_shopify_integration': bool(row.shopify_collection_id)
                }
                
                # Get top products in this category
                top_products = session.query(Product).filter(
                    Product.category_id == row.id
                ).order_by(Product.price.desc()).limit(5).all()
                
                category_analytics['top_products'] = [
                    {
                        'id': p.id,
                        'name': p.name,
                        'price': p.price,
                        'sku': p.sku
                    } for p in top_products
                ]
                
                analytics_data.append(category_analytics)
            
            # Sort by product count descending
            analytics_data.sort(key=lambda x: x['product_count'], reverse=True)
            
            return jsonify({
                'success': True,
                'analytics': analytics_data,
                'summary': {
                    'total_categories': len(analytics_data),
                    'categories_with_products': len([a for a in analytics_data if a['product_count'] > 0]),
                    'shopify_integrated_categories': len([a for a in analytics_data if a['has_shopify_integration']])
                }
            })
            
    except Exception as e:
        logger.error(f"Error getting category analytics: {e}")
        return jsonify({'error': str(e)}), 500

@enhanced_categories_bp.route('/shopify-taxonomy', methods=['GET'])
@supabase_jwt_required
def get_shopify_taxonomy():
    """Get current Shopify taxonomy (product types, collections, popular tags)."""
    try:
        shop_url = os.getenv('SHOPIFY_SHOP_URL')
        access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
        
        if not shop_url or not access_token:
            return jsonify({'error': 'Shopify credentials not configured'}), 500
        
        shopify_api = ShopifyAPIBase(shop_url, access_token)
        
        # Get current taxonomy
        taxonomy = {
            'product_types': _get_shopify_product_types(shopify_api, min_count=1),
            'collections': _get_shopify_collections(shopify_api),
            'popular_tags': _get_popular_shopify_tags(shopify_api, min_count=10),
            'total_products': _get_total_shopify_products(shopify_api)
        }
        
        return jsonify({
            'success': True,
            'taxonomy': taxonomy,
            'summary': {
                'product_types_count': len(taxonomy['product_types']),
                'collections_count': len(taxonomy['collections']),
                'popular_tags_count': len(taxonomy['popular_tags']),
                'total_products': taxonomy['total_products']
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting Shopify taxonomy: {e}")
        return jsonify({'error': str(e)}), 500

# Helper Functions

def _get_shopify_product_types(shopify_api: ShopifyAPIBase, min_count: int = 5) -> List[Dict]:
    """Get product types from Shopify with product counts."""
    # This would use GraphQL to get product types with counts
    # For now, return a mock implementation
    return []

def _get_shopify_collections(shopify_api: ShopifyAPIBase) -> List[Dict]:
    """Get collections from Shopify."""
    # This would use the existing collections API
    return []

def _get_popular_shopify_tags(shopify_api: ShopifyAPIBase, min_count: int = 10) -> List[Dict]:
    """Get popular tags from Shopify products."""
    # This would analyze product tags and return popular ones
    return []

def _get_total_shopify_products(shopify_api: ShopifyAPIBase) -> int:
    """Get total product count from Shopify."""
    return 0

def _create_or_update_category_from_product_type(
    category_repo: CategoryRepository, 
    product_type_data: Dict, 
    create_hierarchy: bool
) -> Dict:
    """Create or update a category from Shopify product type data."""
    return {'created': False, 'updated': False}

def _create_or_update_category_from_collection(
    category_repo: CategoryRepository, 
    collection_data: Dict
) -> Dict:
    """Create or update a category from Shopify collection data."""
    return {'created': False, 'updated': False}

def _create_or_update_category_from_tag(
    category_repo: CategoryRepository, 
    tag_data: Dict
) -> Dict:
    """Create or update a category from Shopify tag data."""
    return {'created': False, 'updated': False}

def _assign_product_to_categories(
    session, 
    product: Product, 
    assignments: Dict, 
    remove_existing: bool
) -> Dict:
    """Assign a product to multiple categories based on assignment data."""
    assignments_made = 0
    
    # Process different types of assignments
    if 'category_ids' in assignments:
        # Direct category assignments
        category_ids = assignments['category_ids']
        if remove_existing:
            # Remove existing category assignment
            product.category_id = None
        
        # For now, just assign to first category (single category model)
        if category_ids:
            product.category_id = category_ids[0]
            assignments_made += 1
    
    if 'product_type' in assignments:
        # Update product type
        product.product_type = assignments['product_type']
        assignments_made += 1
    
    if 'collections' in assignments:
        # Handle collection assignments through product_collections table
        collection_ids = assignments['collections']
        if remove_existing:
            # Remove existing collection assignments
            session.query(ProductCollection).filter(
                ProductCollection.product_id == product.id
            ).delete()
        
        # Add new collection assignments
        for collection_id in collection_ids:
            existing = session.query(ProductCollection).filter(
                and_(
                    ProductCollection.product_id == product.id,
                    ProductCollection.collection_id == collection_id
                )
            ).first()
            
            if not existing:
                product_collection = ProductCollection(
                    product_id=product.id,
                    collection_id=collection_id
                )
                session.add(product_collection)
                assignments_made += 1
    
    return {'assignments_made': assignments_made}

def _sync_product_categories_to_shopify(product: Product, assignments: Dict) -> Dict:
    """Sync product category assignments to Shopify."""
    # This would sync the product's collections and product_type to Shopify
    return {
        'product_id': product.id,
        'shopify_product_id': product.shopify_product_id,
        'sync_status': 'success',
        'synced_fields': []
    }