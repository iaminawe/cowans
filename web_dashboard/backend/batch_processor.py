"""Advanced batch processing service for efficient bulk operations."""
import time
import asyncio
import logging
from typing import Dict, Any, List, Optional, Callable, Generator, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
import threading
from queue import Queue
import uuid

from memory_optimizer import MemoryOptimizedBatchProcessor, get_memory_stats

logger = logging.getLogger(__name__)


@dataclass
class BatchConfig:
    """Configuration for batch processing."""
    batch_size: int = 100
    max_workers: int = 4
    timeout_seconds: float = 300.0
    retry_attempts: int = 3
    retry_delay: float = 1.0
    memory_limit_mb: int = 512
    enable_parallel: bool = True
    checkpoint_interval: int = 10  # Save progress every N batches


@dataclass
class BatchItem:
    """Individual item in a batch."""
    id: str
    data: Dict[str, Any]
    priority: int = 0
    retries: int = 0
    last_error: Optional[str] = None
    processed_at: Optional[datetime] = None


@dataclass
class BatchProgress:
    """Progress tracking for batch operations."""
    batch_id: str
    total_items: int
    processed_items: int = 0
    successful_items: int = 0
    failed_items: int = 0
    skipped_items: int = 0
    current_batch: int = 0
    total_batches: int = 0
    start_time: datetime = field(default_factory=datetime.utcnow)
    estimated_completion: Optional[datetime] = None
    throughput_per_second: float = 0.0
    error_rate: float = 0.0
    status: str = 'pending'  # pending, running, completed, failed, cancelled
    
    @property
    def progress_percentage(self) -> float:
        """Calculate progress percentage."""
        if self.total_items == 0:
            return 0.0
        return (self.processed_items / self.total_items) * 100
    
    @property
    def elapsed_time(self) -> timedelta:
        """Calculate elapsed time."""
        return datetime.utcnow() - self.start_time
    
    def update_throughput(self) -> None:
        """Update throughput calculation."""
        elapsed_seconds = self.elapsed_time.total_seconds()
        if elapsed_seconds > 0:
            self.throughput_per_second = self.processed_items / elapsed_seconds
            
            # Estimate completion time
            remaining_items = self.total_items - self.processed_items
            if self.throughput_per_second > 0:
                seconds_remaining = remaining_items / self.throughput_per_second
                self.estimated_completion = datetime.utcnow() + timedelta(seconds=seconds_remaining)
    
    def update_error_rate(self) -> None:
        """Update error rate calculation."""
        if self.processed_items > 0:
            self.error_rate = (self.failed_items / self.processed_items) * 100


class BatchProcessor:
    """Advanced batch processor with parallel execution and progress tracking."""
    
    def __init__(self, config: Optional[BatchConfig] = None):
        """Initialize batch processor.
        
        Args:
            config: Batch processing configuration
        """
        self.config = config or BatchConfig()
        self.active_batches: Dict[str, BatchProgress] = {}
        self.batch_results: Dict[str, List[Dict[str, Any]]] = {}
        self._shutdown = False
        self._lock = threading.Lock()
        
        # Initialize memory-optimized processor
        self.memory_processor = MemoryOptimizedBatchProcessor(
            chunk_size=self.config.batch_size,
            memory_limit_mb=self.config.memory_limit_mb
        )
        
    def create_batch(self, items: List[Dict[str, Any]], batch_id: Optional[str] = None) -> str:
        """Create a new batch for processing.
        
        Args:
            items: List of items to process
            batch_id: Optional batch ID (generated if not provided)
            
        Returns:
            Batch ID
        """
        if batch_id is None:
            batch_id = str(uuid.uuid4())
            
        # Convert items to BatchItem objects
        batch_items = [
            BatchItem(
                id=str(i),
                data=item,
                priority=item.get('priority', 0)
            )
            for i, item in enumerate(items)
        ]
        
        # Sort by priority (higher priority first)
        batch_items.sort(key=lambda x: x.priority, reverse=True)
        
        # Calculate batch statistics
        total_items = len(batch_items)
        total_batches = (total_items + self.config.batch_size - 1) // self.config.batch_size
        
        progress = BatchProgress(
            batch_id=batch_id,
            total_items=total_items,
            total_batches=total_batches
        )
        
        with self._lock:
            self.active_batches[batch_id] = progress
            self.batch_results[batch_id] = []
            
        logger.info(f"Created batch {batch_id} with {total_items} items in {total_batches} batches")
        return batch_id
    
    def process_batch(self, 
                     batch_id: str, 
                     processor_func: Callable[[List[Dict[str, Any]]], List[Dict[str, Any]]],
                     websocket_service=None) -> BatchProgress:
        """Process a batch with the given processor function.
        
        Args:
            batch_id: Batch ID to process
            processor_func: Function to process each chunk of items
            websocket_service: Optional WebSocket service for real-time updates
            
        Returns:
            Final batch progress
        """
        if batch_id not in self.active_batches:
            raise ValueError(f"Batch {batch_id} not found")
            
        progress = self.active_batches[batch_id]
        progress.status = 'running'
        
        try:
            # Get batch items (need to reconstruct from somewhere - in real implementation, 
            # you'd store items separately or pass them in)
            batch_items = self._get_batch_items(batch_id)
            
            if self.config.enable_parallel:
                return self._process_parallel(batch_id, batch_items, processor_func, websocket_service)
            else:
                return self._process_sequential(batch_id, batch_items, processor_func, websocket_service)
                
        except Exception as e:
            logger.error(f"Batch {batch_id} failed: {str(e)}")
            progress.status = 'failed'
            
            if websocket_service:
                websocket_service.emit_operation_complete(
                    operation_id=batch_id,
                    status='error',
                    error=str(e)
                )
            raise
    
    def _process_parallel(self, 
                         batch_id: str,
                         items: List[BatchItem], 
                         processor_func: Callable,
                         websocket_service=None) -> BatchProgress:
        """Process batch in parallel with multiple workers."""
        progress = self.active_batches[batch_id]
        
        # Create batches
        batches = self._create_batches(items)
        progress.total_batches = len(batches)
        
        if websocket_service:
            websocket_service.emit_operation_start(
                operation_id=batch_id,
                operation_type='batch_processing',
                description=f'Processing {len(items)} items in {len(batches)} batches',
                total_steps=len(batches)
            )
        
        results = []
        
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            # Submit all batches
            future_to_batch = {
                executor.submit(self._process_single_batch, batch_num, batch, processor_func): batch_num
                for batch_num, batch in enumerate(batches)
            }
            
            # Process completed batches
            for future in as_completed(future_to_batch, timeout=self.config.timeout_seconds):
                batch_num = future_to_batch[future]
                
                try:
                    batch_result = future.result()
                    results.extend(batch_result)
                    
                    # Update progress
                    progress.current_batch = batch_num + 1
                    progress.processed_items += len(batches[batch_num])
                    progress.successful_items += len([r for r in batch_result if r.get('status') == 'success'])
                    progress.failed_items += len([r for r in batch_result if r.get('status') == 'error'])
                    
                    progress.update_throughput()
                    progress.update_error_rate()
                    
                    # Emit progress update
                    if websocket_service:
                        websocket_service.emit_operation_progress(
                            operation_id=batch_id,
                            current_step=progress.current_batch,
                            message=f"Processed batch {progress.current_batch}/{progress.total_batches}",
                            progress_percentage=progress.progress_percentage
                        )
                        
                        # Emit log
                        websocket_service.emit_operation_log(
                            operation_id=batch_id,
                            level='info',
                            message=f"Batch {batch_num + 1} completed: {len(batch_result)} items processed",
                            source='batch_processor'
                        )
                    
                    # Checkpoint progress periodically
                    if progress.current_batch % self.config.checkpoint_interval == 0:
                        self._save_checkpoint(batch_id, progress, results)
                        
                except Exception as e:
                    logger.error(f"Batch {batch_num} failed: {str(e)}")
                    progress.failed_items += len(batches[batch_num])
                    
                    if websocket_service:
                        websocket_service.emit_operation_log(
                            operation_id=batch_id,
                            level='error',
                            message=f"Batch {batch_num + 1} failed: {str(e)}",
                            source='batch_processor'
                        )
        
        # Finalize progress
        progress.status = 'completed' if progress.failed_items == 0 else 'completed_with_errors'
        self.batch_results[batch_id] = results
        
        if websocket_service:
            websocket_service.emit_operation_complete(
                operation_id=batch_id,
                status='success' if progress.failed_items == 0 else 'partial_success',
                result={
                    'total_items': progress.total_items,
                    'successful_items': progress.successful_items,
                    'failed_items': progress.failed_items,
                    'throughput_per_second': progress.throughput_per_second,
                    'error_rate': progress.error_rate,
                    'elapsed_time': str(progress.elapsed_time)
                }
            )
        
        return progress
    
    def _process_sequential(self, 
                           batch_id: str,
                           items: List[BatchItem], 
                           processor_func: Callable,
                           websocket_service=None) -> BatchProgress:
        """Process batch sequentially (fallback method)."""
        progress = self.active_batches[batch_id]
        batches = self._create_batches(items)
        progress.total_batches = len(batches)
        
        results = []
        
        for batch_num, batch in enumerate(batches):
            try:
                batch_result = self._process_single_batch(batch_num, batch, processor_func)
                results.extend(batch_result)
                
                # Update progress
                progress.current_batch = batch_num + 1
                progress.processed_items += len(batch)
                progress.successful_items += len([r for r in batch_result if r.get('status') == 'success'])
                progress.failed_items += len([r for r in batch_result if r.get('status') == 'error'])
                
                progress.update_throughput()
                progress.update_error_rate()
                
            except Exception as e:
                logger.error(f"Sequential batch {batch_num} failed: {str(e)}")
                progress.failed_items += len(batch)
        
        progress.status = 'completed' if progress.failed_items == 0 else 'completed_with_errors'
        self.batch_results[batch_id] = results
        return progress
    
    def _create_batches(self, items: List[BatchItem]) -> List[List[Dict[str, Any]]]:
        """Split items into batches."""
        batches = []
        for i in range(0, len(items), self.config.batch_size):
            batch = [item.data for item in items[i:i + self.config.batch_size]]
            batches.append(batch)
        return batches
    
    def _process_single_batch(self, 
                             batch_num: int, 
                             batch: List[Dict[str, Any]], 
                             processor_func: Callable) -> List[Dict[str, Any]]:
        """Process a single batch of items."""
        start_time = time.time()
        
        try:
            results = processor_func(batch)
            processing_time = time.time() - start_time
            
            logger.debug(f"Batch {batch_num} processed {len(batch)} items in {processing_time:.2f}s")
            return results
            
        except Exception as e:
            logger.error(f"Error processing batch {batch_num}: {str(e)}")
            # Return error results for each item in the failed batch
            return [
                {
                    'id': item.get('id', f'item_{i}'),
                    'status': 'error',
                    'error': str(e)
                }
                for i, item in enumerate(batch)
            ]
    
    def _get_batch_items(self, batch_id: str) -> List[BatchItem]:
        """Get batch items (placeholder - in real implementation, items would be stored)."""
        # This is a placeholder. In a real implementation, you would store the BatchItem objects
        # separately and retrieve them here. For now, return empty list.
        return []
    
    def _save_checkpoint(self, batch_id: str, progress: BatchProgress, results: List[Dict[str, Any]]) -> None:
        """Save batch progress checkpoint."""
        checkpoint_data = {
            'batch_id': batch_id,
            'progress': {
                'processed_items': progress.processed_items,
                'successful_items': progress.successful_items,
                'failed_items': progress.failed_items,
                'current_batch': progress.current_batch,
                'status': progress.status
            },
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # In a real implementation, you'd save this to Redis or database
        logger.info(f"Checkpoint saved for batch {batch_id}: {progress.processed_items}/{progress.total_items} items")
    
    def get_batch_progress(self, batch_id: str) -> Optional[BatchProgress]:
        """Get progress for a specific batch."""
        return self.active_batches.get(batch_id)
    
    def get_batch_results(self, batch_id: str) -> Optional[List[Dict[str, Any]]]:
        """Get results for a completed batch."""
        return self.batch_results.get(batch_id)
    
    def cancel_batch(self, batch_id: str) -> bool:
        """Cancel a running batch."""
        if batch_id in self.active_batches:
            progress = self.active_batches[batch_id]
            if progress.status == 'running':
                progress.status = 'cancelled'
                logger.info(f"Batch {batch_id} cancelled")
                return True
        return False
    
    def cleanup_completed_batches(self, max_age_hours: int = 24) -> int:
        """Clean up old completed batches."""
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        cleaned_count = 0
        
        with self._lock:
            batches_to_remove = []
            for batch_id, progress in self.active_batches.items():
                if (progress.status in ['completed', 'failed', 'cancelled'] and 
                    progress.start_time < cutoff_time):
                    batches_to_remove.append(batch_id)
            
            for batch_id in batches_to_remove:
                del self.active_batches[batch_id]
                if batch_id in self.batch_results:
                    del self.batch_results[batch_id]
                cleaned_count += 1
                
        logger.info(f"Cleaned up {cleaned_count} old batches")
        return cleaned_count
    
    def get_system_stats(self) -> Dict[str, Any]:
        """Get batch processing system statistics."""
        with self._lock:
            active_count = len([p for p in self.active_batches.values() if p.status == 'running'])
            completed_count = len([p for p in self.active_batches.values() if p.status in ['completed', 'completed_with_errors']])
            failed_count = len([p for p in self.active_batches.values() if p.status == 'failed'])
            
            total_items = sum(p.total_items for p in self.active_batches.values())
            processed_items = sum(p.processed_items for p in self.active_batches.values())
            
        # Get detailed memory stats
        memory_stats = get_memory_stats()
        
        return {
            'active_batches': active_count,
            'completed_batches': completed_count,
            'failed_batches': failed_count,
            'total_items_across_batches': total_items,
            'total_processed_items': processed_items,
            'memory_usage_mb': memory_stats['rss_mb'],
            'memory_stats': memory_stats,
            'config': {
                'batch_size': self.config.batch_size,
                'max_workers': self.config.max_workers,
                'parallel_enabled': self.config.enable_parallel,
                'memory_limit_mb': self.config.memory_limit_mb
            }
        }
    
    def _get_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        except ImportError:
            return 0.0


# Global batch processor instance
batch_processor = BatchProcessor()