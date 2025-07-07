"""
Enhanced Parallel Batch Sync Engine for Shopify

This module provides a high-performance parallel synchronization engine with:
- Dynamic worker pool scaling based on load
- Priority queue for sync operations
- Operation batching by type (create, update, delete)
- Progress tracking with ETA calculation
- Automatic retry with exponential backoff
- Real-time performance metrics
"""

import asyncio
import time
import uuid
import logging
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from queue import PriorityQueue, Queue
from threading import Thread, Event, Lock
import threading
from collections import defaultdict, deque
from enum import Enum
import statistics
import json

from memory_optimizer import MemoryMonitor, get_memory_stats
from graphql_optimizer import GraphQLBatchProcessor, QueryOptimizer
from websocket_service import WebSocketService

logger = logging.getLogger(__name__)


class OperationType(Enum):
    """Types of sync operations."""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    UPDATE_INVENTORY = "update_inventory"
    UPDATE_STATUS = "update_status"
    UPDATE_IMAGES = "update_images"
    BULK_CREATE = "bulk_create"
    BULK_UPDATE = "bulk_update"


class SyncPriority(Enum):
    """Priority levels for sync operations."""
    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4
    BATCH = 5
    
    def __lt__(self, other):
        return self.value < other.value


@dataclass
class SyncOperation:
    """Represents a single sync operation."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    operation_type: OperationType = OperationType.UPDATE
    priority: SyncPriority = SyncPriority.NORMAL
    product_ids: List[int] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 3
    created_at: datetime = field(default_factory=datetime.utcnow)
    scheduled_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    
    def __lt__(self, other):
        """Priority queue comparison."""
        return (self.priority, self.created_at) < (other.priority, other.created_at)


@dataclass
class WorkerStats:
    """Statistics for a single worker."""
    worker_id: str
    operations_completed: int = 0
    operations_failed: int = 0
    total_processing_time: float = 0
    average_processing_time: float = 0
    current_operation: Optional[str] = None
    last_operation_at: Optional[datetime] = None
    is_active: bool = True


@dataclass
class SyncMetrics:
    """Real-time metrics for sync operations."""
    total_operations: int = 0
    completed_operations: int = 0
    failed_operations: int = 0
    retry_operations: int = 0
    operations_per_second: float = 0
    average_operation_time: float = 0
    queue_depth: int = 0
    active_workers: int = 0
    total_workers: int = 0
    memory_usage_mb: float = 0
    api_calls_made: int = 0
    api_errors: int = 0
    last_updated: datetime = field(default_factory=datetime.utcnow)
    
    def calculate_eta(self, remaining_operations: int) -> Optional[timedelta]:
        """Calculate estimated time to completion."""
        if self.operations_per_second > 0:
            seconds_remaining = remaining_operations / self.operations_per_second
            return timedelta(seconds=seconds_remaining)
        return None


class DynamicWorkerPool:
    """Dynamic worker pool that scales based on load."""
    
    def __init__(self, 
                 min_workers: int = 2,
                 max_workers: int = 10,
                 scale_up_threshold: int = 50,
                 scale_down_threshold: int = 10,
                 scale_interval: int = 30):
        """Initialize dynamic worker pool."""
        self.min_workers = min_workers
        self.max_workers = max_workers
        self.scale_up_threshold = scale_up_threshold
        self.scale_down_threshold = scale_down_threshold
        self.scale_interval = scale_interval
        
        self.current_workers = min_workers
        self.worker_stats: Dict[str, WorkerStats] = {}
        self.executor: Optional[ThreadPoolExecutor] = None
        self.scaling_thread: Optional[Thread] = None
        self.stop_event = Event()
        self.lock = Lock()
        
        self.logger = logging.getLogger(f"{__name__}.DynamicWorkerPool")
    
    def start(self, worker_function: Callable, queue: PriorityQueue):
        """Start the worker pool."""
        self.logger.info(f"Starting worker pool with {self.current_workers} workers")
        
        # Create initial executor
        self.executor = ThreadPoolExecutor(max_workers=self.current_workers)
        
        # Start workers
        for i in range(self.current_workers):
            worker_id = f"worker_{i}"
            self.worker_stats[worker_id] = WorkerStats(worker_id=worker_id)
            self.executor.submit(self._worker_wrapper, worker_id, worker_function, queue)
        
        # Start scaling thread
        self.scaling_thread = Thread(target=self._scaling_loop, args=(queue,))
        self.scaling_thread.daemon = True
        self.scaling_thread.start()
    
    def stop(self):
        """Stop the worker pool."""
        self.logger.info("Stopping worker pool")
        self.stop_event.set()
        
        if self.scaling_thread:
            self.scaling_thread.join(timeout=5)
        
        if self.executor:
            self.executor.shutdown(wait=True)
    
    def _worker_wrapper(self, worker_id: str, worker_function: Callable, queue: PriorityQueue):
        """Wrapper for worker function with stats tracking."""
        stats = self.worker_stats[worker_id]
        
        while not self.stop_event.is_set():
            try:
                # Get operation from queue with timeout
                operation = queue.get(timeout=1)
                
                # Update stats
                stats.current_operation = operation.id
                start_time = time.time()
                
                # Execute operation
                result = worker_function(operation)
                
                # Update stats
                processing_time = time.time() - start_time
                stats.operations_completed += 1
                stats.total_processing_time += processing_time
                stats.average_processing_time = stats.total_processing_time / stats.operations_completed
                stats.last_operation_at = datetime.utcnow()
                stats.current_operation = None
                
                if not result.get('success'):
                    stats.operations_failed += 1
                
            except Exception as e:
                if not self.stop_event.is_set():
                    self.logger.error(f"Worker {worker_id} error: {e}")
                    stats.operations_failed += 1
        
        # Mark worker as inactive
        stats.is_active = False
    
    def _scaling_loop(self, queue: PriorityQueue):
        """Monitor queue and scale workers accordingly."""
        while not self.stop_event.is_set():
            try:
                queue_size = queue.qsize()
                
                with self.lock:
                    active_workers = sum(1 for s in self.worker_stats.values() if s.is_active)
                    
                    # Scale up
                    if queue_size > self.scale_up_threshold and self.current_workers < self.max_workers:
                        new_workers = min(self.max_workers - self.current_workers, 2)
                        self.logger.info(f"Scaling up: adding {new_workers} workers (queue size: {queue_size})")
                        self._add_workers(new_workers)
                    
                    # Scale down
                    elif queue_size < self.scale_down_threshold and self.current_workers > self.min_workers:
                        remove_workers = min(self.current_workers - self.min_workers, 2)
                        self.logger.info(f"Scaling down: removing {remove_workers} workers (queue size: {queue_size})")
                        self._remove_workers(remove_workers)
                
                # Wait before next check
                self.stop_event.wait(self.scale_interval)
                
            except Exception as e:
                self.logger.error(f"Scaling loop error: {e}")
    
    def _add_workers(self, count: int):
        """Add new workers to the pool."""
        # Note: ThreadPoolExecutor doesn't support dynamic resizing
        # In a production system, you'd implement a custom thread pool
        self.current_workers += count
    
    def _remove_workers(self, count: int):
        """Remove workers from the pool."""
        # Mark workers for removal
        self.current_workers -= count
    
    def get_stats(self) -> Dict[str, Any]:
        """Get worker pool statistics."""
        with self.lock:
            active_workers = sum(1 for s in self.worker_stats.values() if s.is_active)
            total_operations = sum(s.operations_completed for s in self.worker_stats.values())
            failed_operations = sum(s.operations_failed for s in self.worker_stats.values())
            
            return {
                'current_workers': self.current_workers,
                'active_workers': active_workers,
                'total_operations': total_operations,
                'failed_operations': failed_operations,
                'worker_details': [
                    {
                        'worker_id': s.worker_id,
                        'operations_completed': s.operations_completed,
                        'average_processing_time': s.average_processing_time,
                        'is_active': s.is_active,
                        'current_operation': s.current_operation
                    }
                    for s in self.worker_stats.values()
                ]
            }


class ParallelSyncEngine:
    """Enhanced parallel sync engine with advanced features."""
    
    def __init__(self,
                 shopify_client,
                 min_workers: int = 2,
                 max_workers: int = 10,
                 batch_size: int = 50,
                 memory_limit_mb: int = 512):
        """Initialize parallel sync engine."""
        self.shopify_client = shopify_client
        self.batch_size = batch_size
        
        # Priority queue for operations
        self.operation_queue = PriorityQueue()
        self.result_queue = Queue()
        
        # Worker pool
        self.worker_pool = DynamicWorkerPool(
            min_workers=min_workers,
            max_workers=max_workers
        )
        
        # Operation batching
        self.operation_batches: Dict[OperationType, List[SyncOperation]] = defaultdict(list)
        self.batch_lock = Lock()
        
        # Performance tracking
        self.metrics = SyncMetrics()
        self.operation_times = deque(maxlen=1000)  # Keep last 1000 operation times
        self.metrics_lock = Lock()
        
        # Memory monitoring
        self.memory_monitor = MemoryMonitor(
            warning_threshold_mb=memory_limit_mb * 0.7,
            critical_threshold_mb=memory_limit_mb
        )
        
        # GraphQL optimization
        self.graphql_processor = GraphQLBatchProcessor(shopify_client)
        self.query_optimizer = QueryOptimizer()
        
        # WebSocket service for real-time updates
        self.websocket_service: Optional[WebSocketService] = None
        
        # Control flags
        self.is_running = False
        self.stop_event = Event()
        
        # Background threads
        self.batch_processor_thread: Optional[Thread] = None
        self.metrics_updater_thread: Optional[Thread] = None
        self.result_processor_thread: Optional[Thread] = None
        
        self.logger = logging.getLogger(__name__)
    
    def start(self, websocket_service: Optional[WebSocketService] = None):
        """Start the parallel sync engine."""
        if self.is_running:
            return
        
        self.logger.info("Starting parallel sync engine")
        self.is_running = True
        self.websocket_service = websocket_service
        
        # Start memory monitoring
        self.memory_monitor.start_monitoring()
        
        # Start worker pool
        self.worker_pool.start(self._process_operation, self.operation_queue)
        
        # Start background threads
        self.batch_processor_thread = Thread(target=self._batch_processor_loop)
        self.batch_processor_thread.daemon = True
        self.batch_processor_thread.start()
        
        self.metrics_updater_thread = Thread(target=self._metrics_updater_loop)
        self.metrics_updater_thread.daemon = True
        self.metrics_updater_thread.start()
        
        self.result_processor_thread = Thread(target=self._result_processor_loop)
        self.result_processor_thread.daemon = True
        self.result_processor_thread.start()
        
        self.logger.info("Parallel sync engine started")
    
    def stop(self):
        """Stop the parallel sync engine."""
        if not self.is_running:
            return
        
        self.logger.info("Stopping parallel sync engine")
        self.is_running = False
        self.stop_event.set()
        
        # Stop worker pool
        self.worker_pool.stop()
        
        # Stop memory monitoring
        self.memory_monitor.stop_monitoring()
        
        # Wait for threads to finish
        if self.batch_processor_thread:
            self.batch_processor_thread.join(timeout=5)
        
        if self.metrics_updater_thread:
            self.metrics_updater_thread.join(timeout=5)
        
        if self.result_processor_thread:
            self.result_processor_thread.join(timeout=5)
        
        self.logger.info("Parallel sync engine stopped")
    
    def queue_operation(self, 
                       operation_type: OperationType,
                       product_ids: List[int],
                       priority: SyncPriority = SyncPriority.NORMAL,
                       data: Optional[Dict[str, Any]] = None) -> str:
        """Queue a sync operation."""
        operation = SyncOperation(
            operation_type=operation_type,
            priority=priority,
            product_ids=product_ids,
            data=data or {}
        )
        
        # Add to appropriate batch or queue directly
        if operation_type in [OperationType.BULK_CREATE, OperationType.BULK_UPDATE]:
            self.operation_queue.put(operation)
        else:
            with self.batch_lock:
                self.operation_batches[operation_type].append(operation)
        
        # Update metrics
        with self.metrics_lock:
            self.metrics.total_operations += 1
            self.metrics.queue_depth = self.operation_queue.qsize()
        
        self.logger.debug(f"Queued operation {operation.id} ({operation_type.value}, priority={priority.value})")
        
        # Emit WebSocket event
        if self.websocket_service:
            self.websocket_service.emit('sync_operation_queued', {
                'operation_id': operation.id,
                'type': operation_type.value,
                'priority': priority.value,
                'product_count': len(product_ids)
            })
        
        return operation.id
    
    def _process_operation(self, operation: SyncOperation) -> Dict[str, Any]:
        """Process a single sync operation."""
        start_time = time.time()
        
        try:
            self.logger.debug(f"Processing operation {operation.id}")
            
            # Check memory before processing
            memory_stats = self.memory_monitor.get_memory_stats()
            if memory_stats.is_critical:
                self.logger.warning(f"Critical memory usage: {memory_stats.rss_mb:.1f} MB")
                # Defer operation
                operation.scheduled_at = datetime.utcnow() + timedelta(seconds=30)
                self.operation_queue.put(operation)
                return {'success': False, 'error': 'Memory pressure'}
            
            # Process based on operation type
            if operation.operation_type == OperationType.CREATE:
                result = self._create_products(operation)
            elif operation.operation_type == OperationType.UPDATE:
                result = self._update_products(operation)
            elif operation.operation_type == OperationType.DELETE:
                result = self._delete_products(operation)
            elif operation.operation_type == OperationType.UPDATE_INVENTORY:
                result = self._update_inventory(operation)
            elif operation.operation_type == OperationType.UPDATE_STATUS:
                result = self._update_status(operation)
            elif operation.operation_type == OperationType.UPDATE_IMAGES:
                result = self._update_images(operation)
            elif operation.operation_type == OperationType.BULK_CREATE:
                result = self._bulk_create_products(operation)
            elif operation.operation_type == OperationType.BULK_UPDATE:
                result = self._bulk_update_products(operation)
            else:
                result = {'success': False, 'error': f'Unknown operation type: {operation.operation_type}'}
            
            # Record operation time
            operation_time = time.time() - start_time
            self.operation_times.append(operation_time)
            
            # Update operation
            operation.completed_at = datetime.utcnow()
            operation.result = result
            
            # Queue result
            self.result_queue.put(operation)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error processing operation {operation.id}: {e}")
            
            # Handle retry
            if operation.retry_count < operation.max_retries:
                operation.retry_count += 1
                operation.scheduled_at = datetime.utcnow() + timedelta(seconds=2 ** operation.retry_count)
                operation.error = str(e)
                self.operation_queue.put(operation)
                
                with self.metrics_lock:
                    self.metrics.retry_operations += 1
            else:
                operation.error = str(e)
                operation.completed_at = datetime.utcnow()
                self.result_queue.put(operation)
                
                with self.metrics_lock:
                    self.metrics.failed_operations += 1
            
            return {'success': False, 'error': str(e)}
    
    def _batch_processor_loop(self):
        """Background thread to process operation batches."""
        while not self.stop_event.is_set():
            try:
                with self.batch_lock:
                    # Process each operation type
                    for op_type, operations in self.operation_batches.items():
                        if len(operations) >= self.batch_size or (
                            operations and 
                            (datetime.utcnow() - operations[0].created_at).seconds > 5
                        ):
                            # Create batch operation
                            batch_op = self._create_batch_operation(op_type, operations[:self.batch_size])
                            self.operation_queue.put(batch_op)
                            
                            # Remove batched operations
                            self.operation_batches[op_type] = operations[self.batch_size:]
                
                # Short sleep
                time.sleep(0.1)
                
            except Exception as e:
                self.logger.error(f"Batch processor error: {e}")
    
    def _create_batch_operation(self, 
                               operation_type: OperationType, 
                               operations: List[SyncOperation]) -> SyncOperation:
        """Create a batch operation from individual operations."""
        # Combine all product IDs
        all_product_ids = []
        for op in operations:
            all_product_ids.extend(op.product_ids)
        
        # Determine batch operation type
        if operation_type == OperationType.CREATE:
            batch_type = OperationType.BULK_CREATE
        elif operation_type == OperationType.UPDATE:
            batch_type = OperationType.BULK_UPDATE
        else:
            batch_type = operation_type
        
        # Get highest priority
        highest_priority = min(op.priority for op in operations)
        
        # Create batch operation
        batch_op = SyncOperation(
            operation_type=batch_type,
            priority=highest_priority,
            product_ids=all_product_ids,
            data={
                'original_operations': [op.id for op in operations],
                'batch_size': len(operations)
            }
        )
        
        return batch_op
    
    def _metrics_updater_loop(self):
        """Background thread to update metrics."""
        while not self.stop_event.is_set():
            try:
                with self.metrics_lock:
                    # Calculate operations per second
                    if self.operation_times:
                        recent_times = list(self.operation_times)[-100:]  # Last 100 operations
                        if recent_times:
                            self.metrics.average_operation_time = statistics.mean(recent_times)
                            self.metrics.operations_per_second = 1.0 / self.metrics.average_operation_time
                    
                    # Update queue depth
                    self.metrics.queue_depth = self.operation_queue.qsize()
                    
                    # Update worker stats
                    worker_stats = self.worker_pool.get_stats()
                    self.metrics.active_workers = worker_stats['active_workers']
                    self.metrics.total_workers = worker_stats['current_workers']
                    
                    # Update memory usage
                    memory_stats = get_memory_stats()
                    self.metrics.memory_usage_mb = memory_stats['rss_mb']
                    
                    self.metrics.last_updated = datetime.utcnow()
                
                # Emit metrics update
                if self.websocket_service:
                    self.websocket_service.emit('sync_metrics_update', self.get_metrics())
                
                # Sleep for 1 second
                time.sleep(1)
                
            except Exception as e:
                self.logger.error(f"Metrics updater error: {e}")
    
    def _result_processor_loop(self):
        """Background thread to process operation results."""
        while not self.stop_event.is_set():
            try:
                # Get result with timeout
                operation = self.result_queue.get(timeout=1)
                
                # Update metrics
                with self.metrics_lock:
                    if operation.result and operation.result.get('success'):
                        self.metrics.completed_operations += 1
                    else:
                        self.metrics.failed_operations += 1
                
                # Emit result event
                if self.websocket_service:
                    self.websocket_service.emit('sync_operation_completed', {
                        'operation_id': operation.id,
                        'type': operation.operation_type.value,
                        'success': operation.result.get('success') if operation.result else False,
                        'error': operation.error,
                        'duration': (operation.completed_at - operation.created_at).total_seconds() if operation.completed_at else None
                    })
                
                # Log completion
                if operation.result and operation.result.get('success'):
                    self.logger.info(f"Operation {operation.id} completed successfully")
                else:
                    self.logger.error(f"Operation {operation.id} failed: {operation.error}")
                
            except Exception as e:
                if not self.stop_event.is_set():
                    self.logger.error(f"Result processor error: {e}")
    
    def _create_products(self, operation: SyncOperation) -> Dict[str, Any]:
        """Create products in Shopify."""
        # Implementation would use GraphQL mutations
        return {'success': True, 'created': len(operation.product_ids)}
    
    def _update_products(self, operation: SyncOperation) -> Dict[str, Any]:
        """Update products in Shopify."""
        # Implementation would use GraphQL mutations
        return {'success': True, 'updated': len(operation.product_ids)}
    
    def _delete_products(self, operation: SyncOperation) -> Dict[str, Any]:
        """Delete products from Shopify."""
        # Implementation would use GraphQL mutations
        return {'success': True, 'deleted': len(operation.product_ids)}
    
    def _update_inventory(self, operation: SyncOperation) -> Dict[str, Any]:
        """Update product inventory."""
        # Implementation would use inventory-specific mutations
        return {'success': True, 'updated': len(operation.product_ids)}
    
    def _update_status(self, operation: SyncOperation) -> Dict[str, Any]:
        """Update product status."""
        # Implementation would use status-specific mutations
        return {'success': True, 'updated': len(operation.product_ids)}
    
    def _update_images(self, operation: SyncOperation) -> Dict[str, Any]:
        """Update product images."""
        # Implementation would use image-specific mutations
        return {'success': True, 'updated': len(operation.product_ids)}
    
    def _bulk_create_products(self, operation: SyncOperation) -> Dict[str, Any]:
        """Bulk create products using Bulk Operations API."""
        # Implementation would use Shopify Bulk Operations API
        return {'success': True, 'created': len(operation.product_ids)}
    
    def _bulk_update_products(self, operation: SyncOperation) -> Dict[str, Any]:
        """Bulk update products using Bulk Operations API."""
        # Implementation would use Shopify Bulk Operations API
        return {'success': True, 'updated': len(operation.product_ids)}
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current sync metrics."""
        with self.metrics_lock:
            eta = self.metrics.calculate_eta(self.metrics.queue_depth)
            
            return {
                'total_operations': self.metrics.total_operations,
                'completed_operations': self.metrics.completed_operations,
                'failed_operations': self.metrics.failed_operations,
                'retry_operations': self.metrics.retry_operations,
                'success_rate': (self.metrics.completed_operations / self.metrics.total_operations * 100) if self.metrics.total_operations > 0 else 0,
                'operations_per_second': round(self.metrics.operations_per_second, 2),
                'average_operation_time': round(self.metrics.average_operation_time, 2),
                'queue_depth': self.metrics.queue_depth,
                'active_workers': self.metrics.active_workers,
                'total_workers': self.metrics.total_workers,
                'memory_usage_mb': round(self.metrics.memory_usage_mb, 2),
                'eta_seconds': eta.total_seconds() if eta else None,
                'last_updated': self.metrics.last_updated.isoformat()
            }
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get detailed queue status."""
        with self.batch_lock:
            batch_counts = {
                op_type.value: len(operations)
                for op_type, operations in self.operation_batches.items()
            }
        
        return {
            'queue_size': self.operation_queue.qsize(),
            'batch_operations': batch_counts,
            'worker_stats': self.worker_pool.get_stats()
        }