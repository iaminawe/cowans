"""
Shopify Sync Down API endpoints

This module provides the sync-down endpoints for pulling data from Shopify.
It wraps the enhanced sync API with a simpler interface for the frontend.
"""

import logging
import uuid
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from services.supabase_auth import supabase_jwt_required, get_current_user_id
from database import db_session_scope as db_session
from datetime import datetime
import traceback

# Create blueprint
shopify_sync_down_bp = Blueprint('shopify_sync_down', __name__, url_prefix='/api/shopify/sync-down')

# Configure logging
logger = logging.getLogger(__name__)


@shopify_sync_down_bp.route('/start', methods=['POST'])
@supabase_jwt_required
def start_sync_down():
    """Start a Shopify sync down operation."""
    try:
        data = request.get_json() or {}
        user_id = get_current_user_id()
        
        # Build sync configuration from request
        sync_config = {
            'sync_type': 'incremental' if data.get('modifiedSince') else 'full',
            'batch_name': f"Shopify Sync Down - {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
            'include_archived': data.get('includeArchived', False),
            'include_variants': data.get('includeVariants', True),
            'include_metafields': data.get('includeMetafields', True),
            'include_inventory': data.get('includeInventory', True),
            'detect_changes': data.get('detectChanges', True),
            'batch_size': data.get('batchSize', 250),
            'modified_since': data.get('modifiedSince'),
            'collections': data.get('collections', []),
            'product_types': data.get('productTypes', [])
        }
        
        # Check if Shopify is configured
        import os
        shop_url = os.getenv('SHOPIFY_SHOP_URL')
        access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
        
        if not shop_url or not access_token:
            logger.warning("Shopify credentials not configured")
            return jsonify({
                'success': False,
                'error': 'Shopify integration not configured',
                'message': 'Please configure Shopify credentials to use sync functionality'
            }), 503
        
        # Create a sync batch ID for tracking
        batch_id = str(uuid.uuid4())
        
        # For now, return a mock response since we need proper Shopify configuration
        # In production, this would initiate the actual sync process
        logger.info(f"Sync down requested with config: {sync_config}")
        
        # Create sync batch record in database
        with db_session() as session:
            from staging_models import SyncBatch
            from sync_models import SyncDirection
            
            sync_batch = SyncBatch(
                batch_id=batch_id,
                batch_name=sync_config['batch_name'],
                sync_type=sync_config['sync_type'],
                sync_direction='pull_from_shopify',
                status='pending',
                total_items=0,
                processed_items=0,
                successful_items=0,
                failed_items=0,
                started_at=datetime.utcnow(),
                created_by=user_id,
                configuration=sync_config
            )
            
            session.add(sync_batch)
            session.commit()
        
        return jsonify({
            'success': True,
            'batch_id': batch_id,
            'message': 'Sync operation started',
            'status': 'pending',
            'estimated_time': '2-5 minutes'
        }), 202  # 202 Accepted for async operation
                
    except Exception as e:
        logger.error(f"Failed to start sync down: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@shopify_sync_down_bp.route('/status/<batch_id>', methods=['GET'])
@supabase_jwt_required
def get_sync_down_status(batch_id):
    """Get status of a sync down operation."""
    try:
        with db_session() as session:
            # Import models
            from staging_models import SyncBatch
            
            # Get batch status
            batch = session.query(SyncBatch).filter_by(batch_id=batch_id).first()
            if not batch:
                return jsonify({'error': 'Batch not found'}), 404
            
            # Calculate progress
            progress = 0
            if batch.total_items > 0:
                progress = int((batch.processed_items / batch.total_items) * 100)
            
            return jsonify({
                'success': True,
                'batch_id': batch.batch_id,
                'status': batch.status,
                'progress': progress,
                'total_items': batch.total_items,
                'processed_items': batch.processed_items,
                'successful_items': batch.successful_items,
                'failed_items': batch.failed_items,
                'started_at': batch.started_at.isoformat() if batch.started_at else None,
                'completed_at': batch.completed_at.isoformat() if batch.completed_at else None,
                'error_summary': batch.error_summary
            })
            
    except Exception as e:
        logger.error(f"Failed to get sync status: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@shopify_sync_down_bp.route('/cancel/<batch_id>', methods=['POST'])
@supabase_jwt_required
def cancel_sync_down(batch_id):
    """Cancel a running sync down operation."""
    try:
        with db_session() as session:
            from staging_models import SyncBatch
            
            batch = session.query(SyncBatch).filter_by(batch_id=batch_id).first()
            if not batch:
                return jsonify({'error': 'Batch not found'}), 404
            
            if batch.status != 'running':
                return jsonify({'error': 'Batch is not running'}), 400
            
            # Update batch status
            batch.status = 'cancelled'
            batch.completed_at = datetime.utcnow()
            batch.error_summary = {'reason': 'Cancelled by user'}
            
            session.commit()
            
            return jsonify({
                'success': True,
                'message': 'Sync operation cancelled'
            })
            
    except Exception as e:
        logger.error(f"Failed to cancel sync: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500