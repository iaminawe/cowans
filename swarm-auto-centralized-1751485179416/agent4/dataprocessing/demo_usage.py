#!/usr/bin/env python3
"""
Demo Usage Script for Data Processing Module

Demonstrates how to use the data processing components with different
data sources and scenarios.
"""

import json
from datetime import datetime
from shopify_collection_processor import (
    ShopifyCollectionProcessor, 
    process_csv_to_collections
)
from api_response_transformer import APIResponseTransformer
from data_validator import DataValidator, DataCleaner
from pagination_handler import PaginationHandler, create_products_with_collections_query
from performance_optimizer import PerformanceOptimizer, create_handle_cache

def demo_csv_processing():
    """
    Demo: Process existing CSV file to extract product-collection relationships.
    """
    print("\n=== CSV Processing Demo ===")
    
    csv_path = '/Users/iaminawe/Sites/cowans/data/products_export_1-8.csv'
    output_path = '/tmp/demo_collections_output.csv'
    
    print(f"Processing CSV: {csv_path}")
    success = process_csv_to_collections(csv_path, output_path, include_metadata=True)
    
    if success:
        print(f"✅ Success! Output saved to: {output_path}")
        print(f"📊 Check analysis at: {output_path.replace('.csv', '_analysis.json')}")
        print(f"📈 Check stats at: {output_path.replace('.csv', '_stats.json')}")
    else:
        print("❌ Processing failed")
    
    return success

def demo_api_response_processing():
    """
    Demo: Process mock API response data.
    """
    print("\n=== API Response Processing Demo ===")
    
    # Mock API response (similar to what Agent 3's script would provide)
    mock_api_response = {
        "data": {
            "products": {
                "edges": [
                    {
                        "node": {
                            "id": "gid://shopify/Product/123",
                            "handle": "test-product-1",
                            "title": "Test Product 1",
                            "description": "A test product description",
                            "productType": "Office Supplies",
                            "vendor": "Test Vendor",
                            "collections": {
                                "edges": [
                                    {
                                        "node": {
                                            "id": "gid://shopify/Collection/456",
                                            "handle": "office-supplies",
                                            "title": "Office Supplies",
                                            "description": "Office supply products"
                                        }
                                    },
                                    {
                                        "node": {
                                            "id": "gid://shopify/Collection/789",
                                            "handle": "featured-products",
                                            "title": "Featured Products",
                                            "description": "Our featured products"
                                        }
                                    }
                                ]
                            }
                        }
                    },
                    {
                        "node": {
                            "id": "gid://shopify/Product/124",
                            "handle": "test-product-2",
                            "title": "Test Product 2",
                            "description": "Another test product",
                            "productType": "Art Supplies",
                            "vendor": "Test Vendor",
                            "collections": {
                                "edges": []
                            }
                        }
                    }
                ]
            }
        }
    }
    
    # Process with the main processor
    processor = ShopifyCollectionProcessor(debug=True)
    relationships = processor.process_api_response(mock_api_response)
    
    print(f"✅ Processed {len(relationships)} relationships from API response")
    
    # Generate CSV output
    output_path = '/tmp/demo_api_output.csv'
    success = processor.generate_csv(relationships, output_path, include_metadata=True)
    
    if success:
        print(f"✅ CSV generated: {output_path}")
        
        # Show some sample data
        with open(output_path, 'r') as f:
            lines = f.readlines()[:5]  # First 5 lines
            print("\n📄 Sample output:")
            for line in lines:
                print(f"  {line.strip()}")
    
    return relationships

def demo_data_validation():
    """
    Demo: Data validation and cleaning.
    """
    print("\n=== Data Validation Demo ===")
    
    # Sample data with various issues
    test_relationships = [
        {
            'product_handle': 'valid-product-handle',
            'product_title': 'Valid Product',
            'collection_handle': 'valid-collection',
            'collection_title': 'Valid Collection',
            'collection_type': 'MANUAL'
        },
        {
            'product_handle': 'Invalid Handle!',  # Invalid characters
            'product_title': 'Product with <b>HTML</b>',  # HTML in title
            'collection_handle': '',  # Empty handle
            'collection_title': 'Collection Title',
            'collection_type': 'invalid_type'  # Invalid type
        },
        {
            'product_handle': '',  # Missing required field
            'product_title': 'Product Without Handle',
            'collection_handle': 'some-collection',
            'collection_title': 'Some Collection',
            'collection_type': 'SMART'
        }
    ]
    
    # Validate the data
    validator = DataValidator(strict_mode=False, debug=True)
    validation_results = validator.validate_batch(test_relationships)
    
    print(f"\n📊 Validation Results:")
    print(f"  Total records: {validation_results['summary']['total_records']}")
    print(f"  Valid records: {validation_results['summary']['valid_records']}")
    print(f"  Invalid records: {validation_results['summary']['invalid_records']}")
    print(f"  Validation rate: {validation_results['summary']['validation_rate']:.1f}%")
    
    # Show error summary
    if validation_results['error_summary']:
        print(f"\n❌ Common errors:")
        for error_type, count in validation_results['error_summary'].items():
            print(f"  {error_type}: {count}")
    
    # Clean the data
    cleaner = DataCleaner(debug=True)
    cleaned_relationships = cleaner.clean_relationships(test_relationships)
    
    print(f"\n🧹 Cleaned {len(cleaned_relationships)} out of {len(test_relationships)} relationships")
    
    return validation_results

def demo_performance_optimization():
    """
    Demo: Performance optimization features.
    """
    print("\n=== Performance Optimization Demo ===")
    
    # Create sample data stream
    def sample_data_generator():
        for i in range(1000):
            yield {
                'product_handle': f'product-{i}',
                'product_title': f'Product {i}',
                'collection_handle': f'collection-{i % 10}',  # 10 different collections
                'collection_title': f'Collection {i % 10}',
                'collection_type': 'SMART' if i % 2 == 0 else 'MANUAL'
            }
    
    # Sample processor function
    def sample_processor(item):
        # Simulate some processing work
        item['processed_at'] = datetime.now().isoformat()
        return item
    
    # Use performance optimizer
    optimizer = PerformanceOptimizer(debug=True)
    
    processed_items = list(optimizer.optimize_processing_pipeline(
        data_source=sample_data_generator(),
        processors=[sample_processor],
        cache_enabled=True,
        parallel_processing=False,
        batch_size=100
    ))
    
    print(f"✅ Processed {len(processed_items)} items with optimization")
    
    # Show performance metrics
    metrics = optimizer.get_performance_metrics()
    print(f"\n📈 Performance Metrics:")
    print(f"  Cache hit rate: {metrics['cache_hit_rate']:.1f}%")
    print(f"  Batch processes: {metrics['batch_processes']}")
    print(f"  Time saved: {metrics['optimization_time_saved']:.3f}s")
    
    return metrics

def demo_pagination_handling():
    """
    Demo: Pagination handling for large datasets.
    """
    print("\n=== Pagination Handling Demo ===")
    
    # Create a GraphQL query for products with collections
    query = create_products_with_collections_query(first=250)
    print(f"\n📋 Generated GraphQL query:")
    print(query[:200] + "...")
    
    # Mock pagination handler
    handler = PaginationHandler(batch_size=250, max_pages=3, debug=True)
    
    # Show estimation capabilities
    print(f"\n⏱️ Pagination Configuration:")
    print(f"  Batch size: {handler.batch_size}")
    print(f"  Max pages: {handler.max_pages}")
    print(f"  Delay between requests: {handler.delay_between_requests}s")
    
    return handler

def main():
    """
    Run all demos.
    """
    print("🚀 Data Processing Module Demo")
    print("=" * 50)
    
    try:
        # Run demos
        demo_csv_processing()
        demo_api_response_processing()
        demo_data_validation()
        demo_performance_optimization()
        demo_pagination_handling()
        
        print("\n✅ All demos completed successfully!")
        print("\n📚 Integration Points:")
        print("  - Agent 3's core script can use APIResponseTransformer")
        print("  - ShopifyCollectionProcessor handles the main data pipeline")
        print("  - DataValidator ensures data quality")
        print("  - PaginationHandler manages large datasets efficiently")
        print("  - PerformanceOptimizer maximizes processing speed")
        
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()