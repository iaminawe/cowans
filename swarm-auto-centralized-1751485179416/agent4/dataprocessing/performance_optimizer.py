"""
Performance Optimizer Module

Optimization utilities for high-performance data processing with
memory management, caching, and parallel processing capabilities.
"""

import gc
import time
import logging
import threading
from typing import Dict, List, Any, Optional, Callable, Iterator, Tuple
from datetime import datetime, timedelta
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import hashlib

class PerformanceOptimizer:
    """
    Main performance optimization coordinator.
    """
    
    def __init__(self, debug: bool = False):
        self.debug = debug
        self.logger = logging.getLogger(self.__class__.__name__)
        
        if debug:
            self.logger.setLevel(logging.DEBUG)
        
        self.performance_metrics = {
            'cache_hits': 0,
            'cache_misses': 0,
            'memory_cleanups': 0,
            'batch_processes': 0,
            'parallel_tasks': 0,
            'optimization_time_saved': 0.0
        }
    
    def optimize_processing_pipeline(self, 
                                   data_source: Iterator[Dict[str, Any]],
                                   processors: List[Callable[[Dict[str, Any]], Dict[str, Any]]],
                                   cache_enabled: bool = True,
                                   parallel_processing: bool = False,
                                   batch_size: int = 1000) -> Iterator[Dict[str, Any]]:
        """
        Optimize a data processing pipeline.
        
        Args:
            data_source: Source of data items
            processors: List of processing functions
            cache_enabled: Enable caching of intermediate results
            parallel_processing: Enable parallel processing
            batch_size: Size of processing batches
            
        Yields:
            Processed data items
        """
        self.logger.info("Starting optimized processing pipeline")
        
        # Initialize caches for each processor if enabled
        caches = [LRUCache(max_size=10000) if cache_enabled else None 
                 for _ in processors]
        
        batch = []
        processed_count = 0
        
        try:
            for item in data_source:
                batch.append(item)
                
                if len(batch) >= batch_size:
                    # Process the batch
                    if parallel_processing and len(processors) > 1:
                        processed_batch = self._process_batch_parallel(
                            batch, processors, caches
                        )
                    else:
                        processed_batch = self._process_batch_sequential(
                            batch, processors, caches
                        )
                    
                    for processed_item in processed_batch:
                        yield processed_item
                        processed_count += 1
                    
                    batch.clear()
                    self.performance_metrics['batch_processes'] += 1
                    
                    # Periodic memory cleanup
                    if processed_count % (batch_size * 10) == 0:
                        self._cleanup_memory()
            
            # Process remaining items
            if batch:
                if parallel_processing and len(processors) > 1:
                    processed_batch = self._process_batch_parallel(
                        batch, processors, caches
                    )
                else:
                    processed_batch = self._process_batch_sequential(
                        batch, processors, caches
                    )
                
                for processed_item in processed_batch:
                    yield processed_item
                    processed_count += 1
        
        finally:
            self.logger.info(f"Pipeline complete: {processed_count} items processed")
            self._log_performance_metrics()
    
    def _process_batch_sequential(self, 
                                batch: List[Dict[str, Any]], 
                                processors: List[Callable], 
                                caches: List[Optional['LRUCache']]) -> List[Dict[str, Any]]:
        """
        Process a batch sequentially through all processors.
        
        Args:
            batch: Batch of items to process
            processors: List of processing functions
            caches: List of caches for each processor
            
        Returns:
            Processed batch
        """
        processed_batch = batch.copy()
        
        for i, processor in enumerate(processors):
            cache = caches[i] if caches else None
            new_batch = []
            
            for item in processed_batch:
                processed_item = self._apply_processor_with_cache(
                    item, processor, cache
                )
                if processed_item is not None:
                    new_batch.append(processed_item)
            
            processed_batch = new_batch
        
        return processed_batch
    
    def _process_batch_parallel(self, 
                              batch: List[Dict[str, Any]], 
                              processors: List[Callable], 
                              caches: List[Optional['LRUCache']]) -> List[Dict[str, Any]]:
        """
        Process a batch in parallel where possible.
        
        Args:
            batch: Batch of items to process
            processors: List of processing functions
            caches: List of caches for each processor
            
        Returns:
            Processed batch
        """
        self.performance_metrics['parallel_tasks'] += 1
        
        # For now, process sequentially but with thread pool for I/O bound operations
        # In a more advanced version, this could analyze processor dependencies
        # and run independent processors in parallel
        
        with ThreadPoolExecutor(max_workers=min(4, len(processors))) as executor:
            # Process each item through all processors
            futures = []
            
            for item in batch:
                future = executor.submit(
                    self._process_item_through_pipeline, 
                    item, processors, caches
                )
                futures.append(future)
            
            processed_batch = []
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result is not None:
                        processed_batch.append(result)
                except Exception as e:
                    self.logger.error(f"Error in parallel processing: {e}")
                    continue
        
        return processed_batch
    
    def _process_item_through_pipeline(self, 
                                     item: Dict[str, Any], 
                                     processors: List[Callable], 
                                     caches: List[Optional['LRUCache']]) -> Optional[Dict[str, Any]]:
        """
        Process a single item through the entire pipeline.
        
        Args:
            item: Item to process
            processors: List of processing functions
            caches: List of caches for each processor
            
        Returns:
            Processed item or None
        """
        current_item = item
        
        for i, processor in enumerate(processors):
            cache = caches[i] if caches else None
            current_item = self._apply_processor_with_cache(
                current_item, processor, cache
            )
            
            if current_item is None:
                return None
        
        return current_item
    
    def _apply_processor_with_cache(self, 
                                  item: Dict[str, Any], 
                                  processor: Callable, 
                                  cache: Optional['LRUCache']) -> Optional[Dict[str, Any]]:
        """
        Apply a processor to an item with optional caching.
        
        Args:
            item: Item to process
            processor: Processing function
            cache: Optional cache
            
        Returns:
            Processed item or None
        """
        if cache is not None:
            # Generate cache key from item content
            cache_key = self._generate_cache_key(item)
            
            # Check cache first
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                self.performance_metrics['cache_hits'] += 1
                return cached_result
            
            self.performance_metrics['cache_misses'] += 1
        
        # Process the item
        start_time = time.time()
        
        try:
            result = processor(item)
            
            # Cache the result if caching is enabled
            if cache is not None and result is not None:
                cache.put(cache_key, result)
            
            # Track time saved by optimization
            processing_time = time.time() - start_time
            if cache is not None and cached_result is not None:
                self.performance_metrics['optimization_time_saved'] += processing_time
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error in processor: {e}")
            return None
    
    def _generate_cache_key(self, item: Dict[str, Any]) -> str:
        """
        Generate a cache key for an item.
        
        Args:
            item: Item to generate key for
            
        Returns:
            Cache key string
        """
        # Create a deterministic hash of the item
        item_str = json.dumps(item, sort_keys=True, separators=(',', ':'))
        return hashlib.md5(item_str.encode()).hexdigest()
    
    def _cleanup_memory(self) -> None:
        """
        Perform memory cleanup operations.
        """
        self.logger.debug("Performing memory cleanup")
        gc.collect()
        self.performance_metrics['memory_cleanups'] += 1
    
    def _log_performance_metrics(self) -> None:
        """
        Log current performance metrics.
        """
        cache_hit_rate = (
            self.performance_metrics['cache_hits'] / 
            (self.performance_metrics['cache_hits'] + self.performance_metrics['cache_misses'])
        ) * 100 if (self.performance_metrics['cache_hits'] + self.performance_metrics['cache_misses']) > 0 else 0
        
        self.logger.info(f"Performance Metrics:")
        self.logger.info(f"  Cache hit rate: {cache_hit_rate:.1f}%")
        self.logger.info(f"  Batches processed: {self.performance_metrics['batch_processes']}")
        self.logger.info(f"  Parallel tasks: {self.performance_metrics['parallel_tasks']}")
        self.logger.info(f"  Memory cleanups: {self.performance_metrics['memory_cleanups']}")
        self.logger.info(f"  Time saved by optimization: {self.performance_metrics['optimization_time_saved']:.2f}s")
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get current performance metrics.
        
        Returns:
            Dictionary of performance metrics
        """
        metrics = self.performance_metrics.copy()
        
        # Calculate derived metrics
        total_cache_operations = metrics['cache_hits'] + metrics['cache_misses']
        metrics['cache_hit_rate'] = (
            (metrics['cache_hits'] / total_cache_operations) * 100 
            if total_cache_operations > 0 else 0
        )
        
        return metrics


class LRUCache:
    """
    Least Recently Used cache implementation.
    """
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.cache = {}
        self.access_order = deque()
        self.lock = threading.Lock()
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get an item from the cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None
        """
        with self.lock:
            if key in self.cache:
                # Move to end (most recently used)
                self.access_order.remove(key)
                self.access_order.append(key)
                return self.cache[key]
        
        return None
    
    def put(self, key: str, value: Any) -> None:
        """
        Put an item in the cache.
        
        Args:
            key: Cache key
            value: Value to cache
        """
        with self.lock:
            if key in self.cache:
                # Update existing key
                self.access_order.remove(key)
                self.access_order.append(key)
                self.cache[key] = value
            else:
                # Add new key
                if len(self.cache) >= self.max_size:
                    # Remove least recently used
                    lru_key = self.access_order.popleft()
                    del self.cache[lru_key]
                
                self.cache[key] = value
                self.access_order.append(key)
    
    def clear(self) -> None:
        """
        Clear the cache.
        """
        with self.lock:
            self.cache.clear()
            self.access_order.clear()
    
    def size(self) -> int:
        """
        Get current cache size.
        
        Returns:
            Number of items in cache
        """
        return len(self.cache)


class BatchProcessor:
    """
    Efficient batch processor for large datasets.
    """
    
    def __init__(self, batch_size: int = 1000, max_memory_mb: int = 500, debug: bool = False):
        self.batch_size = batch_size
        self.max_memory_mb = max_memory_mb
        self.debug = debug
        self.logger = logging.getLogger(self.__class__.__name__)
        
        if debug:
            self.logger.setLevel(logging.DEBUG)
        
        self.current_batch = []
        self.batch_count = 0
        self.processed_count = 0
    
    def process_in_batches(self, 
                          data_source: Iterator[Dict[str, Any]], 
                          processor_func: Callable[[List[Dict[str, Any]]], List[Dict[str, Any]]],
                          memory_check_interval: int = 10) -> Iterator[Dict[str, Any]]:
        """
        Process data in memory-efficient batches.
        
        Args:
            data_source: Source of data items
            processor_func: Function to process each batch
            memory_check_interval: How often to check memory usage
            
        Yields:
            Processed data items
        """
        try:
            for item in data_source:
                self.current_batch.append(item)
                
                # Process batch when it reaches the target size
                if len(self.current_batch) >= self.batch_size:
                    yield from self._process_current_batch(processor_func)
                    
                    # Periodic memory check
                    if self.batch_count % memory_check_interval == 0:
                        self._check_memory_usage()
            
            # Process remaining items
            if self.current_batch:
                yield from self._process_current_batch(processor_func)
        
        finally:
            self.logger.info(f"Batch processing complete: {self.processed_count} items in {self.batch_count} batches")
    
    def _process_current_batch(self, processor_func: Callable) -> Iterator[Dict[str, Any]]:
        """
        Process the current batch.
        
        Args:
            processor_func: Function to process the batch
            
        Yields:
            Processed items
        """
        if not self.current_batch:
            return
        
        start_time = time.time()
        
        try:
            processed_items = processor_func(self.current_batch)
            
            for item in processed_items:
                yield item
                self.processed_count += 1
            
            self.batch_count += 1
            processing_time = time.time() - start_time
            
            self.logger.debug(f"Processed batch {self.batch_count}: {len(processed_items)} items in {processing_time:.2f}s")
            
        except Exception as e:
            self.logger.error(f"Error processing batch {self.batch_count + 1}: {e}")
        
        finally:
            self.current_batch.clear()
    
    def _check_memory_usage(self) -> None:
        """
        Check current memory usage and trigger cleanup if needed.
        """
        try:
            import psutil
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            
            if memory_mb > self.max_memory_mb:
                self.logger.warning(f"High memory usage detected: {memory_mb:.1f}MB, triggering cleanup")
                gc.collect()
                
                # Check again after cleanup
                memory_mb = process.memory_info().rss / 1024 / 1024
                self.logger.info(f"Memory usage after cleanup: {memory_mb:.1f}MB")
            
        except ImportError:
            # psutil not available, skip memory check
            pass
        except Exception as e:
            self.logger.warning(f"Error checking memory usage: {e}")


class DataStreamOptimizer:
    """
    Optimize data streaming operations.
    """
    
    def __init__(self, buffer_size: int = 10000, debug: bool = False):
        self.buffer_size = buffer_size
        self.debug = debug
        self.logger = logging.getLogger(self.__class__.__name__)
        
        if debug:
            self.logger.setLevel(logging.DEBUG)
    
    def optimize_data_stream(self, 
                           data_source: Iterator[Dict[str, Any]], 
                           filters: List[Callable[[Dict[str, Any]], bool]] = None,
                           transformers: List[Callable[[Dict[str, Any]], Dict[str, Any]]] = None) -> Iterator[Dict[str, Any]]:
        """
        Optimize a data stream with filtering and transformation.
        
        Args:
            data_source: Source data stream
            filters: List of filter functions
            transformers: List of transformation functions
            
        Yields:
            Optimized data items
        """
        filters = filters or []
        transformers = transformers or []
        
        buffer = []
        processed_count = 0
        filtered_count = 0
        
        try:
            for item in data_source:
                # Apply filters first
                skip_item = False
                for filter_func in filters:
                    if not filter_func(item):
                        skip_item = True
                        filtered_count += 1
                        break
                
                if skip_item:
                    continue
                
                # Apply transformations
                current_item = item
                for transformer in transformers:
                    try:
                        current_item = transformer(current_item)
                        if current_item is None:
                            skip_item = True
                            break
                    except Exception as e:
                        self.logger.error(f"Error in transformer: {e}")
                        skip_item = True
                        break
                
                if skip_item or current_item is None:
                    continue
                
                buffer.append(current_item)
                processed_count += 1
                
                # Yield buffer contents when it reaches the buffer size
                if len(buffer) >= self.buffer_size:
                    for buffered_item in buffer:
                        yield buffered_item
                    buffer.clear()
            
            # Yield remaining buffered items
            for buffered_item in buffer:
                yield buffered_item
        
        finally:
            self.logger.info(f"Stream optimization complete: {processed_count} items processed, {filtered_count} filtered out")


# Utility functions for common optimizations
def create_handle_cache() -> LRUCache:
    """
    Create a cache optimized for handle validation.
    
    Returns:
        LRU cache instance
    """
    return LRUCache(max_size=50000)  # Large cache for handle validation


def create_collection_cache() -> LRUCache:
    """
    Create a cache optimized for collection data.
    
    Returns:
        LRU cache instance
    """
    return LRUCache(max_size=10000)  # Medium cache for collection data


def optimize_csv_writing(data_stream: Iterator[Dict[str, Any]], 
                        output_path: str, 
                        fieldnames: List[str],
                        buffer_size: int = 10000) -> bool:
    """
    Optimized CSV writing with buffering.
    
    Args:
        data_stream: Stream of data to write
        output_path: Output CSV file path
        fieldnames: CSV column names
        buffer_size: Write buffer size
        
    Returns:
        True if successful, False otherwise
    """
    import csv
    import os
    
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w', newline='', encoding='utf-8', buffering=buffer_size) as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            written_count = 0
            for item in data_stream:
                # Filter out fields not in our fieldnames
                filtered_row = {k: item.get(k, '') for k in fieldnames}
                writer.writerow(filtered_row)
                written_count += 1
                
                if written_count % 10000 == 0:
                    logging.info(f"Written {written_count} rows...")
        
        logging.info(f"Successfully wrote {written_count} rows to {output_path}")
        return True
        
    except Exception as e:
        logging.error(f"Error writing CSV: {e}")
        return False