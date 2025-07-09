"""
Bulk Icon Sync to Shopify API.
"""

import os
import logging
import asyncio
import json
import base64
from typing import Dict, Any, List, Optional
from datetime import datetime
from flask import Blueprint, jsonify, request, g
import requests
from concurrent.futures import ThreadPoolExecutor
import traceback

from models import db
from icon_batch_models import IconGeneration
from services.supabase_auth import supabase_jwt_required
from shopify_service import shopify_service

logger = logging.getLogger(__name__)

icon_sync_bp = Blueprint('icon_sync_api', __name__)

# Thread pool for parallel uploads
executor = ThreadPoolExecutor(max_workers=3)

class IconSyncService:
    """Service for syncing icons to Shopify."""
    
    def __init__(self):
        self.shop_url = os.getenv('SHOPIFY_SHOP_URL')
        self.access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
        self.api_version = '2024-01'
        
    def _get_headers(self):
        """Get Shopify API headers."""
        return {
            'X-Shopify-Access-Token': self.access_token,
            'Content-Type': 'application/json'
        }
    
    def _upload_image_to_shopify(self, file_path: str, alt_text: str = "") -> Optional[Dict]:
        """Upload an image file to Shopify Files API."""
        try:
            # Read image file
            with open(file_path, 'rb') as f:
                image_data = f.read()
            
            # Encode to base64
            base64_data = base64.b64encode(image_data).decode('utf-8')
            filename = os.path.basename(file_path)
            
            # Create file in Shopify
            url = f"https://{self.shop_url}/admin/api/{self.api_version}/graphql.json"
            
            mutation = """
            mutation fileCreate($files: [FileCreateInput!]!) {
                fileCreate(files: $files) {
                    files {
                        id
                        alt
                        createdAt
                        fileStatus
                        ... on MediaImage {
                            image {
                                url
                                width
                                height
                            }
                        }
                    }
                    userErrors {
                        field
                        message
                    }
                }
            }
            """
            
            variables = {
                "files": [{
                    "alt": alt_text,
                    "contentType": "IMAGE",
                    "originalSource": f"data:image/png;base64,{base64_data}"
                }]
            }
            
            response = requests.post(
                url,
                json={'query': mutation, 'variables': variables},
                headers=self._get_headers()
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('data', {}).get('fileCreate', {}).get('files'):
                    file_data = data['data']['fileCreate']['files'][0]
                    return {
                        'id': file_data['id'],
                        'url': file_data.get('image', {}).get('url'),
                        'alt': file_data.get('alt')
                    }
                else:
                    errors = data.get('data', {}).get('fileCreate', {}).get('userErrors', [])
                    logger.error(f"Shopify file creation errors: {errors}")
            else:
                logger.error(f"Shopify API error: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"Error uploading image to Shopify: {e}")
            logger.error(traceback.format_exc())
        
        return None
    
    def sync_icon_to_collection(self, icon_id: str, collection_id: str) -> Dict[str, Any]:
        """Sync a single icon to a Shopify collection."""
        try:
            # Get icon record
            icon = IconGeneration.query.get(icon_id)
            if not icon:
                return {'success': False, 'error': 'Icon not found'}
            
            if not icon.file_path or not os.path.exists(icon.file_path):
                return {'success': False, 'error': 'Icon file not found'}
            
            # Check if already synced
            if icon.is_synced_to_shopify and icon.shopify_collection_id == collection_id:
                return {
                    'success': True, 
                    'message': 'Icon already synced to this collection',
                    'shopify_image_id': icon.shopify_image_id
                }
            
            # Upload to Shopify
            alt_text = f"{icon.category_name} icon"
            file_result = self._upload_image_to_shopify(icon.file_path, alt_text)
            
            if not file_result:
                return {'success': False, 'error': 'Failed to upload image to Shopify'}
            
            # Update collection image
            collection_update_result = self._update_collection_image(
                collection_id, 
                file_result['id']
            )
            
            if collection_update_result['success']:
                # Update icon record
                icon.is_synced_to_shopify = True
                icon.shopify_image_id = file_result['id']
                icon.shopify_collection_id = collection_id
                db.session.commit()
                
                return {
                    'success': True,
                    'shopify_image_id': file_result['id'],
                    'image_url': file_result['url']
                }
            else:
                return {
                    'success': False,
                    'error': collection_update_result.get('error', 'Failed to update collection')
                }
                
        except Exception as e:
            logger.error(f"Error syncing icon: {e}")
            return {'success': False, 'error': str(e)}
    
    def _update_collection_image(self, collection_id: str, image_id: str) -> Dict[str, Any]:
        """Update a collection's image."""
        try:
            url = f"https://{self.shop_url}/admin/api/{self.api_version}/graphql.json"
            
            mutation = """
            mutation collectionUpdate($input: CollectionInput!) {
                collectionUpdate(input: $input) {
                    collection {
                        id
                        title
                        image {
                            url
                            altText
                        }
                    }
                    userErrors {
                        field
                        message
                    }
                }
            }
            """
            
            # Convert REST ID to GraphQL ID
            gid = f"gid://shopify/Collection/{collection_id}"
            image_gid = image_id if image_id.startswith('gid://') else f"gid://shopify/MediaImage/{image_id}"
            
            variables = {
                "input": {
                    "id": gid,
                    "image": {
                        "id": image_gid
                    }
                }
            }
            
            response = requests.post(
                url,
                json={'query': mutation, 'variables': variables},
                headers=self._get_headers()
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('data', {}).get('collectionUpdate', {}).get('collection'):
                    return {'success': True}
                else:
                    errors = data.get('data', {}).get('collectionUpdate', {}).get('userErrors', [])
                    return {'success': False, 'error': str(errors)}
            else:
                return {'success': False, 'error': f"API error: {response.status_code}"}
                
        except Exception as e:
            logger.error(f"Error updating collection image: {e}")
            return {'success': False, 'error': str(e)}
    
    def bulk_sync_icons(self, sync_requests: List[Dict]) -> Dict[str, Any]:
        """Bulk sync multiple icons to collections."""
        results = {
            'total': len(sync_requests),
            'successful': 0,
            'failed': 0,
            'results': []
        }
        
        for request in sync_requests:
            icon_id = request.get('icon_id')
            collection_id = request.get('collection_id')
            
            if not icon_id or not collection_id:
                result = {
                    'icon_id': icon_id,
                    'collection_id': collection_id,
                    'success': False,
                    'error': 'Missing icon_id or collection_id'
                }
            else:
                result = self.sync_icon_to_collection(icon_id, collection_id)
                result['icon_id'] = icon_id
                result['collection_id'] = collection_id
            
            results['results'].append(result)
            
            if result.get('success'):
                results['successful'] += 1
            else:
                results['failed'] += 1
        
        return results

# Create service instance
icon_sync_service = IconSyncService()

@icon_sync_bp.route('/sync/icon', methods=['POST'])
@supabase_jwt_required
def sync_single_icon():
    """Sync a single icon to a Shopify collection."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"message": "Request data required"}), 400
        
        icon_id = data.get('icon_id')
        collection_id = data.get('collection_id')
        
        if not icon_id or not collection_id:
            return jsonify({"message": "icon_id and collection_id are required"}), 400
        
        # Verify icon ownership
        icon = IconGeneration.query.filter_by(
            id=icon_id,
            user_id=g.user['id']
        ).first()
        
        if not icon:
            return jsonify({"message": "Icon not found"}), 404
        
        # Sync to Shopify
        result = icon_sync_service.sync_icon_to_collection(icon_id, collection_id)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify({"message": result.get('error', 'Sync failed')}), 500
            
    except Exception as e:
        logger.error(f"Icon sync error: {e}")
        return jsonify({"message": str(e)}), 500

@icon_sync_bp.route('/sync/bulk', methods=['POST'])
@supabase_jwt_required
def bulk_sync_icons():
    """Bulk sync multiple icons to collections."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"message": "Request data required"}), 400
        
        sync_requests = data.get('sync_requests', [])
        if not sync_requests:
            return jsonify({"message": "sync_requests array is required"}), 400
        
        # Verify icon ownership for all requests
        icon_ids = [req.get('icon_id') for req in sync_requests if req.get('icon_id')]
        
        if icon_ids:
            owned_icons = IconGeneration.query.filter(
                IconGeneration.id.in_(icon_ids),
                IconGeneration.user_id == g.user['id']
            ).all()
            
            owned_icon_ids = {icon.id for icon in owned_icons}
            
            # Filter out non-owned icons
            valid_requests = [
                req for req in sync_requests 
                if req.get('icon_id') in owned_icon_ids
            ]
            
            if len(valid_requests) < len(sync_requests):
                logger.warning(f"Filtered out {len(sync_requests) - len(valid_requests)} non-owned icons")
        else:
            valid_requests = []
        
        # Process bulk sync
        results = icon_sync_service.bulk_sync_icons(valid_requests)
        
        return jsonify(results)
        
    except Exception as e:
        logger.error(f"Bulk sync error: {e}")
        return jsonify({"message": str(e)}), 500

@icon_sync_bp.route('/sync/auto-match', methods=['POST'])
@supabase_jwt_required
def auto_match_and_sync():
    """Automatically match icons to collections and sync."""
    try:
        data = request.get_json()
        
        # Get unsynced icons
        unsynced_icons = IconGeneration.query.filter_by(
            user_id=g.user['id'],
            is_synced_to_shopify=False
        ).all()
        
        if not unsynced_icons:
            return jsonify({
                "message": "No unsynced icons found",
                "matched": 0
            })
        
        # Get Shopify collections
        collections = shopify_service.get_all_collections()
        
        # Build mapping of collection names to IDs
        collection_map = {
            coll.get('title', '').lower(): coll.get('id')
            for coll in collections
        }
        
        # Also map by handle
        for coll in collections:
            if coll.get('handle'):
                collection_map[coll['handle'].lower()] = coll['id']
        
        # Match icons to collections
        sync_requests = []
        matched = 0
        
        for icon in unsynced_icons:
            # Try to match by category name
            category_lower = icon.category_name.lower()
            collection_id = None
            
            # Direct match
            if category_lower in collection_map:
                collection_id = collection_map[category_lower]
            else:
                # Fuzzy match - look for partial matches
                for coll_name, coll_id in collection_map.items():
                    if category_lower in coll_name or coll_name in category_lower:
                        collection_id = coll_id
                        break
            
            if collection_id:
                sync_requests.append({
                    'icon_id': icon.id,
                    'collection_id': collection_id
                })
                matched += 1
        
        # Process sync if matches found
        if sync_requests:
            if data.get('dry_run'):
                # Just return what would be synced
                return jsonify({
                    'matched': matched,
                    'total_icons': len(unsynced_icons),
                    'matches': sync_requests[:10]  # Preview first 10
                })
            else:
                # Actually sync
                results = icon_sync_service.bulk_sync_icons(sync_requests)
                return jsonify(results)
        else:
            return jsonify({
                "message": "No matching collections found",
                "matched": 0,
                "total_icons": len(unsynced_icons)
            })
            
    except Exception as e:
        logger.error(f"Auto-match sync error: {e}")
        return jsonify({"message": str(e)}), 500

@icon_sync_bp.route('/icons/unsynced', methods=['GET'])
@supabase_jwt_required
def get_unsynced_icons():
    """Get list of unsynced icons."""
    try:
        # Get query params
        category_filter = request.args.get('category')
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))
        
        # Build query
        query = IconGeneration.query.filter_by(
            user_id=g.user['id'],
            is_synced_to_shopify=False
        )
        
        if category_filter:
            query = query.filter(
                IconGeneration.category_name.ilike(f'%{category_filter}%')
            )
        
        # Get total count
        total = query.count()
        
        # Get icons
        icons = query.order_by(
            IconGeneration.created_at.desc()
        ).limit(limit).offset(offset).all()
        
        icons_data = []
        for icon in icons:
            icons_data.append({
                'id': icon.id,
                'category_id': icon.category_id,
                'category_name': icon.category_name,
                'thumbnail_url': icon.thumbnail_url,
                'style': icon.style,
                'size': icon.size,
                'created_at': icon.created_at.isoformat()
            })
        
        return jsonify({
            'icons': icons_data,
            'total': total,
            'limit': limit,
            'offset': offset
        })
        
    except Exception as e:
        logger.error(f"Error getting unsynced icons: {e}")
        return jsonify({"message": str(e)}), 500