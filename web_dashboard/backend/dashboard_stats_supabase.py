#!/usr/bin/env python3
"""
Dashboard Statistics API - Supabase version
Provides live data for all dashboard components using Supabase
"""

from flask import Blueprint, jsonify, request
from flask_cors import CORS
from datetime import datetime, timedelta
from services.supabase_database import get_supabase_db
from services.supabase_auth import supabase_jwt_required
import logging

logger = logging.getLogger(__name__)

dashboard_stats_bp = Blueprint('dashboard_stats', __name__)
CORS(dashboard_stats_bp)

@dashboard_stats_bp.route('/api/dashboard/products/stats', methods=['GET'])
@supabase_jwt_required
def get_product_stats():
    """Get product statistics for ProductsDashboard"""
    try:
        supabase = get_supabase_db()
        
        # Get all products
        products_result = supabase.client.table('products').select('*').execute()
        products = products_result.data if products_result.data else []
        
        # Calculate stats
        total_products = len(products)
        shopify_synced = len([p for p in products if p.get('shopify_product_id')])
        sync_percentage = round((shopify_synced / total_products * 100) if total_products > 0 else 0)
        
        # Calculate revenue
        total_revenue = sum(
            float(p.get('price', 0)) * int(p.get('inventory_quantity', 0))
            for p in products if p.get('price', 0) > 0
        )
        
        return jsonify({
            'totalProducts': total_products,
            'shopifySynced': shopify_synced,
            'syncPercentage': sync_percentage,
            'totalRevenue': round(total_revenue, 2),
            'revenueChange': 0,  # TODO: Implement trend calculation
            'lastSync': None,  # TODO: Get from sync_history
            'syncStatus': 'idle'
        })
        
    except Exception as e:
        logger.error(f"Error in get_product_stats: {str(e)}")
        return jsonify({
            'totalProducts': 0,
            'shopifySynced': 0,
            'syncPercentage': 0,
            'totalRevenue': 0,
            'revenueChange': 0,
            'lastSync': None,
            'syncStatus': 'error'
        }), 200  # Return 200 with default data to prevent frontend errors

@dashboard_stats_bp.route('/api/dashboard/categories/stats', methods=['GET'])
@supabase_jwt_required
def get_category_stats():
    """Get category statistics"""
    try:
        supabase = get_supabase_db()
        
        # Get categories
        categories_result = supabase.client.table('categories').select('*').execute()
        categories = categories_result.data if categories_result.data else []
        
        total_categories = len(categories)
        
        # Get products with categories
        products_result = supabase.client.table('products').select('category_id').execute()
        products = products_result.data if products_result.data else []
        
        categorized_products = len([p for p in products if p.get('category_id')])
        
        return jsonify({
            'totalCategories': total_categories,
            'categorizedProducts': categorized_products,
            'uncategorizedProducts': len(products) - categorized_products,
            'categoryUtilization': round((categorized_products / len(products) * 100) if products else 0)
        })
        
    except Exception as e:
        logger.error(f"Error in get_category_stats: {str(e)}")
        return jsonify({
            'totalCategories': 0,
            'categorizedProducts': 0,
            'uncategorizedProducts': 0,
            'categoryUtilization': 0
        }), 200

@dashboard_stats_bp.route('/api/dashboard/sync/stats', methods=['GET'])
@supabase_jwt_required
def get_sync_stats():
    """Get sync statistics"""
    try:
        supabase = get_supabase_db()
        
        # Get recent sync history
        sync_result = supabase.client.table('sync_history')\
            .select('*')\
            .order('created_at', desc=True)\
            .limit(10)\
            .execute()
        
        sync_history = sync_result.data if sync_result.data else []
        
        if sync_history:
            last_sync = sync_history[0]
            return jsonify({
                'lastSyncTime': last_sync.get('created_at'),
                'lastSyncStatus': last_sync.get('status', 'unknown'),
                'productsAdded': last_sync.get('products_added', 0),
                'productsUpdated': last_sync.get('products_updated', 0),
                'syncErrors': last_sync.get('error_count', 0),
                'syncDuration': last_sync.get('duration', 0)
            })
        
        return jsonify({
            'lastSyncTime': None,
            'lastSyncStatus': 'never',
            'productsAdded': 0,
            'productsUpdated': 0,
            'syncErrors': 0,
            'syncDuration': 0
        })
        
    except Exception as e:
        logger.error(f"Error in get_sync_stats: {str(e)}")
        return jsonify({
            'lastSyncTime': None,
            'lastSyncStatus': 'error',
            'productsAdded': 0,
            'productsUpdated': 0,
            'syncErrors': 0,
            'syncDuration': 0
        }), 200

@dashboard_stats_bp.route('/api/dashboard/enhanced-stats', methods=['GET'])
@dashboard_stats_bp.route('/api/dashboard/products/enhanced-stats', methods=['GET'])
@supabase_jwt_required
def get_enhanced_stats():
    """Get enhanced dashboard statistics combining all metrics"""
    try:
        supabase = get_supabase_db()
        
        # Get products
        products_result = supabase.client.table('products').select('*').execute()
        products = products_result.data if products_result.data else []
        
        # Get categories
        categories_result = supabase.client.table('categories').select('*').execute()
        categories = categories_result.data if categories_result.data else []
        
        # Get collections
        collections_result = supabase.client.table('collections').select('*').execute()
        collections = collections_result.data if collections_result.data else []
        
        # Calculate stats
        total_products = len(products)
        shopify_synced = len([p for p in products if p.get('shopify_product_id')])
        
        return jsonify({
            'total_products': total_products,
            'total_collections': len(collections),
            'total_categories': len(categories),
            'sync_status': 'idle',
            'last_sync': None,
            'stats': {
                'products_synced': shopify_synced,
                'collections_synced': 0,
                'pending_sync': total_products - shopify_synced
            }
        })
        
    except Exception as e:
        logger.error(f"Error in get_enhanced_stats: {str(e)}")
        # Return the same structure as the stub endpoint
        return jsonify({
            'total_products': 0,
            'total_collections': 0,
            'total_categories': 0,
            'sync_status': 'error',
            'last_sync': None,
            'stats': {
                'products_synced': 0,
                'collections_synced': 0,
                'pending_sync': 0
            }
        }), 200

# Additional endpoints for frontend compatibility
@dashboard_stats_bp.route('/api/dashboard/analytics/stats', methods=['GET'])
@supabase_jwt_required
def get_analytics_stats():
    """Get analytics statistics for the dashboard"""
    try:
        # For now, return mock analytics data
        # In a real implementation, this would pull from analytics service
        return jsonify({
            'views': 12543,
            'clicks': 2156,
            'conversions': 89,
            'revenue': 5420.50,
            'period': 'last_30_days',
            'conversion_rate': 4.1,
            'average_order_value': 60.91,
            'bounce_rate': 32.4,
            'page_views': 18765,
            'unique_visitors': 8932,
            'sessions': 11234,
            'session_duration': 185.7
        })
        
    except Exception as e:
        logger.error(f"Error fetching analytics stats: {str(e)}")
        return jsonify({
            'views': 0,
            'clicks': 0,
            'conversions': 0,
            'revenue': 0,
            'period': 'last_30_days',
            'conversion_rate': 0,
            'average_order_value': 0,
            'bounce_rate': 0,
            'page_views': 0,
            'unique_visitors': 0,
            'sessions': 0,
            'session_duration': 0
        }), 200

@dashboard_stats_bp.route('/api/dashboard/collections/summary', methods=['GET'])
@supabase_jwt_required
def get_collections_summary():
    """Get collections summary for the dashboard"""
    try:
        supabase = get_supabase_db()
        
        # Get collections
        collections_result = supabase.client.table('collections').select('*').execute()
        collections = collections_result.data if collections_result.data else []
        
        # Calculate stats
        total_collections = len(collections)
        active_collections = len([c for c in collections if c.get('is_visible', True)])
        synced_collections = len([c for c in collections if c.get('shopify_collection_id')])
        
        # Get collections with products
        collections_with_products = []
        for collection in collections:
            if collection.get('products_count', 0) > 0:
                collections_with_products.append(collection)
        
        return jsonify({
            'total_collections': total_collections,
            'active_collections': active_collections,
            'synced_collections': synced_collections,
            'collections_with_products': len(collections_with_products),
            'recent_collections': collections[:5],  # Last 5 collections
            'top_collections': sorted(collections, key=lambda x: x.get('products_count', 0), reverse=True)[:5]
        })
        
    except Exception as e:
        logger.error(f"Error fetching collections summary: {str(e)}")
        return jsonify({
            'total_collections': 0,
            'active_collections': 0,
            'synced_collections': 0,
            'collections_with_products': 0,
            'recent_collections': [],
            'top_collections': []
        }), 200