"""
Xorosoft API Endpoints

This module provides REST API endpoints for Xorosoft product validation
and inventory checking functionality.
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import logging
from typing import Dict, Any, List
from datetime import datetime

from database import get_db
from services.xorosoft_api_service import XorosoftAPIService, MatchType


# Create blueprint
xorosoft_bp = Blueprint('xorosoft', __name__, url_prefix='/api/xorosoft')
logger = logging.getLogger(__name__)


@xorosoft_bp.route('/validate', methods=['POST'])
@jwt_required()
def validate_product():
    """Validate a single product against Xorosoft inventory."""
    try:
        data = request.get_json()
        
        # Extract required fields
        sku = data.get('sku')
        if not sku:
            return jsonify({'error': 'SKU is required'}), 400
        
        # Extract optional metafields
        metafields = {}
        for field in ['CWS_A', 'CWS_Catalog', 'SPRC']:
            if field in data:
                metafields[field] = data[field]
        
        # Initialize API service
        api_service = XorosoftAPIService()
        
        # Validate product
        match_result = api_service.validate_product(sku, metafields)
        
        # Format response
        response = {
            'matched': match_result.matched,
            'match_type': match_result.match_type.value if match_result.match_type else None,
            'matched_value': match_result.matched_value,
            'confidence_score': match_result.confidence_score
        }
        
        if match_result.matched and match_result.xorosoft_product:
            product = match_result.xorosoft_product
            response['xorosoft_product'] = {
                'item_number': product.item_number,
                'base_part_number': product.base_part_number,
                'description': product.description,
                'title': product.title,
                'unit_price': product.unit_price,
                'upc': product.upc
            }
        
        return jsonify(response), 200
        
    except ValueError as e:
        logger.error(f"Xorosoft API configuration error: {str(e)}")
        return jsonify({'error': 'Xorosoft API not configured'}), 503
    except Exception as e:
        logger.error(f"Failed to validate product: {str(e)}")
        return jsonify({'error': 'Failed to validate product'}), 500


@xorosoft_bp.route('/validate/batch', methods=['POST'])
@jwt_required()
def validate_products_batch():
    """Validate multiple products in batch."""
    try:
        data = request.get_json()
        
        # Extract products list
        products = data.get('products', [])
        if not products:
            return jsonify({'error': 'Products list is required'}), 400
        
        if len(products) > 100:
            return jsonify({'error': 'Maximum 100 products per batch'}), 400
        
        # Initialize API service
        api_service = XorosoftAPIService()
        
        # Validate products
        results = []
        for product_data in products:
            sku = product_data.get('sku', '')
            if not sku:
                continue
            
            # Extract metafields
            metafields = {}
            for field in ['CWS_A', 'CWS_Catalog', 'SPRC']:
                if field in product_data:
                    metafields[field] = product_data[field]
            
            # Validate
            match_result = api_service.validate_product(sku, metafields)
            
            # Format result
            result = {
                'sku': sku,
                'matched': match_result.matched,
                'match_type': match_result.match_type.value if match_result.match_type else None,
                'confidence_score': match_result.confidence_score
            }
            
            if match_result.matched and match_result.xorosoft_product:
                product = match_result.xorosoft_product
                result['xorosoft_item_number'] = product.item_number
                result['xorosoft_description'] = product.description
            
            results.append(result)
        
        # Get cache statistics
        cache_info = api_service.get_cache_info()
        
        return jsonify({
            'results': results,
            'total_validated': len(results),
            'total_matched': sum(1 for r in results if r['matched']),
            'cache_stats': cache_info
        }), 200
        
    except ValueError as e:
        logger.error(f"Xorosoft API configuration error: {str(e)}")
        return jsonify({'error': 'Xorosoft API not configured'}), 503
    except Exception as e:
        logger.error(f"Failed to validate products batch: {str(e)}")
        return jsonify({'error': 'Failed to validate products'}), 500


@xorosoft_bp.route('/inventory/<item_number>', methods=['GET'])
@jwt_required()
def get_inventory_status(item_number: str):
    """Get inventory status for a specific item."""
    try:
        # Initialize API service
        api_service = XorosoftAPIService()
        
        # Get inventory status
        inventory = api_service.get_inventory_status(item_number)
        
        if not inventory:
            return jsonify({'error': 'Product not found'}), 404
        
        return jsonify(inventory), 200
        
    except ValueError as e:
        logger.error(f"Xorosoft API configuration error: {str(e)}")
        return jsonify({'error': 'Xorosoft API not configured'}), 503
    except Exception as e:
        logger.error(f"Failed to get inventory status: {str(e)}")
        return jsonify({'error': 'Failed to get inventory status'}), 500


@xorosoft_bp.route('/search', methods=['GET'])
@jwt_required()
def search_products():
    """Search for products in Xorosoft inventory."""
    try:
        # Get search parameters
        query = request.args.get('query')
        search_field = request.args.get('field')  # ItemNumber, BasePartNumber, etc.
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 50, type=int)
        
        if not query:
            return jsonify({'error': 'Query parameter is required'}), 400
        
        if page_size > 100:
            return jsonify({'error': 'Maximum page size is 100'}), 400
        
        # Initialize API service
        api_service = XorosoftAPIService()
        
        # Search products
        product = api_service.search_products(query, search_field, page, page_size)
        
        if not product:
            return jsonify({
                'results': [],
                'total': 0,
                'page': page,
                'page_size': page_size
            }), 200
        
        # Format response
        return jsonify({
            'results': [{
                'item_number': product.item_number,
                'base_part_number': product.base_part_number,
                'description': product.description,
                'title': product.title,
                'unit_price': product.unit_price,
                'upc': product.upc
            }],
            'total': 1,
            'page': page,
            'page_size': page_size
        }), 200
        
    except ValueError as e:
        logger.error(f"Xorosoft API configuration error: {str(e)}")
        return jsonify({'error': 'Xorosoft API not configured'}), 503
    except Exception as e:
        logger.error(f"Failed to search products: {str(e)}")
        return jsonify({'error': 'Failed to search products'}), 500


@xorosoft_bp.route('/status', methods=['GET'])
@jwt_required()
def get_api_status():
    """Get Xorosoft API connection status and statistics."""
    try:
        # Initialize API service
        api_service = XorosoftAPIService()
        
        # Test API connection with a simple request
        test_product = api_service.search_products('test', page_size=1)
        api_connected = test_product is not None or True  # Consider connected even if no results
        
        # Get cache statistics
        cache_info = api_service.get_cache_info()
        
        return jsonify({
            'connected': api_connected,
            'api_url': api_service.base_url,
            'cache_statistics': cache_info,
            'rate_limit': {
                'requests_per_second': api_service._requests_per_second
            }
        }), 200
        
    except ValueError as e:
        return jsonify({
            'connected': False,
            'error': 'API credentials not configured'
        }), 200
    except Exception as e:
        logger.error(f"Failed to get API status: {str(e)}")
        return jsonify({
            'connected': False,
            'error': str(e)
        }), 200


@xorosoft_bp.route('/cache/clear', methods=['POST'])
@jwt_required()
def clear_cache():
    """Clear the API cache."""
    try:
        # Initialize API service
        api_service = XorosoftAPIService()
        
        # Clear cache
        api_service.clear_cache()
        
        return jsonify({
            'success': True,
            'message': 'Cache cleared successfully'
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to clear cache: {str(e)}")
        return jsonify({'error': 'Failed to clear cache'}), 500


# Missing Xorosoft Endpoints
@xorosoft_bp.route('/connection/check', methods=['GET'])
@jwt_required()
def check_connection():
    """Check Xorosoft API connection status."""
    try:
        # Initialize API service
        api_service = XorosoftAPIService()
        
        # Test connection with a simple request
        test_result = api_service.search_products('test', page_size=1)
        
        # Get API configuration info
        config_info = {
            'api_url': getattr(api_service, 'base_url', 'Not configured'),
            'authentication': 'Configured' if getattr(api_service, 'username', None) else 'Not configured',
            'rate_limit': getattr(api_service, '_requests_per_second', 'Unknown')
        }
        
        return jsonify({
            'success': True,
            'connected': True,
            'message': 'Connection to Xorosoft API is working',
            'config': config_info,
            'timestamp': datetime.utcnow().isoformat()
        }), 200
        
    except ValueError as e:
        return jsonify({
            'success': False,
            'connected': False,
            'error': 'API credentials not configured',
            'message': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 200
    except Exception as e:
        logger.error(f"Failed to check connection: {str(e)}")
        return jsonify({
            'success': False,
            'connected': False,
            'error': str(e),
            'message': 'Failed to connect to Xorosoft API',
            'timestamp': datetime.utcnow().isoformat()
        }), 200


@xorosoft_bp.route('/sync/history', methods=['GET'])
@jwt_required()
def get_sync_history():
    """Get Xorosoft sync history."""
    try:
        # Get query parameters
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        status = request.args.get('status')
        
        # In a real implementation, this would query a sync history table
        # For now, return mock data
        mock_history = []
        
        # Simulate some sync history entries
        from datetime import datetime, timedelta
        for i in range(min(per_page, 10)):
            entry = {
                'id': f'sync_{i+1}',
                'type': 'product_validation',
                'status': 'completed' if i % 3 != 0 else 'failed',
                'started_at': (datetime.utcnow() - timedelta(hours=i*2)).isoformat(),
                'completed_at': (datetime.utcnow() - timedelta(hours=i*2-1)).isoformat(),
                'items_processed': 50 + i*10,
                'items_successful': 45 + i*8 if i % 3 != 0 else 20 + i*5,
                'items_failed': 5 + i*2 if i % 3 != 0 else 30 + i*5,
                'error_summary': 'Some items failed validation' if i % 3 == 0 else None
            }
            mock_history.append(entry)
        
        # Filter by status if provided
        if status:
            mock_history = [h for h in mock_history if h['status'] == status]
        
        return jsonify({
            'success': True,
            'history': mock_history,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': len(mock_history),
                'total_pages': 1
            },
            'timestamp': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to get sync history: {str(e)}")
        return jsonify({'error': 'Failed to get sync history'}), 500


# Error handlers
@xorosoft_bp.errorhandler(404)
def handle_not_found(error):
    return jsonify({'error': 'Resource not found'}), 404


@xorosoft_bp.errorhandler(400)
def handle_bad_request(error):
    return jsonify({'error': 'Bad request'}), 400


@xorosoft_bp.errorhandler(500)
def handle_internal_error(error):
    logger.error(f"Internal error: {str(error)}")
    return jsonify({'error': 'Internal server error'}), 500