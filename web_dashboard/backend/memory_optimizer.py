"""Memory optimization utilities for processing large datasets efficiently."""
import gc
import sys
import psutil
import logging
from typing import Generator, Dict, Any, List, Optional, Iterator, Callable
from dataclasses import dataclass
from contextlib import contextmanager
import threading
import time
from collections import deque
import weakref

logger = logging.getLogger(__name__)


@dataclass
class MemoryStats:
    """Memory usage statistics."""
    rss_mb: float  # Resident Set Size
    vms_mb: float  # Virtual Memory Size
    percent: float  # Memory percentage
    available_mb: float
    threshold_mb: float
    is_critical: bool


class MemoryMonitor:
    """Monitor and manage memory usage during processing."""
    
    def __init__(self, warning_threshold_mb: int = 512, critical_threshold_mb: int = 1024):
        """Initialize memory monitor.
        
        Args:
            warning_threshold_mb: Warning threshold in MB
            critical_threshold_mb: Critical threshold in MB (force cleanup)
        """
        self.warning_threshold_mb = warning_threshold_mb
        self.critical_threshold_mb = critical_threshold_mb
        self._monitoring = False
        self._monitor_thread = None
        self._callbacks = []
        
    def get_memory_stats(self) -> MemoryStats:
        """Get current memory statistics."""
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            memory_percent = process.memory_percent()
            
            # Get system memory
            system_memory = psutil.virtual_memory()
            
            rss_mb = memory_info.rss / 1024 / 1024
            vms_mb = memory_info.vms / 1024 / 1024
            available_mb = system_memory.available / 1024 / 1024
            
            return MemoryStats(
                rss_mb=rss_mb,
                vms_mb=vms_mb,
                percent=memory_percent,
                available_mb=available_mb,
                threshold_mb=self.critical_threshold_mb,
                is_critical=rss_mb > self.critical_threshold_mb
            )
        except Exception as e:
            logger.error(f"Failed to get memory stats: {e}")
            return MemoryStats(0, 0, 0, 0, self.critical_threshold_mb, False)
    
    def register_callback(self, callback: Callable[[MemoryStats], None]) -> None:
        """Register callback for memory threshold events."""
        self._callbacks.append(callback)
    
    def start_monitoring(self, interval: float = 5.0) -> None:
        """Start background memory monitoring."""
        if self._monitoring:
            return
            
        self._monitoring = True
        
        def monitor_loop():
            while self._monitoring:
                try:
                    stats = self.get_memory_stats()
                    
                    # Trigger callbacks if thresholds exceeded
                    if stats.rss_mb > self.warning_threshold_mb:
                        for callback in self._callbacks:
                            try:
                                callback(stats)
                            except Exception as e:
                                logger.error(f"Memory callback error: {e}")
                    
                    time.sleep(interval)
                except Exception as e:
                    logger.error(f"Memory monitoring error: {e}")
                    time.sleep(interval)
        
        self._monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info("Memory monitoring started")
    
    def stop_monitoring(self) -> None:
        """Stop background memory monitoring."""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=1.0)
        logger.info("Memory monitoring stopped")
    
    @contextmanager
    def memory_context(self, description: str = "operation"):
        """Context manager to track memory usage for an operation."""
        start_stats = self.get_memory_stats()
        logger.info(f"Starting {description} - Memory: {start_stats.rss_mb:.1f} MB")
        
        try:
            yield start_stats
        finally:
            end_stats = self.get_memory_stats()
            memory_delta = end_stats.rss_mb - start_stats.rss_mb
            logger.info(f"Completed {description} - Memory: {end_stats.rss_mb:.1f} MB (Δ{memory_delta:+.1f} MB)")


class StreamingDataProcessor:
    """Process large datasets with streaming and memory optimization."""
    
    def __init__(self, 
                 chunk_size: int = 1000,
                 memory_monitor: Optional[MemoryMonitor] = None,
                 auto_gc: bool = True):
        """Initialize streaming processor.
        
        Args:
            chunk_size: Number of items to process in each chunk
            memory_monitor: Optional memory monitor
            auto_gc: Enable automatic garbage collection
        """
        self.chunk_size = chunk_size
        self.memory_monitor = memory_monitor or MemoryMonitor()
        self.auto_gc = auto_gc
        self._processed_count = 0
        
        # Register memory cleanup callback
        self.memory_monitor.register_callback(self._handle_memory_pressure)
    
    def _handle_memory_pressure(self, stats: MemoryStats) -> None:
        """Handle memory pressure by forcing cleanup."""
        if stats.is_critical:
            logger.warning(f"Critical memory usage: {stats.rss_mb:.1f} MB - forcing cleanup")
            self.force_cleanup()
        elif stats.rss_mb > self.memory_monitor.warning_threshold_mb:
            logger.info(f"High memory usage: {stats.rss_mb:.1f} MB - gentle cleanup")
            self.gentle_cleanup()
    
    def force_cleanup(self) -> None:
        """Force aggressive memory cleanup."""
        # Force garbage collection
        collected = gc.collect()
        logger.info(f"Forced GC collected {collected} objects")
        
        # Additional cleanup strategies could be added here
        # e.g., clearing caches, reducing buffer sizes, etc.
    
    def gentle_cleanup(self) -> None:
        """Perform gentle memory cleanup."""
        if self.auto_gc:
            gc.collect()
    
    def stream_process(self, 
                      data_iterator: Iterator[Dict[str, Any]],
                      processor_func: Callable[[List[Dict[str, Any]]], List[Dict[str, Any]]],
                      progress_callback: Optional[Callable[[int, int], None]] = None) -> Generator[List[Dict[str, Any]], None, None]:
        """Stream process data in chunks with memory optimization.
        
        Args:
            data_iterator: Iterator of data items
            processor_func: Function to process each chunk
            progress_callback: Optional progress callback
            
        Yields:
            Processed chunks
        """
        with self.memory_monitor.memory_context("stream_processing"):
            chunk = []
            total_processed = 0
            
            for item in data_iterator:
                chunk.append(item)
                
                if len(chunk) >= self.chunk_size:
                    # Process chunk
                    with self.memory_monitor.memory_context(f"chunk_{total_processed // self.chunk_size}"):
                        processed_chunk = processor_func(chunk)
                        yield processed_chunk
                    
                    # Update progress
                    total_processed += len(chunk)
                    if progress_callback:
                        progress_callback(total_processed, -1)  # -1 indicates unknown total
                    
                    # Cleanup
                    chunk.clear()
                    if self.auto_gc and total_processed % (self.chunk_size * 10) == 0:
                        self.gentle_cleanup()
            
            # Process remaining items
            if chunk:
                with self.memory_monitor.memory_context("final_chunk"):
                    processed_chunk = processor_func(chunk)
                    yield processed_chunk
                
                total_processed += len(chunk)
                if progress_callback:
                    progress_callback(total_processed, total_processed)
    
    def process_large_file(self,
                          file_path: str,
                          processor_func: Callable[[List[Dict[str, Any]]], List[Dict[str, Any]]],
                          file_parser: Callable[[str], Iterator[Dict[str, Any]]],
                          progress_callback: Optional[Callable[[int, int], None]] = None) -> Generator[List[Dict[str, Any]], None, None]:
        """Process a large file with streaming and memory optimization.
        
        Args:
            file_path: Path to the file to process
            processor_func: Function to process each chunk
            file_parser: Function to parse file and return iterator
            progress_callback: Optional progress callback
            
        Yields:
            Processed chunks
        """
        logger.info(f"Starting to process large file: {file_path}")
        
        try:
            data_iterator = file_parser(file_path)
            yield from self.stream_process(data_iterator, processor_func, progress_callback)
        except Exception as e:
            logger.error(f"Error processing large file {file_path}: {e}")
            raise
        finally:
            # Final cleanup
            self.force_cleanup()


class MemoryEfficientCache:
    """Memory-efficient cache with automatic cleanup."""
    
    def __init__(self, max_size: int = 10000, cleanup_threshold: float = 0.8):
        """Initialize cache.
        
        Args:
            max_size: Maximum number of items to cache
            cleanup_threshold: Trigger cleanup when cache reaches this fraction of max_size
        """
        self.max_size = max_size
        self.cleanup_threshold = cleanup_threshold
        self._cache: Dict[str, Any] = {}
        self._access_order = deque()
        self._lock = threading.RLock()
        
    def get(self, key: str) -> Optional[Any]:
        """Get item from cache."""
        with self._lock:
            if key in self._cache:
                # Move to end (most recently used)
                self._access_order.remove(key)
                self._access_order.append(key)
                return self._cache[key]
        return None
    
    def put(self, key: str, value: Any) -> None:
        """Put item in cache."""
        with self._lock:
            if key in self._cache:
                # Update existing item
                self._cache[key] = value
                self._access_order.remove(key)
                self._access_order.append(key)
            else:
                # Add new item
                self._cache[key] = value
                self._access_order.append(key)
                
                # Check if cleanup needed
                if len(self._cache) >= self.max_size * self.cleanup_threshold:
                    self._cleanup()
    
    def _cleanup(self) -> None:
        """Remove least recently used items."""
        target_size = int(self.max_size * 0.6)  # Clean to 60% capacity
        while len(self._cache) > target_size and self._access_order:
            oldest_key = self._access_order.popleft()
            self._cache.pop(oldest_key, None)
        
        logger.debug(f"Cache cleaned up to {len(self._cache)} items")
    
    def clear(self) -> None:
        """Clear all cache."""
        with self._lock:
            self._cache.clear()
            self._access_order.clear()
    
    def size(self) -> int:
        """Get current cache size."""
        return len(self._cache)


class ObjectPool:
    """Object pool to reduce memory allocation overhead."""
    
    def __init__(self, factory: Callable[[], Any], max_size: int = 100):
        """Initialize object pool.
        
        Args:
            factory: Function to create new objects
            max_size: Maximum number of objects to pool
        """
        self.factory = factory
        self.max_size = max_size
        self._pool = deque()
        self._lock = threading.RLock()
    
    def get(self) -> Any:
        """Get object from pool or create new one."""
        with self._lock:
            if self._pool:
                return self._pool.popleft()
            else:
                return self.factory()
    
    def put(self, obj: Any) -> None:
        """Return object to pool."""
        with self._lock:
            if len(self._pool) < self.max_size:
                # Reset object state if it has a reset method
                if hasattr(obj, 'reset'):
                    obj.reset()
                self._pool.append(obj)
    
    @contextmanager
    def get_object(self):
        """Context manager to get and automatically return object."""
        obj = self.get()
        try:
            yield obj
        finally:
            self.put(obj)


class MemoryOptimizedBatchProcessor:
    """Batch processor with advanced memory optimization."""
    
    def __init__(self, 
                 chunk_size: int = 500,  # Smaller chunks for better memory control
                 memory_limit_mb: int = 512):
        """Initialize memory-optimized batch processor."""
        self.chunk_size = chunk_size
        self.memory_monitor = MemoryMonitor(
            warning_threshold_mb=memory_limit_mb * 0.7,
            critical_threshold_mb=memory_limit_mb
        )
        self.streaming_processor = StreamingDataProcessor(
            chunk_size=chunk_size,
            memory_monitor=self.memory_monitor
        )
        self.cache = MemoryEfficientCache()
        
        # Start memory monitoring
        self.memory_monitor.start_monitoring()
    
    def process_with_memory_optimization(self,
                                       items: List[Dict[str, Any]],
                                       processor_func: Callable,
                                       progress_callback: Optional[Callable] = None) -> List[Dict[str, Any]]:
        """Process items with full memory optimization."""
        
        def item_iterator():
            """Convert list to iterator for streaming."""
            for item in items:
                yield item
        
        results = []
        total_items = len(items)
        processed_items = 0
        
        # Process in streaming fashion
        for chunk_result in self.streaming_processor.stream_process(
            item_iterator(),
            processor_func,
            lambda processed, total: progress_callback(processed, total_items) if progress_callback else None
        ):
            results.extend(chunk_result)
            processed_items += len(chunk_result)
            
            # Check memory pressure
            stats = self.memory_monitor.get_memory_stats()
            if stats.is_critical:
                logger.warning("Critical memory pressure detected during processing")
                self.streaming_processor.force_cleanup()
        
        logger.info(f"Processed {processed_items} items with memory optimization")
        return results
    
    def shutdown(self) -> None:
        """Shutdown processor and cleanup resources."""
        self.memory_monitor.stop_monitoring()
        self.cache.clear()
        self.streaming_processor.force_cleanup()


# Global instances
memory_monitor = MemoryMonitor()
memory_optimized_processor = MemoryOptimizedBatchProcessor()


def get_memory_stats() -> Dict[str, Any]:
    """Get current memory statistics for API."""
    stats = memory_monitor.get_memory_stats()
    return {
        'rss_mb': round(stats.rss_mb, 2),
        'vms_mb': round(stats.vms_mb, 2),
        'percent': round(stats.percent, 2),
        'available_mb': round(stats.available_mb, 2),
        'threshold_mb': stats.threshold_mb,
        'is_critical': stats.is_critical
    }