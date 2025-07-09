"""Products Batch API endpoints for bulk operations."""
from flask import Blueprint, jsonify, request
from services.supabase_auth import supabase_jwt_required, get_current_user_id
from marshmallow import Schema, fields, validate, ValidationError
from datetime import datetime
from typing import List, Dict, Any
import logging

from database import db_session_scope
from repositories.product_repository import ProductRepository
from repositories.collection_repository import CollectionRepository
from models import Product, ProductStatus

# Configure logging
logger = logging.getLogger(__name__)

# Create Blueprint
products_batch_bp = Blueprint('products_batch', __name__, url_prefix='/api/products/batch')


# Schemas
class BatchUpdateStatusSchema(Schema):
    """Schema for batch status update."""
    product_ids = fields.List(fields.Integer(), required=True, validate=validate.Length(min=1))
    status = fields.String(required=True, validate=validate.OneOf(['active', 'draft', 'archived']))


class BatchUpdateCategorySchema(Schema):
    """Schema for batch category update."""
    product_ids = fields.List(fields.Integer(), required=True, validate=validate.Length(min=1))
    category_id = fields.Integer(required=True)


class BatchUpdatePricingSchema(Schema):
    """Schema for batch pricing update."""
    product_ids = fields.List(fields.Integer(), required=True, validate=validate.Length(min=1))
    adjustment_type = fields.String(required=True, validate=validate.OneOf([
        'fixed', 'percentage_increase', 'percentage_decrease', 'amount_increase', 'amount_decrease'
    ]))
    value = fields.Float(required=True)


class BatchDeleteSchema(Schema):
    """Schema for batch delete."""
    product_ids = fields.List(fields.Integer(), required=True, validate=validate.Length(min=1))


@products_batch_bp.route('/update-status', methods=['POST'])
@supabase_jwt_required
def batch_update_status():
    """Update status for multiple products."""
    try:
        # Validate input
        schema = BatchUpdateStatusSchema()
        data = request.get_json()
        errors = schema.validate(data)
        if errors:
            return jsonify({'errors': errors}), 400
        
        product_ids = data['product_ids']
        new_status = data['status']
        
        with db_session_scope() as session:
            repo = ProductRepository(session)
            
            # Update products
            updated_count = 0
            failed_ids = []
            
            for product_id in product_ids:
                try:
                    product = repo.get(product_id)
                    if product:
                        product.status = new_status
                        updated_count += 1
                    else:
                        failed_ids.append(product_id)
                except Exception as e:
                    logger.error(f"Error updating product {product_id}: {str(e)}")
                    failed_ids.append(product_id)
            
            session.commit()
        
        return jsonify({
            'message': f'Updated status for {updated_count} products',
            'updated_count': updated_count,
            'failed_ids': failed_ids
        }), 200
    
    except Exception as e:
        logger.error(f"Error in batch status update: {str(e)}")
        return jsonify({'error': 'Failed to update products status'}), 500


@products_batch_bp.route('/update-category', methods=['POST'])
@supabase_jwt_required
def batch_update_category():
    """Update category for multiple products."""
    try:
        # Validate input
        schema = BatchUpdateCategorySchema()
        data = request.get_json()
        errors = schema.validate(data)
        if errors:
            return jsonify({'errors': errors}), 400
        
        product_ids = data['product_ids']
        category_id = data['category_id']
        
        with db_session_scope() as session:
            repo = ProductRepository(session)
            
            # Verify category exists
            from repositories.category_repository import CategoryRepository
            category_repo = CategoryRepository(session)
            category = category_repo.get(category_id)
            if not category:
                return jsonify({'error': 'Category not found'}), 404
            
            # Update products
            updated_count = repo.bulk_update_category(product_ids, category_id)
        
        return jsonify({
            'message': f'Updated category for {updated_count} products',
            'updated_count': updated_count
        }), 200
    
    except Exception as e:
        logger.error(f"Error in batch category update: {str(e)}")
        return jsonify({'error': 'Failed to update products category'}), 500


@products_batch_bp.route('/update-pricing', methods=['POST'])
@supabase_jwt_required
def batch_update_pricing():
    """Update pricing for multiple products."""
    try:
        # Validate input
        schema = BatchUpdatePricingSchema()
        data = request.get_json()
        errors = schema.validate(data)
        if errors:
            return jsonify({'errors': errors}), 400
        
        product_ids = data['product_ids']
        adjustment_type = data['adjustment_type']
        value = data['value']
        
        with db_session_scope() as session:
            repo = ProductRepository(session)
            
            # Update products
            updated_count = 0
            failed_ids = []
            
            for product_id in product_ids:
                try:
                    product = repo.get(product_id)
                    if product and product.price is not None:
                        if adjustment_type == 'fixed':
                            product.price = value
                        elif adjustment_type == 'percentage_increase':
                            product.price = product.price * (1 + value / 100)
                        elif adjustment_type == 'percentage_decrease':
                            product.price = product.price * (1 - value / 100)
                        elif adjustment_type == 'amount_increase':
                            product.price = product.price + value
                        elif adjustment_type == 'amount_decrease':
                            product.price = max(0, product.price - value)
                        
                        # Round to 2 decimal places
                        product.price = round(product.price, 2)
                        updated_count += 1
                    else:
                        failed_ids.append(product_id)
                except Exception as e:
                    logger.error(f"Error updating product {product_id} pricing: {str(e)}")
                    failed_ids.append(product_id)
            
            session.commit()
        
        return jsonify({
            'message': f'Updated pricing for {updated_count} products',
            'updated_count': updated_count,
            'failed_ids': failed_ids
        }), 200
    
    except Exception as e:
        logger.error(f"Error in batch pricing update: {str(e)}")
        return jsonify({'error': 'Failed to update products pricing'}), 500


@products_batch_bp.route('/delete', methods=['DELETE'])
@supabase_jwt_required
def batch_delete():
    """Delete multiple products."""
    try:
        # Validate input
        schema = BatchDeleteSchema()
        data = request.get_json()
        errors = schema.validate(data)
        if errors:
            return jsonify({'errors': errors}), 400
        
        product_ids = data['product_ids']
        
        with db_session_scope() as session:
            repo = ProductRepository(session)
            
            # Delete products
            deleted_count = 0
            failed_ids = []
            
            for product_id in product_ids:
                try:
                    if repo.delete(product_id):
                        deleted_count += 1
                    else:
                        failed_ids.append(product_id)
                except Exception as e:
                    logger.error(f"Error deleting product {product_id}: {str(e)}")
                    failed_ids.append(product_id)
            
            session.commit()
        
        return jsonify({
            'message': f'Deleted {deleted_count} products',
            'deleted_count': deleted_count,
            'failed_ids': failed_ids
        }), 200
    
    except Exception as e:
        logger.error(f"Error in batch delete: {str(e)}")
        return jsonify({'error': 'Failed to delete products'}), 500


@products_batch_bp.route('/add-to-collection', methods=['POST'])
@supabase_jwt_required
def batch_add_to_collection():
    """Add multiple products to a collection."""
    try:
        data = request.get_json()
        product_ids = data.get('product_ids', [])
        collection_id = data.get('collection_id')
        
        if not product_ids or not collection_id:
            return jsonify({'error': 'product_ids and collection_id are required'}), 400
        
        with db_session_scope() as session:
            collection_repo = CollectionRepository(session)
            
            # Verify collection exists
            collection = collection_repo.get(collection_id)
            if not collection:
                return jsonify({'error': 'Collection not found'}), 404
            
            # Add products to collection
            added_count = collection_repo.add_products_to_collection(
                collection_id=collection_id,
                product_ids=product_ids
            )
        
        return jsonify({
            'message': f'Added {added_count} products to collection',
            'added_count': added_count
        }), 200
    
    except Exception as e:
        logger.error(f"Error adding products to collection: {str(e)}")
        return jsonify({'error': 'Failed to add products to collection'}), 500


@products_batch_bp.route('/export', methods=['POST'])
@supabase_jwt_required
def batch_export():
    """Export selected products to CSV."""
    try:
        data = request.get_json()
        product_ids = data.get('product_ids', [])
        
        if not product_ids:
            return jsonify({'error': 'No product IDs provided'}), 400
        
        with db_session_scope() as session:
            repo = ProductRepository(session)
            
            # Get products
            products = []
            for product_id in product_ids:
                product = repo.get(product_id)
                if product:
                    products.append({
                        'sku': product.sku,
                        'name': product.name,
                        'description': product.description,
                        'price': product.price,
                        'category': product.category.name if product.category else '',
                        'brand': product.brand,
                        'manufacturer': product.manufacturer,
                        'status': product.status,
                        'inventory_quantity': product.inventory_quantity,
                        'product_type': product.product_type
                    })
        
        # In a real implementation, this would generate a CSV file
        # For now, return the data
        return jsonify({
            'message': f'Exported {len(products)} products',
            'products': products
        }), 200
    
    except Exception as e:
        logger.error(f"Error exporting products: {str(e)}")
        return jsonify({'error': 'Failed to export products'}), 500