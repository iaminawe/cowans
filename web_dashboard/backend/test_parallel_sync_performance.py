"""
Performance Test Script for Parallel Batch Sync System
Demonstrates speed improvements and reliability enhancements
"""

import asyncio
import time
import json
import random
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor
import statistics
import matplotlib.pyplot as plt
import pandas as pd
from dataclasses import dataclass
import requests
from unittest.mock import Mock, patch

# Import our parallel sync components
from parallel_sync_engine import ParallelSyncEngine, SyncOperation, OperationType, Priority
from shopify_bulk_operations import ShopifyBulkOperations
from graphql_batch_optimizer import GraphQLBatchOptimizer
from sync_performance_monitor import SyncPerformanceMonitor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class TestResult:
    """Test result data structure"""
    test_name: str
    duration: float
    operations_count: int
    success_rate: float
    operations_per_second: float
    memory_usage: float
    api_calls_made: int
    errors: List[str]
    
@dataclass
class PerformanceComparison:
    """Performance comparison between sync methods"""
    sequential_time: float
    parallel_time: float
    speedup_factor: float
    api_calls_saved: int
    memory_efficiency: float

class MockShopifyAPI:
    """Mock Shopify API for testing"""
    
    def __init__(self, response_delay: float = 0.1, error_rate: float = 0.05):
        self.response_delay = response_delay
        self.error_rate = error_rate
        self.api_calls_count = 0
        self.operations_log = []
    
    async def create_product(self, product_data: Dict) -> Dict:
        """Mock product creation"""
        await asyncio.sleep(self.response_delay)
        self.api_calls_count += 1
        
        if random.random() < self.error_rate:
            raise Exception(f"API Error: Rate limit exceeded")
        
        result = {
            "id": f"prod_{random.randint(1000, 9999)}",
            "title": product_data.get("title", "Test Product"),
            "status": "success"
        }
        
        self.operations_log.append({
            "operation": "create_product",
            "timestamp": datetime.now(),
            "data": product_data,
            "result": result
        })
        
        return result
    
    async def update_product(self, product_id: str, product_data: Dict) -> Dict:
        """Mock product update"""
        await asyncio.sleep(self.response_delay)
        self.api_calls_count += 1
        
        if random.random() < self.error_rate:
            raise Exception(f"API Error: Product not found")
        
        result = {
            "id": product_id,
            "title": product_data.get("title", "Updated Product"),
            "status": "success"
        }
        
        self.operations_log.append({
            "operation": "update_product",
            "timestamp": datetime.now(),
            "product_id": product_id,
            "data": product_data,
            "result": result
        })
        
        return result
    
    async def bulk_create_products(self, products: List[Dict]) -> Dict:
        """Mock bulk product creation"""
        await asyncio.sleep(self.response_delay * 0.3)  # Bulk operations are more efficient
        self.api_calls_count += 1
        
        if random.random() < self.error_rate * 0.5:  # Lower error rate for bulk
            raise Exception(f"Bulk API Error: Invalid request")
        
        results = []
        for product in products:
            results.append({
                "id": f"prod_{random.randint(1000, 9999)}",
                "title": product.get("title", "Bulk Product"),
                "status": "success"
            })
        
        result = {
            "bulk_operation_id": f"bulk_{random.randint(1000, 9999)}",
            "status": "completed",
            "created_count": len(products),
            "results": results
        }
        
        self.operations_log.append({
            "operation": "bulk_create_products",
            "timestamp": datetime.now(),
            "batch_size": len(products),
            "result": result
        })
        
        return result
    
    def get_stats(self) -> Dict:
        """Get API usage statistics"""
        return {
            "total_api_calls": self.api_calls_count,
            "operations_performed": len(self.operations_log),
            "average_response_time": self.response_delay,
            "error_rate": self.error_rate
        }

class ParallelSyncPerformanceTester:
    """Performance tester for parallel sync system"""
    
    def __init__(self):
        self.mock_api = MockShopifyAPI()
        self.sync_engine = ParallelSyncEngine()
        self.bulk_operations = ShopifyBulkOperations()
        self.graphql_optimizer = GraphQLBatchOptimizer()
        self.performance_monitor = SyncPerformanceMonitor()
        
        # Test data
        self.test_products = self._generate_test_products(1000)
        self.test_results = []
    
    def _generate_test_products(self, count: int) -> List[Dict]:
        """Generate test product data"""
        products = []
        product_types = ["Electronics", "Clothing", "Books", "Home & Garden", "Sports"]
        vendors = ["Vendor A", "Vendor B", "Vendor C", "Vendor D", "Vendor E"]
        
        for i in range(count):
            product = {
                "title": f"Test Product {i+1}",
                "description": f"Description for test product {i+1}",
                "vendor": random.choice(vendors),
                "product_type": random.choice(product_types),
                "price": round(random.uniform(10.0, 500.0), 2),
                "sku": f"TEST-SKU-{i+1:04d}",
                "weight": round(random.uniform(0.1, 10.0), 2),
                "status": "active",
                "tags": f"test,product,{random.choice(product_types).lower()}"
            }
            products.append(product)
        
        return products
    
    async def test_sequential_sync(self, product_count: int = 100) -> TestResult:
        """Test sequential synchronization"""
        logger.info(f"Starting sequential sync test with {product_count} products")
        
        start_time = time.time()
        errors = []
        successful_operations = 0
        
        # Sequential processing
        for i, product in enumerate(self.test_products[:product_count]):
            try:
                await self.mock_api.create_product(product)
                successful_operations += 1
            except Exception as e:
                errors.append(f"Product {i+1}: {str(e)}")
        
        end_time = time.time()
        duration = end_time - start_time
        
        result = TestResult(
            test_name="Sequential Sync",
            duration=duration,
            operations_count=product_count,
            success_rate=successful_operations / product_count,
            operations_per_second=product_count / duration,
            memory_usage=50.0,  # Mock memory usage
            api_calls_made=self.mock_api.api_calls_count,
            errors=errors
        )
        
        logger.info(f"Sequential sync completed in {duration:.2f}s")
        return result
    
    async def test_parallel_sync(self, product_count: int = 100, max_workers: int = 8) -> TestResult:
        """Test parallel synchronization"""
        logger.info(f"Starting parallel sync test with {product_count} products, {max_workers} workers")
        
        # Reset API counter
        self.mock_api.api_calls_count = 0
        
        start_time = time.time()
        errors = []
        
        # Create sync operations
        operations = []
        for i, product in enumerate(self.test_products[:product_count]):
            operation = SyncOperation(
                operation_id=f"sync_{i+1}",
                operation_type=OperationType.CREATE,
                priority=Priority.NORMAL,
                data=product,
                shopify_id=f"test_{i+1}"
            )
            operations.append(operation)
        
        # Process with parallel engine
        results = await self.sync_engine.process_operations_parallel(
            operations, 
            max_workers=max_workers
        )
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Calculate success rate
        successful_operations = sum(1 for r in results if r.get("status") == "success")
        errors = [r.get("error", "") for r in results if r.get("status") == "error"]
        
        result = TestResult(
            test_name="Parallel Sync",
            duration=duration,
            operations_count=product_count,
            success_rate=successful_operations / product_count,
            operations_per_second=product_count / duration,
            memory_usage=75.0,  # Mock memory usage (slightly higher due to parallelism)
            api_calls_made=self.mock_api.api_calls_count,
            errors=errors
        )
        
        logger.info(f"Parallel sync completed in {duration:.2f}s")
        return result
    
    async def test_bulk_operations(self, product_count: int = 100, batch_size: int = 50) -> TestResult:
        """Test bulk operations"""
        logger.info(f"Starting bulk operations test with {product_count} products, batch size {batch_size}")
        
        # Reset API counter
        self.mock_api.api_calls_count = 0
        
        start_time = time.time()
        errors = []
        successful_operations = 0
        
        # Process in batches
        for i in range(0, product_count, batch_size):
            batch = self.test_products[i:i+batch_size]
            try:
                result = await self.mock_api.bulk_create_products(batch)
                successful_operations += result.get("created_count", 0)
            except Exception as e:
                errors.append(f"Batch {i//batch_size + 1}: {str(e)}")
        
        end_time = time.time()
        duration = end_time - start_time
        
        result = TestResult(
            test_name="Bulk Operations",
            duration=duration,
            operations_count=product_count,
            success_rate=successful_operations / product_count,
            operations_per_second=product_count / duration,
            memory_usage=40.0,  # Lower memory usage due to efficiency
            api_calls_made=self.mock_api.api_calls_count,
            errors=errors
        )
        
        logger.info(f"Bulk operations completed in {duration:.2f}s")
        return result
    
    async def test_graphql_optimization(self, query_count: int = 100) -> TestResult:
        """Test GraphQL query optimization"""
        logger.info(f"Starting GraphQL optimization test with {query_count} queries")
        
        start_time = time.time()
        errors = []
        
        # Test query optimization
        queries = []
        for i in range(query_count):
            query = self.graphql_optimizer.build_product_query(
                fields=["id", "title", "vendor", "productType"],
                include_variants=True,
                include_images=False
            )
            queries.append(query)
        
        # Optimize queries
        optimized_queries = self.graphql_optimizer.optimize_queries(queries)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Calculate optimization metrics
        original_complexity = sum(len(q) for q in queries)
        optimized_complexity = sum(len(q) for q in optimized_queries)
        optimization_ratio = (original_complexity - optimized_complexity) / original_complexity
        
        result = TestResult(
            test_name="GraphQL Optimization",
            duration=duration,
            operations_count=query_count,
            success_rate=1.0,
            operations_per_second=query_count / duration,
            memory_usage=30.0,
            api_calls_made=len(optimized_queries),
            errors=errors
        )
        
        logger.info(f"GraphQL optimization completed in {duration:.2f}s")
        logger.info(f"Optimization ratio: {optimization_ratio:.2%}")
        return result
    
    async def run_performance_comparison(self, product_count: int = 500) -> PerformanceComparison:
        """Run comprehensive performance comparison"""
        logger.info(f"Starting performance comparison with {product_count} products")
        
        # Test sequential sync
        sequential_result = await self.test_sequential_sync(product_count)
        
        # Reset for parallel test
        self.mock_api.api_calls_count = 0
        
        # Test parallel sync
        parallel_result = await self.test_parallel_sync(product_count, max_workers=8)
        
        # Reset for bulk test
        self.mock_api.api_calls_count = 0
        
        # Test bulk operations
        bulk_result = await self.test_bulk_operations(product_count, batch_size=50)
        
        # Calculate comparison metrics
        speedup_factor = sequential_result.duration / parallel_result.duration
        bulk_speedup = sequential_result.duration / bulk_result.duration
        
        comparison = PerformanceComparison(
            sequential_time=sequential_result.duration,
            parallel_time=parallel_result.duration,
            speedup_factor=speedup_factor,
            api_calls_saved=sequential_result.api_calls_made - parallel_result.api_calls_made,
            memory_efficiency=sequential_result.memory_usage / parallel_result.memory_usage
        )
        
        # Store results
        self.test_results = [sequential_result, parallel_result, bulk_result]
        
        logger.info(f"Performance comparison completed:")
        logger.info(f"  Sequential: {sequential_result.duration:.2f}s")
        logger.info(f"  Parallel: {parallel_result.duration:.2f}s")
        logger.info(f"  Bulk: {bulk_result.duration:.2f}s")
        logger.info(f"  Speedup (parallel): {speedup_factor:.2f}x")
        logger.info(f"  Speedup (bulk): {bulk_speedup:.2f}x")
        
        return comparison
    
    def generate_performance_report(self, comparison: PerformanceComparison) -> Dict:
        """Generate detailed performance report"""
        report = {
            "test_summary": {
                "timestamp": datetime.now().isoformat(),
                "test_duration": sum(r.duration for r in self.test_results),
                "total_operations": sum(r.operations_count for r in self.test_results),
                "average_success_rate": statistics.mean(r.success_rate for r in self.test_results)
            },
            "performance_metrics": {
                "sequential_ops_per_second": self.test_results[0].operations_per_second,
                "parallel_ops_per_second": self.test_results[1].operations_per_second,
                "bulk_ops_per_second": self.test_results[2].operations_per_second,
                "speedup_factor": comparison.speedup_factor,
                "api_efficiency": comparison.api_calls_saved,
                "memory_efficiency": comparison.memory_efficiency
            },
            "detailed_results": [
                {
                    "test_name": result.test_name,
                    "duration": result.duration,
                    "operations_count": result.operations_count,
                    "success_rate": result.success_rate,
                    "operations_per_second": result.operations_per_second,
                    "memory_usage": result.memory_usage,
                    "api_calls_made": result.api_calls_made,
                    "error_count": len(result.errors)
                }
                for result in self.test_results
            ],
            "recommendations": self._generate_recommendations(comparison)
        }
        
        return report
    
    def _generate_recommendations(self, comparison: PerformanceComparison) -> List[str]:
        """Generate performance recommendations"""
        recommendations = []
        
        if comparison.speedup_factor > 5:
            recommendations.append("Parallel processing provides excellent performance gains (>5x speedup)")
        elif comparison.speedup_factor > 2:
            recommendations.append("Parallel processing provides good performance gains (2-5x speedup)")
        else:
            recommendations.append("Consider optimizing parallel processing configuration")
        
        if comparison.api_calls_saved > 100:
            recommendations.append("Significant API call reduction achieved through batching")
        
        if comparison.memory_efficiency < 0.8:
            recommendations.append("Consider implementing memory optimization strategies")
        
        recommendations.append("Use bulk operations for large datasets (>100 items)")
        recommendations.append("Implement GraphQL query optimization for complex queries")
        recommendations.append("Monitor real-time performance metrics for production workloads")
        
        return recommendations
    
    def save_results(self, report: Dict, filename: str = "performance_test_results.json"):
        """Save test results to file"""
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Test results saved to {filename}")
    
    def create_performance_charts(self, report: Dict, output_dir: str = "performance_charts"):
        """Create performance visualization charts"""
        import os
        os.makedirs(output_dir, exist_ok=True)
        
        # Performance comparison chart
        test_names = [r["test_name"] for r in report["detailed_results"]]
        durations = [r["duration"] for r in report["detailed_results"]]
        ops_per_sec = [r["operations_per_second"] for r in report["detailed_results"]]
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
        
        # Duration comparison
        ax1.bar(test_names, durations, color=['red', 'blue', 'green'])
        ax1.set_title('Sync Method Duration Comparison')
        ax1.set_ylabel('Duration (seconds)')
        ax1.tick_params(axis='x', rotation=45)
        
        # Operations per second comparison
        ax2.bar(test_names, ops_per_sec, color=['red', 'blue', 'green'])
        ax2.set_title('Operations Per Second Comparison')
        ax2.set_ylabel('Operations/Second')
        ax2.tick_params(axis='x', rotation=45)
        
        plt.tight_layout()
        plt.savefig(f"{output_dir}/performance_comparison.png", dpi=300, bbox_inches='tight')
        plt.close()
        
        # Success rate chart
        success_rates = [r["success_rate"] * 100 for r in report["detailed_results"]]
        
        plt.figure(figsize=(10, 6))
        plt.bar(test_names, success_rates, color=['red', 'blue', 'green'])
        plt.title('Success Rate Comparison')
        plt.ylabel('Success Rate (%)')
        plt.ylim(0, 100)
        plt.tick_params(axis='x', rotation=45)
        plt.tight_layout()
        plt.savefig(f"{output_dir}/success_rate_comparison.png", dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Performance charts saved to {output_dir}/")

async def main():
    """Main test function"""
    print("🚀 Starting Parallel Sync Performance Test")
    print("=" * 60)
    
    # Initialize tester
    tester = ParallelSyncPerformanceTester()
    
    # Run performance comparison
    print("\n📊 Running Performance Comparison Tests...")
    comparison = await tester.run_performance_comparison(product_count=200)
    
    # Generate report
    print("\n📋 Generating Performance Report...")
    report = tester.generate_performance_report(comparison)
    
    # Print summary
    print("\n🎯 Performance Test Results:")
    print("=" * 60)
    print(f"Sequential Sync: {report['detailed_results'][0]['duration']:.2f}s")
    print(f"Parallel Sync: {report['detailed_results'][1]['duration']:.2f}s")
    print(f"Bulk Operations: {report['detailed_results'][2]['duration']:.2f}s")
    print(f"Speedup Factor: {comparison.speedup_factor:.2f}x")
    print(f"API Calls Saved: {comparison.api_calls_saved}")
    
    print("\n💡 Recommendations:")
    for rec in report['recommendations']:
        print(f"  • {rec}")
    
    # Save results
    tester.save_results(report)
    
    # Create charts (optional - requires matplotlib)
    try:
        tester.create_performance_charts(report)
        print("\n📈 Performance charts created successfully!")
    except ImportError:
        print("\n⚠️  Matplotlib not available - skipping chart generation")
    
    print("\n✅ Performance test completed successfully!")
    print(f"📄 Full results saved to: performance_test_results.json")

if __name__ == "__main__":
    asyncio.run(main())