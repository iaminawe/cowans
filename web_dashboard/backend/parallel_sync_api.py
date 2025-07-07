"""
Parallel Sync API Endpoints

Provides FastAPI endpoints for the enhanced parallel batch sync system.
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from database import get_db
from schemas import (
    ParallelSyncConfigSchema, SyncOperationSchema, 
    SyncMetricsSchema, PerformanceReportSchema
)
from auth import get_current_user
from models import User
from services.shopify_sync_service import ShopifySyncService, SyncConfiguration, SyncMode
from parallel_sync_engine import ParallelSyncEngine, OperationType, SyncPriority
from sync_performance_monitor import SyncPerformanceMonitor
from websocket_service import WebSocketService

router = APIRouter(prefix="/api/v1/parallel-sync", tags=["parallel-sync"])

# Global instances
parallel_engine: Optional[ParallelSyncEngine] = None
performance_monitor: Optional[SyncPerformanceMonitor] = None
websocket_service: Optional[WebSocketService] = None


def get_parallel_engine() -> ParallelSyncEngine:
    """Get or create parallel sync engine instance."""
    global parallel_engine
    if not parallel_engine:
        raise HTTPException(status_code=503, detail="Parallel sync engine not initialized")
    return parallel_engine


def get_performance_monitor() -> SyncPerformanceMonitor:
    """Get or create performance monitor instance."""
    global performance_monitor
    if not performance_monitor:
        performance_monitor = SyncPerformanceMonitor()
    return performance_monitor


@router.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    global websocket_service
    # WebSocket service would be initialized by the main app
    pass


@router.post("/start")
async def start_parallel_sync(
    config: ParallelSyncConfigSchema,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Start a new parallel sync operation."""
    global parallel_engine
    
    try:
        # Convert schema to config
        sync_config = SyncConfiguration(
            mode=SyncMode(config["sync_mode"]),
            batch_size=config["batch_size"],
            max_workers=config["max_workers"]
        )
        
        # Create sync service
        sync_service = ShopifySyncService(db)
        
        # Create sync job
        sync_id = sync_service.create_sync_job(
            config=sync_config,
            product_filters={}
        )
        
        # Initialize parallel engine if needed
        if not parallel_engine:
            # Get Shopify credentials from environment or config
            shop_url = os.environ.get("SHOPIFY_SHOP_URL", "")
            access_token = os.environ.get("SHOPIFY_ACCESS_TOKEN", "")
            
            if not shop_url or not access_token:
                raise HTTPException(
                    status_code=400,
                    detail="Shopify credentials not configured"
                )
            
            # Create a simple shopify client wrapper
            class ShopifyClient:
                def __init__(self, shop_url, access_token):
                    self.shop_url = shop_url
                    self.access_token = access_token
            
            shopify_client = ShopifyClient(shop_url, access_token)
            
            parallel_engine = ParallelSyncEngine(
                shopify_client=shopify_client,
                min_workers=config["min_workers"],
                max_workers=config["max_workers"],
                batch_size=config["batch_size"],
                memory_limit_mb=config["memory_limit_mb"]
            )
            
            await parallel_engine.start(websocket_service)
        
        # Start sync in background
        async def run_sync():
            try:
                result = await sync_service.execute_sync(
                    sync_id=sync_id,
                    websocket_service=websocket_service
                )
                return result
            except Exception as e:
                logger.error(f"Sync failed: {e}")
                raise
        
        background_tasks.add_task(run_sync)
        
        return {
            "sync_id": sync_id,
            "status": "started",
            "config": config,
            "message": "Parallel sync operation started"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/queue-operation")
async def queue_sync_operation(
    operation: SyncOperationSchema,
    current_user: User = Depends(get_current_user)
):
    """Queue a specific sync operation."""
    engine = get_parallel_engine()
    monitor = get_performance_monitor()
    
    try:
        # Convert operation type
        op_type = OperationType(operation["operation_type"])
        priority = SyncPriority[operation["priority"].upper()]
        
        # Queue the operation
        operation_id = engine.queue_operation(
            operation_type=op_type,
            product_ids=operation["product_ids"],
            priority=priority,
            data=operation.get("data", {})
        )
        
        # Start monitoring
        monitor.start_operation(operation_id)
        
        return {
            "operation_id": operation_id,
            "status": "queued",
            "queue_position": engine.get_queue_status()["queue_size"]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics", response_model=SyncMetricsSchema)
async def get_sync_metrics(
    current_user: User = Depends(get_current_user)
):
    """Get current sync performance metrics."""
    engine = get_parallel_engine()
    monitor = get_performance_monitor()
    
    try:
        # Get engine metrics
        engine_metrics = engine.get_metrics()
        
        # Get performance stats
        perf_stats = monitor.get_current_stats()
        
        # Combine metrics
        metrics = {
            **engine_metrics,
            **perf_stats
        }
        
        return metrics
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/queue-status")
async def get_queue_status(
    current_user: User = Depends(get_current_user)
):
    """Get detailed queue status."""
    engine = get_parallel_engine()
    
    try:
        status = engine.get_queue_status()
        return status
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance-report", response_model=PerformanceReportSchema)
async def get_performance_report(
    hours: int = 1,
    current_user: User = Depends(get_current_user)
):
    """Get performance report for the specified time period."""
    monitor = get_performance_monitor()
    
    try:
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)
        
        report = monitor.get_performance_report(start_time, end_time)
        
        return {
            "period_start": report.period_start,
            "period_end": report.period_end,
            "total_operations": report.total_operations,
            "successful_operations": report.successful_operations,
            "failed_operations": report.failed_operations,
            "average_operation_time": report.average_operation_time,
            "p95_operation_time": report.p95_operation_time,
            "p99_operation_time": report.p99_operation_time,
            "operations_per_second": report.operations_per_second,
            "average_queue_depth": report.average_queue_depth,
            "peak_queue_depth": report.peak_queue_depth,
            "average_memory_usage": report.average_memory_usage,
            "peak_memory_usage": report.peak_memory_usage,
            "average_cpu_usage": report.average_cpu_usage,
            "api_calls": report.api_calls,
            "api_errors": report.api_errors,
            "cache_hits": report.cache_hits,
            "cache_misses": report.cache_misses
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/predict-duration")
async def predict_sync_duration(
    operation_count: int,
    current_user: User = Depends(get_current_user)
):
    """Predict sync duration for a given number of operations."""
    monitor = get_performance_monitor()
    
    try:
        prediction = monitor.predict_sync_duration(operation_count)
        return prediction
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts")
async def get_performance_alerts(
    active_only: bool = True,
    current_user: User = Depends(get_current_user)
):
    """Get performance alerts."""
    monitor = get_performance_monitor()
    
    try:
        if active_only:
            alerts = monitor.get_active_alerts()
        else:
            alerts = monitor.get_alert_history(hours=24)
        
        return {
            "alerts": [
                {
                    "id": alert.id,
                    "level": alert.level.value,
                    "metric_type": alert.metric_type.value,
                    "message": alert.message,
                    "threshold_value": alert.threshold_value,
                    "actual_value": alert.actual_value,
                    "timestamp": alert.timestamp.isoformat(),
                    "resolved": alert.resolved,
                    "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None
                }
                for alert in alerts
            ],
            "total": len(alerts)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str,
    current_user: User = Depends(get_current_user)
):
    """Resolve a performance alert."""
    monitor = get_performance_monitor()
    
    try:
        monitor.resolve_alert(alert_id)
        return {"status": "resolved", "alert_id": alert_id}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop")
async def stop_parallel_sync(
    current_user: User = Depends(get_current_user)
):
    """Stop the parallel sync engine."""
    global parallel_engine
    
    if parallel_engine:
        engine = parallel_engine
        parallel_engine = None
        
        engine.stop()
        
        return {
            "status": "stopped",
            "final_metrics": engine.get_metrics()
        }
    else:
        return {"status": "not_running"}


# Error handlers
@router.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions."""
    logger.error(f"Unhandled exception: {exc}")
    return {
        "error": "Internal server error",
        "detail": str(exc) if settings.DEBUG else "An error occurred"
    }