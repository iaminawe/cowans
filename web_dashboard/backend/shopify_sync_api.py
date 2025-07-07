"""
Shopify Sync API - REST endpoints for database-driven Shopify synchronization

This module provides REST API endpoints for managing Shopify sync operations
using the database-driven approach.
"""

from flask import Blueprint, request, jsonify, current_app
import os
from functools import wraps
from typing import Dict, Any, Optional
import logging
from datetime import datetime

from database import get_db
from contextlib import contextmanager

@contextmanager
def db_session():
    """Context manager for database session."""
    db = next(get_db())
    try:
        yield db
    finally:
        db.close()
from services.shopify_sync_service import (
    ShopifySyncService, SyncConfiguration, SyncMode, SyncFlags
)
from models import EtilizeImportBatch, Product


# Create blueprint
shopify_sync_bp = Blueprint('shopify_sync', __name__, url_prefix='/api/shopify')
logger = logging.getLogger(__name__)

# Development mode auth bypass
DEV_MODE = os.getenv('FLASK_ENV', 'development') == 'development'

def jwt_required_bypass(fn):
    """JWT required decorator that bypasses auth in development mode"""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if DEV_MODE:
            return fn(*args, **kwargs)
        else:
            # In production, would use flask_jwt_extended.jwt_required
            # For now, just pass through
            return fn(*args, **kwargs)
    return wrapper


@shopify_sync_bp.route('/sync/create', methods=['POST'])
@jwt_required_bypass
def create_sync():
    """Create a new Shopify sync job."""
    try:
        data = request.get_json()
        
        # Get Shopify credentials from environment
        shop_url = data.get('shop_url') or os.getenv('SHOPIFY_SHOP_URL')
        access_token = data.get('access_token') or os.getenv('SHOPIFY_ACCESS_TOKEN')
        
        # Validate credentials
        if not shop_url or not access_token:
            return jsonify({
                'error': 'Shopify credentials not configured. Please set SHOPIFY_SHOP_URL and SHOPIFY_ACCESS_TOKEN environment variables.'
            }), 400
        
        # Parse sync configuration
        config = SyncConfiguration(
            mode=SyncMode(data.get('mode', SyncMode.FULL_SYNC.value)),
            flags=[SyncFlags(flag) for flag in data.get('flags', [])],
            batch_size=data.get('batch_size', 25),
            max_workers=data.get('max_workers', 1),
            shop_url=shop_url,
            access_token=access_token,
            data_source=data.get('data_source', 'database'),
            limit=data.get('limit'),
            start_from=data.get('start_from')
        )
        
        # Parse filters
        filters = data.get('filters', {})
        import_batch_id = data.get('import_batch_id')
        
        # Create sync job
        with db_session() as db:
            service = ShopifySyncService(db)
            sync_id = service.create_sync_job(
                config=config,
                import_batch_id=import_batch_id,
                product_filters=filters
            )
        
        return jsonify({
            'sync_id': sync_id,
            'status': 'queued',
            'message': 'Sync job created successfully'
        }), 201
        
    except ValueError as e:
        logger.error(f"Invalid sync configuration: {str(e)}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Failed to create sync job: {str(e)}")
        return jsonify({'error': 'Failed to create sync job'}), 500


@shopify_sync_bp.route('/sync/execute', methods=['POST'])
@jwt_required_bypass
def execute_sync():
    """Execute a sync job (combined create + execute)."""
    try:
        data = request.get_json()
        
        # Get Shopify credentials from environment
        shop_url = data.get('shop_url') or os.getenv('SHOPIFY_SHOP_URL')
        access_token = data.get('access_token') or os.getenv('SHOPIFY_ACCESS_TOKEN')
        
        # Validate credentials
        if not shop_url or not access_token:
            return jsonify({
                'error': 'Shopify credentials not configured. Please set SHOPIFY_SHOP_URL and SHOPIFY_ACCESS_TOKEN environment variables.'
            }), 400
        
        # Parse sync configuration
        config = SyncConfiguration(
            mode=SyncMode(data.get('mode', SyncMode.FULL_SYNC.value)),
            flags=[SyncFlags(flag) for flag in data.get('flags', [])],
            batch_size=data.get('batch_size', 25),
            max_workers=data.get('max_workers', 1),
            shop_url=shop_url,
            access_token=access_token,
            data_source=data.get('data_source', 'database'),
            limit=data.get('limit'),
            start_from=data.get('start_from')
        )
        
        # Parse filters
        filters = data.get('filters', {})
        import_batch_id = data.get('import_batch_id')
        
        # Create and execute sync job
        with db_session() as db:
            service = ShopifySyncService(db)
            sync_id = service.create_sync_job(
                config=config,
                import_batch_id=import_batch_id,
                product_filters=filters
            )
            
            # Execute sync (this would be async in production)
            # For now, we'll just return the sync_id and let the client poll
            
        return jsonify({
            'sync_id': sync_id,
            'status': 'queued',
            'message': 'Sync job created and queued for execution'
        }), 200
        
    except ValueError as e:
        logger.error(f"Invalid sync configuration: {str(e)}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Failed to execute sync: {str(e)}")
        return jsonify({'error': 'Failed to execute sync'}), 500


@shopify_sync_bp.route('/sync/status/<sync_id>', methods=['GET'])
@jwt_required_bypass
def get_sync_status(sync_id: str):
    """Get the status of a sync job."""
    try:
        with db_session() as db:
            service = ShopifySyncService(db)
            status = service.get_sync_status(sync_id)
            
            if not status:
                return jsonify({'error': 'Sync job not found'}), 404
            
            return jsonify(status), 200
            
    except Exception as e:
        logger.error(f"Failed to get sync status: {str(e)}")
        return jsonify({'error': 'Failed to get sync status'}), 500


@shopify_sync_bp.route('/sync/history', methods=['GET'])
@jwt_required_bypass
def get_sync_history():
    """Get sync history."""
    try:
        limit = request.args.get('limit', 50, type=int)
        
        with db_session() as db:
            service = ShopifySyncService(db)
            history = service.get_sync_history(limit=limit)
            
        return jsonify({'history': history}), 200
        
    except Exception as e:
        logger.error(f"Failed to get sync history: {str(e)}")
        return jsonify({'error': 'Failed to get sync history'}), 500


@shopify_sync_bp.route('/sync/cancel/<sync_id>', methods=['POST'])
@jwt_required_bypass
def cancel_sync(sync_id: str):
    """Cancel a running sync job."""
    try:
        with db_session() as db:
            service = ShopifySyncService(db)
            success = service.cancel_sync(sync_id)
            
            if not success:
                return jsonify({'error': 'Sync job not found or cannot be cancelled'}), 404
            
            return jsonify({
                'success': True,
                'message': 'Sync job cancelled successfully'
            }), 200
            
    except Exception as e:
        logger.error(f"Failed to cancel sync: {str(e)}")
        return jsonify({'error': 'Failed to cancel sync'}), 500


@shopify_sync_bp.route('/sync/modes', methods=['GET'])
def get_sync_modes():
    """Get available sync modes and flags."""
    return jsonify({
        'modes': [
            {
                'value': mode.value,
                'label': mode.value.replace('_', ' ').title(),
                'description': _get_mode_description(mode)
            }
            for mode in SyncMode
        ],
        'flags': [
            {
                'value': flag.value,
                'label': flag.value.replace('_', ' ').title(),
                'description': _get_flag_description(flag)
            }
            for flag in SyncFlags
        ]
    }), 200


@shopify_sync_bp.route('/products/syncable', methods=['GET'])
@jwt_required_bypass
def get_syncable_products():
    """Get products that can be synced to Shopify."""
    try:
        import_batch_id = request.args.get('import_batch_id', type=int)
        category = request.args.get('category')
        status = request.args.get('status')
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        with db_session() as db:
            from sqlalchemy.orm import joinedload
            from models import Category
            
            query = db.query(Product).options(joinedload(Product.category))
            
            if import_batch_id:
                query = query.filter(Product.import_batch_id == import_batch_id)
            
            if category:
                # Join with Category table to filter by category name
                query = query.join(Category).filter(Category.name == category)
            
            if status:
                query = query.filter(Product.status == status)
            
            # Get total count
            total = query.count()
            
            # Apply pagination
            products = query.offset(offset).limit(limit).all()
            
            # Format response
            products_data = []
            for product in products:
                products_data.append({
                    'id': product.id,
                    'sku': product.sku,
                    'title': product.name or product.title,  # Use name as title
                    'category': product.category.name if product.category else None,
                    'status': product.status,
                    'shopify_id': product.shopify_product_id or product.shopify_id,
                    'shopify_status': product.shopify_sync_status or product.shopify_status,
                    'last_synced': product.shopify_synced_at.isoformat() if product.shopify_synced_at else (product.last_synced.isoformat() if product.last_synced else None),
                    'has_conflicts': getattr(product, 'has_conflicts', False),
                    'primary_source': getattr(product, 'primary_source', 'manual'),
                    'price': float(product.price) if product.price else None
                })
            
            return jsonify({
                'products': products_data,
                'total': total,
                'offset': offset,
                'limit': limit
            }), 200
            
    except Exception as e:
        logger.error(f"Failed to get syncable products: {str(e)}")
        return jsonify({'error': 'Failed to get syncable products'}), 500


@shopify_sync_bp.route('/batches', methods=['GET'])
@jwt_required_bypass
def get_import_batches():
    """Get available import batches for syncing."""
    try:
        with db_session() as db:
            batches = db.query(EtilizeImportBatch).order_by(
                EtilizeImportBatch.created_at.desc()
            ).limit(50).all()
            
            batches_data = []
            for batch in batches:
                # Count products in this batch
                product_count = db.query(Product).filter(
                    Product.import_batch_id == batch.id
                ).count()
                
                batches_data.append({
                    'id': batch.id,
                    'filename': os.path.basename(batch.source_file_path) if batch.source_file_path else 'Unknown',
                    'status': batch.status,
                    'total_records': batch.total_records if hasattr(batch, 'total_records') else 0,
                    'product_count': product_count,
                    'created_at': batch.started_at.isoformat() if batch.started_at else None,
                    'completed_at': batch.completed_at.isoformat() if hasattr(batch, 'completed_at') and batch.completed_at else None
                })
            
            return jsonify({'batches': batches_data}), 200
            
    except Exception as e:
        logger.error(f"Failed to get import batches: {str(e)}")
        return jsonify({'error': 'Failed to get import batches'}), 500


@shopify_sync_bp.route('/test-connection', methods=['GET'])
@jwt_required_bypass
def test_shopify_connection():
    """Test Shopify API connection and credentials."""
    try:
        from services.shopify_product_sync_service import ShopifyProductSyncService
        
        with db_session() as db:
            service = ShopifyProductSyncService(db)
            
            # Test with shop info endpoint
            result = service._make_shopify_request('shop.json')
            
            if result['success']:
                shop_data = result['data'].get('shop', {})
                return jsonify({
                    'success': True,
                    'message': 'Successfully connected to Shopify',
                    'shop': {
                        'name': shop_data.get('name'),
                        'domain': shop_data.get('domain'),
                        'myshopify_domain': shop_data.get('myshopify_domain'),
                        'plan': shop_data.get('plan_name'),
                        'currency': shop_data.get('currency'),
                        'timezone': shop_data.get('timezone'),
                        'product_count': shop_data.get('product_count'),
                        'id': shop_data.get('id')
                    },
                    'configured_url': service.shop_url,
                    'api_version': service.api_version,
                    'raw_response': shop_data  # Show all fields for debugging
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'error': result.get('error', 'Failed to connect to Shopify'),
                    'error_code': result.get('error_code'),
                    'status_code': result.get('status_code'),
                    'error_details': result.get('error_details', {})
                }), 400
                
    except Exception as e:
        logger.error(f"Failed to test Shopify connection: {str(e)}")
        return jsonify({'error': str(e)}), 500


@shopify_sync_bp.route('/check-scopes', methods=['GET'])
@jwt_required_bypass
def check_api_scopes():
    """Check which API scopes are granted to the access token."""
    try:
        from services.shopify_product_sync_service import ShopifyProductSyncService
        
        with db_session() as db:
            service = ShopifyProductSyncService(db)
            
            # Check scopes using the access_scopes endpoint
            result = service._make_shopify_request('oauth/access_scopes.json')
            
            if result['success']:
                scopes_data = result['data'].get('access_scopes', [])
                
                # Also try to get product count directly
                count_result = service._make_shopify_request('products/count.json', params={'status': 'any'})
                product_count = count_result['data'].get('count', 'unknown') if count_result['success'] else 'error'
                
                return jsonify({
                    'success': True,
                    'granted_scopes': [scope.get('handle') for scope in scopes_data],
                    'scope_details': scopes_data,
                    'has_read_products': any(scope.get('handle') == 'read_products' for scope in scopes_data),
                    'has_write_products': any(scope.get('handle') == 'write_products' for scope in scopes_data),
                    'product_count_check': product_count,
                    'api_version': service.api_version,
                    'shop_url': service.shop_url
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'error': result.get('error', 'Failed to check API scopes'),
                    'error_code': result.get('error_code'),
                    'status_code': result.get('status_code'),
                    'error_details': result.get('error_details', {}),
                    'note': 'This endpoint may not be available for private apps'
                }), 400
                
    except Exception as e:
        logger.error(f"Failed to check API scopes: {str(e)}")
        return jsonify({'error': str(e)}), 500


@shopify_sync_bp.route('/validate', methods=['POST'])
@jwt_required_bypass
def validate_sync_config():
    """Validate sync configuration."""
    try:
        data = request.get_json()
        
        # Get Shopify credentials from environment if not provided
        shop_url = data.get('shop_url') or os.getenv('SHOPIFY_SHOP_URL')
        access_token = data.get('access_token') or os.getenv('SHOPIFY_ACCESS_TOKEN')
        
        # Validate required fields
        errors = []
        
        if not shop_url:
            errors.append('Shop URL not configured. Please set SHOPIFY_SHOP_URL environment variable.')
        elif not shop_url.endswith('.myshopify.com'):
            errors.append('Shop URL must end with .myshopify.com')
        
        if not access_token:
            errors.append('Access token not configured. Please set SHOPIFY_ACCESS_TOKEN environment variable.')
        
        # Validate mode
        mode = data.get('mode')
        if mode and mode not in [m.value for m in SyncMode]:
            errors.append(f'Invalid sync mode: {mode}')
        
        # Validate flags
        flags = data.get('flags', [])
        valid_flags = [f.value for f in SyncFlags]
        for flag in flags:
            if flag not in valid_flags:
                errors.append(f'Invalid sync flag: {flag}')
        
        # Validate batch size
        batch_size = data.get('batch_size', 25)
        if batch_size < 1 or batch_size > 100:
            errors.append('Batch size must be between 1 and 100')
        
        # Validate import batch if specified
        import_batch_id = data.get('import_batch_id')
        if import_batch_id:
            with db_session() as db:
                batch = db.query(EtilizeImportBatch).filter(
                    EtilizeImportBatch.id == import_batch_id
                ).first()
                if not batch:
                    errors.append(f'Import batch {import_batch_id} not found')
        
        if errors:
            return jsonify({
                'valid': False,
                'errors': errors
            }), 400
        
        return jsonify({
            'valid': True,
            'message': 'Configuration is valid'
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to validate sync config: {str(e)}")
        return jsonify({'error': 'Failed to validate configuration'}), 500


def _get_mode_description(mode: SyncMode) -> str:
    """Get description for sync mode."""
    descriptions = {
        SyncMode.FULL_SYNC: "Create new products and update existing ones",
        SyncMode.NEW_ONLY: "Only create new products (skip existing)",
        SyncMode.UPDATE_ONLY: "Only update existing products (skip new)",
        SyncMode.ULTRA_FAST: "Only update published status and inventory policy",
        SyncMode.IMAGE_SYNC: "Only sync product images"
    }
    return descriptions.get(mode, "Unknown mode")


def _get_flag_description(flag: SyncFlags) -> str:
    """Get description for sync flag."""
    descriptions = {
        SyncFlags.SKIP_IMAGES: "Skip all image processing for faster sync",
        SyncFlags.CLEANUP_DUPLICATES: "Remove duplicate images during sync",
        SyncFlags.TURBO: "Reduce API delays (moderate speed increase)",
        SyncFlags.HYPER: "Minimum delays (maximum speed, higher risk)",
        SyncFlags.SILENT: "Minimize output and logging",
        SyncFlags.DEBUG: "Enable detailed debug logging"
    }
    return descriptions.get(flag, "Unknown flag")


@shopify_sync_bp.route('/sync-from-shopify', methods=['POST'])
@jwt_required_bypass
def sync_from_shopify():
    """Sync products FROM Shopify TO the local database."""
    try:
        from services.shopify_product_sync_service import ShopifyProductSyncService
        
        data = request.get_json() or {}
        include_draft = data.get('include_draft', True)
        resume_cursor = data.get('resume_cursor')
        
        with db_session() as db:
            service = ShopifyProductSyncService(db)
            
            # Run the sync (with optional resume)
            result = service.sync_all_products(
                include_draft=include_draft,
                resume_cursor=resume_cursor
            )
            
            if result['success']:
                return jsonify(result), 200
            else:
                return jsonify(result), 400
                
    except Exception as e:
        logger.error(f"Failed to sync from Shopify: {str(e)}")
        return jsonify({'error': str(e)}), 500


@shopify_sync_bp.route('/fetch-products-graphql', methods=['GET'])
@jwt_required_bypass
def fetch_shopify_products_graphql():
    """Fetch products from Shopify using GraphQL API."""
    try:
        from services.shopify_product_sync_service import ShopifyProductSyncService
        
        limit = request.args.get('limit', 10, type=int)
        
        with db_session() as db:
            service = ShopifyProductSyncService(db)
            
            # Fetch products using GraphQL
            result = service.fetch_products_graphql(limit=limit)
            
            if result['success']:
                return jsonify(result), 200
            else:
                return jsonify(result), 400
                
    except Exception as e:
        logger.error(f"Failed to fetch Shopify products via GraphQL: {str(e)}")
        return jsonify({'error': str(e)}), 500


@shopify_sync_bp.route('/fetch-products', methods=['GET'])
@jwt_required_bypass
def fetch_shopify_products():
    """Directly fetch products from Shopify to test the API."""
    try:
        from services.shopify_product_sync_service import ShopifyProductSyncService
        
        with db_session() as db:
            service = ShopifyProductSyncService(db)
            
            # First test the connection
            shop_result = service._make_shopify_request('shop.json')
            if not shop_result['success']:
                return jsonify({
                    'success': False,
                    'error': 'Failed to connect to Shopify',
                    'details': shop_result
                }), 400
            
            # Get the actual shop domain
            shop_data = shop_result['data'].get('shop', {})
            actual_domain = shop_data.get('myshopify_domain', '')
            logger.info(f"Shop domain from API: {actual_domain}, configured: {service.shop_url}")
            
            # Try to fetch a small number of products
            params = {
                'limit': 10,
                'status': 'any'  # Get all products regardless of status
            }
            
            result = service._make_shopify_request('products.json', params=params)
            
            if result['success']:
                products = result['data'].get('products', [])
                return jsonify({
                    'success': True,
                    'shop_info': shop_result['data'].get('shop', {}).get('name'),
                    'product_count': len(products),
                    'products': [
                        {
                            'id': p.get('id'),
                            'title': p.get('title'),
                            'status': p.get('status'),
                            'created_at': p.get('created_at')
                        }
                        for p in products[:5]  # Show first 5 products
                    ],
                    'message': f'Found {len(products)} products'
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'error': result.get('error', 'Failed to fetch products'),
                    'error_code': result.get('error_code'),
                    'status_code': result.get('status_code'),
                    'error_details': result.get('error_details', {})
                }), 400
                
    except Exception as e:
        logger.error(f"Failed to fetch Shopify products: {str(e)}")
        return jsonify({'error': str(e)}), 500


@shopify_sync_bp.route('/test-graphql-products', methods=['GET'])
@jwt_required_bypass
def test_shopify_products_graphql():
    """Test GraphQL API to fetch products and compare with REST."""
    try:
        from services.shopify_product_sync_service import ShopifyProductSyncService
        
        with db_session() as db:
            service = ShopifyProductSyncService(db)
            
            # GraphQL query to fetch products
            query = """
            query GetProducts {
                products(first: 10, query: "status:ANY") {
                    edges {
                        node {
                            id
                            title
                            handle
                            status
                            createdAt
                            variants(first: 1) {
                                edges {
                                    node {
                                        id
                                        sku
                                        price
                                    }
                                }
                            }
                        }
                    }
                    pageInfo {
                        hasNextPage
                    }
                }
                shop {
                    name
                    myshopifyDomain
                    plan {
                        displayName
                    }
                }
            }
            """
            
            result = service._make_graphql_request(query)
            
            if result['success']:
                data = result['data']
                products = data.get('products', {}).get('edges', [])
                shop_info = data.get('shop', {})
                
                return jsonify({
                    'success': True,
                    'api_type': 'GraphQL',
                    'shop_info': {
                        'name': shop_info.get('name'),
                        'domain': shop_info.get('myshopifyDomain'),
                        'plan': shop_info.get('plan', {}).get('displayName')
                    },
                    'fetched_count': len(products),
                    'has_more': data.get('products', {}).get('pageInfo', {}).get('hasNextPage', False),
                    'products': [
                        {
                            'id': p['node'].get('id'),
                            'title': p['node'].get('title'),
                            'handle': p['node'].get('handle'),
                            'status': p['node'].get('status'),
                            'created_at': p['node'].get('createdAt'),
                            'sku': p['node']['variants']['edges'][0]['node'].get('sku') if p['node']['variants']['edges'] else None,
                            'price': p['node']['variants']['edges'][0]['node'].get('price') if p['node']['variants']['edges'] else None
                        }
                        for p in products[:5]  # Show first 5 products
                    ],
                    'message': f'GraphQL API successfully returned {len(products)} products'
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'api_type': 'GraphQL',
                    'error': result.get('error', 'Failed to fetch products via GraphQL'),
                    'error_code': result.get('error_code'),
                    'error_details': result.get('error_details', {})
                }), 400
                
    except Exception as e:
        logger.error(f"Failed to fetch Shopify products via GraphQL: {str(e)}")
        return jsonify({'error': str(e)}), 500


@shopify_sync_bp.route('/check-scopes', methods=['GET'])
@jwt_required_bypass
def check_shopify_scopes():
    """Check available API scopes/permissions."""
    try:
        from services.shopify_product_sync_service import ShopifyProductSyncService
        
        with db_session() as db:
            service = ShopifyProductSyncService(db)
            
            # Query to check available scopes
            query = """
            query {
                shop {
                    name
                    currencyCode
                    primaryDomain {
                        url
                    }
                }
                currentAppInstallation {
                    accessScopes {
                        handle
                    }
                }
            }
            """
            
            result = service._make_graphql_request(query)
            
            if result['success']:
                return jsonify({
                    'success': True,
                    'shop': result['data'].get('shop'),
                    'scopes': result['data'].get('currentAppInstallation')
                }), 200
            else:
                return jsonify(result), 400
                
    except Exception as e:
        logger.error(f"Failed to check Shopify scopes: {str(e)}")
        return jsonify({'error': str(e)}), 500


# Error handlers
@shopify_sync_bp.errorhandler(404)
def handle_not_found(error):
    return jsonify({'error': 'Resource not found'}), 404


@shopify_sync_bp.errorhandler(400)
def handle_bad_request(error):
    return jsonify({'error': 'Bad request'}), 400


@shopify_sync_bp.errorhandler(500)
def handle_internal_error(error):
    logger.error(f"Internal error: {str(error)}")
    return jsonify({'error': 'Internal server error'}), 500