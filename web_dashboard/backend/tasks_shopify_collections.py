"""
Shopify Collection Icon Generation Tasks

Background tasks for generating and uploading icons to Shopify collections.
"""

import os
import logging
from typing import Dict, List, Any
from datetime import datetime

from shopify_collections import ShopifyCollectionsManager
from icon_generator import IconGenerator
from icon_storage import IconStorage

logger = logging.getLogger(__name__)

def generate_shopify_collection_icons_task(
    categories: List[Dict[str, Any]],
    options: Dict[str, Any],
    shop_url: str,
    access_token: str,
    job_id: str,
    socketio=None
) -> Dict[str, Any]:
    """
    Generate icons for Shopify collections and upload them.
    
    Args:
        categories: List of collections to generate icons for
        options: Generation options (style, color, etc.)
        shop_url: Shopify store URL
        access_token: Shopify access token
        job_id: Job ID for progress tracking
        socketio: SocketIO instance for real-time updates
    
    Returns:
        Dictionary with results
    """
    try:
        # Initialize services
        shopify_manager = ShopifyCollectionsManager(shop_url, access_token)
        icon_generator = IconGenerator()
        icon_storage = IconStorage()
        
        results = {
            'success': [],
            'failed': [],
            'total': len(categories)
        }
        
        # Emit starting status
        if socketio:
            socketio.emit('job_update', {
                'job_id': job_id,
                'status': 'running',
                'message': f'Starting icon generation for {len(categories)} collections',
                'progress': 0
            })
        
        for idx, category in enumerate(categories):
            collection_id = category['id']
            collection_name = category['name']
            graphql_id = category.get('graphql_id')
            
            try:
                # Update progress
                progress = int((idx / len(categories)) * 100)
                if socketio:
                    socketio.emit('job_update', {
                        'job_id': job_id,
                        'status': 'running',
                        'message': f'Generating icon for {collection_name}',
                        'progress': progress,
                        'current_item': collection_name
                    })
                
                # Generate icon
                logger.info(f"Generating icon for collection: {collection_name}")
                icon_result = icon_generator.generate_category_icon(
                    category_id=collection_id,
                    category_name=collection_name,
                    style=options.get('style', 'modern'),
                    color=options.get('color', '#3B82F6')
                )
                
                if not icon_result['success']:
                    logger.error(f"Failed to generate icon for {collection_name}: {icon_result.get('error')}")
                    results['failed'].append({
                        'collection_id': collection_id,
                        'collection_name': collection_name,
                        'error': icon_result.get('error', 'Generation failed')
                    })
                    continue
                
                # Save icon locally
                icon_path = icon_result['file_path']
                icon_record = icon_storage.save_icon(
                    category_id=collection_id,
                    category_name=collection_name,
                    file_path=icon_path,
                    metadata={
                        'style': options.get('style', 'modern'),
                        'color': options.get('color', '#3B82F6'),
                        'generated_at': datetime.now().isoformat(),
                        'shopify_collection': True
                    }
                )
                
                # Upload to Shopify
                logger.info(f"Uploading icon to Shopify for collection: {collection_name}")
                upload_result = shopify_manager.upload_collection_icon(
                    collection_id=graphql_id,
                    image_path=icon_path,
                    alt_text=f"{collection_name} collection icon"
                )
                
                if upload_result['success']:
                    # Update metadata
                    metadata_result = shopify_manager.update_collection_metadata(
                        collection_id=graphql_id,
                        metadata={
                            'icon_style': options.get('style', 'modern'),
                            'icon_color': options.get('color', '#3B82F6'),
                            'generated_at': datetime.now().isoformat()
                        }
                    )
                    
                    # Update local storage with sync status
                    icon_storage.update_sync_status(
                        icon_id=icon_record['id'],
                        synced=True,
                        shopify_collection_id=collection_id,
                        shopify_image_url=upload_result.get('image_url')
                    )
                    
                    results['success'].append({
                        'collection_id': collection_id,
                        'collection_name': collection_name,
                        'icon_url': upload_result.get('image_url'),
                        'local_icon_id': icon_record['id']
                    })
                    
                    logger.info(f"Successfully uploaded icon for {collection_name}")
                else:
                    logger.error(f"Failed to upload icon for {collection_name}: {upload_result.get('error')}")
                    results['failed'].append({
                        'collection_id': collection_id,
                        'collection_name': collection_name,
                        'error': upload_result.get('error', 'Upload failed')
                    })
                    
            except Exception as e:
                logger.error(f"Error processing collection {collection_name}: {str(e)}")
                results['failed'].append({
                    'collection_id': collection_id,
                    'collection_name': collection_name,
                    'error': str(e)
                })
        
        # Final status update
        success_count = len(results['success'])
        failed_count = len(results['failed'])
        
        if socketio:
            socketio.emit('job_update', {
                'job_id': job_id,
                'status': 'completed',
                'message': f'Completed: {success_count} successful, {failed_count} failed',
                'progress': 100,
                'results': results
            })
        
        logger.info(f"Icon generation task completed: {success_count} successful, {failed_count} failed")
        
        return {
            'status': 'completed',
            'results': results,
            'summary': {
                'total': results['total'],
                'successful': success_count,
                'failed': failed_count
            }
        }
        
    except Exception as e:
        logger.error(f"Error in Shopify collection icon generation task: {str(e)}")
        
        if socketio:
            socketio.emit('job_update', {
                'job_id': job_id,
                'status': 'failed',
                'message': f'Task failed: {str(e)}',
                'error': str(e)
            })
        
        return {
            'status': 'failed',
            'error': str(e)
        }