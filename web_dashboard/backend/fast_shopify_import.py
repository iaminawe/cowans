"""
Fast Shopify Import Script using Parallel Batch Processing
Imports 1000 products from Shopify using the new parallel sync system
"""

import os
import sys
import asyncio
import time
import json
import logging
from datetime import datetime
from typing import Dict, List, Any
import requests

# Add the backend directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from parallel_sync_engine import ParallelSyncEngine, SyncOperation, OperationType, Priority
from shopify_bulk_operations import ShopifyBulkOperations
from sync_performance_monitor import SyncPerformanceMonitor
from services.shopify_product_sync_service import ShopifyProductSyncService
from repositories.product_repository import ProductRepository
from database import db_session_scope

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('shopify_import.log')
    ]
)
logger = logging.getLogger(__name__)

class FastShopifyImporter:
    """Fast Shopify product importer using parallel batch processing"""
    
    def __init__(self):
        self.sync_engine = ParallelSyncEngine()
        self.bulk_operations = ShopifyBulkOperations()
        self.performance_monitor = SyncPerformanceMonitor()
        self.shopify_service = ShopifyProductSyncService()
        self.product_repo = ProductRepository()
        
        # Configuration
        self.batch_size = 50  # Products per batch
        self.max_workers = 8  # Parallel workers
        self.target_count = 1000  # Products to import
        
        logger.info("Fast Shopify Importer initialized")
    
    async def fetch_shopify_products(self, limit: int = 1000) -> List[Dict]:
        """Fetch products from Shopify API using GraphQL"""
        logger.info(f"Fetching {limit} products from Shopify...")
        
        try:
            # Use bulk operations for efficient fetching
            query = f"""
            {{
              products(first: {limit}) {{
                edges {{
                  node {{
                    id
                    title
                    descriptionHtml
                    vendor
                    productType
                    handle
                    status
                    tags
                    createdAt
                    updatedAt
                    variants(first: 10) {{
                      edges {{
                        node {{
                          id
                          title
                          price
                          sku
                          inventoryQuantity
                          weight
                          weightUnit
                        }}
                      }}
                    }}
                    images(first: 5) {{
                      edges {{
                        node {{
                          id
                          url
                          altText
                        }}
                      }}
                    }}
                  }}
                }}
              }}
            }}
            """
            
            # Use the shopify service to execute the query
            result = await self.shopify_service.execute_graphql_query(query)
            
            if result and 'data' in result and 'products' in result['data']:
                products = []
                for edge in result['data']['products']['edges']:
                    product = edge['node']
                    # Transform GraphQL response to our format
                    transformed_product = self._transform_shopify_product(product)
                    products.append(transformed_product)
                
                logger.info(f"Successfully fetched {len(products)} products from Shopify")
                return products
            else:
                logger.error(f"Invalid response from Shopify: {result}")
                return []
                
        except Exception as e:
            logger.error(f"Error fetching products from Shopify: {str(e)}")
            return []
    
    def _transform_shopify_product(self, shopify_product: Dict) -> Dict:
        """Transform Shopify GraphQL product to our database format"""
        try:
            # Extract basic product info
            product_data = {
                'shopify_id': shopify_product['id'].split('/')[-1],  # Extract numeric ID
                'title': shopify_product.get('title', ''),
                'description': shopify_product.get('descriptionHtml', ''),
                'vendor': shopify_product.get('vendor', ''),
                'product_type': shopify_product.get('productType', ''),
                'handle': shopify_product.get('handle', ''),
                'status': shopify_product.get('status', 'active').lower(),
                'tags': shopify_product.get('tags', []),
                'created_at': shopify_product.get('createdAt'),
                'updated_at': shopify_product.get('updatedAt'),
                'variants': [],
                'images': []
            }
            
            # Extract variants
            if 'variants' in shopify_product and 'edges' in shopify_product['variants']:
                for variant_edge in shopify_product['variants']['edges']:
                    variant = variant_edge['node']
                    product_data['variants'].append({
                        'shopify_id': variant['id'].split('/')[-1],
                        'title': variant.get('title', ''),
                        'price': float(variant.get('price', 0)),
                        'sku': variant.get('sku', ''),
                        'inventory_quantity': variant.get('inventoryQuantity', 0),
                        'weight': float(variant.get('weight', 0)),
                        'weight_unit': variant.get('weightUnit', 'kg')
                    })
            
            # Extract images
            if 'images' in shopify_product and 'edges' in shopify_product['images']:
                for image_edge in shopify_product['images']['edges']:
                    image = image_edge['node']
                    product_data['images'].append({
                        'shopify_id': image['id'].split('/')[-1],
                        'url': image.get('url', ''),
                        'alt_text': image.get('altText', '')
                    })
            
            return product_data
            
        except Exception as e:
            logger.error(f"Error transforming product {shopify_product.get('id', 'unknown')}: {str(e)}")
            return {}
    
    async def create_sync_operations(self, products: List[Dict]) -> List[SyncOperation]:
        """Create sync operations for parallel processing"""
        operations = []
        
        for i, product in enumerate(products):
            if not product:  # Skip empty products
                continue
                
            operation = SyncOperation(
                operation_id=f"import_{product.get('shopify_id', i)}",
                operation_type=OperationType.CREATE,
                priority=Priority.NORMAL,
                data=product,
                shopify_id=product.get('shopify_id', ''),
                entity_type='product'
            )
            operations.append(operation)
        
        logger.info(f"Created {len(operations)} sync operations")
        return operations
    
    async def run_parallel_import(self, products: List[Dict]) -> Dict:
        """Run parallel import using the sync engine"""
        logger.info(f"Starting parallel import of {len(products)} products with {self.max_workers} workers")
        
        start_time = time.time()
        
        # Create sync operations
        operations = await self.create_sync_operations(products)
        
        # Process with parallel engine
        results = await self.sync_engine.process_operations_parallel(
            operations,
            max_workers=self.max_workers
        )
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Calculate statistics
        successful = sum(1 for r in results if r.get('status') == 'success')
        failed = len(results) - successful
        
        stats = {
            'total_products': len(products),
            'successful_imports': successful,
            'failed_imports': failed,
            'duration_seconds': duration,
            'products_per_second': len(products) / duration if duration > 0 else 0,
            'success_rate': successful / len(products) if products else 0
        }
        
        logger.info(f"Parallel import completed:")
        logger.info(f"  Duration: {duration:.2f}s")
        logger.info(f"  Success rate: {stats['success_rate']:.1%}")
        logger.info(f"  Speed: {stats['products_per_second']:.1f} products/second")
        
        return stats
    
    async def run_batch_import(self, products: List[Dict]) -> Dict:
        """Run batch import using bulk operations"""
        logger.info(f"Starting batch import of {len(products)} products in batches of {self.batch_size}")
        
        start_time = time.time()
        successful = 0
        failed = 0
        
        # Process in batches
        for i in range(0, len(products), self.batch_size):
            batch = products[i:i+self.batch_size]
            batch_num = (i // self.batch_size) + 1
            
            logger.info(f"Processing batch {batch_num}/{(len(products) + self.batch_size - 1) // self.batch_size}")
            
            try:
                # Use bulk operations for batch processing
                result = await self.bulk_operations.bulk_create_products(batch)
                
                if result and result.get('status') == 'completed':
                    successful += result.get('created_count', 0)
                    logger.info(f"Batch {batch_num} completed: {result.get('created_count', 0)} products created")
                else:
                    failed += len(batch)
                    logger.error(f"Batch {batch_num} failed: {result}")
                    
            except Exception as e:
                failed += len(batch)
                logger.error(f"Batch {batch_num} error: {str(e)}")
        
        end_time = time.time()
        duration = end_time - start_time
        
        stats = {
            'total_products': len(products),
            'successful_imports': successful,
            'failed_imports': failed,
            'duration_seconds': duration,
            'products_per_second': len(products) / duration if duration > 0 else 0,
            'success_rate': successful / len(products) if products else 0
        }
        
        logger.info(f"Batch import completed:")
        logger.info(f"  Duration: {duration:.2f}s")
        logger.info(f"  Success rate: {stats['success_rate']:.1%}")
        logger.info(f"  Speed: {stats['products_per_second']:.1f} products/second")
        
        return stats
    
    async def run_fast_import(self, method: str = 'batch') -> Dict:
        """Run fast import using specified method"""
        logger.info(f"Starting fast Shopify import using {method} method")
        
        # Start performance monitoring
        self.performance_monitor.start_monitoring()
        
        try:
            # Fetch products from Shopify
            products = await self.fetch_shopify_products(self.target_count)
            
            if not products:
                logger.error("No products fetched from Shopify")
                return {'error': 'No products fetched'}
            
            # Choose import method
            if method == 'parallel':
                stats = await self.run_parallel_import(products)
            elif method == 'batch':
                stats = await self.run_batch_import(products)
            else:
                raise ValueError(f"Unknown method: {method}")
            
            # Add performance metrics
            performance_stats = self.performance_monitor.get_current_metrics()
            stats.update({
                'performance_metrics': performance_stats,
                'method_used': method,
                'timestamp': datetime.now().isoformat()
            })
            
            return stats
            
        except Exception as e:
            logger.error(f"Fast import failed: {str(e)}")
            return {'error': str(e)}
        
        finally:
            self.performance_monitor.stop_monitoring()
    
    def save_import_report(self, stats: Dict, filename: str = "shopify_import_report.json"):
        """Save import statistics to file"""
        with open(filename, 'w') as f:
            json.dump(stats, f, indent=2)
        
        logger.info(f"Import report saved to {filename}")

async def main():
    """Main import function"""
    print("🚀 Starting Fast Shopify Import")
    print("=" * 50)
    
    importer = FastShopifyImporter()
    
    # Run batch import (fastest method)
    print("📦 Running Batch Import (fastest method)...")
    batch_stats = await importer.run_fast_import(method='batch')
    
    if 'error' not in batch_stats:
        print(f"\n✅ Batch Import Results:")
        print(f"   • Products imported: {batch_stats['successful_imports']}/{batch_stats['total_products']}")
        print(f"   • Duration: {batch_stats['duration_seconds']:.2f}s")
        print(f"   • Speed: {batch_stats['products_per_second']:.1f} products/second")
        print(f"   • Success rate: {batch_stats['success_rate']:.1%}")
    else:
        print(f"❌ Batch import failed: {batch_stats['error']}")
    
    # Run parallel import for comparison
    print("\n⚡ Running Parallel Import (for comparison)...")
    parallel_stats = await importer.run_fast_import(method='parallel')
    
    if 'error' not in parallel_stats:
        print(f"\n✅ Parallel Import Results:")
        print(f"   • Products imported: {parallel_stats['successful_imports']}/{parallel_stats['total_products']}")
        print(f"   • Duration: {parallel_stats['duration_seconds']:.2f}s")
        print(f"   • Speed: {parallel_stats['products_per_second']:.1f} products/second")
        print(f"   • Success rate: {parallel_stats['success_rate']:.1%}")
        
        # Performance comparison
        if 'error' not in batch_stats:
            speedup = batch_stats['duration_seconds'] / parallel_stats['duration_seconds']
            print(f"\n📊 Performance Comparison:")
            print(f"   • Batch method: {batch_stats['products_per_second']:.1f} products/sec")
            print(f"   • Parallel method: {parallel_stats['products_per_second']:.1f} products/sec")
            print(f"   • Speedup factor: {speedup:.2f}x")
    else:
        print(f"❌ Parallel import failed: {parallel_stats['error']}")
    
    # Save reports
    if 'error' not in batch_stats:
        importer.save_import_report(batch_stats, "batch_import_report.json")
    if 'error' not in parallel_stats:
        importer.save_import_report(parallel_stats, "parallel_import_report.json")
    
    print(f"\n🎯 Fast Shopify import completed!")

if __name__ == "__main__":
    asyncio.run(main())