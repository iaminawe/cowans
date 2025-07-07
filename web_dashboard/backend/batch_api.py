"""API endpoints for batch processing operations."""
import uuid
import logging
from typing import Dict, Any, List, Optional
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from batch_processor import batch_processor, BatchConfig
from memory_optimizer import get_memory_stats
from database import db_session_scope
from repositories.user_repository import UserRepository
from websocket_service import WebSocketService

# Note: websocket_service instance is created in app.py
# For now, we'll pass it as a parameter to avoid circular imports


def get_user_id():
    """Helper function to get numeric user ID, handling dev mode."""
    jwt_identity = get_jwt_identity()
    if jwt_identity == "dev-user":
        return 1  # Development mode fallback
    try:
        return int(jwt_identity)
    except (ValueError, TypeError):
        return 1  # Fallback for invalid ID

logger = logging.getLogger(__name__)

batch_bp = Blueprint('batch', __name__, url_prefix='/api/batch')


def sample_product_processor(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Sample processor function for product data.
    
    Args:
        items: List of product items to process
        
    Returns:
        List of processing results
    """
    results = []
    
    for item in items:
        try:
            # Simulate processing time
            import time
            time.sleep(0.1)  # Simulate work
            
            # Validate required fields
            required_fields = ['title', 'sku']
            missing_fields = [field for field in required_fields if not item.get(field)]
            
            if missing_fields:
                results.append({
                    'id': item.get('id', 'unknown'),
                    'status': 'error',
                    'error': f"Missing required fields: {', '.join(missing_fields)}",
                    'original_item': item
                })
            else:
                # Process the item (example: normalize title)
                processed_item = item.copy()
                processed_item['title'] = processed_item['title'].strip().title()
                processed_item['processed_at'] = time.time()
                
                results.append({
                    'id': item.get('id', 'unknown'),
                    'status': 'success',
                    'processed_item': processed_item,
                    'original_item': item
                })
                
        except Exception as e:
            results.append({
                'id': item.get('id', 'unknown'),
                'status': 'error',
                'error': str(e),
                'original_item': item
            })
    
    return results


@batch_bp.route('/config', methods=['GET'])
@jwt_required()
def get_batch_config():
    """Get current batch processing configuration."""
    config = batch_processor.config
    return jsonify({
        'batch_size': config.batch_size,
        'max_workers': config.max_workers,
        'timeout_seconds': config.timeout_seconds,
        'retry_attempts': config.retry_attempts,
        'retry_delay': config.retry_delay,
        'memory_limit_mb': config.memory_limit_mb,
        'enable_parallel': config.enable_parallel,
        'checkpoint_interval': config.checkpoint_interval
    })


@batch_bp.route('/config', methods=['PUT'])
@jwt_required()
def update_batch_config():
    """Update batch processing configuration (admin only)."""
    user_id = get_user_id()
    
    # Check if user is admin
    with db_session_scope() as session:
        user_repo = UserRepository(session)
        user = user_repo.get_by_id(user_id)
        
        if not user or not user.is_admin:
            return jsonify({"message": "Admin access required"}), 403
    
    data = request.get_json()
    config = batch_processor.config
    
    # Update configuration values
    if 'batch_size' in data:
        config.batch_size = max(1, min(1000, int(data['batch_size'])))
    if 'max_workers' in data:
        config.max_workers = max(1, min(16, int(data['max_workers'])))
    if 'timeout_seconds' in data:
        config.timeout_seconds = max(10, min(3600, float(data['timeout_seconds'])))
    if 'retry_attempts' in data:
        config.retry_attempts = max(0, min(10, int(data['retry_attempts'])))
    if 'retry_delay' in data:
        config.retry_delay = max(0.1, min(60, float(data['retry_delay'])))
    if 'memory_limit_mb' in data:
        config.memory_limit_mb = max(64, min(4096, int(data['memory_limit_mb'])))
    if 'enable_parallel' in data:
        config.enable_parallel = bool(data['enable_parallel'])
    if 'checkpoint_interval' in data:
        config.checkpoint_interval = max(1, min(100, int(data['checkpoint_interval'])))
    
    logger.info(f"Batch configuration updated by user {user_id}")
    
    return jsonify({
        'message': 'Configuration updated successfully',
        'config': {
            'batch_size': config.batch_size,
            'max_workers': config.max_workers,
            'timeout_seconds': config.timeout_seconds,
            'retry_attempts': config.retry_attempts,
            'retry_delay': config.retry_delay,
            'memory_limit_mb': config.memory_limit_mb,
            'enable_parallel': config.enable_parallel,
            'checkpoint_interval': config.checkpoint_interval
        }
    })


@batch_bp.route('/create', methods=['POST'])
@jwt_required()
def create_batch():
    """Create a new batch for processing."""
    try:
        data = request.get_json()
        items = data.get('items', [])
        batch_type = data.get('type', 'product_processing')
        
        if not items:
            return jsonify({'message': 'No items provided'}), 400
        
        if len(items) > 10000:  # Limit batch size
            return jsonify({'message': 'Batch size too large (max 10000 items)'}), 400
        
        # Add metadata to items
        for i, item in enumerate(items):
            if 'id' not in item:
                item['id'] = f"{batch_type}_item_{i}"
            item['batch_type'] = batch_type
            item['created_by'] = get_user_id()
        
        batch_id = batch_processor.create_batch(items)
        
        logger.info(f"Batch {batch_id} created with {len(items)} items by user {get_user_id()}")
        
        return jsonify({
            'message': 'Batch created successfully',
            'batch_id': batch_id,
            'total_items': len(items),
            'batch_type': batch_type
        })
        
    except Exception as e:
        logger.error(f"Error creating batch: {str(e)}")
        return jsonify({'message': f'Failed to create batch: {str(e)}'}), 500


@batch_bp.route('/process/<batch_id>', methods=['POST'])
@jwt_required()
def process_batch(batch_id: str):
    """Process a batch with specified processor."""
    try:
        data = request.get_json() or {}
        processor_type = data.get('processor_type', 'sample_product')
        
        # Select processor function based on type
        processor_functions = {
            'sample_product': sample_product_processor,
            # Add more processors as needed
        }
        
        if processor_type not in processor_functions:
            return jsonify({
                'message': f'Unknown processor type: {processor_type}',
                'available_processors': list(processor_functions.keys())
            }), 400
        
        processor_func = processor_functions[processor_type]
        
        # Start processing in background thread
        import threading
        
        def process_in_background():
            try:
                batch_processor.process_batch(
                    batch_id=batch_id,
                    processor_func=processor_func,
                    websocket_service=None  # Will be handled separately
                )
            except Exception as e:
                logger.error(f"Background processing failed for batch {batch_id}: {str(e)}")
        
        thread = threading.Thread(target=process_in_background)
        thread.start()
        
        logger.info(f"Started processing batch {batch_id} with processor {processor_type}")
        
        return jsonify({
            'message': 'Batch processing started',
            'batch_id': batch_id,
            'processor_type': processor_type
        })
        
    except Exception as e:
        logger.error(f"Error starting batch processing: {str(e)}")
        return jsonify({'message': f'Failed to start processing: {str(e)}'}), 500


@batch_bp.route('/status/<batch_id>', methods=['GET'])
@jwt_required()
def get_batch_status(batch_id: str):
    """Get status and progress of a specific batch."""
    try:
        progress = batch_processor.get_batch_progress(batch_id)
        
        if not progress:
            return jsonify({'message': 'Batch not found'}), 404
        
        return jsonify({
            'batch_id': progress.batch_id,
            'status': progress.status,
            'total_items': progress.total_items,
            'processed_items': progress.processed_items,
            'successful_items': progress.successful_items,
            'failed_items': progress.failed_items,
            'skipped_items': progress.skipped_items,
            'current_batch': progress.current_batch,
            'total_batches': progress.total_batches,
            'progress_percentage': round(progress.progress_percentage, 2),
            'throughput_per_second': round(progress.throughput_per_second, 2),
            'error_rate': round(progress.error_rate, 2),
            'elapsed_time': str(progress.elapsed_time),
            'estimated_completion': progress.estimated_completion.isoformat() if progress.estimated_completion else None,
            'start_time': progress.start_time.isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting batch status: {str(e)}")
        return jsonify({'message': f'Failed to get status: {str(e)}'}), 500


@batch_bp.route('/results/<batch_id>', methods=['GET'])
@jwt_required()
def get_batch_results(batch_id: str):
    """Get results of a completed batch."""
    try:
        progress = batch_processor.get_batch_progress(batch_id)
        
        if not progress:
            return jsonify({'message': 'Batch not found'}), 404
        
        if progress.status not in ['completed', 'completed_with_errors', 'failed']:
            return jsonify({'message': 'Batch not yet completed'}), 400
        
        results = batch_processor.get_batch_results(batch_id)
        
        # Add pagination
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 100)), 1000)
        
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        
        paginated_results = results[start_idx:end_idx] if results else []
        
        return jsonify({
            'batch_id': batch_id,
            'status': progress.status,
            'total_results': len(results) if results else 0,
            'page': page,
            'per_page': per_page,
            'total_pages': (len(results) + per_page - 1) // per_page if results else 0,
            'results': paginated_results,
            'summary': {
                'successful_items': progress.successful_items,
                'failed_items': progress.failed_items,
                'total_items': progress.total_items,
                'error_rate': round(progress.error_rate, 2)
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting batch results: {str(e)}")
        return jsonify({'message': f'Failed to get results: {str(e)}'}), 500


@batch_bp.route('/cancel/<batch_id>', methods=['POST'])
@jwt_required()
def cancel_batch(batch_id: str):
    """Cancel a running batch."""
    try:
        success = batch_processor.cancel_batch(batch_id)
        
        if success:
            logger.info(f"Batch {batch_id} cancelled by user {get_user_id()}")
            return jsonify({'message': 'Batch cancelled successfully'})
        else:
            return jsonify({'message': 'Batch not found or not cancellable'}), 400
            
    except Exception as e:
        logger.error(f"Error cancelling batch: {str(e)}")
        return jsonify({'message': f'Failed to cancel batch: {str(e)}'}), 500


@batch_bp.route('/list', methods=['GET'])
@jwt_required()
def list_batches():
    """List all batches with optional filtering."""
    try:
        status_filter = request.args.get('status')
        limit = min(int(request.args.get('limit', 50)), 200)
        
        batches = []
        for batch_id, progress in batch_processor.active_batches.items():
            if status_filter and progress.status != status_filter:
                continue
                
            batches.append({
                'batch_id': batch_id,
                'status': progress.status,
                'total_items': progress.total_items,
                'processed_items': progress.processed_items,
                'progress_percentage': round(progress.progress_percentage, 2),
                'start_time': progress.start_time.isoformat(),
                'throughput_per_second': round(progress.throughput_per_second, 2),
                'error_rate': round(progress.error_rate, 2)
            })
        
        # Sort by start time (newest first)
        batches.sort(key=lambda x: x['start_time'], reverse=True)
        
        return jsonify({
            'batches': batches[:limit],
            'total_count': len(batches),
            'limit': limit
        })
        
    except Exception as e:
        logger.error(f"Error listing batches: {str(e)}")
        return jsonify({'message': f'Failed to list batches: {str(e)}'}), 500


@batch_bp.route('/stats', methods=['GET'])
@jwt_required()
def get_batch_stats():
    """Get batch processing system statistics."""
    try:
        stats = batch_processor.get_system_stats()
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Error getting batch stats: {str(e)}")
        return jsonify({'message': f'Failed to get stats: {str(e)}'}), 500


@batch_bp.route('/cleanup', methods=['POST'])
@jwt_required()
def cleanup_old_batches():
    """Clean up old completed batches (admin only)."""
    user_id = get_user_id()
    
    # Check if user is admin
    with db_session_scope() as session:
        user_repo = UserRepository(session)
        user = user_repo.get_by_id(user_id)
        
        if not user or not user.is_admin:
            return jsonify({"message": "Admin access required"}), 403
    
    try:
        max_age_hours = int(request.args.get('max_age_hours', 24))
        cleaned_count = batch_processor.cleanup_completed_batches(max_age_hours)
        
        logger.info(f"Cleaned up {cleaned_count} old batches (older than {max_age_hours}h) by user {user_id}")
        
        return jsonify({
            'message': f'Cleaned up {cleaned_count} old batches',
            'max_age_hours': max_age_hours
        })
        
    except Exception as e:
        logger.error(f"Error cleaning up batches: {str(e)}")
        return jsonify({'message': f'Failed to cleanup batches: {str(e)}'}), 500


@batch_bp.route('/memory', methods=['GET'])
@jwt_required()
def get_memory_status():
    """Get current memory usage and statistics."""
    try:
        stats = get_memory_stats()
        return jsonify({
            'memory_stats': stats,
            'recommendations': _get_memory_recommendations(stats)
        })
        
    except Exception as e:
        logger.error(f"Error getting memory status: {str(e)}")
        return jsonify({'message': f'Failed to get memory status: {str(e)}'}), 500


def _get_memory_recommendations(stats: Dict[str, Any]) -> List[str]:
    """Generate memory optimization recommendations."""
    recommendations = []
    
    if stats['is_critical']:
        recommendations.append("Critical memory usage detected. Consider reducing batch size or max workers.")
    elif stats['rss_mb'] > stats['threshold_mb'] * 0.7:
        recommendations.append("High memory usage. Monitor for potential issues.")
    
    if stats['percent'] > 80:
        recommendations.append("System memory usage is high. Consider adding more RAM.")
    
    if stats['available_mb'] < 512:
        recommendations.append("Low available system memory. Close unnecessary applications.")
    
    if not recommendations:
        recommendations.append("Memory usage is within normal parameters.")
    
    return recommendations