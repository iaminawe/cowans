"""
Performance Benchmarks for Shopify Handles and Collections Downloader

This module provides comprehensive performance testing and benchmarking
for the Shopify handles and collections downloader script.

Benchmarks include:
- API response time measurements
- Memory usage profiling
- Large dataset processing performance
- Rate limiting behavior validation
- File I/O performance metrics
"""

import pytest
import time
import psutil
import os
import sys
import memory_profiler
from unittest.mock import Mock, patch
import pandas as pd
import tempfile
import shutil
from pathlib import Path
import json
import statistics
from datetime import datetime, timedelta

# Performance thresholds (adjust based on requirements)
PERFORMANCE_THRESHOLDS = {
    'api_response_time_ms': 1000,  # Max 1 second per API call
    'csv_export_time_per_product_ms': 10,  # Max 10ms per product for CSV export
    'memory_usage_mb_per_1k_products': 50,  # Max 50MB per 1000 products
    'max_total_memory_mb': 500,  # Max 500MB total memory usage
    'products_per_second_target': 10,  # Target processing rate
    'file_write_speed_mb_per_s': 10,  # Minimum file write speed
}

class PerformanceBenchmark:
    """Performance benchmarking utilities"""
    
    def __init__(self):
        self.start_time = None
        self.start_memory = None
        self.process = psutil.Process()
        self.metrics = {}
    
    def start_benchmark(self, test_name: str):
        """Start performance measurement"""
        self.start_time = time.time()
        self.start_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        self.test_name = test_name
        print(f"\n📊 Starting benchmark: {test_name}")
        print(f"   Initial memory: {self.start_memory:.2f} MB")
    
    def end_benchmark(self) -> dict:
        """End performance measurement and return metrics"""
        end_time = time.time()
        end_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        
        execution_time = end_time - self.start_time
        memory_used = end_memory - self.start_memory
        peak_memory = end_memory
        
        metrics = {
            'test_name': self.test_name,
            'execution_time_s': execution_time,
            'execution_time_ms': execution_time * 1000,
            'memory_used_mb': memory_used,
            'peak_memory_mb': peak_memory,
            'timestamp': datetime.now().isoformat()
        }
        
        print(f"   Execution time: {execution_time:.3f}s ({execution_time*1000:.1f}ms)")
        print(f"   Memory used: {memory_used:.2f} MB")
        print(f"   Peak memory: {peak_memory:.2f} MB")
        
        self.metrics[self.test_name] = metrics
        return metrics
    
    def save_benchmark_results(self, output_file: str = "benchmark_results.json"):
        """Save all benchmark results to file"""
        with open(output_file, 'w') as f:
            json.dump(self.metrics, f, indent=2)
        print(f"📈 Benchmark results saved to: {output_file}")

# Mock classes for performance testing
class MockPerformanceDownloader:
    """High-performance mock for benchmarking"""
    
    def __init__(self, shop_url: str, access_token: str, output_file: str = None):
        self.shop_url = shop_url
        self.access_token = access_token
        self.output_file = output_file or "benchmark_output.csv"
        self.api_call_times = []
        
    def simulate_api_delay(self, product_count: int) -> float:
        """Simulate realistic API response times"""
        # Base delay + variable delay based on data size
        base_delay = 0.1  # 100ms base
        variable_delay = product_count * 0.001  # 1ms per product
        total_delay = base_delay + variable_delay
        time.sleep(total_delay)
        return total_delay
        
    def fetch_products_with_collections(self, limit: int = None) -> list:
        """Generate mock products for performance testing"""
        if limit is None:
            limit = 1000  # Default for performance testing
            
        start_time = time.time()
        api_delay = self.simulate_api_delay(limit)
        
        # Generate realistic mock data
        products = []
        for i in range(limit):
            collections = []
            # Vary collection count (0-5 collections per product)
            collection_count = i % 6
            for j in range(collection_count):
                collections.append({
                    'id': f'gid://shopify/Collection/{j+1}',
                    'handle': f'collection-{j+1}',
                    'title': f'Collection {j+1}'
                })
            
            products.append({
                'id': f'gid://shopify/Product/{i+1}',
                'handle': f'product-handle-{i+1:06d}',
                'title': f'Performance Test Product {i+1}',
                'collections': collections
            })
        
        end_time = time.time()
        self.api_call_times.append(end_time - start_time)
        
        return products
    
    def export_to_csv(self, products: list) -> str:
        """High-performance CSV export"""
        if not products:
            raise ValueError("No products to export")
        
        # Prepare data efficiently
        csv_data = []
        for product in products:
            collection_handles = [col['handle'] for col in product.get('collections', [])]
            collection_titles = [col['title'] for col in product.get('collections', [])]
            
            csv_data.append({
                'product_id': product['id'],
                'product_handle': product['handle'],
                'product_title': product['title'],
                'collection_handles': ';'.join(collection_handles),
                'collection_titles': ';'.join(collection_titles),
                'collection_count': len(collection_handles)
            })
        
        # Use pandas for efficient CSV writing
        df = pd.DataFrame(csv_data)
        df.to_csv(self.output_file, index=False, encoding='utf-8')
        
        return self.output_file
    
    def get_performance_stats(self) -> dict:
        """Get performance statistics"""
        if not self.api_call_times:
            return {}
            
        return {
            'api_calls_made': len(self.api_call_times),
            'avg_api_response_time_s': statistics.mean(self.api_call_times),
            'min_api_response_time_s': min(self.api_call_times),
            'max_api_response_time_s': max(self.api_call_times),
            'total_api_time_s': sum(self.api_call_times)
        }

# Test fixtures
@pytest.fixture
def benchmark():
    """Performance benchmark fixture"""
    return PerformanceBenchmark()

@pytest.fixture
def performance_downloader():
    """Performance-focused downloader"""
    return MockPerformanceDownloader(
        "performance-test-store.myshopify.com",
        "performance_test_token",
        "performance_test_output.csv"
    )

@pytest.fixture
def temp_benchmark_dir():
    """Temporary directory for benchmark files"""
    temp_dir = tempfile.mkdtemp(prefix="benchmark_")
    yield temp_dir
    shutil.rmtree(temp_dir)

# API Performance Tests
@pytest.mark.performance
def test_api_response_time_single_call(benchmark, performance_downloader):
    """Benchmark single API call performance"""
    benchmark.start_benchmark("api_single_call")
    
    products = performance_downloader.fetch_products_with_collections(limit=100)
    
    metrics = benchmark.end_benchmark()
    
    # Validate performance
    assert len(products) == 100
    assert metrics['execution_time_ms'] < PERFORMANCE_THRESHOLDS['api_response_time_ms']
    
    # Validate API call statistics
    stats = performance_downloader.get_performance_stats()
    assert stats['avg_api_response_time_s'] < 1.0  # Should be under 1 second

@pytest.mark.performance
def test_api_response_time_multiple_calls(benchmark, performance_downloader):
    """Benchmark multiple API calls performance"""
    benchmark.start_benchmark("api_multiple_calls")
    
    call_count = 5
    batch_size = 50
    total_products = 0
    
    for i in range(call_count):
        products = performance_downloader.fetch_products_with_collections(limit=batch_size)
        total_products += len(products)
    
    metrics = benchmark.end_benchmark()
    
    # Validate results
    assert total_products == call_count * batch_size
    
    # Validate API performance
    stats = performance_downloader.get_performance_stats()
    assert stats['api_calls_made'] == call_count
    assert stats['avg_api_response_time_s'] < 1.0

# Memory Performance Tests
@pytest.mark.performance
def test_memory_usage_small_dataset(benchmark, performance_downloader, temp_benchmark_dir):
    """Test memory usage with small dataset (100 products)"""
    benchmark.start_benchmark("memory_small_dataset")
    
    output_file = os.path.join(temp_benchmark_dir, "small_dataset.csv")
    performance_downloader.output_file = output_file
    
    products = performance_downloader.fetch_products_with_collections(limit=100)
    csv_file = performance_downloader.export_to_csv(products)
    
    metrics = benchmark.end_benchmark()
    
    # Memory should be minimal for small datasets
    assert metrics['memory_used_mb'] < 10  # Less than 10MB for 100 products
    assert os.path.exists(csv_file)

@pytest.mark.performance
def test_memory_usage_medium_dataset(benchmark, performance_downloader, temp_benchmark_dir):
    """Test memory usage with medium dataset (1000 products)"""
    benchmark.start_benchmark("memory_medium_dataset")
    
    output_file = os.path.join(temp_benchmark_dir, "medium_dataset.csv")
    performance_downloader.output_file = output_file
    
    products = performance_downloader.fetch_products_with_collections(limit=1000)
    csv_file = performance_downloader.export_to_csv(products)
    
    metrics = benchmark.end_benchmark()
    
    # Validate memory usage
    memory_per_1k = metrics['memory_used_mb']
    assert memory_per_1k < PERFORMANCE_THRESHOLDS['memory_usage_mb_per_1k_products']
    assert os.path.exists(csv_file)
    
    # Validate file size
    file_size_mb = os.path.getsize(csv_file) / 1024 / 1024
    print(f"   CSV file size: {file_size_mb:.2f} MB")

@pytest.mark.performance
def test_memory_usage_large_dataset(benchmark, performance_downloader, temp_benchmark_dir):
    """Test memory usage with large dataset (5000 products)"""
    benchmark.start_benchmark("memory_large_dataset")
    
    output_file = os.path.join(temp_benchmark_dir, "large_dataset.csv")
    performance_downloader.output_file = output_file
    
    products = performance_downloader.fetch_products_with_collections(limit=5000)
    csv_file = performance_downloader.export_to_csv(products)
    
    metrics = benchmark.end_benchmark()
    
    # Validate memory usage scaling
    memory_per_1k = metrics['memory_used_mb'] / 5  # 5k products = 5 * 1k
    assert memory_per_1k < PERFORMANCE_THRESHOLDS['memory_usage_mb_per_1k_products']
    assert metrics['peak_memory_mb'] < PERFORMANCE_THRESHOLDS['max_total_memory_mb']
    
    # Validate processing rate
    products_per_second = 5000 / metrics['execution_time_s']
    print(f"   Processing rate: {products_per_second:.1f} products/second")
    assert products_per_second > PERFORMANCE_THRESHOLDS['products_per_second_target']

# CSV Export Performance Tests
@pytest.mark.performance
def test_csv_export_performance(benchmark, temp_benchmark_dir):
    """Test CSV export performance with various data sizes"""
    dataset_sizes = [100, 500, 1000, 2000]
    
    for size in dataset_sizes:
        benchmark.start_benchmark(f"csv_export_{size}_products")
        
        # Generate test data
        test_products = []
        for i in range(size):
            collections = [
                {'handle': f'collection-{j}', 'title': f'Collection {j}'}
                for j in range(i % 3 + 1)  # 1-3 collections per product
            ]
            test_products.append({
                'id': f'gid://shopify/Product/{i}',
                'handle': f'product-{i:06d}',
                'title': f'Test Product {i}',
                'collections': collections
            })
        
        # Export to CSV
        output_file = os.path.join(temp_benchmark_dir, f"export_test_{size}.csv")
        downloader = MockPerformanceDownloader("test", "test", output_file)
        csv_file = downloader.export_to_csv(test_products)
        
        metrics = benchmark.end_benchmark()
        
        # Validate performance
        time_per_product = metrics['execution_time_ms'] / size
        assert time_per_product < PERFORMANCE_THRESHOLDS['csv_export_time_per_product_ms']
        
        # Validate file integrity
        df = pd.read_csv(csv_file)
        assert len(df) == size
        
        print(f"   {size} products: {time_per_product:.2f}ms per product")

# File I/O Performance Tests
@pytest.mark.performance
def test_file_write_performance(benchmark, temp_benchmark_dir):
    """Test file write performance"""
    benchmark.start_benchmark("file_write_performance")
    
    # Generate large dataset
    large_products = []
    for i in range(10000):
        collections = [
            {'handle': f'collection-{j}', 'title': f'Very Long Collection Title {j} with Extra Data'}
            for j in range(5)  # 5 collections per product
        ]
        large_products.append({
            'id': f'gid://shopify/Product/{i:08d}',
            'handle': f'very-long-product-handle-with-descriptive-name-{i:08d}',
            'title': f'Very Long Product Title with Detailed Description and Extra Information {i}',
            'collections': collections
        })
    
    # Export to CSV
    output_file = os.path.join(temp_benchmark_dir, "large_file_test.csv")
    downloader = MockPerformanceDownloader("test", "test", output_file)
    csv_file = downloader.export_to_csv(large_products)
    
    metrics = benchmark.end_benchmark()
    
    # Calculate file write speed
    file_size_mb = os.path.getsize(csv_file) / 1024 / 1024
    write_speed_mb_per_s = file_size_mb / metrics['execution_time_s']
    
    print(f"   File size: {file_size_mb:.2f} MB")
    print(f"   Write speed: {write_speed_mb_per_s:.2f} MB/s")
    
    # Validate performance
    assert write_speed_mb_per_s > PERFORMANCE_THRESHOLDS['file_write_speed_mb_per_s']

# Rate Limiting Simulation Tests
@pytest.mark.performance
def test_rate_limiting_behavior(benchmark, performance_downloader):
    """Test behavior under rate limiting conditions"""
    benchmark.start_benchmark("rate_limiting_simulation")
    
    # Simulate rapid API calls
    call_count = 10
    products_per_call = 100
    
    api_call_times = []
    for i in range(call_count):
        start_time = time.time()
        products = performance_downloader.fetch_products_with_collections(limit=products_per_call)
        end_time = time.time()
        
        api_call_times.append(end_time - start_time)
        assert len(products) == products_per_call
        
        # Small delay between calls to simulate rate limiting
        time.sleep(0.1)
    
    metrics = benchmark.end_benchmark()
    
    # Validate rate limiting behavior
    avg_call_time = statistics.mean(api_call_times)
    print(f"   Average API call time: {avg_call_time:.3f}s")
    print(f"   Total API calls: {call_count}")
    
    # Should handle rate limiting gracefully
    assert avg_call_time < 2.0  # Should not exceed 2 seconds per call

# Stress Tests
@pytest.mark.performance
def test_stress_test_concurrent_operations(benchmark, temp_benchmark_dir):
    """Stress test with concurrent-like operations"""
    benchmark.start_benchmark("stress_test_concurrent")
    
    downloaders = []
    results = []
    
    # Create multiple downloader instances
    for i in range(5):
        output_file = os.path.join(temp_benchmark_dir, f"stress_test_{i}.csv")
        downloader = MockPerformanceDownloader("test", "test", output_file)
        downloaders.append(downloader)
    
    # Simulate concurrent operations
    for i, downloader in enumerate(downloaders):
        products = downloader.fetch_products_with_collections(limit=500)
        csv_file = downloader.export_to_csv(products)
        results.append({'downloader': i, 'products': len(products), 'file': csv_file})
    
    metrics = benchmark.end_benchmark()
    
    # Validate results
    assert len(results) == 5
    total_products = sum(r['products'] for r in results)
    assert total_products == 5 * 500
    
    # All files should exist
    for result in results:
        assert os.path.exists(result['file'])
    
    print(f"   Processed {total_products} products across {len(results)} operations")

# Comprehensive benchmark suite
@pytest.mark.performance
def test_comprehensive_performance_suite(benchmark, temp_benchmark_dir):
    """Run comprehensive performance test suite"""
    print("\n🚀 Running Comprehensive Performance Suite")
    
    suite_results = {}
    
    # Test 1: Small dataset end-to-end
    benchmark.start_benchmark("suite_small_e2e")
    downloader = MockPerformanceDownloader(
        "test-store.myshopify.com", 
        "test_token", 
        os.path.join(temp_benchmark_dir, "suite_small.csv")
    )
    products = downloader.fetch_products_with_collections(limit=100)
    csv_file = downloader.export_to_csv(products)
    suite_results['small_e2e'] = benchmark.end_benchmark()
    
    # Test 2: Medium dataset end-to-end
    benchmark.start_benchmark("suite_medium_e2e")
    downloader.output_file = os.path.join(temp_benchmark_dir, "suite_medium.csv")
    products = downloader.fetch_products_with_collections(limit=1000)
    csv_file = downloader.export_to_csv(products)
    suite_results['medium_e2e'] = benchmark.end_benchmark()
    
    # Test 3: Large dataset end-to-end
    benchmark.start_benchmark("suite_large_e2e")
    downloader.output_file = os.path.join(temp_benchmark_dir, "suite_large.csv")
    products = downloader.fetch_products_with_collections(limit=3000)
    csv_file = downloader.export_to_csv(products)
    suite_results['large_e2e'] = benchmark.end_benchmark()
    
    # Performance summary
    print("\n📊 Performance Suite Summary:")
    for test_name, metrics in suite_results.items():
        products_count = 100 if 'small' in test_name else (1000 if 'medium' in test_name else 3000)
        rate = products_count / metrics['execution_time_s']
        print(f"   {test_name}: {rate:.1f} products/second, {metrics['memory_used_mb']:.1f} MB")
    
    # Save comprehensive results
    benchmark_file = os.path.join(temp_benchmark_dir, "comprehensive_benchmark.json")
    benchmark.save_benchmark_results(benchmark_file)
    
    return suite_results

# Performance regression test
@pytest.mark.performance
def test_performance_regression_baseline():
    """Establish performance baseline for regression testing"""
    baseline_file = "performance_baseline.json"
    
    # Create or load baseline
    if os.path.exists(baseline_file):
        with open(baseline_file, 'r') as f:
            baseline = json.load(f)
        print(f"📈 Loaded performance baseline from {baseline_file}")
    else:
        baseline = {
            'api_response_time_ms': PERFORMANCE_THRESHOLDS['api_response_time_ms'],
            'csv_export_time_per_product_ms': PERFORMANCE_THRESHOLDS['csv_export_time_per_product_ms'],
            'memory_usage_mb_per_1k_products': PERFORMANCE_THRESHOLDS['memory_usage_mb_per_1k_products'],
            'products_per_second_target': PERFORMANCE_THRESHOLDS['products_per_second_target'],
            'created': datetime.now().isoformat()
        }
        with open(baseline_file, 'w') as f:
            json.dump(baseline, f, indent=2)
        print(f"📊 Created performance baseline: {baseline_file}")
    
    # Current performance test
    benchmark = PerformanceBenchmark()
    benchmark.start_benchmark("regression_test")
    
    downloader = MockPerformanceDownloader("test", "test")
    products = downloader.fetch_products_with_collections(limit=1000)
    csv_file = downloader.export_to_csv(products)
    
    metrics = benchmark.end_benchmark()
    
    # Regression checks
    current_rate = 1000 / metrics['execution_time_s']
    baseline_rate = baseline['products_per_second_target']
    
    print(f"   Current rate: {current_rate:.1f} products/second")
    print(f"   Baseline rate: {baseline_rate:.1f} products/second")
    
    # Allow 20% regression tolerance
    tolerance = 0.8
    assert current_rate >= baseline_rate * tolerance, f"Performance regression detected: {current_rate:.1f} < {baseline_rate * tolerance:.1f}"
    
    # Clean up
    if os.path.exists(csv_file):
        os.remove(csv_file)

if __name__ == "__main__":
    # Run performance tests
    print("🏃‍♂️ Running Performance Benchmarks...")
    pytest.main([__file__, "-m", "performance", "-v", "--tb=short"])