"""
Collections Icon Management API

Provides endpoints for generating and managing icons specifically for Shopify collections.
"""

import os
import logging
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from services.supabase_auth import supabase_jwt_required, get_current_user_id
from datetime import datetime
from typing import List, Dict, Any

from database import db_session_scope
from models import Icon, Category, Collection
from icon_generation_service import IconGenerationService, BatchGenerationRequest
from services.enhanced_shopify_icon_sync import EnhancedShopifyIconSync
from shopify_collections import ShopifyCollectionsManager

# Create blueprint
collections_icon_bp = Blueprint('collections_icon', __name__, url_prefix='/api/collections/icons')

# Configure logging
logger = logging.getLogger(__name__)


@collections_icon_bp.route('/generate-missing', methods=['POST'])
@supabase_jwt_required
def generate_missing_icons():
    """Generate icons for all collections that don't have them."""
    try:
        # Get Shopify credentials
        shop_url = os.getenv('SHOPIFY_SHOP_URL')
        access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
        
        if not shop_url or not access_token:
            return jsonify({'error': 'Shopify credentials not configured'}), 500
        
        # Initialize Shopify manager
        shopify_manager = ShopifyCollectionsManager(shop_url, access_token)
        
        # Get all collections
        collections = shopify_manager.get_all_collections()
        
        # Filter collections without icons
        collections_without_icons = [
            col for col in collections 
            if not col.get('image') or not col['image'].get('url')
        ]
        
        if not collections_without_icons:
            return jsonify({
                'message': 'All collections already have icons',
                'total_collections': len(collections),
                'with_icons': len(collections),
                'without_icons': 0
            })
        
        # Get generation options from request
        data = request.get_json() or {}
        style = data.get('style', 'modern')
        color = data.get('color', '#3B82F6')
        batch_size = data.get('batch_size', 10)
        
        # Create batch generation request
        categories = []
        for col in collections_without_icons[:batch_size]:  # Limit batch size
            categories.append({
                'id': col['numeric_id'],
                'name': col['title'],
                'shopify_collection_id': col['id']
            })
        
        # Initialize icon generation service
        async def generate():
            async with IconGenerationService() as service:
                batch_request = BatchGenerationRequest(
                    categories=[cat['name'] for cat in categories],
                    style=style,
                    color_scheme=color,
                    user_id=get_current_user_id(),
                    metadata={'source': 'shopify_collections'}
                )
                
                batch_id = await service.generate_batch_icons(batch_request)
                return batch_id
        
        import asyncio
        batch_id = asyncio.run(generate())
        
        # Store collection mapping for later sync
        with db_session_scope() as session:
            for cat in categories:
                # Create or update collection record
                collection = session.query(Collection).filter_by(
                    shopify_collection_id=cat['shopify_collection_id']
                ).first()
                
                if not collection:
                    collection = Collection(
                        name=cat['name'],
                        handle=cat['name'].lower().replace(' ', '-'),
                        shopify_collection_id=cat['shopify_collection_id'],
                        created_by=get_current_user_id()
                    )
                    session.add(collection)
                
                collection.icon_generation_batch_id = batch_id
                collection.icon_generation_status = 'pending'
            
            session.commit()
        
        return jsonify({
            'success': True,
            'batch_id': batch_id,
            'message': f'Started generating icons for {len(categories)} collections',
            'collections_processed': len(categories),
            'total_without_icons': len(collections_without_icons)
        })
        
    except Exception as e:
        logger.error(f"Error generating missing icons: {str(e)}")
        return jsonify({'error': str(e)}), 500


@collections_icon_bp.route('/auto-sync', methods=['POST'])
@supabase_jwt_required
def auto_sync_generated_icons():
    """Automatically sync newly generated icons to their collections."""
    try:
        data = request.get_json() or {}
        batch_id = data.get('batch_id')
        
        if not batch_id:
            return jsonify({'error': 'batch_id is required'}), 400
        
        # Get collections associated with this batch
        with db_session_scope() as session:
            collections = session.query(Collection).filter_by(
                icon_generation_batch_id=batch_id,
                icon_generation_status='pending'
            ).all()
            
            if not collections:
                return jsonify({
                    'message': 'No collections found for this batch',
                    'batch_id': batch_id
                })
            
            # Initialize sync service
            sync_service = EnhancedShopifyIconSync(
                shop_url=os.getenv('SHOPIFY_SHOP_URL'),
                access_token=os.getenv('SHOPIFY_ACCESS_TOKEN')
            )
            
            synced = 0
            failed = 0
            results = []
            
            for collection in collections:
                # Find the generated icon
                icon = session.query(Icon).filter_by(
                    category_name=collection.name,
                    metadata_contains={'batch_id': batch_id}
                ).order_by(Icon.created_at.desc()).first()
                
                if not icon:
                    failed += 1
                    results.append({
                        'collection_id': collection.shopify_collection_id,
                        'status': 'failed',
                        'error': 'Icon not found'
                    })
                    continue
                
                # Sync the icon
                sync_result = sync_service.sync_icon_to_collection(
                    icon_path=icon.file_path,
                    collection_id=collection.shopify_collection_id,
                    alt_text=f"{collection.name} collection icon",
                    icon_id=icon.id
                )
                
                if sync_result.status.value == 'success':
                    synced += 1
                    collection.icon_generation_status = 'synced'
                    collection.shopify_icon_url = sync_result.shopify_image_url
                    collection.shopify_synced_at = datetime.utcnow()
                    
                    # Update icon record
                    icon.shopify_synced_at = datetime.utcnow()
                    icon.shopify_sync_status = 'synced'
                    icon.shopify_image_url = sync_result.shopify_image_url
                else:
                    failed += 1
                    collection.icon_generation_status = 'sync_failed'
                
                results.append({
                    'collection_id': collection.shopify_collection_id,
                    'collection_name': collection.name,
                    'status': sync_result.status.value,
                    'shopify_image_url': sync_result.shopify_image_url,
                    'error': sync_result.error
                })
            
            session.commit()
        
        return jsonify({
            'success': True,
            'batch_id': batch_id,
            'summary': {
                'total_collections': len(collections),
                'synced': synced,
                'failed': failed
            },
            'results': results
        })
        
    except Exception as e:
        logger.error(f"Error auto-syncing icons: {str(e)}")
        return jsonify({'error': str(e)}), 500


@collections_icon_bp.route('/sync-status', methods=['GET'])
@supabase_jwt_required
def get_collection_sync_status():
    """Get the sync status of collections and their icons."""
    try:
        with db_session_scope() as session:
            # Get collections with generation status
            collections = session.query(Collection).filter(
                Collection.icon_generation_batch_id.isnot(None)
            ).all()
            
            status_summary = {
                'pending': 0,
                'synced': 0,
                'sync_failed': 0,
                'total': len(collections)
            }
            
            collection_details = []
            for col in collections:
                status_summary[col.icon_generation_status] = status_summary.get(
                    col.icon_generation_status, 0
                ) + 1
                
                collection_details.append({
                    'id': col.id,
                    'name': col.name,
                    'shopify_collection_id': col.shopify_collection_id,
                    'batch_id': col.icon_generation_batch_id,
                    'status': col.icon_generation_status,
                    'shopify_icon_url': col.shopify_icon_url,
                    'synced_at': col.shopify_synced_at.isoformat() if col.shopify_synced_at else None
                })
            
            return jsonify({
                'summary': status_summary,
                'collections': collection_details
            })
            
    except Exception as e:
        logger.error(f"Error getting sync status: {str(e)}")
        return jsonify({'error': str(e)}), 500


@collections_icon_bp.route('/verify-coverage', methods=['GET'])
@supabase_jwt_required
def verify_icon_coverage():
    """Verify which Shopify collections have icons."""
    try:
        # Initialize Shopify manager
        shopify_manager = ShopifyCollectionsManager(
            shop_url=os.getenv('SHOPIFY_SHOP_URL'),
            access_token=os.getenv('SHOPIFY_ACCESS_TOKEN')
        )
        
        # Get all collections
        collections = shopify_manager.get_all_collections()
        
        with_icons = []
        without_icons = []
        
        for col in collections:
            if col.get('image') and col['image'].get('url'):
                with_icons.append({
                    'id': col['id'],
                    'title': col['title'],
                    'handle': col['handle'],
                    'image_url': col['image']['url']
                })
            else:
                without_icons.append({
                    'id': col['id'],
                    'title': col['title'],
                    'handle': col['handle']
                })
        
        coverage_percentage = (len(with_icons) / len(collections) * 100) if collections else 0
        
        return jsonify({
            'summary': {
                'total_collections': len(collections),
                'with_icons': len(with_icons),
                'without_icons': len(without_icons),
                'coverage_percentage': round(coverage_percentage, 2)
            },
            'collections_with_icons': with_icons,
            'collections_without_icons': without_icons
        })
        
    except Exception as e:
        logger.error(f"Error verifying icon coverage: {str(e)}")
        return jsonify({'error': str(e)}), 500


@collections_icon_bp.route('/retry-failed', methods=['POST'])
@supabase_jwt_required
def retry_failed_syncs():
    """Retry failed icon sync operations."""
    try:
        with db_session_scope() as session:
            # Get failed collections
            failed_collections = session.query(Collection).filter_by(
                icon_generation_status='sync_failed'
            ).all()
            
            if not failed_collections:
                return jsonify({
                    'message': 'No failed syncs to retry',
                    'total_failed': 0
                })
            
            # Initialize sync service
            sync_service = EnhancedShopifyIconSync(
                shop_url=os.getenv('SHOPIFY_SHOP_URL'),
                access_token=os.getenv('SHOPIFY_ACCESS_TOKEN')
            )
            
            retried = 0
            success = 0
            still_failed = 0
            results = []
            
            for collection in failed_collections:
                # Find the icon
                icon = session.query(Icon).filter_by(
                    category_name=collection.name
                ).order_by(Icon.created_at.desc()).first()
                
                if not icon:
                    still_failed += 1
                    continue
                
                retried += 1
                
                # Retry sync
                sync_result = sync_service.sync_icon_to_collection(
                    icon_path=icon.file_path,
                    collection_id=collection.shopify_collection_id,
                    alt_text=f"{collection.name} collection icon",
                    icon_id=icon.id
                )
                
                if sync_result.status.value == 'success':
                    success += 1
                    collection.icon_generation_status = 'synced'
                    collection.shopify_icon_url = sync_result.shopify_image_url
                    collection.shopify_synced_at = datetime.utcnow()
                else:
                    still_failed += 1
                
                results.append({
                    'collection_id': collection.shopify_collection_id,
                    'collection_name': collection.name,
                    'status': sync_result.status.value,
                    'error': sync_result.error
                })
            
            session.commit()
        
        return jsonify({
            'success': True,
            'summary': {
                'total_failed': len(failed_collections),
                'retried': retried,
                'success': success,
                'still_failed': still_failed
            },
            'results': results
        })
        
    except Exception as e:
        logger.error(f"Error retrying failed syncs: {str(e)}")
        return jsonify({'error': str(e)}), 500