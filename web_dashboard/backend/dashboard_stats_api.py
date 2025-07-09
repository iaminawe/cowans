#!/usr/bin/env python3
"""
Dashboard Statistics API - Provides live data for all dashboard components
"""

from flask import Blueprint, jsonify, request
from flask_cors import CORS
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import requests
from dotenv import load_dotenv
load_dotenv()

dashboard_stats_bp = Blueprint('dashboard_stats', __name__)
CORS(dashboard_stats_bp)

# Database connection
def get_db_connection():
    db_url = os.getenv('DATABASE_URL')
    if db_url.startswith('postgresql+psycopg://'):
        db_url = db_url.replace('postgresql+psycopg://', 'postgresql://')
    return psycopg2.connect(db_url, cursor_factory=RealDictCursor)

@dashboard_stats_bp.route('/api/dashboard/products/stats', methods=['GET'])
def get_product_stats():
    """Get product statistics for ProductsDashboard"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Total products
        cursor.execute("SELECT COUNT(*) as count FROM products")
        total_products = cursor.fetchone()['count']
        
        # Shopify synced products
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM products 
            WHERE shopify_product_id IS NOT NULL
        """)
        shopify_synced = cursor.fetchone()['count']
        
        # Calculate sync percentage
        sync_percentage = round((shopify_synced / total_products * 100) if total_products > 0 else 0)
        
        # Revenue calculation (sum of price * inventory_quantity)
        cursor.execute("""
            SELECT SUM(price * COALESCE(inventory_quantity, 0)) as revenue
            FROM products
            WHERE price > 0
        """)
        revenue_result = cursor.fetchone()['revenue']
        total_revenue = float(revenue_result) if revenue_result else 0.0
        
        # Revenue trend (compare with last month)
        thirty_days_ago = datetime.now() - timedelta(days=30)
        cursor.execute("""
            SELECT SUM(price * COALESCE(inventory_quantity, 0)) as revenue
            FROM products
            WHERE price > 0 AND updated_at < %s
        """, (thirty_days_ago,))
        last_month_revenue = cursor.fetchone()['revenue'] or 0
        
        revenue_change = 0
        if last_month_revenue > 0:
            revenue_change = round(((total_revenue - float(last_month_revenue)) / float(last_month_revenue)) * 100, 1)
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'totalProducts': total_products,
            'shopifySynced': shopify_synced,
            'syncPercentage': sync_percentage,
            'totalRevenue': round(total_revenue, 2),
            'revenueChange': revenue_change,
            'revenueChangeType': 'increase' if revenue_change > 0 else 'decrease'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@dashboard_stats_bp.route('/api/dashboard/products/enhanced-stats', methods=['GET'])
def get_enhanced_product_stats():
    """Get enhanced product statistics for ProductsDashboardEnhanced"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Total products
        cursor.execute("SELECT COUNT(*) as count FROM products")
        total_products = cursor.fetchone()['count']
        
        # Shopify synced products
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM products 
            WHERE shopify_product_id IS NOT NULL
        """)
        shopify_synced = cursor.fetchone()['count']
        
        # Staging changes (products modified since last sync)
        try:
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM products
                WHERE updated_at > (
                    SELECT COALESCE(MAX(created_at), '1900-01-01'::timestamp) 
                    FROM sync_batches 
                    WHERE status = 'completed'
                )
            """)
            staging_changes = cursor.fetchone()['count'] or 0
        except Exception as e:
            # If sync_batches table doesn't exist, count all products as staging changes
            cursor.execute("SELECT COUNT(*) as count FROM products")
            staging_changes = cursor.fetchone()['count'] or 0
        
        # Recent activity
        try:
            cursor.execute("""
                SELECT 
                    'Product Updated' as action,
                    name as description,
                    updated_at as timestamp
                FROM products
                WHERE updated_at >= %s
                ORDER BY updated_at DESC
                LIMIT 10
            """, (datetime.now() - timedelta(hours=24),))
            
            recent_activity = cursor.fetchall()
        except Exception as e:
            # If there's an error with recent activity, return empty list
            recent_activity = []
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'totalProducts': total_products,
            'shopifySynced': shopify_synced,
            'stagingChanges': staging_changes,
            'recentActivity': recent_activity
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@dashboard_stats_bp.route('/api/dashboard/analytics/stats', methods=['GET'])
def get_analytics_stats():
    """Get comprehensive analytics for ProductAnalytics component"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Basic counts
        cursor.execute("""
            SELECT 
                COUNT(*) as total_products,
                COUNT(CASE WHEN is_active = true THEN 1 END) as active_products,
                SUM(price * COALESCE(inventory_quantity, 0)) as total_inventory_value,
                AVG(price) as average_price,
                COUNT(CASE WHEN inventory_quantity <= 5 AND inventory_quantity > 0 THEN 1 END) as low_stock,
                COUNT(CASE WHEN inventory_quantity = 0 OR inventory_quantity IS NULL THEN 1 END) as out_of_stock
            FROM products
        """)
        
        stats = cursor.fetchone()
        
        # Category breakdown
        cursor.execute("""
            SELECT 
                c.name as category,
                COUNT(p.id) as count,
                SUM(p.price * COALESCE(p.inventory_quantity, 0)) as value
            FROM categories c
            LEFT JOIN products p ON p.category_id = c.id
            GROUP BY c.id, c.name
            ORDER BY count DESC
            LIMIT 10
        """)
        
        category_breakdown = cursor.fetchall()
        
        # Price distribution
        cursor.execute("""
            SELECT 
                price_range,
                COUNT(*) as count
            FROM (
                SELECT 
                    CASE 
                        WHEN price < 10 THEN 'Under $10'
                        WHEN price < 25 THEN '$10-$25'
                        WHEN price < 50 THEN '$25-$50'
                        WHEN price < 100 THEN '$50-$100'
                        ELSE 'Over $100'
                    END as price_range,
                    CASE 
                        WHEN price < 10 THEN 1
                        WHEN price < 25 THEN 2
                        WHEN price < 50 THEN 3
                        WHEN price < 100 THEN 4
                        ELSE 5
                    END as sort_order
                FROM products
                WHERE price > 0
            ) as price_ranges
            GROUP BY price_range, sort_order
            ORDER BY sort_order
        """)
        
        price_distribution = cursor.fetchall()
        
        # Inventory trends (last 7 days)
        cursor.execute("""
            SELECT 
                DATE(updated_at) as date,
                SUM(inventory_quantity) as total_inventory
            FROM products
            WHERE updated_at >= CURRENT_DATE - INTERVAL '7 days'
            GROUP BY DATE(updated_at)
            ORDER BY date
        """)
        
        inventory_trends = cursor.fetchall()
        
        # Top products by value
        cursor.execute("""
            SELECT 
                name,
                price,
                inventory_quantity,
                (price * COALESCE(inventory_quantity, 0)) as total_value
            FROM products
            WHERE price > 0 AND inventory_quantity > 0
            ORDER BY total_value DESC
            LIMIT 10
        """)
        
        top_products = cursor.fetchall()
        
        # Brand performance
        cursor.execute("""
            SELECT 
                vendor,
                COUNT(*) as product_count,
                AVG(price) as avg_price,
                SUM(inventory_quantity) as total_inventory
            FROM products
            WHERE vendor IS NOT NULL AND vendor != ''
            GROUP BY vendor
            ORDER BY product_count DESC
            LIMIT 10
        """)
        
        brand_performance = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'stats': {
                'totalProducts': stats['total_products'],
                'activeProducts': stats['active_products'],
                'totalInventoryValue': round(float(stats['total_inventory_value'] or 0), 2),
                'averagePrice': round(float(stats['average_price'] or 0), 2),
                'lowStock': stats['low_stock'],
                'outOfStock': stats['out_of_stock']
            },
            'categoryBreakdown': category_breakdown,
            'priceDistribution': price_distribution,
            'inventoryTrends': inventory_trends,
            'topProducts': top_products,
            'brandPerformance': brand_performance
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@dashboard_stats_bp.route('/api/dashboard/collections/stats', methods=['GET'])
def get_collections_stats():
    """Get collections statistics"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Total collections
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM categories 
            WHERE parent_id IS NULL
        """)
        total_collections = cursor.fetchone()['count']
        
        # Collections with products
        cursor.execute("""
            SELECT COUNT(DISTINCT c.id) as count
            FROM categories c
            INNER JOIN products p ON p.category_id = c.id
            WHERE c.parent_id IS NULL
        """)
        active_collections = cursor.fetchone()['count']
        
        # Products per collection
        cursor.execute("""
            SELECT 
                c.name,
                COUNT(p.id) as product_count
            FROM categories c
            LEFT JOIN products p ON p.category_id = c.id
            WHERE c.parent_id IS NULL
            GROUP BY c.id, c.name
            ORDER BY product_count DESC
        """)
        
        collections_breakdown = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'totalCollections': total_collections,
            'activeCollections': active_collections,
            'collectionsBreakdown': collections_breakdown
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@dashboard_stats_bp.route('/api/dashboard/collections/summary', methods=['GET'])
def get_collections_summary():
    """Get collections summary statistics for dashboard"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get collection counts from Shopify API
        headers = {
            'X-Shopify-Access-Token': os.getenv('SHOPIFY_ACCESS_TOKEN'),
            'Content-Type': 'application/json'
        }
        
        shop_url = os.getenv('SHOPIFY_SHOP_URL')
        
        # Count custom collections
        custom_url = f"https://{shop_url}/admin/api/2023-10/custom_collections/count.json"
        custom_response = requests.get(custom_url, headers=headers)
        custom_count = custom_response.json().get('count', 0) if custom_response.status_code == 200 else 0
        
        # Count smart collections
        smart_url = f"https://{shop_url}/admin/api/2023-10/smart_collections/count.json"
        smart_response = requests.get(smart_url, headers=headers)
        smart_count = smart_response.json().get('count', 0) if smart_response.status_code == 200 else 0
        
        total_collections = custom_count + smart_count
        
        # Get products in collections count
        cursor.execute("""
            SELECT COUNT(DISTINCT p.id) 
            FROM products p
            WHERE p.category_id IN (
                SELECT id FROM categories WHERE parent_id IS NULL
            )
        """)
        products_in_collections = cursor.fetchone()['count']
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'total_collections': total_collections,
            'active_collections': total_collections,  # All Shopify collections are considered active
            'draft_collections': 0,
            'synced_collections': total_collections,
            'total_products_in_collections': products_in_collections,
            'custom_collections': custom_count,
            'smart_collections': smart_count
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@dashboard_stats_bp.route('/api/dashboard/sync/stats', methods=['GET'])
def get_sync_stats():
    """Get sync statistics for monitoring"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Last sync info
        try:
            cursor.execute("""
                SELECT 
                    created_at,
                    total_products,
                    processed_products,
                    status,
                    EXTRACT(EPOCH FROM (completed_at - created_at)) as duration_seconds
                FROM sync_batches
                ORDER BY created_at DESC
                LIMIT 1
            """)
            
            last_sync = cursor.fetchone()
        except Exception as e:
            # If sync_batches table doesn't exist
            last_sync = None
        
        # Sync history (last 7 days)
        try:
            cursor.execute("""
                SELECT 
                    DATE(created_at) as date,
                    COUNT(*) as sync_count,
                    SUM(processed_products) as total_processed,
                    AVG(EXTRACT(EPOCH FROM (completed_at - created_at))) as avg_duration
                FROM sync_batches
                WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
                GROUP BY DATE(created_at)
                ORDER BY date DESC
            """)
            
            sync_history = cursor.fetchall()
        except Exception as e:
            # If sync_batches table doesn't exist
            sync_history = []
        
        # Pending changes
        try:
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM products
                WHERE updated_at > COALESCE(
                    (SELECT MAX(created_at) FROM sync_batches WHERE status = 'completed'),
                    '1900-01-01'::timestamp
                )
            """)
            
            pending_changes = cursor.fetchone()['count']
        except Exception as e:
            # If sync_batches table doesn't exist, count all products as pending
            cursor.execute("SELECT COUNT(*) as count FROM products")
            pending_changes = cursor.fetchone()['count']
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'lastSync': last_sync,
            'syncHistory': sync_history,
            'pendingChanges': pending_changes
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

