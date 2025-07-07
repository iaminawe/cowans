"""
Sync API Endpoints - REST API for Shopify Sync Engine

This module provides REST API endpoints for managing Shopify synchronization
operations, job monitoring, conflict resolution, and sync configuration.
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta
import logging
import asyncio
from typing import Dict, Any, List

from database import db_session_scope
from repositories import UserRepository, ProductRepository, JobRepository
from sync_service import SyncService, SyncJobRequest, SyncJobType, SyncPriority
from shopify_sync_engine import ConflictResolution, SyncOperation
from models import User

# Global sync service instance (will be initialized in app.py)
sync_service: SyncService = None

# Create blueprint
sync_api = Blueprint('sync_api', __name__, url_prefix='/api/sync')

# Logger
logger = logging.getLogger(__name__)


def get_current_user() -> User:
    """Get current user from JWT token."""
    user_id = get_jwt_identity()
    with db_session_scope() as session:
        user_repo = UserRepository(session)
        return user_repo.get_by_id(User, user_id)


@sync_api.route('/status', methods=['GET'])
@jwt_required()
def get_sync_status():
    """Get current sync engine status and metrics."""
    try:
        if not sync_service:
            return jsonify({"error": "Sync service not initialized"}), 503
        
        status = sync_service.get_sync_status()
        return jsonify({
            "success": True,
            "data": status
        })
        
    except Exception as e:
        logger.error(f"Failed to get sync status: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@sync_api.route('/jobs', methods=['POST'])
@jwt_required()
def start_sync_job():
    """Start a new sync job."""
    try:
        if not sync_service:
            return jsonify({"error": "Sync service not initialized"}), 503
        
        data = request.get_json()
        
        # Validate required fields
        if 'job_type' not in data:
            return jsonify({
                "success": False,
                "error": "job_type is required"
            }), 400
        
        # Parse job type
        try:
            job_type = SyncJobType(data['job_type'])
        except ValueError:
            return jsonify({
                "success": False,
                "error": f"Invalid job_type: {data['job_type']}"
            }), 400
        
        # Parse priority
        priority = SyncPriority.NORMAL
        if 'priority' in data:
            try:
                priority = SyncPriority(data['priority'])
            except ValueError:
                return jsonify({
                    "success": False,
                    "error": f"Invalid priority: {data['priority']}"
                }), 400
        
        # Get current user
        current_user = get_current_user()
        if not current_user:
            return jsonify({
                "success": False,
                "error": "User not found"
            }), 401
        
        # Create job request
        job_request = SyncJobRequest(
            job_type=job_type,
            user_id=current_user.id,
            priority=priority,
            parameters=data.get('parameters', {})
        )
        
        # Start job
        job_id = sync_service.start_sync_job(job_request)
        
        return jsonify({
            "success": True,
            "data": {
                "job_id": job_id,
                "message": f"Started {job_type.value} job"
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to start sync job: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@sync_api.route('/jobs/<job_id>', methods=['GET'])
@jwt_required()
def get_job_progress(job_id: str):
    """Get progress information for a specific job."""
    try:
        if not sync_service:
            return jsonify({"error": "Sync service not initialized"}), 503
        
        progress = sync_service.get_job_progress(job_id)
        
        if not progress:
            return jsonify({
                "success": False,
                "error": "Job not found"
            }), 404
        
        return jsonify({
            "success": True,
            "data": {
                "job_id": progress.job_id,
                "job_type": progress.job_type.value,
                "status": progress.status.value,
                "progress_percentage": progress.progress_percentage,
                "current_stage": progress.current_stage,
                "items_total": progress.items_total,
                "items_processed": progress.items_processed,
                "items_successful": progress.items_successful,
                "items_failed": progress.items_failed,
                "errors": progress.errors,
                "warnings": progress.warnings,
                "started_at": progress.started_at.isoformat(),
                "estimated_completion": progress.estimated_completion.isoformat() if progress.estimated_completion else None
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to get job progress: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@sync_api.route('/jobs/<job_id>', methods=['DELETE'])
@jwt_required()
def cancel_job(job_id: str):
    """Cancel a running sync job."""
    try:
        if not sync_service:
            return jsonify({"error": "Sync service not initialized"}), 503
        
        # Cancel job (async operation)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(sync_service.cancel_job(job_id))
        loop.close()
        
        if success:
            return jsonify({
                "success": True,
                "message": f"Job {job_id} cancelled"
            })
        else:
            return jsonify({
                "success": False,
                "error": "Job not found or already completed"
            }), 404
        
    except Exception as e:
        logger.error(f"Failed to cancel job: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@sync_api.route('/jobs', methods=['GET'])
@jwt_required()
def get_active_jobs():
    """Get all active sync jobs."""
    try:
        if not sync_service:
            return jsonify({"error": "Sync service not initialized"}), 503
        
        jobs = sync_service.get_active_jobs()
        
        return jsonify({
            "success": True,
            "data": [
                {
                    "job_id": job.job_id,
                    "job_type": job.job_type.value,
                    "status": job.status.value,
                    "progress_percentage": job.progress_percentage,
                    "current_stage": job.current_stage,
                    "started_at": job.started_at.isoformat()
                }
                for job in jobs
            ]
        })
        
    except Exception as e:
        logger.error(f"Failed to get active jobs: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@sync_api.route('/products/<int:product_id>/sync', methods=['POST'])
@jwt_required()
def sync_single_product(product_id: int):
    """Sync a single product to Shopify."""
    try:
        if not sync_service:
            return jsonify({"error": "Sync service not initialized"}), 503
        
        # Get current user
        current_user = get_current_user()
        if not current_user:
            return jsonify({
                "success": False,
                "error": "User not found"
            }), 401
        
        # Create job request for single product
        job_request = SyncJobRequest(
            job_type=SyncJobType.PRODUCT_SYNC,
            user_id=current_user.id,
            priority=SyncPriority.HIGH,
            parameters={"product_ids": [product_id]}
        )
        
        # Start job
        job_id = sync_service.start_sync_job(job_request)
        
        return jsonify({
            "success": True,
            "data": {
                "job_id": job_id,
                "message": f"Started sync for product {product_id}"
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to sync product {product_id}: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@sync_api.route('/products/batch-sync', methods=['POST'])
@jwt_required()
def batch_sync_products():
    """Sync multiple products to Shopify."""
    try:
        if not sync_service:
            return jsonify({"error": "Sync service not initialized"}), 503
        
        data = request.get_json()
        
        # Validate product IDs
        product_ids = data.get('product_ids', [])
        if not product_ids:
            return jsonify({
                "success": False,
                "error": "product_ids array is required"
            }), 400
        
        if not isinstance(product_ids, list):
            return jsonify({
                "success": False,
                "error": "product_ids must be an array"
            }), 400
        
        # Limit batch size
        if len(product_ids) > 1000:
            return jsonify({
                "success": False,
                "error": "Maximum 1000 products per batch"
            }), 400
        
        # Get current user
        current_user = get_current_user()
        if not current_user:
            return jsonify({
                "success": False,
                "error": "User not found"
            }), 401
        
        # Create job request
        job_request = SyncJobRequest(
            job_type=SyncJobType.PRODUCT_SYNC,
            user_id=current_user.id,
            priority=SyncPriority.NORMAL,
            parameters={"product_ids": product_ids}
        )
        
        # Start job
        job_id = sync_service.start_sync_job(job_request)
        
        return jsonify({
            "success": True,
            "data": {
                "job_id": job_id,
                "message": f"Started batch sync for {len(product_ids)} products"
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to start batch sync: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@sync_api.route('/incremental', methods=['POST'])
@jwt_required()
def start_incremental_sync():
    """Start an incremental sync of modified products."""
    try:
        if not sync_service:
            return jsonify({"error": "Sync service not initialized"}), 503
        
        data = request.get_json() or {}
        
        # Get since parameter (default to 24 hours)
        since_hours = data.get('since_hours', 24)
        
        # Validate since_hours
        if not isinstance(since_hours, (int, float)) or since_hours <= 0:
            return jsonify({
                "success": False,
                "error": "since_hours must be a positive number"
            }), 400
        
        # Get current user
        current_user = get_current_user()
        if not current_user:
            return jsonify({
                "success": False,
                "error": "User not found"
            }), 401
        
        # Create job request
        job_request = SyncJobRequest(
            job_type=SyncJobType.INCREMENTAL_SYNC,
            user_id=current_user.id,
            priority=SyncPriority.NORMAL,
            parameters={"since_hours": since_hours}
        )
        
        # Start job
        job_id = sync_service.start_sync_job(job_request)
        
        return jsonify({
            "success": True,
            "data": {
                "job_id": job_id,
                "message": f"Started incremental sync (since {since_hours} hours ago)"
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to start incremental sync: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@sync_api.route('/full-sync', methods=['POST'])
@jwt_required()
def start_full_sync():
    """Start a full sync of all products."""
    try:
        if not sync_service:
            return jsonify({"error": "Sync service not initialized"}), 503
        
        # Get current user
        current_user = get_current_user()
        if not current_user:
            return jsonify({
                "success": False,
                "error": "User not found"
            }), 401
        
        # Check if user is admin (full sync is resource intensive)
        if not current_user.is_admin:
            return jsonify({
                "success": False,
                "error": "Admin privileges required for full sync"
            }), 403
        
        # Create job request
        job_request = SyncJobRequest(
            job_type=SyncJobType.FULL_SYNC,
            user_id=current_user.id,
            priority=SyncPriority.LOW,  # Full sync is low priority
            parameters={}
        )
        
        # Start job
        job_id = sync_service.start_sync_job(job_request)
        
        return jsonify({
            "success": True,
            "data": {
                "job_id": job_id,
                "message": "Started full sync of all products"
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to start full sync: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@sync_api.route('/conflicts', methods=['GET'])
@jwt_required()
def get_conflicts():
    """Get pending sync conflicts."""
    try:
        if not sync_service:
            return jsonify({"error": "Sync service not initialized"}), 503
        
        conflicts = sync_service.get_conflicts()
        
        return jsonify({
            "success": True,
            "data": conflicts
        })
        
    except Exception as e:
        logger.error(f"Failed to get conflicts: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@sync_api.route('/conflicts/<conflict_id>/resolve', methods=['POST'])
@jwt_required()
def resolve_conflict(conflict_id: str):
    """Manually resolve a sync conflict."""
    try:
        if not sync_service:
            return jsonify({"error": "Sync service not initialized"}), 503
        
        data = request.get_json()
        
        # Validate resolution value
        if 'resolved_value' not in data:
            return jsonify({
                "success": False,
                "error": "resolved_value is required"
            }), 400
        
        # Resolve conflict
        success = sync_service.resolve_conflict(
            conflict_id, 
            data['resolved_value']
        )
        
        if success:
            return jsonify({
                "success": True,
                "message": f"Conflict {conflict_id} resolved"
            })
        else:
            return jsonify({
                "success": False,
                "error": "Conflict not found"
            }), 404
        
    except Exception as e:
        logger.error(f"Failed to resolve conflict: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@sync_api.route('/config', methods=['GET'])
@jwt_required()
def get_sync_config():
    """Get current sync configuration."""
    try:
        if not sync_service:
            return jsonify({"error": "Sync service not initialized"}), 503
        
        engine = sync_service.sync_engine
        
        config = {
            "conflict_resolution_strategy": engine.conflict_resolution_strategy.value,
            "auto_resolve_conflicts": engine.auto_resolve_conflicts,
            "bidirectional_sync": engine.enable_bidirectional_sync,
            "batch_size": engine.batch_size,
            "max_concurrent": engine.max_concurrent,
            "max_concurrent_jobs": sync_service.max_concurrent_jobs
        }
        
        return jsonify({
            "success": True,
            "data": config
        })
        
    except Exception as e:
        logger.error(f"Failed to get sync config: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@sync_api.route('/config', methods=['PUT'])
@jwt_required()
def update_sync_config():
    """Update sync configuration."""
    try:
        if not sync_service:
            return jsonify({"error": "Sync service not initialized"}), 503
        
        # Check if user is admin
        current_user = get_current_user()
        if not current_user or not current_user.is_admin:
            return jsonify({
                "success": False,
                "error": "Admin privileges required"
            }), 403
        
        data = request.get_json()
        
        # Update conflict resolution strategy
        if 'conflict_resolution_strategy' in data:
            try:
                strategy = ConflictResolution(data['conflict_resolution_strategy'])
                sync_service.configure_conflict_resolution(
                    strategy, 
                    data.get('auto_resolve_conflicts', sync_service.sync_engine.auto_resolve_conflicts)
                )
            except ValueError:
                return jsonify({
                    "success": False,
                    "error": f"Invalid conflict resolution strategy: {data['conflict_resolution_strategy']}"
                }), 400
        
        # Update bidirectional sync
        if 'bidirectional_sync' in data:
            sync_service.enable_bidirectional_sync(data['bidirectional_sync'])
        
        # Update batch settings
        if 'batch_size' in data:
            batch_size = data['batch_size']
            if isinstance(batch_size, int) and 1 <= batch_size <= 100:
                sync_service.sync_engine.batch_size = batch_size
            else:
                return jsonify({
                    "success": False,
                    "error": "batch_size must be between 1 and 100"
                }), 400
        
        if 'max_concurrent' in data:
            max_concurrent = data['max_concurrent']
            if isinstance(max_concurrent, int) and 1 <= max_concurrent <= 20:
                sync_service.sync_engine.max_concurrent = max_concurrent
            else:
                return jsonify({
                    "success": False,
                    "error": "max_concurrent must be between 1 and 20"
                }), 400
        
        if 'max_concurrent_jobs' in data:
            max_jobs = data['max_concurrent_jobs']
            if isinstance(max_jobs, int) and 1 <= max_jobs <= 10:
                sync_service.max_concurrent_jobs = max_jobs
            else:
                return jsonify({
                    "success": False,
                    "error": "max_concurrent_jobs must be between 1 and 10"
                }), 400
        
        return jsonify({
            "success": True,
            "message": "Sync configuration updated"
        })
        
    except Exception as e:
        logger.error(f"Failed to update sync config: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@sync_api.route('/history', methods=['GET'])
@jwt_required()
def get_sync_history():
    """Get sync history records."""
    try:
        if not sync_service:
            return jsonify({"error": "Sync service not initialized"}), 503
        
        # Get query parameters
        limit = request.args.get('limit', 100, type=int)
        sync_type = request.args.get('sync_type')
        
        # Validate limit
        if limit > 1000:
            limit = 1000
        
        history = sync_service.get_sync_history(limit=limit, sync_type=sync_type)
        
        return jsonify({
            "success": True,
            "data": history
        })
        
    except Exception as e:
        logger.error(f"Failed to get sync history: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@sync_api.route('/products/stats', methods=['GET'])
@jwt_required()
def get_product_sync_stats():
    """Get product synchronization statistics."""
    try:
        with db_session_scope() as session:
            product_repo = ProductRepository(session)
            stats = product_repo.get_product_stats()
            
            return jsonify({
                "success": True,
                "data": stats
            })
            
    except Exception as e:
        logger.error(f"Failed to get product sync stats: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@sync_api.route('/test-connection', methods=['POST'])
@jwt_required()
def test_shopify_connection():
    """Test Shopify API connection."""
    try:
        if not sync_service:
            return jsonify({"error": "Sync service not initialized"}), 503
        
        # Test authentication
        sync_service.sync_engine.product_manager.test_auth()
        
        return jsonify({
            "success": True,
            "message": "Shopify connection successful"
        })
        
    except Exception as e:
        logger.error(f"Shopify connection test failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


def init_sync_service(shop_url: str, access_token: str) -> SyncService:
    """Initialize the global sync service instance."""
    global sync_service
    
    if not sync_service:
        sync_service = SyncService(shop_url, access_token)
        logger.info("Sync service initialized")
    
    return sync_service


def get_sync_service() -> SyncService:
    """Get the global sync service instance."""
    return sync_service