"""
Pagination Handler Module

Efficient handling of paginated API responses with memory management
and progress tracking for large datasets.
"""

import time
import logging
from typing import Dict, List, Any, Optional, Iterator, Callable
from datetime import datetime
import json

class PaginationHandler:
    """
    Handles pagination for large dataset processing.
    """
    
    def __init__(self, batch_size: int = 250, max_pages: Optional[int] = None, 
                 delay_between_requests: float = 0.5, debug: bool = False):
        """
        Initialize pagination handler.
        
        Args:
            batch_size: Number of items per page
            max_pages: Maximum number of pages to process (None for unlimited)
            delay_between_requests: Delay between API requests in seconds
            debug: Enable debug logging
        """
        self.batch_size = batch_size
        self.max_pages = max_pages
        self.delay_between_requests = delay_between_requests
        self.debug = debug
        self.logger = logging.getLogger(self.__class__.__name__)
        
        if debug:
            self.logger.setLevel(logging.DEBUG)
        
        # Statistics tracking
        self.stats = {
            'pages_processed': 0,
            'total_items': 0,
            'start_time': None,
            'end_time': None,
            'processing_time': 0,
            'average_items_per_second': 0,
            'api_calls_made': 0,
            'errors_encountered': 0
        }
    
    def process_paginated_data(self, 
                             api_call_func: Callable[[Optional[str]], Dict[str, Any]],
                             data_processor_func: Callable[[Dict[str, Any]], List[Dict[str, Any]]],
                             progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None) -> Iterator[Dict[str, Any]]:
        """
        Process paginated API data efficiently.
        
        Args:
            api_call_func: Function to make API calls with cursor parameter
            data_processor_func: Function to process each page of data
            progress_callback: Optional callback for progress updates
            
        Yields:
            Processed data items
        """
        self.logger.info("Starting paginated data processing")
        self.stats['start_time'] = datetime.now()
        
        cursor = None
        page_count = 0
        
        try:
            while True:
                # Check if we've reached the maximum pages limit
                if self.max_pages and page_count >= self.max_pages:
                    self.logger.info(f"Reached maximum pages limit: {self.max_pages}")
                    break
                
                # Make API call with rate limiting
                if page_count > 0:  # Don't delay on first request
                    time.sleep(self.delay_between_requests)
                
                try:
                    self.logger.debug(f"Fetching page {page_count + 1} with cursor: {cursor}")
                    api_response = api_call_func(cursor)
                    self.stats['api_calls_made'] += 1
                    
                except Exception as e:
                    self.logger.error(f"API call failed on page {page_count + 1}: {e}")
                    self.stats['errors_encountered'] += 1
                    break
                
                # Process the response
                try:
                    processed_items = data_processor_func(api_response)
                    
                    for item in processed_items:
                        yield item
                        self.stats['total_items'] += 1
                    
                    page_count += 1
                    self.stats['pages_processed'] = page_count
                    
                    self.logger.info(f"Processed page {page_count}, {len(processed_items)} items")
                    
                except Exception as e:
                    self.logger.error(f"Error processing page {page_count + 1}: {e}")
                    self.stats['errors_encountered'] += 1
                    continue
                
                # Check for next page
                pagination_info = self._extract_pagination_info(api_response)
                
                if not pagination_info.get('hasNextPage', False):
                    self.logger.info("No more pages available")
                    break
                
                cursor = pagination_info.get('endCursor')
                
                if not cursor:
                    self.logger.warning("No cursor available for next page")
                    break
                
                # Call progress callback if provided
                if progress_callback:
                    progress_info = {
                        'pages_processed': page_count,
                        'total_items': self.stats['total_items'],
                        'current_cursor': cursor,
                        'has_next_page': pagination_info.get('hasNextPage', False)
                    }
                    progress_callback(progress_info)
        
        finally:
            self.stats['end_time'] = datetime.now()
            self.stats['processing_time'] = (self.stats['end_time'] - self.stats['start_time']).total_seconds()
            
            if self.stats['processing_time'] > 0:
                self.stats['average_items_per_second'] = self.stats['total_items'] / self.stats['processing_time']
            
            self.logger.info(f"Pagination complete: {self.stats['pages_processed']} pages, {self.stats['total_items']} total items")
    
    def _extract_pagination_info(self, api_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract pagination information from API response.
        
        Args:
            api_response: API response to extract pagination info from
            
        Returns:
            Dictionary containing pagination information
        """
        pagination_info = {
            'hasNextPage': False,
            'hasPreviousPage': False,
            'startCursor': None,
            'endCursor': None
        }
        
        try:
            # Try to find pageInfo in various locations
            data = api_response.get('data', {})
            
            # Look for pageInfo in common locations
            for key in ['products', 'collections', 'orders', 'customers']:
                if key in data and 'pageInfo' in data[key]:
                    page_info = data[key]['pageInfo']
                    pagination_info.update({
                        'hasNextPage': page_info.get('hasNextPage', False),
                        'hasPreviousPage': page_info.get('hasPreviousPage', False),
                        'startCursor': page_info.get('startCursor'),
                        'endCursor': page_info.get('endCursor')
                    })
                    break
            
        except Exception as e:
            self.logger.error(f"Error extracting pagination info: {e}")
        
        return pagination_info
    
    def create_paginated_query(self, base_query: str, fields: List[str], 
                             first: int = None, after: str = None) -> str:
        """
        Create a paginated GraphQL query.
        
        Args:
            base_query: Base query name (e.g., 'products', 'collections')
            fields: List of fields to include in the query
            first: Number of items to fetch
            after: Cursor for pagination
            
        Returns:
            Complete GraphQL query string
        """
        first = first or self.batch_size
        
        # Build the fields string
        fields_str = '\n        '.join(fields)
        
        # Build the query parameters
        params = [f'first: {first}']
        if after:
            params.append(f'after: "{after}"')
        
        params_str = ', '.join(params)
        
        query = f"""
        query {{{base_query}({params_str}) {{
            edges {{
                node {{
                    {fields_str}
                }}
            }}
            pageInfo {{
                hasNextPage
                hasPreviousPage
                startCursor
                endCursor
            }}
        }}}}
        """
        
        return query.strip()
    
    def batch_process_items(self, items: List[Dict[str, Any]], 
                          processor_func: Callable[[List[Dict[str, Any]]], List[Dict[str, Any]]],
                          batch_size: Optional[int] = None) -> Iterator[Dict[str, Any]]:
        """
        Process items in batches for memory efficiency.
        
        Args:
            items: List of items to process
            processor_func: Function to process each batch
            batch_size: Size of each batch (defaults to self.batch_size)
            
        Yields:
            Processed items
        """
        batch_size = batch_size or self.batch_size
        
        self.logger.info(f"Processing {len(items)} items in batches of {batch_size}")
        
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            
            try:
                processed_batch = processor_func(batch)
                
                for item in processed_batch:
                    yield item
                
                self.logger.debug(f"Processed batch {i//batch_size + 1}, {len(processed_batch)} items")
                
            except Exception as e:
                self.logger.error(f"Error processing batch {i//batch_size + 1}: {e}")
                continue
    
    def estimate_remaining_time(self) -> Dict[str, Any]:
        """
        Estimate remaining processing time based on current progress.
        
        Returns:
            Dictionary with time estimates
        """
        if not self.stats['start_time'] or self.stats['pages_processed'] == 0:
            return {'error': 'No processing data available'}
        
        current_time = datetime.now()
        elapsed_time = (current_time - self.stats['start_time']).total_seconds()
        
        pages_per_second = self.stats['pages_processed'] / elapsed_time if elapsed_time > 0 else 0
        items_per_second = self.stats['total_items'] / elapsed_time if elapsed_time > 0 else 0
        
        # If we have a max_pages limit, calculate remaining time
        remaining_estimate = None
        if self.max_pages:
            remaining_pages = self.max_pages - self.stats['pages_processed']
            if pages_per_second > 0:
                remaining_seconds = remaining_pages / pages_per_second
                remaining_estimate = remaining_seconds
        
        return {
            'elapsed_time_seconds': elapsed_time,
            'pages_per_second': round(pages_per_second, 3),
            'items_per_second': round(items_per_second, 1),
            'estimated_remaining_seconds': remaining_estimate,
            'estimated_completion_time': (
                current_time.timestamp() + remaining_estimate 
                if remaining_estimate else None
            )
        }
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """
        Get current processing statistics.
        
        Returns:
            Dictionary of processing statistics
        """
        stats = self.stats.copy()
        
        # Add calculated fields
        if stats['start_time']:
            stats['start_time'] = stats['start_time'].isoformat()
        if stats['end_time']:
            stats['end_time'] = stats['end_time'].isoformat()
        
        # Add time estimates
        time_estimates = self.estimate_remaining_time()
        if 'error' not in time_estimates:
            stats.update(time_estimates)
        
        return stats
    
    def save_checkpoint(self, checkpoint_path: str, cursor: Optional[str], 
                       additional_data: Optional[Dict[str, Any]] = None) -> bool:
        """
        Save a checkpoint for resuming processing later.
        
        Args:
            checkpoint_path: Path to save checkpoint file
            cursor: Current pagination cursor
            additional_data: Additional data to save in checkpoint
            
        Returns:
            True if successful, False otherwise
        """
        try:
            checkpoint_data = {
                'timestamp': datetime.now().isoformat(),
                'cursor': cursor,
                'stats': self.get_processing_stats(),
                'config': {
                    'batch_size': self.batch_size,
                    'max_pages': self.max_pages,
                    'delay_between_requests': self.delay_between_requests
                }
            }
            
            if additional_data:
                checkpoint_data['additional_data'] = additional_data
            
            with open(checkpoint_path, 'w') as f:
                json.dump(checkpoint_data, f, indent=2)
            
            self.logger.info(f"Checkpoint saved to {checkpoint_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving checkpoint: {e}")
            return False
    
    def load_checkpoint(self, checkpoint_path: str) -> Optional[Dict[str, Any]]:
        """
        Load a checkpoint to resume processing.
        
        Args:
            checkpoint_path: Path to checkpoint file
            
        Returns:
            Checkpoint data or None if failed
        """
        try:
            with open(checkpoint_path, 'r') as f:
                checkpoint_data = json.load(f)
            
            self.logger.info(f"Checkpoint loaded from {checkpoint_path}")
            return checkpoint_data
            
        except Exception as e:
            self.logger.error(f"Error loading checkpoint: {e}")
            return None
    
    def reset_stats(self) -> None:
        """
        Reset processing statistics.
        """
        self.stats = {
            'pages_processed': 0,
            'total_items': 0,
            'start_time': None,
            'end_time': None,
            'processing_time': 0,
            'average_items_per_second': 0,
            'api_calls_made': 0,
            'errors_encountered': 0
        }
        self.logger.info("Processing statistics reset")


class MemoryEfficientProcessor:
    """
    Memory-efficient processor for large datasets.
    """
    
    def __init__(self, max_memory_items: int = 10000, debug: bool = False):
        """
        Initialize memory-efficient processor.
        
        Args:
            max_memory_items: Maximum number of items to keep in memory
            debug: Enable debug logging
        """
        self.max_memory_items = max_memory_items
        self.debug = debug
        self.logger = logging.getLogger(self.__class__.__name__)
        
        if debug:
            self.logger.setLevel(logging.DEBUG)
        
        self.current_batch = []
        self.processed_count = 0
    
    def add_item(self, item: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """
        Add an item to the current batch.
        
        Args:
            item: Item to add
            
        Returns:
            Batch of items if ready for processing, None otherwise
        """
        self.current_batch.append(item)
        
        if len(self.current_batch) >= self.max_memory_items:
            return self.flush_batch()
        
        return None
    
    def flush_batch(self) -> List[Dict[str, Any]]:
        """
        Flush the current batch and return it.
        
        Returns:
            Current batch of items
        """
        batch = self.current_batch.copy()
        self.current_batch.clear()
        self.processed_count += len(batch)
        
        self.logger.debug(f"Flushed batch of {len(batch)} items, total processed: {self.processed_count}")
        
        return batch
    
    def get_remaining_items(self) -> List[Dict[str, Any]]:
        """
        Get any remaining items in the current batch.
        
        Returns:
            Remaining items
        """
        return self.flush_batch() if self.current_batch else []
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get processing statistics.
        
        Returns:
            Dictionary of statistics
        """
        return {
            'processed_count': self.processed_count,
            'current_batch_size': len(self.current_batch),
            'max_memory_items': self.max_memory_items
        }


# Utility functions for common pagination patterns
def create_products_with_collections_query(first: int = 250, after: Optional[str] = None) -> str:
    """
    Create a GraphQL query to fetch products with their collections.
    
    Args:
        first: Number of products to fetch
        after: Cursor for pagination
        
    Returns:
        GraphQL query string
    """
    params = [f'first: {first}']
    if after:
        params.append(f'after: "{after}"')
    
    params_str = ', '.join(params)
    
    return f"""
    query {{
        products({params_str}) {{
            edges {{
                node {{
                    id
                    handle
                    title
                    description
                    productType
                    vendor
                    status
                    publishedAt
                    createdAt
                    updatedAt
                    collections(first: 50) {{
                        edges {{
                            node {{
                                id
                                handle
                                title
                                description
                                sortOrder
                                updatedAt
                            }}
                        }}
                    }}
                }}
            }}
            pageInfo {{
                hasNextPage
                hasPreviousPage
                startCursor
                endCursor
            }}
        }}
    }}
    """


def create_collections_with_products_query(first: int = 250, after: Optional[str] = None) -> str:
    """
    Create a GraphQL query to fetch collections with their products.
    
    Args:
        first: Number of collections to fetch
        after: Cursor for pagination
        
    Returns:
        GraphQL query string
    """
    params = [f'first: {first}']
    if after:
        params.append(f'after: "{after}"')
    
    params_str = ', '.join(params)
    
    return f"""
    query {{
        collections({params_str}) {{
            edges {{
                node {{
                    id
                    handle
                    title
                    description
                    sortOrder
                    updatedAt
                    products(first: 250) {{
                        edges {{
                            node {{
                                id
                                handle
                                title
                                productType
                                vendor
                                status
                            }}
                        }}
                    }}
                }}
            }}
            pageInfo {{
                hasNextPage
                hasPreviousPage
                startCursor
                endCursor
            }}
        }}
    }}
    """