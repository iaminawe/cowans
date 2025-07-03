"""
Icon Storage Module

Manages storage and retrieval of generated icons using SQLite database.
Maintains backward compatibility with existing file-based storage.
"""

import os
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import logging
from PIL import Image

from database import get_db
from repositories.icon_repository import IconRepository
from models import Icon, IconStatus

logger = logging.getLogger(__name__)


class IconStorage:
    """Manages icon storage in the filesystem with metadata in SQLite database."""
    
    def __init__(self, base_path: str = "data/generated_icons"):
        """Initialize icon storage."""
        self.base_path = base_path
        self.metadata_file = os.path.join(base_path, "metadata.json")
        
        # Create directories if they don't exist
        os.makedirs(base_path, exist_ok=True)
        os.makedirs(os.path.join(base_path, "thumbnails"), exist_ok=True)
        
        # Initialize repository
        self.repository = IconRepository()
        
        # Migrate existing metadata to database if needed
        self._migrate_metadata_to_db()
    
    def _migrate_metadata_to_db(self):
        """Migrate existing JSON metadata to database."""
        if not os.path.exists(self.metadata_file):
            return
        
        try:
            # Load existing metadata
            with open(self.metadata_file, 'r') as f:
                metadata = json.load(f)
            
            if not metadata.get("icons"):
                return
            
            # Check if migration is needed
            db = next(get_db())
            existing_count = db.query(Icon).count()
            
            if existing_count > 0:
                logger.info("Database already contains icons, skipping migration")
                return
            
            logger.info(f"Migrating {len(metadata['icons'])} icons from JSON to database")
            
            # Migrate each icon
            migrated_count = 0
            for icon_id, icon_data in metadata["icons"].items():
                try:
                    # Get file info if file exists
                    file_hash = None
                    file_size = None
                    width = None
                    height = None
                    
                    if os.path.exists(icon_data["file_path"]):
                        file_size = os.path.getsize(icon_data["file_path"])
                        file_hash = self.repository.calculate_file_hash(icon_data["file_path"])
                        
                        # Try to get image dimensions
                        try:
                            img = Image.open(icon_data["file_path"])
                            width, height = img.size
                            img.close()
                        except:
                            pass
                    
                    # Create icon in database
                    icon_db_data = {
                        "category_id": int(icon_data["category_id"]),
                        "filename": os.path.basename(icon_data["file_path"]),
                        "file_path": icon_data["file_path"],
                        "file_size": file_size,
                        "file_hash": file_hash,
                        "width": width,
                        "height": height,
                        "style": icon_data.get("metadata", {}).get("style", "modern"),
                        "color": icon_data.get("metadata", {}).get("color", "#3B82F6"),
                        "background": icon_data.get("metadata", {}).get("background", "transparent"),
                        "model": icon_data.get("metadata", {}).get("model", "unknown"),
                        "status": IconStatus.ACTIVE.value,
                        "created_by": 1,  # Default to first user
                        "meta_data": icon_data.get("metadata", {})
                    }
                    
                    # Handle sync status
                    if icon_data.get("synced"):
                        icon_db_data["shopify_sync_status"] = "success"
                        icon_db_data["shopify_image_id"] = icon_data.get("shopify_collection_id")
                        icon_db_data["shopify_image_url"] = icon_data.get("shopify_image_url")
                    
                    self.repository.create_icon(icon_db_data)
                    migrated_count += 1
                    
                except Exception as e:
                    logger.error(f"Error migrating icon {icon_id}: {str(e)}")
            
            logger.info(f"Successfully migrated {migrated_count} icons to database")
            
            # Rename metadata file to indicate migration completed
            os.rename(self.metadata_file, self.metadata_file + ".migrated")
            
        except Exception as e:
            logger.error(f"Error during metadata migration: {str(e)}")
    
    def save_icon(
        self,
        category_id: str,
        category_name: str,
        file_path: str,
        metadata: Dict[str, Any],
        created_by: int = 1
    ) -> Dict[str, Any]:
        """Save icon record to database."""
        try:
            # Calculate file info
            file_size = os.path.getsize(file_path)
            file_hash = self.repository.calculate_file_hash(file_path)
            
            # Get image dimensions
            width = None
            height = None
            try:
                img = Image.open(file_path)
                width, height = img.size
                img.close()
            except:
                pass
            
            # Prepare icon data
            icon_data = {
                "category_id": int(category_id),
                "filename": os.path.basename(file_path),
                "file_path": file_path,
                "file_size": file_size,
                "file_hash": file_hash,
                "width": width,
                "height": height,
                "format": metadata.get("format", "PNG"),
                "prompt": metadata.get("prompt"),
                "style": metadata.get("style", "modern"),
                "color": metadata.get("color", "#3B82F6"),
                "background": metadata.get("background", "transparent"),
                "model": metadata.get("model", "gpt-image-1"),
                "status": IconStatus.ACTIVE.value,
                "created_by": created_by,
                "generation_time": metadata.get("generation_time"),
                "generation_cost": metadata.get("generation_cost"),
                "meta_data": metadata
            }
            
            # Check if icon already exists
            existing = self.repository.find_existing_icon(int(category_id), file_hash)
            if existing:
                logger.info(f"Icon already exists for category {category_id} with same file hash")
                return self._icon_to_dict(existing)
            
            # Create icon in database
            icon = self.repository.create_icon(icon_data)
            
            return self._icon_to_dict(icon)
            
        except Exception as e:
            logger.error(f"Error saving icon: {str(e)}")
            raise
    
    def get_icon_by_id(self, icon_id: str) -> Optional[Dict[str, Any]]:
        """Get icon by ID."""
        try:
            icon = self.repository.get_icon_by_id(int(icon_id))
            return self._icon_to_dict(icon) if icon else None
        except:
            return None
    
    def get_categories(self) -> List[Dict[str, Any]]:
        """Get all categories with their icon status."""
        db = next(get_db())
        
        # Query to get categories with icon counts
        from sqlalchemy import func
        from models import Category
        
        results = db.query(
            Category.id,
            Category.name,
            func.count(Icon.id).label('icon_count'),
            func.max(Icon.created_at).label('latest_icon_date')
        ).outerjoin(
            Icon,
            (Category.id == Icon.category_id) & (Icon.is_active == True)
        ).group_by(Category.id, Category.name).all()
        
        categories = []
        for cat_id, cat_name, icon_count, latest_date in results:
            if icon_count > 0:
                # Get the latest icon
                latest_icon = self.repository.get_latest_icon_for_category(cat_id)
                categories.append({
                    "id": str(cat_id),
                    "name": cat_name,
                    "icon_count": icon_count,
                    "latest_icon": self._icon_to_dict(latest_icon) if latest_icon else None
                })
        
        return categories
    
    def get_category(self, category_id: str) -> Optional[Dict[str, Any]]:
        """Get category details."""
        db = next(get_db())
        from models import Category
        
        category = db.query(Category).filter(Category.id == int(category_id)).first()
        if category:
            return {
                "id": str(category.id),
                "name": category.name
            }
        return None
    
    def get_icon_path(self, category_id: str) -> Optional[str]:
        """Get the latest icon path for a category."""
        # First check database
        latest_icon = self.repository.get_latest_icon_for_category(int(category_id))
        if latest_icon and os.path.exists(latest_icon.file_path):
            return latest_icon.file_path
        
        # Fallback: Check for files directly in the filesystem
        import glob
        pattern = os.path.join(self.base_path, f"icon_{category_id}_*.png")
        icon_files = glob.glob(pattern)
        
        if icon_files:
            # Return the most recently modified file
            return max(icon_files, key=os.path.getmtime)
        
        return None
    
    def delete_icon(self, category_id: str) -> bool:
        """Delete all icons for a category."""
        deleted_count = self.repository.delete_icons_by_category(int(category_id), hard_delete=True)
        return deleted_count > 0
    
    def update_sync_status(
        self,
        icon_id: str,
        synced: bool,
        shopify_collection_id: str = None,
        shopify_image_url: str = None
    ):
        """Update sync status for an icon."""
        self.repository.update_sync_status(
            int(icon_id),
            synced,
            shopify_collection_id,
            shopify_image_url
        )
    
    def search_icons(
        self,
        query: str = "",
        synced: Optional[bool] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Search icons by query and filters."""
        icons, total = self.repository.search_icons(
            query=query,
            synced=synced,
            limit=limit
        )
        
        return [self._icon_to_dict(icon) for icon in icons]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get icon storage statistics."""
        stats = self.repository.get_statistics()
        
        # Add storage size information
        total_size = 0
        icon_files = []
        
        for root, dirs, files in os.walk(self.base_path):
            for file in files:
                if file.endswith(('.png', '.jpg', '.jpeg', '.svg')):
                    file_path = os.path.join(root, file)
                    try:
                        total_size += os.path.getsize(file_path)
                        icon_files.append(file_path)
                    except:
                        pass
        
        stats['total_storage_size_mb'] = round(total_size / (1024 * 1024), 2)
        stats['total_files_on_disk'] = len(icon_files)
        
        return stats
    
    def health_check(self) -> bool:
        """Check if storage is healthy."""
        # Check file system
        fs_ok = os.path.exists(self.base_path) and os.access(self.base_path, os.W_OK)
        
        # Check database connection
        try:
            db = next(get_db())
            db.query(Icon).limit(1).all()
            db_ok = True
        except:
            db_ok = False
        
        return fs_ok and db_ok
    
    def _icon_to_dict(self, icon: Optional[Icon]) -> Optional[Dict[str, Any]]:
        """Convert Icon model to dictionary."""
        if not icon:
            return None
        
        return {
            "id": str(icon.id),
            "category_id": str(icon.category_id),
            "category_name": icon.category.name if icon.category else "",
            "file_path": icon.file_path,
            "filename": icon.filename,
            "created_at": icon.created_at.isoformat() if icon.created_at else None,
            "metadata": {
                "style": icon.style,
                "color": icon.color,
                "background": icon.background,
                "model": icon.model,
                "ai_generated": icon.model != "unknown",
                "width": icon.width,
                "height": icon.height,
                "file_size": icon.file_size,
                "prompt": icon.prompt
            },
            "synced": icon.shopify_synced_at is not None,
            "shopify_collection_id": icon.shopify_image_id,
            "shopify_image_url": icon.shopify_image_url
        }