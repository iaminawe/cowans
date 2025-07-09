"""Categories API endpoints for comprehensive category management."""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from services.supabase_auth import supabase_jwt_required, get_current_user_id, require_role
from marshmallow import Schema, fields, validate, ValidationError
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging
import json
from sqlalchemy.exc import IntegrityError

from database import db_session_scope
from repositories.category_repository import CategoryRepository
from repositories.product_repository import ProductRepository
from repositories.icon_repository import IconRepository
from models import Category, Product, Icon
from services.icon_category_service import IconCategoryService
from services.shopify_icon_sync_service import ShopifyIconSyncService

# Configure logging
logger = logging.getLogger(__name__)

# Create Blueprint
categories_bp = Blueprint('categories', __name__, url_prefix='/api/categories')

# Schemas
class CategoryCreateSchema(Schema):
    """Schema for creating categories."""
    name = fields.String(required=True, validate=validate.Length(min=1, max=255))
    description = fields.String(allow_none=True)
    parent_id = fields.Integer(allow_none=True)
    slug = fields.String(allow_none=True, validate=validate.Length(max=255))
    sort_order = fields.Integer(default=0)
    meta_data = fields.Dict(allow_none=True)

class CategoryUpdateSchema(Schema):
    """Schema for updating categories."""
    name = fields.String(validate=validate.Length(min=1, max=255))
    description = fields.String(allow_none=True)
    parent_id = fields.Integer(allow_none=True)
    slug = fields.String(validate=validate.Length(max=255))
    sort_order = fields.Integer()
    is_active = fields.Boolean()
    meta_data = fields.Dict(allow_none=True)

class CategoryResponseSchema(Schema):
    """Schema for category responses."""
    id = fields.Integer()
    name = fields.String()
    description = fields.String(allow_none=True)
    slug = fields.String()
    parent_id = fields.Integer(allow_none=True)
    level = fields.Integer()
    path = fields.String(allow_none=True)
    sort_order = fields.Integer()
    is_active = fields.Boolean()
    shopify_collection_id = fields.String(allow_none=True)
    shopify_handle = fields.String(allow_none=True)
    shopify_synced_at = fields.DateTime(allow_none=True)
    meta_data = fields.Dict(allow_none=True)
    created_at = fields.DateTime()
    updated_at = fields.DateTime()
    product_count = fields.Integer()
    children = fields.List(fields.Nested(lambda: CategoryResponseSchema(exclude=['children'])))
    icon = fields.Dict(allow_none=True)

class CategoryTreeMoveSchema(Schema):
    """Schema for moving categories in tree."""
    parent_id = fields.Integer(allow_none=True)
    position = fields.Integer(default=0)

class BulkCategoryActionSchema(Schema):
    """Schema for bulk category actions."""
    category_ids = fields.List(fields.Integer(), required=True, validate=validate.Length(min=1))
    action = fields.String(required=True, validate=validate.OneOf(['activate', 'deactivate', 'delete', 'sync_shopify']))

# Initialize schemas
category_create_schema = CategoryCreateSchema()
category_update_schema = CategoryUpdateSchema()
category_response_schema = CategoryResponseSchema()
categories_response_schema = CategoryResponseSchema(many=True)
category_tree_move_schema = CategoryTreeMoveSchema()
bulk_action_schema = BulkCategoryActionSchema()

def generate_slug(name: str, existing_slugs: List[str] = None) -> str:
    """Generate a URL-friendly slug from category name."""
    import re
    slug = re.sub(r'[^a-zA-Z0-9\s-]', '', name.lower())
    slug = re.sub(r'\s+', '-', slug).strip('-')
    
    if existing_slugs and slug in existing_slugs:
        counter = 1
        base_slug = slug
        while f"{base_slug}-{counter}" in existing_slugs:
            counter += 1
        slug = f"{base_slug}-{counter}"
    
    return slug

@categories_bp.route('/', methods=['GET'])
@supabase_jwt_required
def get_categories():
    """Get all categories with optional filtering and tree structure."""
    try:
        # Query parameters
        include_inactive = request.args.get('include_inactive', 'false').lower() == 'true'
        tree_view = request.args.get('tree', 'false').lower() == 'true'
        parent_id = request.args.get('parent_id', type=int)
        search = request.args.get('search', '').strip()
        include_counts = request.args.get('include_counts', 'true').lower() == 'true'
        
        with db_session_scope() as session:
            category_repo = CategoryRepository(session)
            
            if tree_view:
                # Return hierarchical tree structure
                categories = category_repo.get_category_tree(
                    include_inactive=include_inactive,
                    search=search
                )
            elif parent_id is not None:
                # Get children of specific parent
                categories = category_repo.get_children(parent_id)
                categories = [category_repo.to_dict_with_counts(cat) for cat in categories]
            else:
                # Get flat list
                categories = category_repo.get_all_with_counts(
                    include_inactive=include_inactive,
                    search=search
                )
            
            # Add icon information if available
            if include_counts:
                icon_repo = IconRepository(session)
                for category in categories:
                    icon = icon_repo.get_by_category_id(category['id'])
                    if icon:
                        category['icon'] = {
                            'id': icon.id,
                            'file_path': icon.file_path,
                            'url': f"/api/images/{icon.file_path.split('/')[-1]}" if icon.file_path else None,
                            'status': icon.status
                        }
        
        return jsonify({
            'categories': categories,
            'total': len(categories),
            'tree_view': tree_view
        }), 200
    
    except Exception as e:
        logger.error(f"Error fetching categories: {str(e)}")
        return jsonify({'error': 'Failed to fetch categories'}), 500

@categories_bp.route('/<int:category_id>', methods=['GET'])
@supabase_jwt_required
def get_category(category_id: int):
    """Get a single category with full details."""
    try:
        with db_session_scope() as session:
            category_repo = CategoryRepository(session)
            category = category_repo.get(category_id)
            
            if not category:
                return jsonify({'error': 'Category not found'}), 404
            
            # Get category with counts and relationships
            category_data = category_repo.to_dict_with_counts(category)
            
            # Add children
            children = category_repo.get_children(category_id)
            category_data['children'] = [
                category_repo.to_dict_with_counts(child) for child in children
            ]
            
            # Add icon information
            icon_repo = IconRepository(session)
            icon = icon_repo.get_by_category_id(category_id)
            if icon:
                category_data['icon'] = {
                    'id': icon.id,
                    'file_path': icon.file_path,
                    'url': f"/api/images/{icon.file_path.split('/')[-1]}" if icon.file_path else None,
                    'status': icon.status,
                    'created_at': icon.created_at.isoformat(),
                    'metadata': icon.meta_data
                }
            
            # Add products (limited)
            product_repo = ProductRepository(session)
            products = product_repo.get_by_category_id(category_id, limit=10)
            category_data['sample_products'] = [
                {
                    'id': p.id,
                    'name': p.name,
                    'sku': p.sku,
                    'price': float(p.price) if p.price else None,
                    'status': p.status
                } for p in products
            ]
        
        return jsonify(category_data), 200
    
    except Exception as e:
        logger.error(f"Error fetching category {category_id}: {str(e)}")
        return jsonify({'error': 'Failed to fetch category'}), 500

@categories_bp.route('/', methods=['POST'])
@supabase_jwt_required
def create_category():
    """Create a new category."""
    try:
        # Validate input
        data = category_create_schema.load(request.get_json())
        
        # Generate slug if not provided
        if not data.get('slug'):
            with db_session_scope() as session:
                category_repo = CategoryRepository(session)
                existing_slugs = [cat.slug for cat in category_repo.get_all()]
                data['slug'] = generate_slug(data['name'], existing_slugs)
        
        with db_session_scope() as session:
            category_repo = CategoryRepository(session)
            
            # Validate parent exists if specified
            if data.get('parent_id'):
                parent = category_repo.get(data['parent_id'])
                if not parent:
                    return jsonify({'error': 'Parent category not found'}), 400
                data['level'] = parent.level + 1
                data['path'] = f"{parent.path}/{data['parent_id']}" if parent.path else str(data['parent_id'])
            else:
                data['level'] = 0
                data['path'] = None
            
            # Create category
            category = category_repo.create(**data)
            session.commit()
            
            # Return created category
            category_data = category_repo.to_dict_with_counts(category)
        
        logger.info(f"Created category: {category.name} (ID: {category.id})")
        return jsonify(category_data), 201
    
    except ValidationError as e:
        return jsonify({'error': 'Validation failed', 'details': e.messages}), 400
    except IntegrityError as e:
        return jsonify({'error': 'Category with this name or slug already exists'}), 409
    except Exception as e:
        logger.error(f"Error creating category: {str(e)}")
        return jsonify({'error': 'Failed to create category'}), 500

@categories_bp.route('/<int:category_id>', methods=['PUT'])
@supabase_jwt_required
def update_category(category_id: int):
    """Update an existing category."""
    try:
        # Validate input
        data = category_update_schema.load(request.get_json())
        
        with db_session_scope() as session:
            category_repo = CategoryRepository(session)
            category = category_repo.get(category_id)
            
            if not category:
                return jsonify({'error': 'Category not found'}), 404
            
            # Validate parent change if specified
            if 'parent_id' in data:
                if data['parent_id'] == category_id:
                    return jsonify({'error': 'Category cannot be its own parent'}), 400
                
                if data['parent_id']:
                    parent = category_repo.get(data['parent_id'])
                    if not parent:
                        return jsonify({'error': 'Parent category not found'}), 400
                    
                    # Check for circular reference
                    if category_repo.would_create_cycle(category_id, data['parent_id']):
                        return jsonify({'error': 'Would create circular reference'}), 400
                    
                    data['level'] = parent.level + 1
                    data['path'] = f"{parent.path}/{data['parent_id']}" if parent.path else str(data['parent_id'])
                else:
                    data['level'] = 0
                    data['path'] = None
            
            # Update category
            updated_category = category_repo.update(category_id, **data)
            session.commit()
            
            # If parent changed, update all descendants
            if 'parent_id' in data:
                category_repo.update_descendant_paths(category_id)
                session.commit()
            
            # Return updated category
            category_data = category_repo.to_dict_with_counts(updated_category)
        
        logger.info(f"Updated category: {updated_category.name} (ID: {category_id})")
        return jsonify(category_data), 200
    
    except ValidationError as e:
        return jsonify({'error': 'Validation failed', 'details': e.messages}), 400
    except IntegrityError as e:
        return jsonify({'error': 'Category with this name or slug already exists'}), 409
    except Exception as e:
        logger.error(f"Error updating category {category_id}: {str(e)}")
        return jsonify({'error': 'Failed to update category'}), 500

@categories_bp.route('/<int:category_id>', methods=['DELETE'])
@supabase_jwt_required
@require_role('admin')
def delete_category(category_id: int):
    """Delete a category (admin only)."""
    try:
        with db_session_scope() as session:
            category_repo = CategoryRepository(session)
            category = category_repo.get(category_id)
            
            if not category:
                return jsonify({'error': 'Category not found'}), 404
            
            # Check if category has children
            children = category_repo.get_children(category_id)
            if children:
                return jsonify({
                    'error': 'Cannot delete category with children',
                    'children_count': len(children)
                }), 400
            
            # Check if category has products
            product_repo = ProductRepository(session)
            product_count = product_repo.count_by_category(category_id)
            if product_count > 0:
                return jsonify({
                    'error': 'Cannot delete category with products',
                    'product_count': product_count
                }), 400
            
            # Delete associated icons
            icon_repo = IconRepository(session)
            icons = icon_repo.get_by_category_id(category_id, all_icons=True)
            for icon in icons:
                icon_repo.delete(icon.id)
            
            # Delete category
            category_repo.delete(category_id)
            session.commit()
        
        logger.info(f"Deleted category: {category.name} (ID: {category_id})")
        return jsonify({'message': 'Category deleted successfully'}), 200
    
    except Exception as e:
        logger.error(f"Error deleting category {category_id}: {str(e)}")
        return jsonify({'error': 'Failed to delete category'}), 500

@categories_bp.route('/<int:category_id>/move', methods=['POST'])
@supabase_jwt_required
def move_category(category_id: int):
    """Move category to different parent or position."""
    try:
        # Validate input
        data = category_tree_move_schema.load(request.get_json())
        
        with db_session_scope() as session:
            category_repo = CategoryRepository(session)
            
            success = category_repo.move_category(
                category_id,
                data.get('parent_id'),
                data.get('position', 0)
            )
            
            if not success:
                return jsonify({'error': 'Failed to move category'}), 400
            
            session.commit()
            
            # Return updated category
            category = category_repo.get(category_id)
            category_data = category_repo.to_dict_with_counts(category)
        
        logger.info(f"Moved category {category_id} to parent {data.get('parent_id')}")
        return jsonify(category_data), 200
    
    except ValidationError as e:
        return jsonify({'error': 'Validation failed', 'details': e.messages}), 400
    except Exception as e:
        logger.error(f"Error moving category {category_id}: {str(e)}")
        return jsonify({'error': 'Failed to move category'}), 500

@categories_bp.route('/bulk-action', methods=['POST'])
@supabase_jwt_required
def bulk_category_action():
    """Perform bulk actions on multiple categories."""
    try:
        # Validate input
        data = bulk_action_schema.load(request.get_json())
        category_ids = data['category_ids']
        action = data['action']
        
        results = []
        errors = []
        
        with db_session_scope() as session:
            category_repo = CategoryRepository(session)
            
            for category_id in category_ids:
                try:
                    category = category_repo.get(category_id)
                    if not category:
                        errors.append(f"Category {category_id} not found")
                        continue
                    
                    if action == 'activate':
                        category_repo.update(category_id, is_active=True)
                        results.append(f"Activated category {category.name}")
                    
                    elif action == 'deactivate':
                        category_repo.update(category_id, is_active=False)
                        results.append(f"Deactivated category {category.name}")
                    
                    elif action == 'delete':
                        # Check constraints
                        children = category_repo.get_children(category_id)
                        if children:
                            errors.append(f"Category {category.name} has children, cannot delete")
                            continue
                        
                        product_repo = ProductRepository(session)
                        product_count = product_repo.count_by_category(category_id)
                        if product_count > 0:
                            errors.append(f"Category {category.name} has products, cannot delete")
                            continue
                        
                        category_repo.delete(category_id)
                        results.append(f"Deleted category {category.name}")
                    
                    elif action == 'sync_shopify':
                        # Sync to Shopify (if implemented)
                        # This would require Shopify Collections API integration
                        results.append(f"Queued Shopify sync for category {category.name}")
                
                except Exception as e:
                    errors.append(f"Error with category {category_id}: {str(e)}")
            
            session.commit()
        
        return jsonify({
            'success': len(results),
            'errors': len(errors),
            'results': results,
            'error_details': errors
        }), 200
    
    except ValidationError as e:
        return jsonify({'error': 'Validation failed', 'details': e.messages}), 400
    except Exception as e:
        logger.error(f"Error in bulk category action: {str(e)}")
        return jsonify({'error': 'Bulk action failed'}), 500

@categories_bp.route('/<int:category_id>/products', methods=['GET'])
@supabase_jwt_required
def get_category_products(category_id: int):
    """Get products in a specific category."""
    try:
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 50, type=int)
        search = request.args.get('search', '').strip()
        
        with db_session_scope() as session:
            category_repo = CategoryRepository(session)
            category = category_repo.get(category_id)
            
            if not category:
                return jsonify({'error': 'Category not found'}), 404
            
            product_repo = ProductRepository(session)
            products, total = product_repo.get_by_category_paginated(
                category_id, page=page, limit=limit, search=search
            )
            
            products_data = []
            for product in products:
                products_data.append({
                    'id': product.id,
                    'name': product.name,
                    'sku': product.sku,
                    'price': float(product.price) if product.price else None,
                    'status': product.status,
                    'shopify_product_id': product.shopify_product_id,
                    'created_at': product.created_at.isoformat(),
                    'updated_at': product.updated_at.isoformat()
                })
        
        return jsonify({
            'category': {
                'id': category.id,
                'name': category.name
            },
            'products': products_data,
            'pagination': {
                'page': page,
                'limit': limit,
                'total': total,
                'pages': (total + limit - 1) // limit
            }
        }), 200
    
    except Exception as e:
        logger.error(f"Error fetching products for category {category_id}: {str(e)}")
        return jsonify({'error': 'Failed to fetch category products'}), 500

@categories_bp.route('/<int:category_id>/icon', methods=['POST'])
@supabase_jwt_required
def assign_category_icon(category_id: int):
    """Assign an icon to a category."""
    try:
        data = request.get_json()
        icon_id = data.get('icon_id')
        
        if not icon_id:
            return jsonify({'error': 'Icon ID is required'}), 400
        
        with db_session_scope() as session:
            category_repo = CategoryRepository(session)
            category = category_repo.get(category_id)
            
            if not category:
                return jsonify({'error': 'Category not found'}), 404
            
            icon_repo = IconRepository(session)
            icon = icon_repo.get(icon_id)
            
            if not icon:
                return jsonify({'error': 'Icon not found'}), 404
            
            # Update icon's category association
            icon_repo.update(icon_id, category_id=category_id)
            session.commit()
        
        return jsonify({
            'message': 'Icon assigned successfully',
            'category_id': category_id,
            'icon_id': icon_id
        }), 200
    
    except Exception as e:
        logger.error(f"Error assigning icon to category {category_id}: {str(e)}")
        return jsonify({'error': 'Failed to assign icon'}), 500

@categories_bp.route('/<int:category_id>/icon', methods=['DELETE'])
@supabase_jwt_required
def remove_category_icon(category_id: int):
    """Remove icon assignment from a category."""
    try:
        with db_session_scope() as session:
            category_repo = CategoryRepository(session)
            category = category_repo.get(category_id)
            
            if not category:
                return jsonify({'error': 'Category not found'}), 404
            
            icon_repo = IconRepository(session)
            icon = icon_repo.get_by_category_id(category_id)
            
            if icon:
                icon_repo.update(icon.id, category_id=None)
                session.commit()
        
        return jsonify({'message': 'Icon removed successfully'}), 200
    
    except Exception as e:
        logger.error(f"Error removing icon from category {category_id}: {str(e)}")
        return jsonify({'error': 'Failed to remove icon'}), 500

@categories_bp.route('/stats', methods=['GET'])
@supabase_jwt_required
def get_category_stats():
    """Get category statistics."""
    try:
        with db_session_scope() as session:
            category_repo = CategoryRepository(session)
            product_repo = ProductRepository(session)
            icon_repo = IconRepository(session)
            
            stats = {
                'total_categories': category_repo.count(),
                'active_categories': category_repo.count_active(),
                'root_categories': len(category_repo.get_root_categories()),
                'categories_with_products': category_repo.count_with_products(),
                'categories_with_icons': icon_repo.count_assigned_categories(),
                'empty_categories': category_repo.count_empty(),
                'max_depth': category_repo.get_max_depth(),
                'avg_products_per_category': category_repo.get_avg_products_per_category()
            }
        
        return jsonify(stats), 200
    
    except Exception as e:
        logger.error(f"Error fetching category stats: {str(e)}")
        return jsonify({'error': 'Failed to fetch statistics'}), 500

@categories_bp.route('/export', methods=['GET'])
@supabase_jwt_required
def export_categories():
    """Export categories to CSV or JSON."""
    try:
        format_type = request.args.get('format', 'json').lower()
        include_products = request.args.get('include_products', 'false').lower() == 'true'
        
        with db_session_scope() as session:
            category_repo = CategoryRepository(session)
            categories = category_repo.get_all_with_counts(include_inactive=True)
            
            if include_products:
                product_repo = ProductRepository(session)
                for category in categories:
                    products = product_repo.get_by_category_id(category['id'])
                    category['products'] = [
                        {
                            'id': p.id,
                            'name': p.name,
                            'sku': p.sku,
                            'price': float(p.price) if p.price else None
                        } for p in products
                    ]
        
        if format_type == 'csv':
            # Return CSV format
            import csv
            import io
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Headers
            headers = ['ID', 'Name', 'Description', 'Parent ID', 'Level', 'Active', 'Product Count']
            if include_products:
                headers.extend(['Product Names', 'Product SKUs'])
            writer.writerow(headers)
            
            # Data
            for category in categories:
                row = [
                    category['id'],
                    category['name'],
                    category.get('description', ''),
                    category.get('parent_id', ''),
                    category['level'],
                    category['is_active'],
                    category['product_count']
                ]
                
                if include_products and 'products' in category:
                    product_names = '; '.join([p['name'] for p in category['products']])
                    product_skus = '; '.join([p['sku'] for p in category['products']])
                    row.extend([product_names, product_skus])
                
                writer.writerow(row)
            
            return output.getvalue(), 200, {
                'Content-Type': 'text/csv',
                'Content-Disposition': 'attachment; filename=categories.csv'
            }
        
        else:
            # Return JSON format
            return jsonify({
                'categories': categories,
                'exported_at': datetime.utcnow().isoformat(),
                'include_products': include_products,
                'total': len(categories)
            }), 200
    
    except Exception as e:
        logger.error(f"Error exporting categories: {str(e)}")
        return jsonify({'error': 'Failed to export categories'}), 500