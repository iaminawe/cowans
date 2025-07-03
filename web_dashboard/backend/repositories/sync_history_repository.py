"""
Sync History Repository for managing sync history database operations.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from datetime import datetime, timedelta

from models import SyncHistory, SyncStatus
from .base import BaseRepository

class SyncHistoryRepository(BaseRepository):
    """Repository for SyncHistory model operations."""
    
    def __init__(self, session: Session):
        super().__init__(SyncHistory, session)
    
    def create_sync_record(self, sync_type: str, user_id: int, sync_source: Optional[str] = None,
                          sync_target: Optional[str] = None, job_id: Optional[int] = None) -> SyncHistory:
        """Create a new sync history record."""
        return self.create(
            sync_type=sync_type,
            user_id=user_id,
            sync_source=sync_source,
            sync_target=sync_target,
            job_id=job_id,
            status=SyncStatus.PENDING.value,
            started_at=datetime.utcnow()
        )
    
    def start_sync(self, sync_id: int, total_items: int) -> Optional[SyncHistory]:
        """Mark sync as started with total items to process."""
        return self.update(
            sync_id,
            status=SyncStatus.PENDING.value,
            total_items=total_items,
            items_processed=0
        )
    
    def update_progress(self, sync_id: int, items_processed: int, items_successful: Optional[int] = None,
                       items_failed: Optional[int] = None, items_skipped: Optional[int] = None) -> Optional[SyncHistory]:
        """Update sync progress."""
        updates = {'items_processed': items_processed}
        
        if items_successful is not None:
            updates['items_successful'] = items_successful
        if items_failed is not None:
            updates['items_failed'] = items_failed
        if items_skipped is not None:
            updates['items_skipped'] = items_skipped
        
        return self.update(sync_id, **updates)
    
    def complete_sync(self, sync_id: int, message: Optional[str] = None) -> Optional[SyncHistory]:
        """Mark sync as completed successfully."""
        sync = self.get(sync_id)
        if not sync:
            return None
        
        duration = int((datetime.utcnow() - sync.started_at).total_seconds())
        
        # Determine status based on results
        status = SyncStatus.SUCCESS.value
        if sync.items_failed and sync.items_failed > 0:
            if sync.items_successful and sync.items_successful > 0:
                status = SyncStatus.PARTIAL.value
            else:
                status = SyncStatus.FAILED.value
        
        return self.update(
            sync_id,
            status=status,
            completed_at=datetime.utcnow(),
            duration=duration,
            message=message
        )
    
    def fail_sync(self, sync_id: int, error_message: str) -> Optional[SyncHistory]:
        """Mark sync as failed."""
        sync = self.get(sync_id)
        if not sync:
            return None
        
        duration = int((datetime.utcnow() - sync.started_at).total_seconds())
        
        return self.update(
            sync_id,
            status=SyncStatus.FAILED.value,
            completed_at=datetime.utcnow(),
            duration=duration,
            error_message=error_message
        )
    
    def add_warning(self, sync_id: int, warning: str) -> Optional[SyncHistory]:
        """Add a warning to sync record."""
        sync = self.get(sync_id)
        if not sync:
            return None
        
        warnings = sync.warnings or []
        warnings.append({
            'timestamp': datetime.utcnow().isoformat(),
            'message': warning
        })
        
        return self.update(sync_id, warnings=warnings)
    
    def add_error(self, sync_id: int, error: str) -> Optional[SyncHistory]:
        """Add an error to sync record."""
        sync = self.get(sync_id)
        if not sync:
            return None
        
        errors = sync.errors or []
        errors.append({
            'timestamp': datetime.utcnow().isoformat(),
            'message': error
        })
        
        return self.update(sync_id, errors=errors)
    
    def update_sync_counts(self, sync_id: int, products_synced: Optional[int] = None,
                          categories_synced: Optional[int] = None,
                          icons_synced: Optional[int] = None) -> Optional[SyncHistory]:
        """Update specific sync counts."""
        updates = {}
        
        if products_synced is not None:
            updates['products_synced'] = products_synced
        if categories_synced is not None:
            updates['categories_synced'] = categories_synced
        if icons_synced is not None:
            updates['icons_synced'] = icons_synced
        
        return self.update(sync_id, **updates) if updates else None
    
    def get_recent_syncs(self, sync_type: Optional[str] = None, days: int = 7,
                        limit: int = 100) -> List[SyncHistory]:
        """Get recent sync history."""
        since_date = datetime.utcnow() - timedelta(days=days)
        
        query = self.session.query(SyncHistory).filter(
            SyncHistory.started_at >= since_date
        )
        
        if sync_type:
            query = query.filter(SyncHistory.sync_type == sync_type)
        
        return query.order_by(SyncHistory.started_at.desc()).limit(limit).all()
    
    def get_user_syncs(self, user_id: int, limit: Optional[int] = None) -> List[SyncHistory]:
        """Get sync history for a specific user."""
        query = self.session.query(SyncHistory).filter(
            SyncHistory.user_id == user_id
        ).order_by(SyncHistory.started_at.desc())
        
        if limit:
            query = query.limit(limit)
        
        return query.all()
    
    def get_last_successful_sync(self, sync_type: str) -> Optional[SyncHistory]:
        """Get the last successful sync of a specific type."""
        return self.session.query(SyncHistory).filter(
            SyncHistory.sync_type == sync_type,
            SyncHistory.status == SyncStatus.SUCCESS.value
        ).order_by(SyncHistory.completed_at.desc()).first()
    
    def get_sync_statistics(self, sync_type: Optional[str] = None) -> Dict[str, Any]:
        """Get sync statistics."""
        query = self.session.query(SyncHistory)
        if sync_type:
            query = query.filter(SyncHistory.sync_type == sync_type)
        
        # Status counts
        status_counts = query.with_entities(
            SyncHistory.status,
            func.count(SyncHistory.id).label('count')
        ).group_by(SyncHistory.status).all()
        
        # Average duration by type
        avg_durations = query.filter(
            SyncHistory.duration.isnot(None)
        ).with_entities(
            SyncHistory.sync_type,
            func.avg(SyncHistory.duration).label('avg_duration')
        ).group_by(SyncHistory.sync_type).all()
        
        # Success metrics
        total_completed = query.filter(
            SyncHistory.status.in_([SyncStatus.SUCCESS.value, SyncStatus.FAILED.value, SyncStatus.PARTIAL.value])
        ).count()
        
        successful = query.filter(
            SyncHistory.status == SyncStatus.SUCCESS.value
        ).count()
        
        # Total items synced
        total_items_synced = query.with_entities(
            func.sum(SyncHistory.items_successful).label('total')
        ).scalar() or 0
        
        # Recent sync performance (last 7 days)
        recent_date = datetime.utcnow() - timedelta(days=7)
        recent_syncs = query.filter(
            SyncHistory.started_at >= recent_date
        ).count()
        
        return {
            'status_breakdown': {status: count for status, count in status_counts},
            'average_durations': {sync_type: round(avg_dur, 2) for sync_type, avg_dur in avg_durations},
            'success_rate': round((successful / total_completed * 100), 2) if total_completed > 0 else 0,
            'total_syncs': query.count(),
            'total_items_synced': total_items_synced,
            'recent_syncs_count': recent_syncs
        }
    
    def get_sync_timeline(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get sync timeline for dashboard visualization."""
        since_date = datetime.utcnow() - timedelta(days=days)
        
        syncs = self.session.query(SyncHistory).filter(
            SyncHistory.started_at >= since_date
        ).order_by(SyncHistory.started_at.desc()).all()
        
        timeline = []
        for sync in syncs:
            timeline.append({
                'id': sync.id,
                'type': sync.sync_type,
                'status': sync.status,
                'started_at': sync.started_at.isoformat(),
                'completed_at': sync.completed_at.isoformat() if sync.completed_at else None,
                'duration': sync.duration,
                'items_processed': sync.items_processed,
                'items_successful': sync.items_successful,
                'items_failed': sync.items_failed,
                'user_id': sync.user_id
            })
        
        return timeline
    
    def cleanup_old_syncs(self, days: int = 90) -> int:
        """Clean up old sync records."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        deleted_count = self.session.query(SyncHistory).filter(
            SyncHistory.started_at < cutoff_date
        ).count()
        
        self.session.query(SyncHistory).filter(
            SyncHistory.started_at < cutoff_date
        ).delete(synchronize_session=False)
        
        self.session.flush()
        return deleted_count
    
    def get_with_user(self, sync_id: int) -> Optional[SyncHistory]:
        """Get sync record with user eagerly loaded."""
        return self.session.query(SyncHistory).options(
            joinedload(SyncHistory.user)
        ).filter(SyncHistory.id == sync_id).first()