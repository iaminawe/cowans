"""
Icon Repository Module

Handles all database operations for icons.
"""

import os
import hashlib
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func
import logging

from models import Icon, Category, IconStatus, SyncStatus
from database import get_db

logger = logging.getLogger(__name__)


class IconRepository:
    """Repository for icon database operations."""
    
    def __init__(self, db_session: Session = None):
        """Initialize icon repository."""
        self.db = db_session
    
    def _get_db(self) -> Session:
        """Get database session."""
        if self.db:
            return self.db
        return next(get_db())
    
    def create_icon(self, icon_data: Dict[str, Any]) -> Icon:
        """Create a new icon record."""
        db = self._get_db()
        try:
            icon = Icon(
                category_id=icon_data['category_id'],
                filename=icon_data['filename'],
                file_path=icon_data['file_path'],
                file_size=icon_data.get('file_size'),
                file_hash=icon_data.get('file_hash'),
                width=icon_data.get('width'),
                height=icon_data.get('height'),
                format=icon_data.get('format', 'PNG'),
                prompt=icon_data.get('prompt'),
                style=icon_data.get('style', 'modern'),
                color=icon_data.get('color', '#3B82F6'),
                background=icon_data.get('background', 'transparent'),
                model=icon_data.get('model', 'gpt-image-1'),
                status=icon_data.get('status', IconStatus.ACTIVE.value),
                created_by=icon_data['created_by'],
                generation_time=icon_data.get('generation_time'),
                generation_cost=icon_data.get('generation_cost'),
                generation_batch_id=icon_data.get('generation_batch_id'),
                meta_data=icon_data.get('meta_data', {})
            )
            
            db.add(icon)
            db.commit()
            db.refresh(icon)
            
            logger.info(f"Created icon {icon.id} for category {icon.category_id}")
            return icon
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating icon: {str(e)}")
            raise
    
    def get_icon_by_id(self, icon_id: int) -> Optional[Icon]:
        """Get icon by ID."""
        db = self._get_db()
        return db.query(Icon).filter(Icon.id == icon_id).first()
    
    def get_icons_by_category(self, category_id: int, active_only: bool = True) -> List[Icon]:
        """Get all icons for a category."""
        db = self._get_db()
        query = db.query(Icon).filter(Icon.category_id == category_id)
        
        if active_only:
            query = query.filter(Icon.is_active == True)
        
        return query.order_by(desc(Icon.created_at)).all()
    
    def get_latest_icon_for_category(self, category_id: int) -> Optional[Icon]:
        """Get the most recent active icon for a category."""
        db = self._get_db()
        return db.query(Icon).filter(
            and_(
                Icon.category_id == category_id,
                Icon.is_active == True,
                Icon.status == IconStatus.ACTIVE.value
            )
        ).order_by(desc(Icon.created_at)).first()
    
    def find_existing_icon(self, category_id: int, file_hash: str) -> Optional[Icon]:
        """Find existing icon by category and file hash."""
        db = self._get_db()
        return db.query(Icon).filter(
            and_(
                Icon.category_id == category_id,
                Icon.file_hash == file_hash,
                Icon.is_active == True
            )
        ).first()
    
    def search_icons(
        self,
        query: str = "",
        status: Optional[str] = None,
        synced: Optional[bool] = None,
        model: Optional[str] = None,
        style: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[Icon], int]:
        """Search icons with filters."""
        db = self._get_db()
        
        # Build base query with join to category
        base_query = db.query(Icon).join(Category)
        
        # Apply filters
        if query:
            base_query = base_query.filter(
                or_(
                    Category.name.ilike(f"%{query}%"),
                    Icon.filename.ilike(f"%{query}%"),
                    Icon.prompt.ilike(f"%{query}%")
                )
            )
        
        if status:
            base_query = base_query.filter(Icon.status == status)
        
        if synced is not None:
            if synced:
                base_query = base_query.filter(Icon.shopify_synced_at.isnot(None))
            else:
                base_query = base_query.filter(Icon.shopify_synced_at.is_(None))
        
        if model:
            base_query = base_query.filter(Icon.model == model)
        
        if style:
            base_query = base_query.filter(Icon.style == style)
        
        # Get total count
        total = base_query.count()
        
        # Apply pagination and ordering
        icons = base_query.order_by(desc(Icon.created_at)).limit(limit).offset(offset).all()
        
        return icons, total
    
    def update_icon(self, icon_id: int, update_data: Dict[str, Any]) -> Optional[Icon]:
        """Update icon record."""
        db = self._get_db()
        try:
            icon = db.query(Icon).filter(Icon.id == icon_id).first()
            if not icon:
                return None
            
            # Update allowed fields
            allowed_fields = [
                'status', 'is_active', 'shopify_image_id', 'shopify_image_url',
                'shopify_synced_at', 'shopify_sync_status', 'meta_data'
            ]
            
            for field in allowed_fields:
                if field in update_data:
                    setattr(icon, field, update_data[field])
            
            db.commit()
            db.refresh(icon)
            
            logger.info(f"Updated icon {icon_id}")
            return icon
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating icon {icon_id}: {str(e)}")
            raise
    
    def update_sync_status(
        self,
        icon_id: int,
        synced: bool,
        shopify_collection_id: Optional[str] = None,
        shopify_image_url: Optional[str] = None
    ) -> Optional[Icon]:
        """Update sync status for an icon."""
        update_data = {
            'shopify_sync_status': SyncStatus.SUCCESS.value if synced else SyncStatus.FAILED.value
        }
        
        if synced:
            update_data['shopify_synced_at'] = datetime.utcnow()
        
        if shopify_collection_id:
            update_data['shopify_image_id'] = shopify_collection_id
        
        if shopify_image_url:
            update_data['shopify_image_url'] = shopify_image_url
        
        return self.update_icon(icon_id, update_data)
    
    def delete_icon(self, icon_id: int, hard_delete: bool = False) -> bool:
        """Delete an icon (soft delete by default)."""
        db = self._get_db()
        try:
            icon = db.query(Icon).filter(Icon.id == icon_id).first()
            if not icon:
                return False
            
            if hard_delete:
                # Delete physical file if it exists
                if icon.file_path and os.path.exists(icon.file_path):
                    try:
                        os.remove(icon.file_path)
                    except Exception as e:
                        logger.error(f"Error deleting file {icon.file_path}: {str(e)}")
                
                db.delete(icon)
            else:
                # Soft delete
                icon.is_active = False
                icon.status = IconStatus.INACTIVE.value
            
            db.commit()
            logger.info(f"{'Hard' if hard_delete else 'Soft'} deleted icon {icon_id}")
            return True
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error deleting icon {icon_id}: {str(e)}")
            return False
    
    def delete_icons_by_category(self, category_id: int, hard_delete: bool = False) -> int:
        """Delete all icons for a category."""
        db = self._get_db()
        try:
            icons = db.query(Icon).filter(Icon.category_id == category_id).all()
            deleted_count = 0
            
            for icon in icons:
                if self.delete_icon(icon.id, hard_delete):
                    deleted_count += 1
            
            logger.info(f"Deleted {deleted_count} icons for category {category_id}")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error deleting icons for category {category_id}: {str(e)}")
            return 0
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get icon statistics."""
        db = self._get_db()
        
        total_icons = db.query(func.count(Icon.id)).scalar()
        active_icons = db.query(func.count(Icon.id)).filter(Icon.is_active == True).scalar()
        synced_icons = db.query(func.count(Icon.id)).filter(Icon.shopify_synced_at.isnot(None)).scalar()
        
        # Icons by status
        status_counts = db.query(
            Icon.status,
            func.count(Icon.id)
        ).group_by(Icon.status).all()
        
        # Icons by model
        model_counts = db.query(
            Icon.model,
            func.count(Icon.id)
        ).group_by(Icon.model).all()
        
        # Icons by style
        style_counts = db.query(
            Icon.style,
            func.count(Icon.id)
        ).group_by(Icon.style).all()
        
        # Categories with icons
        categories_with_icons = db.query(
            func.count(func.distinct(Icon.category_id))
        ).scalar()
        
        return {
            'total_icons': total_icons,
            'active_icons': active_icons,
            'inactive_icons': total_icons - active_icons,
            'synced_icons': synced_icons,
            'unsynced_icons': total_icons - synced_icons,
            'categories_with_icons': categories_with_icons,
            'icons_by_status': dict(status_counts),
            'icons_by_model': dict(model_counts),
            'icons_by_style': dict(style_counts)
        }
    
    def create_batch(self, batch_icons: List[Dict[str, Any]], batch_id: str) -> List[Icon]:
        """Create multiple icons in a batch."""
        db = self._get_db()
        created_icons = []
        
        try:
            for icon_data in batch_icons:
                icon_data['generation_batch_id'] = batch_id
                icon = self.create_icon(icon_data)
                created_icons.append(icon)
            
            logger.info(f"Created batch {batch_id} with {len(created_icons)} icons")
            return created_icons
            
        except Exception as e:
            # Rollback all icons in the batch
            db.rollback()
            logger.error(f"Error creating batch {batch_id}: {str(e)}")
            raise
    
    def get_batch_icons(self, batch_id: str) -> List[Icon]:
        """Get all icons from a batch."""
        db = self._get_db()
        return db.query(Icon).filter(Icon.generation_batch_id == batch_id).all()
    
    def calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA256 hash of a file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def find_duplicate_icons(self) -> List[Tuple[str, List[Icon]]]:
        """Find duplicate icons based on file hash."""
        db = self._get_db()
        
        # Find all file hashes that appear more than once
        duplicates_query = db.query(
            Icon.file_hash,
            func.count(Icon.id).label('count')
        ).group_by(Icon.file_hash).having(func.count(Icon.id) > 1)
        
        duplicate_hashes = duplicates_query.all()
        
        results = []
        for file_hash, count in duplicate_hashes:
            if file_hash:  # Skip null hashes
                icons = db.query(Icon).filter(Icon.file_hash == file_hash).all()
                results.append((file_hash, icons))
        
        return results