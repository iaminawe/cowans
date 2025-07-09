"""
Enhanced Icon Sync API Endpoints

Provides REST API endpoints for syncing icons to Shopify collections with:
- Batch sync support
- Progress tracking
- Retry management
- Comprehensive error handling
"""

import json
import logging
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required
from services.supabase_auth import supabase_jwt_required, get_current_user_id
from database import db_session_scope as db_session
from models import Icon, Category
from services.enhanced_shopify_icon_sync import EnhancedShopifyIconSync, IconSyncResult, SyncStatus
import os
from datetime import datetime

# Create blueprint
enhanced_icon_sync_bp = Blueprint('enhanced_icon_sync', __name__, url_prefix='/api/icons/sync')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_enhanced_sync_service():
    """Get configured enhanced sync service."""
    shop_url = os.getenv('SHOPIFY_SHOP_URL')
    access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
    
    if not shop_url or not access_token:
        raise ValueError("Shopify credentials not configured")
    
    return EnhancedShopifyIconSync(
        shop_url=shop_url,
        access_token=access_token,
        max_retries=3,
        batch_size=10,
        concurrent_uploads=3
    )


@enhanced_icon_sync_bp.route('/single', methods=['POST'])
@supabase_jwt_required
def sync_single_icon():
    """Sync a single icon to a Shopify collection."""
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get('icon_id') or not data.get('collection_id'):
            return jsonify({'error': 'icon_id and collection_id are required'}), 400
        
        icon_id = data['icon_id']
        collection_id = data['collection_id']
        
        # Get icon from database
        with db_session() as session:
            icon = session.query(Icon).filter_by(id=icon_id).first()
            if not icon:
                return jsonify({'error': 'Icon not found'}), 404
            
            if not icon.file_path or not os.path.exists(icon.file_path):
                return jsonify({'error': 'Icon file not found'}), 404
            
            # Get category for alt text
            category = session.query(Category).filter_by(id=icon.category_id).first()
            alt_text = f"{category.name} icon" if category else "Collection icon"
        
        # Get sync service
        sync_service = get_enhanced_sync_service()
        
        # Perform sync
        result = sync_service.sync_icon_to_collection(
            icon_path=icon.file_path,
            collection_id=collection_id,
            alt_text=alt_text,
            icon_id=icon_id
        )
        
        # Update database with results
        if result.status == SyncStatus.SUCCESS:
            with db_session() as session:
                icon = session.query(Icon).filter_by(id=icon_id).first()
                if icon:
                    icon.shopify_synced_at = datetime.utcnow()
                    icon.shopify_sync_status = 'synced'
                    icon.shopify_image_id = result.shopify_image_id
                    icon.shopify_image_url = result.shopify_image_url
                    
                    # Update metadata
                    meta_data = icon.meta_data or {}
                    meta_data.update({
                        'shopify_collection_id': collection_id,
                        'last_sync': datetime.utcnow().isoformat(),
                        'sync_retries': result.retry_count
                    })
                    icon.meta_data = meta_data
                    
                    session.commit()
        
        return jsonify({
            'success': result.status == SyncStatus.SUCCESS,
            'icon_id': result.icon_id,
            'collection_id': result.collection_id,
            'status': result.status.value,
            'shopify_image_id': result.shopify_image_id,
            'shopify_image_url': result.shopify_image_url,
            'error': result.error,
            'retry_count': result.retry_count,
            'processing_time': result.processing_time
        })
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        logger.error(f"Error syncing icon: {str(e)}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500


@enhanced_icon_sync_bp.route('/batch', methods=['POST'])
@supabase_jwt_required
def sync_batch_icons():
    """Sync multiple icons to collections in batch."""
    try:
        data = request.get_json()
        
        # Validate input
        if not data.get('mappings') or not isinstance(data['mappings'], list):
            return jsonify({'error': 'mappings array is required'}), 400
        
        mappings = data['mappings']
        
        # Prepare sync mappings
        sync_mappings = []
        icon_ids = []
        
        with db_session() as session:
            for mapping in mappings:
                if not mapping.get('icon_id') or not mapping.get('collection_id'):
                    continue
                
                icon_id = mapping['icon_id']
                icon_ids.append(icon_id)
                
                icon = session.query(Icon).filter_by(id=icon_id).first()
                if not icon or not icon.file_path or not os.path.exists(icon.file_path):
                    continue
                
                # Get category for alt text
                category = session.query(Category).filter_by(id=icon.category_id).first()
                alt_text = mapping.get('alt_text') or (f"{category.name} icon" if category else "Collection icon")
                
                sync_mappings.append({
                    'icon_id': icon_id,
                    'icon_path': icon.file_path,
                    'collection_id': mapping['collection_id'],
                    'alt_text': alt_text
                })
        
        if not sync_mappings:
            return jsonify({
                'error': 'No valid icon mappings found',
                'details': f'Checked {len(mappings)} mappings'
            }), 400
        
        # Get sync service
        sync_service = get_enhanced_sync_service()
        
        # Track progress
        progress_updates = []
        
        def progress_callback(completed, total, result):
            progress_updates.append({
                'completed': completed,
                'total': total,
                'icon_id': result.icon_id,
                'status': result.status.value,
                'timestamp': datetime.utcnow().isoformat()
            })
        
        # Perform batch sync
        results = sync_service.sync_icons_batch(sync_mappings, progress_callback)
        
        # Update database with results
        with db_session() as session:
            for result_data in results['results']:
                if result_data['status'] == 'success':
                    icon = session.query(Icon).filter_by(id=result_data['icon_id']).first()
                    if icon:
                        icon.shopify_synced_at = datetime.utcnow()
                        icon.shopify_sync_status = 'synced'
                        icon.shopify_image_id = result_data['shopify_image_id']
                        icon.shopify_image_url = result_data['shopify_image_url']
                        
                        # Update metadata
                        meta_data = icon.meta_data or {}
                        meta_data.update({
                            'shopify_collection_id': result_data['collection_id'],
                            'last_sync': datetime.utcnow().isoformat(),
                            'sync_retries': result_data['retry_count']
                        })
                        icon.meta_data = meta_data
            
            session.commit()
        
        return jsonify({
            'success': True,
            'summary': results['summary'],
            'results': results['results'],
            'progress_log': progress_updates
        })
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        logger.error(f"Error in batch sync: {str(e)}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500


@enhanced_icon_sync_bp.route('/verify', methods=['POST'])
@supabase_jwt_required
def verify_collection_images():
    """Verify which collections have images."""
    try:
        data = request.get_json()
        
        # Get collection IDs to verify
        collection_ids = data.get('collection_ids', [])
        if not collection_ids:
            return jsonify({'error': 'collection_ids array is required'}), 400
        
        # Get sync service
        sync_service = get_enhanced_sync_service()
        
        # Verify collections
        verification_results = sync_service.verify_collection_images(collection_ids)
        
        # Format response
        results = []
        for collection_id, status in verification_results.items():
            results.append({
                'collection_id': collection_id,
                'has_image': status.get('has_image', False),
                'image_url': status.get('image_url'),
                'title': status.get('title'),
                'handle': status.get('handle'),
                'error': status.get('error')
            })
        
        # Calculate summary
        total = len(results)
        with_images = sum(1 for r in results if r['has_image'])
        without_images = total - with_images
        errors = sum(1 for r in results if r.get('error'))
        
        return jsonify({
            'success': True,
            'summary': {
                'total_collections': total,
                'with_images': with_images,
                'without_images': without_images,
                'errors': errors,
                'coverage_percentage': (with_images / total * 100) if total > 0 else 0
            },
            'results': results
        })
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        logger.error(f"Error verifying collections: {str(e)}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500


@enhanced_icon_sync_bp.route('/status', methods=['GET'])
@supabase_jwt_required
def get_sync_status():
    """Get overall sync status and statistics."""
    try:
        with db_session() as session:
            # Get total icons
            total_icons = session.query(Icon).count()
            
            # Get synced icons
            synced_icons = session.query(Icon).filter(
                Icon.shopify_synced_at.isnot(None)
            ).count()
            
            # Get failed syncs
            failed_syncs = session.query(Icon).filter(
                Icon.shopify_sync_status == 'failed'
            ).count()
            
            # Get categories with Shopify collections
            categories_with_shopify = session.query(Category).filter(
                Category.shopify_collection_id.isnot(None)
            ).count()
            
            # Get recent syncs
            recent_syncs = session.query(Icon).filter(
                Icon.shopify_synced_at.isnot(None)
            ).order_by(Icon.shopify_synced_at.desc()).limit(10).all()
            
            recent_sync_list = []
            for icon in recent_syncs:
                category = session.query(Category).filter_by(id=icon.category_id).first()
                recent_sync_list.append({
                    'icon_id': icon.id,
                    'filename': icon.filename,
                    'category': category.name if category else 'Unknown',
                    'synced_at': icon.shopify_synced_at.isoformat() if icon.shopify_synced_at else None,
                    'shopify_image_url': icon.shopify_image_url
                })
        
        return jsonify({
            'success': True,
            'statistics': {
                'total_icons': total_icons,
                'synced_icons': synced_icons,
                'unsynced_icons': total_icons - synced_icons,
                'failed_syncs': failed_syncs,
                'sync_percentage': (synced_icons / total_icons * 100) if total_icons > 0 else 0,
                'categories_with_shopify': categories_with_shopify
            },
            'recent_syncs': recent_sync_list
        })
        
    except Exception as e:
        logger.error(f"Error getting sync status: {str(e)}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500


@enhanced_icon_sync_bp.route('/retry-failed', methods=['POST'])
@supabase_jwt_required
def retry_failed_syncs():
    """Retry all failed sync operations."""
    try:
        # Get all failed icons
        with db_session() as session:
            failed_icons = session.query(Icon).filter(
                Icon.shopify_sync_status == 'failed'
            ).all()
            
            if not failed_icons:
                return jsonify({
                    'success': True,
                    'message': 'No failed syncs to retry',
                    'total': 0
                })
            
            # Prepare mappings for retry
            sync_mappings = []
            for icon in failed_icons:
                if not icon.file_path or not os.path.exists(icon.file_path):
                    continue
                
                # Get collection ID from metadata or category
                collection_id = None
                if icon.meta_data and 'shopify_collection_id' in icon.meta_data:
                    collection_id = icon.meta_data['shopify_collection_id']
                else:
                    category = session.query(Category).filter_by(id=icon.category_id).first()
                    if category and category.shopify_collection_id:
                        collection_id = category.shopify_collection_id
                
                if collection_id:
                    sync_mappings.append({
                        'icon_id': icon.id,
                        'icon_path': icon.file_path,
                        'collection_id': collection_id,
                        'alt_text': f"Icon for category"
                    })
        
        if not sync_mappings:
            return jsonify({
                'success': True,
                'message': 'No valid failed syncs to retry',
                'total': len(failed_icons),
                'retryable': 0
            })
        
        # Get sync service and retry
        sync_service = get_enhanced_sync_service()
        results = sync_service.sync_icons_batch(sync_mappings)
        
        # Update database with results
        with db_session() as session:
            for result_data in results['results']:
                icon = session.query(Icon).filter_by(id=result_data['icon_id']).first()
                if icon:
                    if result_data['status'] == 'success':
                        icon.shopify_synced_at = datetime.utcnow()
                        icon.shopify_sync_status = 'synced'
                        icon.shopify_image_id = result_data['shopify_image_id']
                        icon.shopify_image_url = result_data['shopify_image_url']
                    else:
                        icon.shopify_sync_status = 'failed'
                    
                    # Update retry count in metadata
                    meta_data = icon.meta_data or {}
                    meta_data['retry_attempts'] = meta_data.get('retry_attempts', 0) + 1
                    meta_data['last_retry'] = datetime.utcnow().isoformat()
                    icon.meta_data = meta_data
            
            session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Retry completed',
            'summary': results['summary'],
            'total_failed': len(failed_icons),
            'retried': len(sync_mappings)
        })
        
    except Exception as e:
        logger.error(f"Error retrying failed syncs: {str(e)}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500