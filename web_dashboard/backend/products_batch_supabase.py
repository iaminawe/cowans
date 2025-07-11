#!/usr/bin/env python3
"""
Products Batch API - Supabase version
Handles bulk product operations using Supabase
"""

from flask import Blueprint, jsonify, request
from flask_cors import CORS
from services.supabase_database import get_supabase_db
from services.supabase_auth import supabase_jwt_required
from marshmallow import Schema, fields, validate, ValidationError
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Create Blueprint
products_batch_bp = Blueprint('products_batch', __name__, url_prefix='/api/products/batch')
CORS(products_batch_bp)

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
        
        supabase = get_supabase_db()
        
        # Update products in batches
        updated_count = 0
        failed_ids = []
        
        for product_id in product_ids:
            try:
                result = supabase.client.table('products')\
                    .update({
                        'status': new_status,
                        'updated_at': datetime.utcnow().isoformat()
                    })\
                    .eq('id', product_id)\
                    .execute()
                
                if result.data:
                    updated_count += 1
                else:
                    failed_ids.append(product_id)
            except Exception as e:
                logger.error(f"Error updating product {product_id}: {str(e)}")
                failed_ids.append(product_id)
        
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
        
        supabase = get_supabase_db()
        
        # Verify category exists
        category_result = supabase.client.table('categories')\
            .select('id')\
            .eq('id', category_id)\
            .single()\
            .execute()
        
        if not category_result.data:
            return jsonify({'error': 'Category not found'}), 404
        
        # Update products
        updated_count = 0
        failed_ids = []
        
        for product_id in product_ids:
            try:
                result = supabase.client.table('products')\
                    .update({
                        'category_id': category_id,
                        'updated_at': datetime.utcnow().isoformat()
                    })\
                    .eq('id', product_id)\
                    .execute()
                
                if result.data:
                    updated_count += 1
                else:
                    failed_ids.append(product_id)
            except Exception as e:
                logger.error(f"Error updating product {product_id}: {str(e)}")
                failed_ids.append(product_id)
        
        return jsonify({
            'message': f'Updated category for {updated_count} products',
            'updated_count': updated_count,
            'failed_ids': failed_ids
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
        
        supabase = get_supabase_db()
        
        # Get products to update
        products_result = supabase.client.table('products')\
            .select('id, price')\
            .in_('id', product_ids)\
            .execute()
        
        products = products_result.data if products_result.data else []
        
        # Update products
        updated_count = 0
        failed_ids = []
        
        for product in products:
            try:
                current_price = product.get('price')
                if current_price is None:
                    failed_ids.append(product['id'])
                    continue
                
                new_price = current_price
                
                if adjustment_type == 'fixed':
                    new_price = value
                elif adjustment_type == 'percentage_increase':
                    new_price = current_price * (1 + value / 100)
                elif adjustment_type == 'percentage_decrease':
                    new_price = current_price * (1 - value / 100)
                elif adjustment_type == 'amount_increase':
                    new_price = current_price + value
                elif adjustment_type == 'amount_decrease':
                    new_price = max(0, current_price - value)
                
                # Round to 2 decimal places
                new_price = round(new_price, 2)
                
                result = supabase.client.table('products')\
                    .update({
                        'price': new_price,
                        'updated_at': datetime.utcnow().isoformat()
                    })\
                    .eq('id', product['id'])\
                    .execute()
                
                if result.data:
                    updated_count += 1
                else:
                    failed_ids.append(product['id'])
            except Exception as e:
                logger.error(f"Error updating product {product['id']} pricing: {str(e)}")
                failed_ids.append(product['id'])
        
        # Check for missing products
        found_ids = [p['id'] for p in products]
        missing_ids = [pid for pid in product_ids if pid not in found_ids]
        failed_ids.extend(missing_ids)
        
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
        
        supabase = get_supabase_db()
        
        # Delete products
        deleted_count = 0
        failed_ids = []
        
        for product_id in product_ids:
            try:
                # First remove from product_collections
                supabase.client.table('product_collections')\
                    .delete()\
                    .eq('product_id', product_id)\
                    .execute()
                
                # Then delete the product
                result = supabase.client.table('products')\
                    .delete()\
                    .eq('id', product_id)\
                    .execute()
                
                if result.data:
                    deleted_count += 1
                else:
                    failed_ids.append(product_id)
            except Exception as e:
                logger.error(f"Error deleting product {product_id}: {str(e)}")
                failed_ids.append(product_id)
        
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
        
        supabase = get_supabase_db()
        
        # Verify collection exists
        collection_result = supabase.client.table('collections')\
            .select('id')\
            .eq('id', collection_id)\
            .single()\
            .execute()
        
        if not collection_result.data:
            return jsonify({'error': 'Collection not found'}), 404
        
        # Add products to collection
        associations = []
        for idx, product_id in enumerate(product_ids):
            associations.append({
                'collection_id': collection_id,
                'product_id': product_id,
                'position': idx
            })
        
        # Insert all associations (upsert to handle duplicates)
        result = supabase.client.table('product_collections')\
            .upsert(associations, on_conflict='product_id,collection_id')\
            .execute()
        
        added_count = len(result.data) if result.data else 0
        
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
        
        supabase = get_supabase_db()
        
        # Get products with categories
        products_result = supabase.client.table('products')\
            .select('*, categories(*)')\
            .in_('id', product_ids)\
            .execute()
        
        products = products_result.data if products_result.data else []
        
        # Format products for export
        export_data = []
        for product in products:
            export_data.append({
                'sku': product.get('sku', ''),
                'name': product.get('name', ''),
                'description': product.get('description', ''),
                'price': product.get('price'),
                'category': product['categories']['name'] if product.get('categories') else '',
                'brand': product.get('brand', ''),
                'manufacturer': product.get('manufacturer', ''),
                'status': product.get('status', ''),
                'inventory_quantity': product.get('inventory_quantity', 0),
                'product_type': product.get('product_type', '')
            })
        
        # In a real implementation, this would generate a CSV file
        # For now, return the data
        return jsonify({
            'message': f'Exported {len(export_data)} products',
            'products': export_data
        }), 200
    
    except Exception as e:
        logger.error(f"Error exporting products: {str(e)}")
        return jsonify({'error': 'Failed to export products'}), 500

# Additional batch operations
@products_batch_bp.route('/summary', methods=['GET'])
@supabase_jwt_required
def get_batch_summary():
    """Get summary statistics for batch operations."""
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
        
        archived_result = supabase.client.table('products')\
            .select('id', count='exact')\
            .eq('status', 'archived')\
            .execute()
        archived_products = archived_result.count if hasattr(archived_result, 'count') else 0
        
        # Get uncategorized products
        uncategorized_result = supabase.client.table('products')\
            .select('id', count='exact')\
            .is_('category_id', 'null')\
            .execute()
        uncategorized_products = uncategorized_result.count if hasattr(uncategorized_result, 'count') else 0
        
        return jsonify({
            'total_products': total_products,
            'active_products': active_products,
            'draft_products': draft_products,
            'archived_products': archived_products,
            'uncategorized_products': uncategorized_products,
            'batch_operations_available': [
                'update-status',
                'update-category',
                'update-pricing',
                'delete',
                'add-to-collection',
                'export'
            ]
        })
        
    except Exception as e:
        logger.error(f"Error fetching batch summary: {str(e)}")
        return jsonify({
            'total_products': 0,
            'active_products': 0,
            'draft_products': 0,
            'archived_products': 0,
            'uncategorized_products': 0,
            'batch_operations_available': []
        }), 200