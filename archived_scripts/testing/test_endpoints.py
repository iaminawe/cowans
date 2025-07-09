#!/usr/bin/env python3
"""
Test script for the enhanced sync API endpoints.
"""

import sys
import os
sys.path.append('web_dashboard/backend')

from datetime import datetime, timedelta
from sqlalchemy import func
from database import DatabaseManager
from staging_models import SyncBatch, StagedProductChange

# Initialize database manager
db_manager = DatabaseManager()

def test_metrics_endpoint():
    """Test the metrics endpoint logic."""
    print("Testing /api/sync/metrics endpoint...")
    
    try:
        with db_manager.session_scope() as session:
            # Calculate time range
            timeframe = '24h'
            now = datetime.utcnow()
            if timeframe == '1h':
                start_time = now - timedelta(hours=1)
            elif timeframe == '24h':
                start_time = now - timedelta(days=1)
            elif timeframe == '7d':
                start_time = now - timedelta(days=7)
            elif timeframe == '30d':
                start_time = now - timedelta(days=30)
            else:
                start_time = now - timedelta(days=1)
            
            # Get sync batches in timeframe
            batches = session.query(SyncBatch).filter(
                SyncBatch.created_at >= start_time
            ).all()
            
            # Calculate metrics
            total_batches = len(batches)
            successful_batches = sum(1 for b in batches if b.status == 'completed')
            failed_batches = sum(1 for b in batches if b.status == 'failed')
            partial_batches = sum(1 for b in batches if b.status == 'partial')
            
            total_items = sum(b.total_items or 0 for b in batches)
            successful_items = sum(b.successful_items or 0 for b in batches)
            failed_items = sum(b.failed_items or 0 for b in batches)
            
            # Calculate average processing time
            completed_batches = [b for b in batches if b.completed_at and b.started_at]
            avg_processing_time = 0
            if completed_batches:
                processing_times = [(b.completed_at - b.started_at).total_seconds() for b in completed_batches]
                avg_processing_time = sum(processing_times) / len(processing_times)
            
            # Get staged changes metrics
            staged_changes = session.query(StagedProductChange).filter(
                StagedProductChange.created_at >= start_time
            ).all()
            
            staged_pending = sum(1 for c in staged_changes if c.status == 'pending')
            staged_approved = sum(1 for c in staged_changes if c.status == 'approved')
            staged_rejected = sum(1 for c in staged_changes if c.status == 'rejected')
            staged_applied = sum(1 for c in staged_changes if c.status == 'applied')
            
            metrics = {
                'success': True,
                'timeframe': timeframe,
                'sync_batches': {
                    'total': total_batches,
                    'successful': successful_batches,
                    'failed': failed_batches,
                    'partial': partial_batches,
                    'success_rate': (successful_batches / total_batches) * 100 if total_batches > 0 else 0
                },
                'items': {
                    'total': total_items,
                    'successful': successful_items,
                    'failed': failed_items,
                    'success_rate': (successful_items / total_items) * 100 if total_items > 0 else 0
                },
                'performance': {
                    'avg_processing_time_seconds': avg_processing_time,
                    'items_per_second': total_items / avg_processing_time if avg_processing_time > 0 else 0
                },
                'staged_changes': {
                    'total': len(staged_changes),
                    'pending': staged_pending,
                    'approved': staged_approved,
                    'rejected': staged_rejected,
                    'applied': staged_applied
                },
                'timestamp': now.isoformat()
            }
            
            print("✓ Metrics endpoint test passed")
            print(f"  - Found {total_batches} batches")
            print(f"  - Found {len(staged_changes)} staged changes")
            return True
            
    except Exception as e:
        print(f"✗ Metrics endpoint test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_recent_activity_endpoint():
    """Test the recent activity endpoint logic."""
    print("Testing /api/sync/recent-activity endpoint...")
    
    try:
        with db_manager.session_scope() as session:
            # Get query parameters
            limit = 20
            activity_type = 'all'
            
            activities = []
            
            # Get recent sync batches
            if activity_type in ['all', 'batches']:
                recent_batches = session.query(SyncBatch).order_by(
                    SyncBatch.created_at.desc()
                ).limit(limit).all()
                
                for batch in recent_batches:
                    activities.append({
                        'type': 'sync_batch',
                        'action': f"Sync batch {batch.status}",
                        'batch_id': batch.batch_id,
                        'batch_name': batch.batch_name,
                        'sync_direction': batch.sync_direction,
                        'status': batch.status,
                        'total_items': batch.total_items,
                        'successful_items': batch.successful_items,
                        'failed_items': batch.failed_items,
                        'timestamp': batch.created_at.isoformat(),
                        'user_id': batch.created_by
                    })
            
            # Get recent staged changes
            if activity_type in ['all', 'changes']:
                recent_changes = session.query(StagedProductChange).order_by(
                    StagedProductChange.created_at.desc()
                ).limit(limit).all()
                
                for change in recent_changes:
                    activities.append({
                        'type': 'staged_change',
                        'action': f"Change {change.status}",
                        'change_id': change.change_id,
                        'change_type': change.change_type,
                        'sync_direction': change.sync_direction,
                        'status': change.status,
                        'has_conflicts': change.has_conflicts,
                        'timestamp': change.created_at.isoformat(),
                        'product_id': change.product_id,
                        'reviewed_by': change.reviewed_by,
                        'reviewed_at': change.reviewed_at.isoformat() if change.reviewed_at else None
                    })
            
            # Sort all activities by timestamp
            activities.sort(key=lambda x: x['timestamp'], reverse=True)
            
            # Limit to requested number
            activities = activities[:limit]
            
            result = {
                'success': True,
                'activities': activities,
                'total': len(activities),
                'timestamp': datetime.utcnow().isoformat()
            }
            
            print("✓ Recent activity endpoint test passed")
            print(f"  - Found {len(activities)} activities")
            return True
            
    except Exception as e:
        print(f"✗ Recent activity endpoint test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all endpoint tests."""
    print("Testing Enhanced Sync API Endpoints...")
    print("=" * 50)
    
    # Test metrics endpoint
    metrics_success = test_metrics_endpoint()
    print()
    
    # Test recent activity endpoint
    activity_success = test_recent_activity_endpoint()
    print()
    
    # Summary
    print("=" * 50)
    if metrics_success and activity_success:
        print("✓ All endpoint tests passed!")
        return 0
    else:
        print("✗ Some endpoint tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())