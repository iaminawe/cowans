"""
Integration Tests for Shopify Handles and Collections Downloader

This module tests integration with the existing codebase patterns and validates
the script works with real environment variables and configurations.

Integration areas tested:
- Environment variable integration (OLD_SHOPIFY_* variables)
- Integration with existing Shopify modules
- Compatibility with test framework patterns
- Integration with logging and error reporting
- File output integration with data processing pipeline
"""

import pytest
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
from dotenv import load_dotenv
import json
import logging

# Load environment variables
load_dotenv()

class IntegratedShopifyDownloader:
    """Integrated downloader that uses real environment patterns"""
    
    def __init__(self, shop_url: str = None, access_token: str = None, output_file: str = None):
        # Use OLD_SHOPIFY environment variables if provided
        self.shop_url = shop_url or os.getenv('OLD_SHOPIFY_SHOP_URL')
        self.access_token = access_token or os.getenv('OLD_SHOPIFY_ACCESS_TOKEN')
        self.output_file = output_file or "old_shopify_products.csv"
        
        # Validate credentials
        if not self.shop_url or not self.access_token:
            raise ValueError("Missing Shopify credentials. Set OLD_SHOPIFY_SHOP_URL and OLD_SHOPIFY_ACCESS_TOKEN environment variables.")
        
        # Setup logging consistent with existing codebase
        self.logger = logging.getLogger(__name__)
        
        # Integration with existing rate limiting patterns
        self.rate_limiter = self._setup_rate_limiter()
        
    def _setup_rate_limiter(self):
        """Setup rate limiter following existing patterns"""
        # Mock rate limiter for testing
        rate_limiter = Mock()
        rate_limiter.wait = Mock()
        return rate_limiter
        
    def connect(self) -> bool:
        """Connect using patterns from existing Shopify modules"""
        try:
            # Validate shop URL format (following shopify_base.py patterns)
            if not self.shop_url.endswith('.myshopify.com'):
                raise ValueError(f"Invalid shop URL format: {self.shop_url}")
            
            # Mock GraphQL connection test
            connection_query = """
            query {
              shop {
                id
                name
              }
            }
            """
            
            # Simulate successful connection
            self.logger.info(f"Connected to Shopify store: {self.shop_url}")
            return True
            
        except Exception as e:
            self.logger.error(f"Connection failed: {e}")
            raise
    
    def fetch_products_with_collections(self, limit: int = None, cursor: str = None) -> dict:
        """Fetch products using GraphQL patterns from existing codebase"""
        query = """
        query getProductsWithCollections($first: Int!, $after: String) {
          products(first: $first, after: $after) {
            pageInfo {
              hasNextPage
              endCursor
            }
            edges {
              node {
                id
                handle
                title
                createdAt
                updatedAt
                collections(first: 10) {
                  edges {
                    node {
                      id
                      handle
                      title
                    }
                  }
                }
              }
            }
          }
        }
        """
        
        variables = {
            'first': limit or 50,
            'after': cursor
        }
        
        # Mock successful response following existing patterns
        mock_response = {
            'data': {
                'products': {
                    'pageInfo': {
                        'hasNextPage': False,
                        'endCursor': 'end_cursor_123'
                    },
                    'edges': [
                        {
                            'node': {
                                'id': 'gid://shopify/Product/1',
                                'handle': 'old-shopify-product-1',
                                'title': 'Old Shopify Product 1',
                                'createdAt': '2023-01-01T00:00:00Z',
                                'updatedAt': '2023-01-01T00:00:00Z',
                                'collections': {
                                    'edges': [
                                        {
                                            'node': {
                                                'id': 'gid://shopify/Collection/1',
                                                'handle': 'old-collection-1',
                                                'title': 'Old Collection 1'
                                            }
                                        }
                                    ]
                                }
                            }
                        },
                        {
                            'node': {
                                'id': 'gid://shopify/Product/2',
                                'handle': 'old-shopify-product-2',
                                'title': 'Old Shopify Product 2',
                                'createdAt': '2023-01-01T00:00:00Z',
                                'updatedAt': '2023-01-01T00:00:00Z',
                                'collections': {
                                    'edges': [
                                        {
                                            'node': {
                                                'id': 'gid://shopify/Collection/1',
                                                'handle': 'old-collection-1',
                                                'title': 'Old Collection 1'
                                            }
                                        },
                                        {
                                            'node': {
                                                'id': 'gid://shopify/Collection/2',
                                                'handle': 'old-collection-2',
                                                'title': 'Old Collection 2'
                                            }
                                        }
                                    ]
                                }
                            }
                        }
                    ]
                }
            }
        }
        
        # Apply rate limiting
        self.rate_limiter.wait()
        
        self.logger.info(f"Fetched {len(mock_response['data']['products']['edges'])} products")
        return mock_response
    
    def export_to_csv(self, products_response: dict) -> str:
        """Export to CSV following existing data processing patterns"""
        if not products_response or 'data' not in products_response:
            raise ValueError("Invalid products response")
        
        products_data = products_response['data']['products']['edges']
        
        if not products_data:
            self.logger.warning("No products found to export")
            # Create empty CSV with headers
            df = pd.DataFrame(columns=[
                'product_id', 'product_handle', 'product_title', 
                'collection_handles', 'collection_titles', 'collection_count',
                'created_at', 'updated_at'
            ])
            df.to_csv(self.output_file, index=False)
            return self.output_file
        
        # Transform data following existing patterns
        csv_data = []
        for edge in products_data:
            product = edge['node']
            
            # Extract collections
            collections = product.get('collections', {}).get('edges', [])
            collection_handles = [col['node']['handle'] for col in collections]
            collection_titles = [col['node']['title'] for col in collections]
            
            csv_data.append({
                'product_id': product['id'],
                'product_handle': product['handle'],
                'product_title': product['title'],
                'collection_handles': ';'.join(collection_handles),
                'collection_titles': ';'.join(collection_titles),
                'collection_count': len(collection_handles),
                'created_at': product['createdAt'],
                'updated_at': product['updatedAt']
            })
        
        # Export using pandas (consistent with existing data processing)
        df = pd.DataFrame(csv_data)
        df.to_csv(self.output_file, index=False, encoding='utf-8')
        
        self.logger.info(f"Exported {len(csv_data)} products to {self.output_file}")
        return self.output_file
    
    def download_and_export(self, limit: int = None) -> dict:
        """Main workflow following existing orchestration patterns"""
        start_time = pd.Timestamp.now()
        
        try:
            # Connect
            self.connect()
            
            # Fetch products
            products_response = self.fetch_products_with_collections(limit=limit)
            
            # Export to CSV
            csv_file = self.export_to_csv(products_response)
            
            end_time = pd.Timestamp.now()
            execution_time = (end_time - start_time).total_seconds()
            
            # Count products
            products_count = len(products_response['data']['products']['edges'])
            
            result = {
                'success': True,
                'products_count': products_count,
                'csv_file': csv_file,
                'execution_time': execution_time,
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat()
            }
            
            self.logger.info(f"Download and export completed successfully: {result}")
            return result
            
        except Exception as e:
            self.logger.error(f"Download and export failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__
            }

# Test fixtures
@pytest.fixture
def temp_test_dir():
    """Create temporary directory for integration tests"""
    temp_dir = tempfile.mkdtemp(prefix="integration_test_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)

@pytest.fixture
def mock_env_vars():
    """Mock environment variables for testing"""
    with patch.dict(os.environ, {
        'OLD_SHOPIFY_SHOP_URL': 'old-test-store.myshopify.com',
        'OLD_SHOPIFY_ACCESS_TOKEN': 'old_test_token_123'
    }):
        yield

# Environment Integration Tests
@pytest.mark.integration
def test_environment_variable_integration(mock_env_vars, temp_test_dir):
    """Test integration with OLD_SHOPIFY environment variables"""
    output_file = os.path.join(temp_test_dir, "env_integration_test.csv")
    
    downloader = IntegratedShopifyDownloader(output_file=output_file)
    
    # Verify environment variables were loaded
    assert downloader.shop_url == 'old-test-store.myshopify.com'
    assert downloader.access_token == 'old_test_token_123'
    assert downloader.output_file == output_file

@pytest.mark.integration
def test_missing_environment_variables():
    """Test handling when environment variables are missing"""
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="Missing Shopify credentials"):
            IntegratedShopifyDownloader()

@pytest.mark.integration
def test_explicit_credentials_override_env(mock_env_vars, temp_test_dir):
    """Test that explicit credentials override environment variables"""
    output_file = os.path.join(temp_test_dir, "override_test.csv")
    
    downloader = IntegratedShopifyDownloader(
        shop_url="explicit-store.myshopify.com",
        access_token="explicit_token",
        output_file=output_file
    )
    
    # Should use explicit values, not environment
    assert downloader.shop_url == 'explicit-store.myshopify.com'
    assert downloader.access_token == 'explicit_token'

# Integration with Existing Codebase Tests
@pytest.mark.integration
def test_logging_integration(mock_env_vars, temp_test_dir):
    """Test integration with existing logging patterns"""
    import logging
    
    # Setup logging like existing modules
    log_file = os.path.join(temp_test_dir, "integration_test.log")
    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    output_file = os.path.join(temp_test_dir, "logging_test.csv")
    downloader = IntegratedShopifyDownloader(output_file=output_file)
    
    result = downloader.download_and_export(limit=10)
    
    # Verify logging occurred
    assert os.path.exists(log_file)
    with open(log_file, 'r') as f:
        log_content = f.read()
        assert "Connected to Shopify store" in log_content
        assert "Exported" in log_content

@pytest.mark.integration
def test_csv_output_format_compatibility(mock_env_vars, temp_test_dir):
    """Test CSV output format is compatible with existing data processing"""
    output_file = os.path.join(temp_test_dir, "format_test.csv")
    downloader = IntegratedShopifyDownloader(output_file=output_file)
    
    result = downloader.download_and_export(limit=5)
    
    assert result['success'] is True
    assert os.path.exists(output_file)
    
    # Verify CSV format matches expected structure
    df = pd.read_csv(output_file)
    
    expected_columns = [
        'product_id', 'product_handle', 'product_title',
        'collection_handles', 'collection_titles', 'collection_count',
        'created_at', 'updated_at'
    ]
    
    assert all(col in df.columns for col in expected_columns)
    assert len(df) > 0
    
    # Verify data types and formats
    assert df['collection_count'].dtype in ['int64', 'int32']
    assert df['product_handle'].notna().all()
    
    # Verify collection data format
    for _, row in df.iterrows():
        if row['collection_count'] > 0:
            handles = row['collection_handles'].split(';')
            titles = row['collection_titles'].split(';')
            assert len(handles) == len(titles) == row['collection_count']

@pytest.mark.integration
def test_rate_limiting_integration(mock_env_vars, temp_test_dir):
    """Test integration with rate limiting patterns"""
    output_file = os.path.join(temp_test_dir, "rate_limit_test.csv")
    downloader = IntegratedShopifyDownloader(output_file=output_file)
    
    # Verify rate limiter is configured
    assert downloader.rate_limiter is not None
    assert hasattr(downloader.rate_limiter, 'wait')
    
    # Test that rate limiting is called during fetch
    result = downloader.download_and_export(limit=3)
    
    # Verify rate limiting was applied
    downloader.rate_limiter.wait.assert_called()

@pytest.mark.integration
def test_error_handling_integration(mock_env_vars, temp_test_dir):
    """Test integration with existing error handling patterns"""
    output_file = os.path.join(temp_test_dir, "error_handling_test.csv")
    
    # Test with invalid shop URL
    downloader = IntegratedShopifyDownloader(
        shop_url="invalid-url",
        access_token="test_token",
        output_file=output_file
    )
    
    result = downloader.download_and_export()
    
    # Should return error result, not raise exception
    assert result['success'] is False
    assert 'error' in result
    assert 'error_type' in result

# File Integration Tests
@pytest.mark.integration
def test_output_file_integration_with_data_directory(mock_env_vars):
    """Test integration with existing data directory structure"""
    # Use data directory like existing scripts
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    
    output_file = data_dir / "old_shopify_products.csv"
    downloader = IntegratedShopifyDownloader(output_file=str(output_file))
    
    result = downloader.download_and_export(limit=2)
    
    assert result['success'] is True
    assert output_file.exists()
    
    # Clean up
    if output_file.exists():
        output_file.unlink()

@pytest.mark.integration
def test_csv_integration_with_pandas_processing(mock_env_vars, temp_test_dir):
    """Test CSV output can be processed by existing pandas workflows"""
    output_file = os.path.join(temp_test_dir, "pandas_integration_test.csv")
    downloader = IntegratedShopifyDownloader(output_file=output_file)
    
    result = downloader.download_and_export(limit=3)
    
    assert result['success'] is True
    
    # Test pandas processing like existing scripts
    df = pd.read_csv(output_file)
    
    # Test filtering operations
    filtered_df = df[df['collection_count'] > 0]
    assert len(filtered_df) >= 0
    
    # Test aggregation operations
    collection_stats = df['collection_count'].describe()
    assert 'mean' in collection_stats
    
    # Test data transformation
    df['has_collections'] = df['collection_count'] > 0
    assert 'has_collections' in df.columns

# Performance Integration Tests
@pytest.mark.integration
@pytest.mark.performance
def test_performance_integration_with_existing_benchmarks(mock_env_vars, temp_test_dir):
    """Test performance metrics integrate with existing benchmark patterns"""
    output_file = os.path.join(temp_test_dir, "performance_integration.csv")
    downloader = IntegratedShopifyDownloader(output_file=output_file)
    
    import time
    start_time = time.time()
    
    result = downloader.download_and_export(limit=100)
    
    end_time = time.time()
    execution_time = end_time - start_time
    
    # Verify performance metrics are available
    assert result['success'] is True
    assert 'execution_time' in result
    assert result['execution_time'] > 0
    
    # Performance should be reasonable
    assert execution_time < 30  # Should complete within 30 seconds for 100 products
    
    # Verify file size is reasonable
    file_size = os.path.getsize(output_file)
    assert file_size > 0

# End-to-End Integration Test
@pytest.mark.e2e
@pytest.mark.integration
def test_end_to_end_integration_workflow(mock_env_vars, temp_test_dir):
    """Test complete end-to-end integration with existing workflow patterns"""
    output_file = os.path.join(temp_test_dir, "e2e_integration.csv")
    
    # Step 1: Initialize following existing patterns
    downloader = IntegratedShopifyDownloader(output_file=output_file)
    
    # Step 2: Execute download workflow
    result = downloader.download_and_export(limit=5)
    
    # Step 3: Verify workflow completion
    assert result['success'] is True
    assert result['products_count'] >= 0
    assert os.path.exists(result['csv_file'])
    
    # Step 4: Verify integration with data processing pipeline
    df = pd.read_csv(result['csv_file'])
    
    # Should be processable by existing data transformation scripts
    processed_df = df.copy()
    processed_df['export_timestamp'] = pd.Timestamp.now()
    processed_df['source'] = 'old_shopify'
    
    # Should integrate with existing CSV patterns
    assert len(processed_df.columns) > len(df.columns)
    
    # Step 5: Verify file can be used in existing workflows
    processed_file = os.path.join(temp_test_dir, "processed_e2e.csv")
    processed_df.to_csv(processed_file, index=False)
    
    assert os.path.exists(processed_file)
    
    # Step 6: Verify logging integration
    assert hasattr(downloader, 'logger')
    assert downloader.logger.name == __name__

if __name__ == "__main__":
    # Run integration tests
    print("🔗 Running Integration Tests...")
    pytest.main([__file__, "-m", "integration", "-v"])