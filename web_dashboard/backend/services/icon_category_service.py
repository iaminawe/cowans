"""
Icon Category Service

Manages the relationship between icons and categories, including
assignment, unassignment, and Shopify synchronization.
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from repositories.icon_repository import IconRepository
from repositories.category_repository import CategoryRepository
from models import Icon, Category, IconStatus, SyncStatus

logger = logging.getLogger(__name__)


class IconCategoryService:
    """Service for managing icon-category relationships."""
    
    def __init__(self, db_session=None):
        """Initialize the service with database session."""
        self.db_session = db_session
        self.icon_repo = IconRepository(db_session)
        self.category_repo = CategoryRepository(db_session)
    
    def assign_icon_to_category(self, icon_id: int, category_id: int) -> Dict[str, Any]:
        """
        Assign an existing icon to a category.
        
        Args:
            icon_id: ID of the icon to assign
            category_id: ID of the category to assign to
            
        Returns:
            Result dictionary with success status and details
        """
        try:
            # Check if icon exists
            icon = self.icon_repo.get_icon_by_id(icon_id)
            if not icon:
                return {
                    'success': False,
                    'error': 'Icon not found',
                    'error_code': 'ICON_NOT_FOUND'
                }
            
            # Check if category exists
            category = self.category_repo.get(category_id)
            if not category:
                return {
                    'success': False,
                    'error': 'Category not found',
                    'error_code': 'CATEGORY_NOT_FOUND'
                }
            
            # Check if icon is already assigned to this category
            if icon.category_id == category_id:
                return {
                    'success': True,
                    'message': 'Icon is already assigned to this category',
                    'icon_id': icon_id,
                    'category_id': category_id
                }
            
            # Deactivate other icons for this category (only one active icon per category)
            existing_icons = self.icon_repo.get_icons_by_category(category_id, active_only=True)
            for existing_icon in existing_icons:
                if existing_icon.id != icon_id:
                    self.icon_repo.update_icon(existing_icon.id, {
                        'is_active': False,
                        'status': IconStatus.INACTIVE.value
                    })
            
            # Update the icon's category assignment
            updated_icon = self.icon_repo.update_icon(icon_id, {
                'category_id': category_id,
                'is_active': True,
                'status': IconStatus.ACTIVE.value
            })
            
            if updated_icon:
                logger.info(f"Icon {icon_id} assigned to category {category_id}")
                return {
                    'success': True,
                    'message': 'Icon assigned to category successfully',
                    'icon': {
                        'id': updated_icon.id,
                        'category_id': updated_icon.category_id,
                        'filename': updated_icon.filename,
                        'status': updated_icon.status,
                        'is_active': updated_icon.is_active
                    }
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to update icon assignment',
                    'error_code': 'UPDATE_FAILED'
                }
                
        except Exception as e:
            logger.error(f"Error assigning icon {icon_id} to category {category_id}: {str(e)}")
            return {
                'success': False,
                'error': f'Internal error: {str(e)}',
                'error_code': 'INTERNAL_ERROR'
            }
    
    def unassign_icon_from_category(self, category_id: int) -> Dict[str, Any]:
        """
        Remove the active icon assignment from a category.
        
        Args:
            category_id: ID of the category to unassign icon from
            
        Returns:
            Result dictionary with success status and details
        """
        try:
            # Check if category exists
            category = self.category_repo.get(category_id)
            if not category:
                return {
                    'success': False,
                    'error': 'Category not found',
                    'error_code': 'CATEGORY_NOT_FOUND'
                }
            
            # Find active icon for this category
            active_icon = self.icon_repo.get_latest_icon_for_category(category_id)
            if not active_icon:
                return {
                    'success': True,
                    'message': 'No active icon found for this category',
                    'category_id': category_id
                }
            
            # Deactivate the icon (soft delete)
            updated_icon = self.icon_repo.update_icon(active_icon.id, {
                'is_active': False,
                'status': IconStatus.INACTIVE.value
            })
            
            if updated_icon:
                logger.info(f"Icon {active_icon.id} unassigned from category {category_id}")
                return {
                    'success': True,
                    'message': 'Icon unassigned from category successfully',
                    'unassigned_icon_id': active_icon.id,
                    'category_id': category_id
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to unassign icon',
                    'error_code': 'UPDATE_FAILED'
                }
                
        except Exception as e:
            logger.error(f"Error unassigning icon from category {category_id}: {str(e)}")
            return {
                'success': False,
                'error': f'Internal error: {str(e)}',
                'error_code': 'INTERNAL_ERROR'
            }
    
    def get_category_icon_history(self, category_id: int) -> Dict[str, Any]:
        """
        Get the history of icons for a category.
        
        Args:
            category_id: ID of the category
            
        Returns:
            Result dictionary with icon history
        """
        try:
            # Check if category exists
            category = self.category_repo.get(category_id)
            if not category:
                return {
                    'success': False,
                    'error': 'Category not found',
                    'error_code': 'CATEGORY_NOT_FOUND'
                }
            
            # Get all icons for this category
            all_icons = self.icon_repo.get_icons_by_category(category_id, active_only=False)
            
            icon_history = []
            for icon in all_icons:
                icon_history.append({
                    'id': icon.id,
                    'filename': icon.filename,
                    'file_path': icon.file_path,
                    'style': icon.style,
                    'color': icon.color,
                    'status': icon.status,
                    'is_active': icon.is_active,
                    'created_at': icon.created_at.isoformat(),
                    'shopify_synced_at': icon.shopify_synced_at.isoformat() if icon.shopify_synced_at else None,
                    'shopify_image_url': icon.shopify_image_url
                })
            
            return {
                'success': True,
                'category': {
                    'id': category.id,
                    'name': category.name,
                    'slug': category.slug
                },
                'icons': icon_history,
                'total_icons': len(icon_history),
                'active_icons': len([i for i in icon_history if i['is_active']])
            }
            
        except Exception as e:
            logger.error(f"Error getting icon history for category {category_id}: {str(e)}")
            return {
                'success': False,
                'error': f'Internal error: {str(e)}',
                'error_code': 'INTERNAL_ERROR'
            }
    
    def sync_icon_to_shopify(self, icon_id: int, collection_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Sync an icon to Shopify as a collection image.
        
        Args:
            icon_id: ID of the icon to sync
            collection_id: Optional Shopify collection ID to sync to
            
        Returns:
            Result dictionary with sync status
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
            
            # TODO: Implement actual Shopify API call here
            # For now, simulate successful sync
            sync_success = True
            shopify_image_url = f"https://cdn.shopify.com/collections/{collection_id}/icon.png"
            
            if sync_success:
                # Update icon with Shopify sync info
                self.icon_repo.update_sync_status(
                    icon_id=icon_id,
                    synced=True,
                    shopify_collection_id=collection_id,
                    shopify_image_url=shopify_image_url
                )
                
                logger.info(f"Icon {icon_id} synced to Shopify collection {collection_id}")
                return {
                    'success': True,
                    'message': 'Icon synced to Shopify successfully',
                    'icon_id': icon_id,
                    'shopify_collection_id': collection_id,
                    'shopify_image_url': shopify_image_url
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to sync icon to Shopify',
                    'error_code': 'SHOPIFY_SYNC_FAILED'
                }
                
        except Exception as e:
            logger.error(f"Error syncing icon {icon_id} to Shopify: {str(e)}")
            return {
                'success': False,
                'error': f'Internal error: {str(e)}',
                'error_code': 'INTERNAL_ERROR'
            }
    
    def get_categories_without_icons(self) -> List[Dict[str, Any]]:
        """
        Get list of categories that don't have active icons.
        
        Returns:
            List of categories without active icons
        """
        try:
            all_categories = self.category_repo.get_all()
            categories_without_icons = []
            
            for category in all_categories:
                active_icon = self.icon_repo.get_latest_icon_for_category(category.id)
                if not active_icon:
                    categories_without_icons.append({
                        'id': category.id,
                        'name': category.name,
                        'slug': category.slug,
                        'description': category.description,
                        'shopify_collection_id': category.shopify_collection_id
                    })
            
            return categories_without_icons
            
        except Exception as e:
            logger.error(f"Error getting categories without icons: {str(e)}")
            return []
    
    def bulk_assign_icons(self, assignments: List[Dict[str, int]]) -> Dict[str, Any]:
        """
        Assign multiple icons to categories in bulk.
        
        Args:
            assignments: List of {'icon_id': int, 'category_id': int} dictionaries
            
        Returns:
            Result dictionary with bulk assignment results
        """
        try:
            results = []
            successful = 0
            failed = 0
            
            for assignment in assignments:
                icon_id = assignment.get('icon_id')
                category_id = assignment.get('category_id')
                
                if not icon_id or not category_id:
                    results.append({
                        'icon_id': icon_id,
                        'category_id': category_id,
                        'success': False,
                        'error': 'Missing icon_id or category_id'
                    })
                    failed += 1
                    continue
                
                result = self.assign_icon_to_category(icon_id, category_id)
                results.append({
                    'icon_id': icon_id,
                    'category_id': category_id,
                    'success': result['success'],
                    'error': result.get('error')
                })
                
                if result['success']:
                    successful += 1
                else:
                    failed += 1
            
            return {
                'success': True,
                'total_assignments': len(assignments),
                'successful': successful,
                'failed': failed,
                'results': results
            }
            
        except Exception as e:
            logger.error(f"Error in bulk icon assignment: {str(e)}")
            return {
                'success': False,
                'error': f'Internal error: {str(e)}',
                'error_code': 'INTERNAL_ERROR'
            }