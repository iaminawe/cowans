"""
Shopify Collection Data Processing Module

A comprehensive data processing toolkit for extracting, transforming,
and outputting product-collection relationship data from Shopify.

Main Components:
- ShopifyCollectionProcessor: Core data processing and CSV generation
- APIResponseTransformer: API response standardization
- DataValidator: Data validation and cleansing
- PaginationHandler: Efficient pagination for large datasets
- PerformanceOptimizer: Performance optimization utilities

Usage:
    from shopify_collection_processor import ShopifyCollectionProcessor, process_csv_to_collections
    
    # Process existing CSV
    success = process_csv_to_collections('input.csv', 'output.csv')
    
    # Or use individual components
    processor = ShopifyCollectionProcessor(debug=True)
    relationships = processor.process_api_response(api_response)
"""

# Import main classes for easy access
from .shopify_collection_processor import (
    ShopifyCollectionProcessor,
    CSVCollectionExtractor,
    DataQualityAnalyzer,
    process_csv_to_collections,
    store_memory
)

from .api_response_transformer import APIResponseTransformer

from .data_validator import (
    DataValidator,
    DataCleaner
)

from .pagination_handler import (
    PaginationHandler,
    MemoryEfficientProcessor,
    create_products_with_collections_query,
    create_collections_with_products_query
)

from .performance_optimizer import (
    PerformanceOptimizer,
    LRUCache,
    BatchProcessor,
    DataStreamOptimizer,
    create_handle_cache,
    create_collection_cache,
    optimize_csv_writing
)

__version__ = '1.0.0'
__author__ = 'Agent 4: Data Processing Specialist'
__description__ = 'Shopify Collection Data Processing Module'

# Module-level constants
DEFAULT_CSV_COLUMNS = [
    'product_handle',
    'product_title',
    'collection_handle',
    'collection_title',
    'collection_type',
    'collection_description'
]

EXTENDED_CSV_COLUMNS = [
    'product_handle',
    'product_title',
    'collection_handle',
    'collection_title',
    'collection_type',
    'collection_description',
    'is_synthetic',
    'source',
    'processing_timestamp'
]

# Export all main functionality
__all__ = [
    # Main processor classes
    'ShopifyCollectionProcessor',
    'CSVCollectionExtractor', 
    'DataQualityAnalyzer',
    'APIResponseTransformer',
    'DataValidator',
    'DataCleaner',
    'PaginationHandler',
    'MemoryEfficientProcessor',
    'PerformanceOptimizer',
    'LRUCache',
    'BatchProcessor',
    'DataStreamOptimizer',
    
    # Utility functions
    'process_csv_to_collections',
    'store_memory',
    'create_products_with_collections_query',
    'create_collections_with_products_query',
    'create_handle_cache',
    'create_collection_cache',
    'optimize_csv_writing',
    
    # Constants
    'DEFAULT_CSV_COLUMNS',
    'EXTENDED_CSV_COLUMNS'
]