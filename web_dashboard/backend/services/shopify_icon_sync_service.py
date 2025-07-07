"""
Shopify Icon Sync Service

Handles synchronization of generated icons to Shopify collections as images.
This service integrates with the Shopify Admin API to upload and manage
collection images for product categories.
"""

import os
import logging
import requests
import json
from typing import Dict, List, Optional, Any
from datetime import datetime

from repositories.icon_repository import IconRepository
from repositories.category_repository import CategoryRepository
from models import Icon, Category, SyncStatus

logger = logging.getLogger(__name__)


class ShopifyIconSyncService:
    """Service for syncing icons to Shopify collections."""
    
    def __init__(self, db_session=None):
        """Initialize the service with database session."""
        self.db_session = db_session
        self.icon_repo = IconRepository(db_session)
        self.category_repo = CategoryRepository(db_session)
        
        # Get Shopify credentials from environment
        self.shop_url = os.getenv('SHOPIFY_SHOP_URL')
        self.access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
        
        if not self.shop_url or not self.access_token:
            logger.warning("Shopify credentials not found in environment variables")
    
    def _make_shopify_request(self, endpoint: str, method: str = 'GET', data: dict = None) -> Dict[str, Any]:
        """
        Make a request to the Shopify Admin API.
        
        Args:
            endpoint: API endpoint (without domain)
            method: HTTP method
            data: Request data for POST/PUT requests
            
        Returns:
            Response data or error information
        """
        if not self.shop_url or not self.access_token:
            return {
                'success': False,
                'error': 'Shopify credentials not configured',
                'error_code': 'MISSING_CREDENTIALS'
            }
        
        # Ensure shop URL format is correct
        if not self.shop_url.startswith('https://'):
            shop_url = f"https://{self.shop_url}"
        else:
            shop_url = self.shop_url
            
        if not shop_url.endswith('.myshopify.com'):
            if not shop_url.endswith('/'):
                shop_url += '.myshopify.com'
            else:
                shop_url = shop_url.rstrip('/') + '.myshopify.com'
        
        url = f"{shop_url}/admin/api/2023-10/{endpoint}"
        
        headers = {
            'X-Shopify-Access-Token': self.access_token,
            'Content-Type': 'application/json'
        }
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=30)
            elif method == 'POST':
                response = requests.post(url, headers=headers, json=data, timeout=30)
            elif method == 'PUT':
                response = requests.put(url, headers=headers, json=data, timeout=30)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=30)
            else:
                return {
                    'success': False,
                    'error': f'Unsupported HTTP method: {method}',
                    'error_code': 'INVALID_METHOD'
                }
            
            if response.status_code == 200 or response.status_code == 201:
                return {
                    'success': True,
                    'data': response.json(),
                    'status_code': response.status_code
                }
            elif response.status_code == 404:
                return {
                    'success': False,
                    'error': 'Resource not found',
                    'error_code': 'NOT_FOUND',
                    'status_code': response.status_code
                }
            elif response.status_code == 429:
                return {
                    'success': False,
                    'error': 'Rate limit exceeded',
                    'error_code': 'RATE_LIMITED',
                    'status_code': response.status_code
                }
            else:
                error_data = {}
                try:
                    error_data = response.json()
                except:
                    pass
                    
                return {
                    'success': False,
                    'error': f'API request failed: {response.status_code}',
                    'error_code': 'API_ERROR',
                    'status_code': response.status_code,
                    'error_details': error_data
                }
                
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'error': 'Request timeout',
                'error_code': 'TIMEOUT'
            }
        except requests.exceptions.ConnectionError:
            return {
                'success': False,
                'error': 'Connection error',
                'error_code': 'CONNECTION_ERROR'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Unexpected error: {str(e)}',
                'error_code': 'UNEXPECTED_ERROR'
            }
    
    def get_collection_by_id(self, collection_id: str) -> Dict[str, Any]:
        """Get Shopify collection details."""
        result = self._make_shopify_request(f"collections/{collection_id}.json")
        if result['success']:
            return {
                'success': True,
                'collection': result['data']['collection']
            }
        return result
    
    def upload_icon_to_collection(self, icon_id: int, collection_id: str = None) -> Dict[str, Any]:
        """
        Upload an icon as a collection image to Shopify.
        
        Args:
            icon_id: ID of the icon to upload
            collection_id: Shopify collection ID (optional, will use category's collection ID if not provided)
            
        Returns:
            Result dictionary with upload status
        """
        try:
            # Get icon details
            icon = self.icon_repo.get_icon_by_id(icon_id)
            if not icon:
                return {
                    'success': False,
                    'error': 'Icon not found',
                    'error_code': 'ICON_NOT_FOUND'
                }
            
            # Check if icon file exists
            if not icon.file_path or not os.path.exists(icon.file_path):
                return {
                    'success': False,
                    'error': 'Icon file not found',
                    'error_code': 'FILE_NOT_FOUND'
                }
            
            # Get category details
            category = self.category_repo.get(icon.category_id)
            if not category:
                return {
                    'success': False,
                    'error': 'Category not found for icon',
                    'error_code': 'CATEGORY_NOT_FOUND'
                }
            
            # Use category's Shopify collection ID if not provided
            if not collection_id:
                collection_id = category.shopify_collection_id
                if not collection_id:
                    return {
                        'success': False,
                        'error': 'No Shopify collection ID found for category',
                        'error_code': 'NO_SHOPIFY_COLLECTION'
                    }
            
            # Read icon file
            try:
                with open(icon.file_path, 'rb') as f:
                    icon_data = f.read()
            except Exception as e:
                return {
                    'success': False,
                    'error': f'Failed to read icon file: {str(e)}',
                    'error_code': 'FILE_READ_ERROR'
                }
            
            # Convert to base64 for Shopify API
            import base64
            icon_base64 = base64.b64encode(icon_data).decode('utf-8')
            
            # Prepare image data for Shopify
            image_data = {
                "image": {
                    "attachment": icon_base64,
                    "filename": icon.filename,
                    "alt": f"Icon for {category.name}"
                }
            }
            
            # Upload to Shopify collection
            result = self._make_shopify_request(
                f"collections/{collection_id}/images.json",
                method='POST',
                data=image_data
            )
            
            if result['success']:
                # Extract image details from response
                image_info = result['data']['image']
                shopify_image_id = str(image_info['id'])
                shopify_image_url = image_info['src']
                
                # Update icon with Shopify sync information
                self.icon_repo.update_sync_status(
                    icon_id=icon_id,
                    synced=True,
                    shopify_collection_id=collection_id,
                    shopify_image_url=shopify_image_url
                )
                
                # Update icon metadata
                meta_data = icon.meta_data or {}
                meta_data.update({
                    'shopify_image_id': shopify_image_id,
                    'shopify_collection_id': collection_id,
                    'last_sync': datetime.utcnow().isoformat()
                })
                
                self.icon_repo.update_icon(icon_id, {
                    'shopify_image_id': shopify_image_id,
                    'meta_data': meta_data
                })
                
                logger.info(f"Icon {icon_id} successfully uploaded to Shopify collection {collection_id}")
                
                return {
                    'success': True,
                    'message': 'Icon uploaded to Shopify successfully',
                    'icon_id': icon_id,
                    'shopify_collection_id': collection_id,
                    'shopify_image_id': shopify_image_id,
                    'shopify_image_url': shopify_image_url
                }
            else:
                # Update icon sync status to failed
                self.icon_repo.update_sync_status(
                    icon_id=icon_id,
                    synced=False
                )
                
                return {
                    'success': False,
                    'error': f"Failed to upload to Shopify: {result.get('error')}",
                    'error_code': 'SHOPIFY_UPLOAD_FAILED',
                    'shopify_error': result
                }
                
        except Exception as e:
            logger.error(f"Error uploading icon {icon_id} to Shopify: {str(e)}")
            return {
                'success': False,
                'error': f'Internal error: {str(e)}',
                'error_code': 'INTERNAL_ERROR'
            }
    
    def sync_category_icons_to_shopify(self, category_id: int) -> Dict[str, Any]:
        """
        Sync all active icons for a category to Shopify.
        
        Args:
            category_id: ID of the category to sync icons for
            
        Returns:
            Result dictionary with sync status
        """
        try:
            # Get category details
            category = self.category_repo.get(category_id)
            if not category:
                return {
                    'success': False,
                    'error': 'Category not found',
                    'error_code': 'CATEGORY_NOT_FOUND'
                }
            
            if not category.shopify_collection_id:
                return {
                    'success': False,
                    'error': 'Category is not linked to a Shopify collection',
                    'error_code': 'NO_SHOPIFY_COLLECTION'
                }
            
            # Get active icons for category
            icons = self.icon_repo.get_icons_by_category(category_id, active_only=True)
            if not icons:
                return {
                    'success': True,
                    'message': 'No active icons found for category',
                    'category_id': category_id,
                    'synced_count': 0
                }
            
            results = []
            successful_syncs = 0
            failed_syncs = 0
            
            for icon in icons:
                sync_result = self.upload_icon_to_collection(icon.id, category.shopify_collection_id)
                results.append({
                    'icon_id': icon.id,
                    'filename': icon.filename,
                    'success': sync_result['success'],
                    'error': sync_result.get('error')
                })
                
                if sync_result['success']:
                    successful_syncs += 1
                else:
                    failed_syncs += 1
            
            return {
                'success': True,
                'message': f'Category icon sync completed',
                'category_id': category_id,
                'category_name': category.name,
                'shopify_collection_id': category.shopify_collection_id,
                'total_icons': len(icons),
                'successful_syncs': successful_syncs,
                'failed_syncs': failed_syncs,
                'results': results
            }
            
        except Exception as e:
            logger.error(f"Error syncing category {category_id} icons to Shopify: {str(e)}")
            return {
                'success': False,
                'error': f'Internal error: {str(e)}',
                'error_code': 'INTERNAL_ERROR'
            }
    
    def remove_icon_from_shopify(self, icon_id: int) -> Dict[str, Any]:
        """
        Remove an icon from Shopify collection.
        
        Args:
            icon_id: ID of the icon to remove from Shopify
            
        Returns:
            Result dictionary with removal status
        """
        try:
            # Get icon details
            icon = self.icon_repo.get_icon_by_id(icon_id)
            if not icon:
                return {
                    'success': False,
                    'error': 'Icon not found',
                    'error_code': 'ICON_NOT_FOUND'
                }
            
            # Check if icon has Shopify data
            if not icon.shopify_image_id or not icon.meta_data or 'shopify_collection_id' not in icon.meta_data:
                return {
                    'success': True,
                    'message': 'Icon is not synced to Shopify',
                    'icon_id': icon_id
                }
            
            collection_id = icon.meta_data['shopify_collection_id']
            image_id = icon.shopify_image_id
            
            # Remove from Shopify
            result = self._make_shopify_request(
                f"collections/{collection_id}/images/{image_id}.json",
                method='DELETE'
            )
            
            if result['success'] or result.get('status_code') == 404:
                # Update icon to remove Shopify sync data
                self.icon_repo.update_icon(icon_id, {
                    'shopify_image_id': None,
                    'shopify_image_url': None,
                    'shopify_synced_at': None,
                    'shopify_sync_status': SyncStatus.NOT_SYNCED.value
                })
                
                # Update metadata
                meta_data = icon.meta_data or {}
                meta_data.pop('shopify_image_id', None)
                meta_data.pop('shopify_collection_id', None)
                meta_data['last_unsynced'] = datetime.utcnow().isoformat()
                
                self.icon_repo.update_icon(icon_id, {'meta_data': meta_data})
                
                logger.info(f"Icon {icon_id} removed from Shopify collection {collection_id}")
                
                return {
                    'success': True,
                    'message': 'Icon removed from Shopify successfully',
                    'icon_id': icon_id
                }
            else:
                return {
                    'success': False,
                    'error': f"Failed to remove from Shopify: {result.get('error')}",
                    'error_code': 'SHOPIFY_REMOVAL_FAILED',
                    'shopify_error': result
                }
                
        except Exception as e:
            logger.error(f"Error removing icon {icon_id} from Shopify: {str(e)}")
            return {
                'success': False,
                'error': f'Internal error: {str(e)}',
                'error_code': 'INTERNAL_ERROR'
            }
    
    def get_sync_status_summary(self) -> Dict[str, Any]:
        """
        Get summary of icon sync status across all categories.
        
        Returns:
            Summary of sync status
        """
        try:
            # Get all categories with Shopify collections
            categories = self.category_repo.get_all()
            shopify_categories = [cat for cat in categories if cat.shopify_collection_id]
            
            summary = {
                'total_categories': len(categories),
                'shopify_linked_categories': len(shopify_categories),
                'categories_with_icons': 0,
                'categories_with_synced_icons': 0,
                'total_icons': 0,
                'synced_icons': 0,
                'unsynced_icons': 0,
                'failed_syncs': 0
            }
            
            for category in shopify_categories:
                icons = self.icon_repo.get_icons_by_category(category.id, active_only=False)
                if icons:
                    summary['categories_with_icons'] += 1
                    summary['total_icons'] += len(icons)
                    
                    synced_count = len([icon for icon in icons if icon.shopify_synced_at])
                    failed_count = len([icon for icon in icons if icon.shopify_sync_status == SyncStatus.FAILED.value])
                    
                    if synced_count > 0:
                        summary['categories_with_synced_icons'] += 1
                    
                    summary['synced_icons'] += synced_count
                    summary['failed_syncs'] += failed_count
            
            summary['unsynced_icons'] = summary['total_icons'] - summary['synced_icons']
            
            return {
                'success': True,
                'summary': summary
            }
            
        except Exception as e:
            logger.error(f"Error getting sync status summary: {str(e)}")
            return {
                'success': False,
                'error': f'Internal error: {str(e)}',
                'error_code': 'INTERNAL_ERROR'
            }