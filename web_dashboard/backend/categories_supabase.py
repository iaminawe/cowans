#!/usr/bin/env python3
"""
Categories API - Supabase version
Handles all category-related operations using Supabase
"""

from flask import Blueprint, jsonify, request
from flask_cors import CORS
from services.supabase_database import get_supabase_db
from services.supabase_auth import supabase_jwt_required
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

categories_bp = Blueprint('categories', __name__)
CORS(categories_bp)

@categories_bp.route('/api/categories', methods=['GET'])
@supabase_jwt_required
def get_categories():
    """Get all categories with hierarchical structure"""
    try:
        supabase = get_supabase_db()
        
        # Get all categories
        result = supabase.client.table('categories')\
            .select('*')\
            .order('path', asc=True)\
            .execute()
        
        categories = result.data if result.data else []
        
        # Build hierarchical structure if requested
        if request.args.get('hierarchical') == 'true':
            categories = build_category_tree(categories)
        
        return jsonify({
            'categories': categories,
            'total': len(categories)
        })
        
    except Exception as e:
        logger.error(f"Error fetching categories: {str(e)}")
        return jsonify({
            'categories': [],
            'total': 0
        }), 200

def build_category_tree(categories):
    """Build hierarchical tree from flat category list"""
    category_map = {cat['id']: cat for cat in categories}
    tree = []
    
    for category in categories:
        category['children'] = []
        if category['parent_id'] is None:
            tree.append(category)
        else:
            parent = category_map.get(category['parent_id'])
            if parent:
                parent['children'].append(category)
    
    return tree

@categories_bp.route('/api/categories/<int:category_id>', methods=['GET'])
@supabase_jwt_required
def get_category(category_id):
    """Get a specific category with its products"""
    try:
        supabase = get_supabase_db()
        
        # Get category
        result = supabase.client.table('categories')\
            .select('*')\
            .eq('id', category_id)\
            .single()\
            .execute()
        
        if result.data:
            category = result.data
            
            # Get products in this category
            products_result = supabase.client.table('products')\
                .select('*')\
                .eq('category_id', category_id)\
                .execute()
            
            category['products'] = products_result.data if products_result.data else []
            category['product_count'] = len(category['products'])
            
            # Get child categories
            children_result = supabase.client.table('categories')\
                .select('*')\
                .eq('parent_id', category_id)\
                .execute()
            
            category['children'] = children_result.data if children_result.data else []
            
            return jsonify(category)
        else:
            return jsonify({'error': 'Category not found'}), 404
            
    except Exception as e:
        logger.error(f"Error fetching category {category_id}: {str(e)}")
        return jsonify({'error': 'Failed to fetch category'}), 500

@categories_bp.route('/api/categories', methods=['POST'])
@supabase_jwt_required
def create_category():
    """Create a new category"""
    try:
        supabase = get_supabase_db()
        data = request.get_json()
        
        # Validate required fields
        if not data.get('name'):
            return jsonify({'error': 'Name is required'}), 400
        
        # Create slug from name
        slug = data.get('slug', data['name'].lower().replace(' ', '-').replace('/', '-'))
        
        # Determine level and path based on parent
        parent_id = data.get('parent_id')
        level = 0
        path = slug
        
        if parent_id:
            # Get parent category
            parent_result = supabase.client.table('categories')\
                .select('level, path')\
                .eq('id', parent_id)\
                .single()\
                .execute()
            
            if parent_result.data:
                level = parent_result.data['level'] + 1
                path = f"{parent_result.data['path']}/{slug}"
        
        # Create category
        category_data = {
            'name': data['name'],
            'slug': slug,
            'parent_id': parent_id,
            'level': level,
            'path': path,
            'is_active': data.get('is_active', True),
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }
        
        result = supabase.client.table('categories').insert(category_data).execute()
        
        if result.data:
            return jsonify(result.data[0]), 201
        else:
            return jsonify({'error': 'Failed to create category'}), 500
            
    except Exception as e:
        logger.error(f"Error creating category: {str(e)}")
        return jsonify({'error': 'Failed to create category'}), 500

@categories_bp.route('/api/categories/<int:category_id>', methods=['PUT'])
@supabase_jwt_required
def update_category(category_id):
    """Update a category"""
    try:
        supabase = get_supabase_db()
        data = request.get_json()
        
        # Update only provided fields
        update_data = {}
        if 'name' in data:
            update_data['name'] = data['name']
        if 'slug' in data:
            update_data['slug'] = data['slug']
        if 'is_active' in data:
            update_data['is_active'] = data['is_active']
        
        update_data['updated_at'] = datetime.utcnow().isoformat()
        
        result = supabase.client.table('categories')\
            .update(update_data)\
            .eq('id', category_id)\
            .execute()
        
        if result.data:
            return jsonify(result.data[0])
        else:
            return jsonify({'error': 'Category not found'}), 404
            
    except Exception as e:
        logger.error(f"Error updating category {category_id}: {str(e)}")
        return jsonify({'error': 'Failed to update category'}), 500

@categories_bp.route('/api/categories/<int:category_id>', methods=['DELETE'])
@supabase_jwt_required
def delete_category(category_id):
    """Delete a category"""
    try:
        supabase = get_supabase_db()
        
        # Check if category has products
        products_result = supabase.client.table('products')\
            .select('id')\
            .eq('category_id', category_id)\
            .limit(1)\
            .execute()
        
        if products_result.data:
            return jsonify({'error': 'Cannot delete category with products'}), 400
        
        # Check if category has children
        children_result = supabase.client.table('categories')\
            .select('id')\
            .eq('parent_id', category_id)\
            .limit(1)\
            .execute()
        
        if children_result.data:
            return jsonify({'error': 'Cannot delete category with subcategories'}), 400
        
        # Delete the category
        result = supabase.client.table('categories')\
            .delete()\
            .eq('id', category_id)\
            .execute()
        
        return jsonify({'message': 'Category deleted successfully'}), 200
        
    except Exception as e:
        logger.error(f"Error deleting category {category_id}: {str(e)}")
        return jsonify({'error': 'Failed to delete category'}), 500

@categories_bp.route('/api/categories/stats', methods=['GET'])
@supabase_jwt_required
def get_category_stats():
    """Get category statistics"""
    try:
        supabase = get_supabase_db()
        
        # Get all categories
        categories_result = supabase.client.table('categories').select('*').execute()
        categories = categories_result.data if categories_result.data else []
        
        # Get products with categories
        products_result = supabase.client.table('products')\
            .select('id, category_id')\
            .execute()
        products = products_result.data if products_result.data else []
        
        # Calculate stats
        total_categories = len(categories)
        active_categories = len([c for c in categories if c.get('is_active')])
        
        # Count products per category
        category_product_counts = {}
        uncategorized = 0
        
        for product in products:
            cat_id = product.get('category_id')
            if cat_id:
                category_product_counts[cat_id] = category_product_counts.get(cat_id, 0) + 1
            else:
                uncategorized += 1
        
        # Get most used categories
        top_categories = []
        for cat in categories:
            count = category_product_counts.get(cat['id'], 0)
            if count > 0:
                top_categories.append({
                    'id': cat['id'],
                    'name': cat['name'],
                    'product_count': count
                })
        
        top_categories.sort(key=lambda x: x['product_count'], reverse=True)
        
        return jsonify({
            'total_categories': total_categories,
            'active_categories': active_categories,
            'categories_with_products': len(category_product_counts),
            'uncategorized_products': uncategorized,
            'top_categories': top_categories[:10]  # Top 10 categories
        })
        
    except Exception as e:
        logger.error(f"Error fetching category stats: {str(e)}")
        return jsonify({
            'total_categories': 0,
            'active_categories': 0,
            'categories_with_products': 0,
            'uncategorized_products': 0,
            'top_categories': []
        }), 200

@categories_bp.route('/api/categories/tree', methods=['GET'])
@supabase_jwt_required
def get_category_tree():
    """Get category tree structure"""
    try:
        supabase = get_supabase_db()
        
        # Get all categories ordered by path
        result = supabase.client.table('categories')\
            .select('*')\
            .order('path', asc=True)\
            .execute()
        
        categories = result.data if result.data else []
        
        # Build tree structure
        tree = build_category_tree(categories)
        
        return jsonify({
            'tree': tree,
            'total': len(categories)
        })
        
    except Exception as e:
        logger.error(f"Error fetching category tree: {str(e)}")
        return jsonify({
            'tree': [],
            'total': 0
        }), 200

@categories_bp.route('/api/categories/search', methods=['GET'])
@supabase_jwt_required
def search_categories():
    """Search categories by name"""
    try:
        supabase = get_supabase_db()
        
        query = request.args.get('q', '').strip()
        if not query:
            return jsonify({'categories': []})
        
        # Search categories by name (case-insensitive)
        result = supabase.client.table('categories')\
            .select('*')\
            .ilike('name', f'%{query}%')\
            .limit(20)\
            .execute()
        
        return jsonify({
            'categories': result.data if result.data else []
        })
        
    except Exception as e:
        logger.error(f"Error searching categories: {str(e)}")
        return jsonify({'categories': []}), 200

# Batch operations
@categories_bp.route('/api/categories/batch/assign', methods=['POST'])
@supabase_jwt_required
def batch_assign_categories():
    """Batch assign categories to products"""
    try:
        supabase = get_supabase_db()
        data = request.get_json()
        
        assignments = data.get('assignments', [])
        if not assignments:
            return jsonify({'error': 'No assignments provided'}), 400
        
        # Update products with new categories
        updated = 0
        errors = []
        
        for assignment in assignments:
            product_id = assignment.get('product_id')
            category_id = assignment.get('category_id')
            
            if product_id and category_id:
                try:
                    result = supabase.client.table('products')\
                        .update({'category_id': category_id, 'updated_at': datetime.utcnow().isoformat()})\
                        .eq('id', product_id)\
                        .execute()
                    
                    if result.data:
                        updated += 1
                except Exception as e:
                    errors.append({'product_id': product_id, 'error': str(e)})
        
        return jsonify({
            'updated': updated,
            'errors': errors,
            'message': f'Updated {updated} products'
        })
        
    except Exception as e:
        logger.error(f"Error in batch category assignment: {str(e)}")
        return jsonify({'error': 'Failed to assign categories'}), 500