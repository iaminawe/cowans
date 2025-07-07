"""
Sync Service - High-level service for managing Shopify synchronization

This service provides a high-level interface for managing synchronization
between the local database and Shopify, including job management, 
progress tracking, and webhook handling.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from enum import Enum

from sqlalchemy.orm import Session
from models import (
    Product, Category, Job, SyncHistory, JobStatus, SyncStatus,
    ProductStatus, User
)
from database import db_session_scope
from repositories import (
    ProductRepository, CategoryRepository, JobRepository, 
    SyncHistoryRepository, UserRepository
)
from shopify_sync_engine import (
    ShopifySyncEngine, SyncOperation, SyncPriority, SyncResult,
    ConflictResolution
)


class SyncJobType(Enum):
    """Types of sync jobs."""
    FULL_SYNC = "full_sync"
    INCREMENTAL_SYNC = "incremental_sync"
    PRODUCT_SYNC = "product_sync"
    CATEGORY_SYNC = "category_sync"
    IMAGE_SYNC = "image_sync"
    CONFLICT_RESOLUTION = "conflict_resolution"


@dataclass
class SyncJobRequest:
    """Request to start a sync job."""
    job_type: SyncJobType
    user_id: int
    priority: SyncPriority = SyncPriority.NORMAL
    parameters: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.parameters is None:
            self.parameters = {}


@dataclass
class SyncJobProgress:
    """Progress information for a sync job."""
    job_id: str
    job_type: SyncJobType
    status: JobStatus
    progress_percentage: float
    current_stage: str
    items_total: int
    items_processed: int
    items_successful: int
    items_failed: int
    errors: List[str]
    warnings: List[str]
    started_at: datetime
    estimated_completion: Optional[datetime] = None


class SyncService:
    """
    High-level service for managing Shopify synchronization operations.
    
    This service orchestrates the sync engine, manages jobs, tracks progress,
    and provides a clean API for the web dashboard.
    """
    
    def __init__(self, shop_url: str, access_token: str):
        """Initialize the sync service."""
        self.shop_url = shop_url
        self.access_token = access_token
        
        # Initialize sync engine
        self.sync_engine = ShopifySyncEngine(
            shop_url=shop_url,
            access_token=access_token,
            batch_size=20,  # Larger batches for better performance
            max_concurrent=10
        )
        
        # Job management
        self.active_jobs: Dict[str, SyncJobProgress] = {}
        self.job_callbacks: Dict[str, List[Callable]] = {}
        
        # Configuration
        self.max_concurrent_jobs = 3
        self.job_timeout = timedelta(hours=2)
        
        # Logger
        self.logger = logging.getLogger(__name__)
    
    async def start_service(self):
        """Start the sync service and engine."""
        self.logger.info("Starting Sync Service")
        
        # Start the sync engine
        await self.sync_engine.start_sync_engine()
    
    async def stop_service(self):
        """Stop the sync service gracefully."""
        self.logger.info("Stopping Sync Service")
        
        # Cancel active jobs
        for job_id in list(self.active_jobs.keys()):
            await self.cancel_job(job_id)
        
        # Stop sync engine
        await self.sync_engine.stop_sync_engine()
    
    def start_sync_job(self, request: SyncJobRequest) -> str:
        """Start a new sync job."""
        job_id = str(uuid.uuid4())
        
        # Check concurrent job limit
        if len(self.active_jobs) >= self.max_concurrent_jobs:
            raise Exception("Maximum concurrent jobs reached")
        
        # Create job progress tracker
        progress = SyncJobProgress(
            job_id=job_id,
            job_type=request.job_type,
            status=JobStatus.PENDING,
            progress_percentage=0.0,
            current_stage="Initializing",
            items_total=0,
            items_processed=0,
            items_successful=0,
            items_failed=0,
            errors=[],
            warnings=[],
            started_at=datetime.utcnow()
        )
        
        self.active_jobs[job_id] = progress
        
        # Create database job record
        try:
            with db_session_scope() as session:
                job_repo = JobRepository(session)
                
                db_job = job_repo.create(
                    job_uuid=job_id,
                    script_name=f"sync_{request.job_type.value}",
                    display_name=f"Shopify {request.job_type.value.replace('_', ' ').title()}",
                    description=f"Synchronization job: {request.job_type.value}",
                    user_id=request.user_id,
                    parameters=request.parameters,
                    priority=request.priority.value
                )
                
                session.commit()
                
        except Exception as e:
            self.logger.error(f"Failed to create job record: {e}")
            del self.active_jobs[job_id]
            raise
        
        # Start job execution in background
        asyncio.create_task(self._execute_job(job_id, request))
        
        self.logger.info(f"Started sync job {job_id} of type {request.job_type.value}")
        return job_id
    
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a running sync job."""
        if job_id not in self.active_jobs:
            return False
        
        progress = self.active_jobs[job_id]
        progress.status = JobStatus.CANCELLED
        progress.current_stage = "Cancelled"
        
        # Update database
        try:
            with db_session_scope() as session:
                job_repo = JobRepository(session)
                job = job_repo.get_by_uuid(job_id)
                
                if job:
                    job.status = JobStatus.CANCELLED.value
                    job.completed_at = datetime.utcnow()
                    session.commit()
                    
        except Exception as e:
            self.logger.error(f"Failed to update cancelled job {job_id}: {e}")
        
        # Remove from active jobs
        del self.active_jobs[job_id]
        
        self.logger.info(f"Cancelled job {job_id}")
        return True
    
    def get_job_progress(self, job_id: str) -> Optional[SyncJobProgress]:
        """Get progress information for a job."""
        return self.active_jobs.get(job_id)
    
    def get_active_jobs(self) -> List[SyncJobProgress]:
        """Get all active jobs."""
        return list(self.active_jobs.values())
    
    def get_sync_status(self) -> Dict[str, Any]:
        """Get overall sync service status."""
        engine_status = self.sync_engine.get_sync_status()
        
        return {
            "service": {
                "active_jobs": len(self.active_jobs),
                "max_concurrent_jobs": self.max_concurrent_jobs,
                "job_timeout_hours": self.job_timeout.total_seconds() / 3600
            },
            "engine": engine_status,
            "jobs": [
                {
                    "id": progress.job_id,
                    "type": progress.job_type.value,
                    "status": progress.status.value,
                    "progress": progress.progress_percentage,
                    "stage": progress.current_stage,
                    "started": progress.started_at.isoformat()
                }
                for progress in self.active_jobs.values()
            ]
        }
    
    def register_job_callback(self, job_id: str, callback: Callable[[SyncJobProgress], None]):
        """Register a callback for job progress updates."""
        if job_id not in self.job_callbacks:
            self.job_callbacks[job_id] = []
        self.job_callbacks[job_id].append(callback)
    
    def get_sync_history(self, limit: int = 100, 
                        sync_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get sync history records."""
        try:
            with db_session_scope() as session:
                sync_repo = SyncHistoryRepository(session)
                
                history = sync_repo.get_recent(limit=limit, sync_type=sync_type)
                
                return [
                    {
                        "id": record.id,
                        "sync_type": record.sync_type,
                        "status": record.status,
                        "started_at": record.started_at.isoformat(),
                        "completed_at": record.completed_at.isoformat() if record.completed_at else None,
                        "duration": record.duration,
                        "items_processed": record.items_processed,
                        "items_successful": record.items_successful,
                        "items_failed": record.items_failed,
                        "message": record.message,
                        "error_message": record.error_message
                    }
                    for record in history
                ]
                
        except Exception as e:
            self.logger.error(f"Failed to get sync history: {e}")
            return []
    
    async def _execute_job(self, job_id: str, request: SyncJobRequest):
        """Execute a sync job in the background."""
        progress = self.active_jobs[job_id]
        start_time = datetime.utcnow()
        
        try:
            progress.status = JobStatus.RUNNING
            progress.current_stage = "Starting"
            
            # Update database job status
            with db_session_scope() as session:
                job_repo = JobRepository(session)
                job = job_repo.get_by_uuid(job_id)
                if job:
                    job.status = JobStatus.RUNNING.value
                    job.started_at = start_time
                    session.commit()
            
            # Execute based on job type
            if request.job_type == SyncJobType.FULL_SYNC:
                await self._execute_full_sync(job_id, request)
            elif request.job_type == SyncJobType.INCREMENTAL_SYNC:
                await self._execute_incremental_sync(job_id, request)
            elif request.job_type == SyncJobType.PRODUCT_SYNC:
                await self._execute_product_sync(job_id, request)
            elif request.job_type == SyncJobType.CATEGORY_SYNC:
                await self._execute_category_sync(job_id, request)
            else:
                raise Exception(f"Unsupported job type: {request.job_type}")
            
            # Mark as completed
            progress.status = JobStatus.COMPLETED
            progress.current_stage = "Completed"
            progress.progress_percentage = 100.0
            
        except Exception as e:
            self.logger.error(f"Job {job_id} failed: {e}")
            progress.status = JobStatus.FAILED
            progress.current_stage = "Failed"
            progress.errors.append(str(e))
        
        finally:
            # Update database
            completion_time = datetime.utcnow()
            duration = int((completion_time - start_time).total_seconds())
            
            try:
                with db_session_scope() as session:
                    job_repo = JobRepository(session)
                    job = job_repo.get_by_uuid(job_id)
                    
                    if job:
                        job.status = progress.status.value
                        job.completed_at = completion_time
                        job.actual_duration = duration
                        job.progress = int(progress.progress_percentage)
                        job.current_stage = progress.current_stage
                        
                        if progress.errors:
                            job.error_message = "; ".join(progress.errors[-5:])  # Last 5 errors
                        
                        # Store results
                        job.result = {
                            "items_total": progress.items_total,
                            "items_processed": progress.items_processed,
                            "items_successful": progress.items_successful,
                            "items_failed": progress.items_failed,
                            "errors": progress.errors,
                            "warnings": progress.warnings
                        }
                        
                        session.commit()
                        
                    # Create sync history record
                    sync_repo = SyncHistoryRepository(session)
                    sync_repo.create(
                        sync_type=request.job_type.value,
                        sync_source="manual",
                        sync_target="shopify",
                        status=SyncStatus.SUCCESS.value if progress.status == JobStatus.COMPLETED else SyncStatus.FAILED.value,
                        started_at=start_time,
                        completed_at=completion_time,
                        duration=duration,
                        total_items=progress.items_total,
                        items_processed=progress.items_processed,
                        items_successful=progress.items_successful,
                        items_failed=progress.items_failed,
                        message=f"Job completed with {progress.items_successful} successful items",
                        error_message="; ".join(progress.errors) if progress.errors else None,
                        user_id=request.user_id,
                        job_id=job.id if job else None
                    )
                    session.commit()
                    
            except Exception as e:
                self.logger.error(f"Failed to update job completion for {job_id}: {e}")
            
            # Call callbacks
            if job_id in self.job_callbacks:
                for callback in self.job_callbacks[job_id]:
                    try:
                        callback(progress)
                    except Exception as e:
                        self.logger.error(f"Callback error for job {job_id}: {e}")
                
                del self.job_callbacks[job_id]
            
            # Remove from active jobs
            if job_id in self.active_jobs:
                del self.active_jobs[job_id]
    
    async def _execute_full_sync(self, job_id: str, request: SyncJobRequest):
        """Execute a full synchronization of all products."""
        progress = self.active_jobs[job_id]
        progress.current_stage = "Fetching products"
        
        with db_session_scope() as session:
            product_repo = ProductRepository(session)
            
            # Get all active products
            products = product_repo.get_active_products()
            progress.items_total = len(products)
            
            if not products:
                progress.warnings.append("No active products found to sync")
                return
            
            progress.current_stage = "Syncing products"
            
            # Sync in batches
            batch_size = 50
            for i in range(0, len(products), batch_size):
                batch = products[i:i + batch_size]
                product_ids = [p.id for p in batch]
                
                # Execute batch sync
                results = await self.sync_engine.batch_sync_products(
                    product_ids, SyncOperation.UPDATE
                )
                
                # Update progress
                for result in results:
                    progress.items_processed += 1
                    if result.success:
                        progress.items_successful += 1
                    else:
                        progress.items_failed += 1
                        if result.error_message:
                            progress.errors.append(
                                f"Product {result.entity_id}: {result.error_message}"
                            )
                
                # Update progress percentage
                progress.progress_percentage = min(
                    (progress.items_processed / progress.items_total) * 100, 100
                )
                
                self.logger.info(
                    f"Job {job_id}: {progress.items_processed}/{progress.items_total} "
                    f"({progress.progress_percentage:.1f}%)"
                )
    
    async def _execute_incremental_sync(self, job_id: str, request: SyncJobRequest):
        """Execute an incremental sync of modified products."""
        progress = self.active_jobs[job_id]
        progress.current_stage = "Finding modified products"
        
        # Get since parameter from request
        since_hours = request.parameters.get("since_hours", 24)
        since = datetime.utcnow() - timedelta(hours=since_hours)
        
        # Execute incremental sync
        results = await self.sync_engine.incremental_sync(since=since)
        
        # Process results
        product_results = results.get("products", [])
        progress.items_total = len(product_results)
        
        for result in product_results:
            progress.items_processed += 1
            if result.success:
                progress.items_successful += 1
            else:
                progress.items_failed += 1
                if result.error_message:
                    progress.errors.append(
                        f"Product {result.entity_id}: {result.error_message}"
                    )
        
        progress.progress_percentage = 100.0
        progress.current_stage = "Incremental sync completed"
    
    async def _execute_product_sync(self, job_id: str, request: SyncJobRequest):
        """Execute sync for specific products."""
        progress = self.active_jobs[job_id]
        progress.current_stage = "Syncing specified products"
        
        # Get product IDs from parameters
        product_ids = request.parameters.get("product_ids", [])
        
        if not product_ids:
            progress.warnings.append("No product IDs specified")
            return
        
        progress.items_total = len(product_ids)
        
        # Execute sync
        results = await self.sync_engine.batch_sync_products(
            product_ids, SyncOperation.UPDATE
        )
        
        # Process results
        for result in results:
            progress.items_processed += 1
            if result.success:
                progress.items_successful += 1
            else:
                progress.items_failed += 1
                if result.error_message:
                    progress.errors.append(
                        f"Product {result.entity_id}: {result.error_message}"
                    )
        
        progress.progress_percentage = 100.0
    
    async def _execute_category_sync(self, job_id: str, request: SyncJobRequest):
        """Execute category synchronization (collections in Shopify)."""
        progress = self.active_jobs[job_id]
        progress.current_stage = "Syncing categories (collections)"
        
        # TODO: Implement category/collection sync
        # This would involve creating/updating Shopify collections
        # based on the category hierarchy in the database
        
        progress.warnings.append("Category sync not yet implemented")
        progress.progress_percentage = 100.0
    
    def configure_conflict_resolution(self, strategy: ConflictResolution,
                                    auto_resolve: bool = True):
        """Configure conflict resolution strategy."""
        self.sync_engine.conflict_resolution_strategy = strategy
        self.sync_engine.auto_resolve_conflicts = auto_resolve
        
        self.logger.info(f"Configured conflict resolution: {strategy.value}, auto: {auto_resolve}")
    
    def enable_bidirectional_sync(self, enabled: bool = True):
        """Enable or disable bidirectional synchronization."""
        self.sync_engine.enable_bidirectional_sync = enabled
        
        self.logger.info(f"Bidirectional sync: {'enabled' if enabled else 'disabled'}")
    
    def get_conflicts(self) -> List[Dict[str, Any]]:
        """Get pending conflicts that need resolution."""
        conflicts = self.sync_engine.conflict_queue
        
        return [
            {
                "id": conflict.id,
                "entity_type": conflict.entity_type,
                "entity_id": conflict.entity_id,
                "field_name": conflict.field_name,
                "local_value": conflict.local_value,
                "shopify_value": conflict.shopify_value,
                "resolution_strategy": conflict.resolution_strategy.value,
                "created_at": conflict.created_at.isoformat(),
                "resolved_at": conflict.resolved_at.isoformat() if conflict.resolved_at else None,
                "resolved_value": conflict.resolved_value
            }
            for conflict in conflicts
        ]
    
    def resolve_conflict(self, conflict_id: str, resolution_value: Any) -> bool:
        """Manually resolve a conflict."""
        for conflict in self.sync_engine.conflict_queue:
            if conflict.id == conflict_id:
                conflict.resolved_value = resolution_value
                conflict.resolved_at = datetime.utcnow()
                self.sync_engine.conflict_queue.remove(conflict)
                self.sync_engine.metrics.record_conflict(resolved=True)
                
                self.logger.info(f"Manually resolved conflict {conflict_id}")
                return True
        
        return False