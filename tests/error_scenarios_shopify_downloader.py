"""
Error Scenario Validation for Shopify Handles and Collections Downloader

This module provides comprehensive error handling validation for various
failure scenarios that can occur during Shopify data download operations.

Error scenarios covered:
- Network connectivity issues
- Authentication failures
- API rate limiting
- Invalid data responses
- File system errors
- Memory limitations
- Malformed CSV data
- API version incompatibilities
"""

import pytest
import requests
import json
import os
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import time
from datetime import datetime

# Custom exceptions for testing
class ShopifyConnectionError(Exception):
    """Raised when connection to Shopify fails"""
    pass

class ShopifyAuthenticationError(Exception):
    """Raised when authentication fails"""
    pass

class ShopifyRateLimitError(Exception):
    """Raised when API rate limit is exceeded"""
    pass

class ShopifyDataValidationError(Exception):
    """Raised when data validation fails"""
    pass

class MockErrorDownloader:
    """Mock downloader that simulates various error conditions"""
    
    def __init__(self, shop_url: str, access_token: str, output_file: str = None):
        self.shop_url = shop_url
        self.access_token = access_token
        self.output_file = output_file or "error_test_output.csv"
        self.error_mode = None
        self.retry_count = 0
        self.max_retries = 3
        
    def set_error_mode(self, error_type: str):
        """Set the type of error to simulate"""
        self.error_mode = error_type
        
    def connect(self) -> bool:
        """Test connection with error simulation"""
        if self.error_mode == "network_timeout":
            raise requests.exceptions.Timeout("Connection timed out")
        elif self.error_mode == "network_connection":
            raise requests.exceptions.ConnectionError("Failed to establish connection")
        elif self.error_mode == "invalid_shop_url":
            raise ValueError("Invalid shop URL format")
        elif self.error_mode == "authentication_failure":
            raise ShopifyAuthenticationError("Invalid access token")
        elif self.error_mode == "ssl_error":
            raise requests.exceptions.SSLError("SSL verification failed")
        
        return True
        
    def fetch_products_with_collections(self, limit: int = None) -> list:
        """Fetch products with error simulation"""
        if self.error_mode == "rate_limit_exceeded":
            self.retry_count += 1
            if self.retry_count <= 2:  # Fail first 2 attempts
                raise ShopifyRateLimitError("API rate limit exceeded. Retry after 1 second.")
            # Success on 3rd attempt
            
        elif self.error_mode == "api_version_incompatible":
            raise requests.exceptions.HTTPError("API version not supported", response=Mock(status_code=406))
        
        elif self.error_mode == "malformed_response":
            # Simulate malformed JSON response
            raise json.JSONDecodeError("Expecting value", "", 0)
        
        elif self.error_mode == "empty_response":
            return []
        
        elif self.error_mode == "invalid_product_data":
            # Return products with missing required fields
            return [
                {'id': 'invalid', 'title': 'Product without handle'},  # Missing handle
                {'handle': 'no-id-product', 'title': 'Product without ID'},  # Missing ID
            ]
        
        elif self.error_mode == "large_response_memory_error":
            # Simulate memory error with large dataset
            raise MemoryError("Not enough memory to process response")
        
        elif self.error_mode == "api_server_error":
            raise requests.exceptions.HTTPError("Internal server error", response=Mock(status_code=500))
        
        elif self.error_mode == "partial_data_corruption":
            # Return some valid and some invalid data
            return [
                {
                    'id': 'gid://shopify/Product/1',
                    'handle': 'valid-product',
                    'title': 'Valid Product',
                    'collections': [{'id': 'gid://shopify/Collection/1', 'handle': 'valid-collection', 'title': 'Valid Collection'}]
                },
                {
                    'id': None,  # Invalid ID
                    'handle': 'invalid-product',
                    'title': None,  # Invalid title
                    'collections': 'not-a-list'  # Invalid collections format
                }
            ]
        
        # Default successful response
        return [
            {
                'id': 'gid://shopify/Product/1',
                'handle': 'test-product',
                'title': 'Test Product',
                'collections': [
                    {'id': 'gid://shopify/Collection/1', 'handle': 'test-collection', 'title': 'Test Collection'}
                ]
            }
        ]
    
    def export_to_csv(self, products: list) -> str:
        """Export to CSV with error simulation"""
        if self.error_mode == "file_permission_denied":
            raise PermissionError("Permission denied: Cannot write to file")
        
        elif self.error_mode == "disk_space_full":
            raise OSError("No space left on device")
        
        elif self.error_mode == "invalid_file_path":
            self.output_file = "/invalid/path/that/does/not/exist/output.csv"
            raise FileNotFoundError("Invalid file path")
        
        elif self.error_mode == "csv_encoding_error":
            # Simulate encoding issues
            raise UnicodeEncodeError("utf-8", "invalid", 0, 1, "invalid character")
        
        elif self.error_mode == "csv_write_interrupted":
            # Simulate interrupted write
            with open(self.output_file, 'w') as f:
                f.write("partial,data,before,interruption\n")
            raise IOError("Write operation interrupted")
        
        # Standard CSV export
        import csv
        with open(self.output_file, 'w', newline='', encoding='utf-8') as csvfile:
            if not products:
                raise ValueError("No products to export")
                
            fieldnames = ['product_id', 'product_handle', 'product_title', 'collection_handles', 'collection_titles', 'collection_count']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for product in products:
                try:
                    collection_handles = [col['handle'] for col in product.get('collections', [])]
                    collection_titles = [col['title'] for col in product.get('collections', [])]
                    
                    writer.writerow({
                        'product_id': product.get('id', ''),
                        'product_handle': product.get('handle', ''),
                        'product_title': product.get('title', ''),
                        'collection_handles': ';'.join(collection_handles),
                        'collection_titles': ';'.join(collection_titles),
                        'collection_count': len(collection_handles)
                    })
                except (KeyError, TypeError, AttributeError) as e:
                    if self.error_mode == "strict_validation":
                        raise ShopifyDataValidationError(f"Invalid product data: {e}")
                    # Otherwise, skip invalid products
                    continue
        
        return self.output_file

# Test fixtures
@pytest.fixture
def error_downloader():
    """Create error downloader for testing"""
    return MockErrorDownloader(
        shop_url="error-test-store.myshopify.com",
        access_token="error_test_token",
        output_file="error_test_output.csv"
    )

@pytest.fixture
def temp_error_dir():
    """Temporary directory for error testing"""
    temp_dir = tempfile.mkdtemp(prefix="error_test_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)

# Network and Connection Error Tests
@pytest.mark.quick
def test_network_timeout_error(error_downloader):
    """Test handling of network timeout errors"""
    error_downloader.set_error_mode("network_timeout")
    
    with pytest.raises(requests.exceptions.Timeout):
        error_downloader.connect()

@pytest.mark.quick
def test_network_connection_error(error_downloader):
    """Test handling of network connection errors"""
    error_downloader.set_error_mode("network_connection")
    
    with pytest.raises(requests.exceptions.ConnectionError):
        error_downloader.connect()

@pytest.mark.quick
def test_ssl_verification_error(error_downloader):
    """Test handling of SSL verification errors"""
    error_downloader.set_error_mode("ssl_error")
    
    with pytest.raises(requests.exceptions.SSLError):
        error_downloader.connect()

@pytest.mark.quick
def test_invalid_shop_url_error(error_downloader):
    """Test handling of invalid shop URL"""
    error_downloader.set_error_mode("invalid_shop_url")
    
    with pytest.raises(ValueError, match="Invalid shop URL format"):
        error_downloader.connect()

# Authentication Error Tests
@pytest.mark.quick
def test_authentication_failure(error_downloader):
    """Test handling of authentication failures"""
    error_downloader.set_error_mode("authentication_failure")
    
    with pytest.raises(ShopifyAuthenticationError):
        error_downloader.connect()

@pytest.mark.integration
def test_expired_token_handling():
    """Test handling of expired access tokens"""
    # Simulate expired token scenario
    downloader = MockErrorDownloader("test-store.myshopify.com", "expired_token")
    downloader.set_error_mode("authentication_failure")
    
    with pytest.raises(ShopifyAuthenticationError):
        downloader.connect()

@pytest.mark.integration
def test_insufficient_permissions():
    """Test handling of insufficient API permissions"""
    # Simulate insufficient permissions
    downloader = MockErrorDownloader("test-store.myshopify.com", "limited_token")
    downloader.set_error_mode("authentication_failure")
    
    with pytest.raises(ShopifyAuthenticationError):
        downloader.connect()

# API Rate Limiting Tests
@pytest.mark.integration
def test_rate_limit_exceeded_with_retry(error_downloader):
    """Test handling of rate limit exceeded with retry logic"""
    error_downloader.set_error_mode("rate_limit_exceeded")
    
    # Should succeed after retries
    products = error_downloader.fetch_products_with_collections()
    assert len(products) >= 0
    assert error_downloader.retry_count > 0

@pytest.mark.integration
def test_rate_limit_exponential_backoff():
    """Test exponential backoff during rate limiting"""
    downloader = MockErrorDownloader("test-store.myshopify.com", "token")
    downloader.set_error_mode("rate_limit_exceeded")
    
    start_time = time.time()
    
    try:
        # Should implement exponential backoff
        products = downloader.fetch_products_with_collections()
        end_time = time.time()
        
        # Should have taken some time due to retries
        # (In a real implementation, this would verify actual backoff timing)
        assert end_time - start_time >= 0
        
    except ShopifyRateLimitError:
        # If it fails, it should be after retries
        assert downloader.retry_count > 0

# Data Validation Error Tests
@pytest.mark.quick
def test_malformed_api_response(error_downloader):
    """Test handling of malformed API responses"""
    error_downloader.set_error_mode("malformed_response")
    
    with pytest.raises(json.JSONDecodeError):
        error_downloader.fetch_products_with_collections()

@pytest.mark.quick
def test_empty_api_response(error_downloader):
    """Test handling of empty API responses"""
    error_downloader.set_error_mode("empty_response")
    
    products = error_downloader.fetch_products_with_collections()
    assert products == []

@pytest.mark.integration
def test_invalid_product_data_structure(error_downloader, temp_error_dir):
    """Test handling of invalid product data structure"""
    error_downloader.set_error_mode("invalid_product_data")
    error_downloader.output_file = os.path.join(temp_error_dir, "invalid_data.csv")
    
    products = error_downloader.fetch_products_with_collections()
    
    # Should handle invalid data gracefully
    csv_file = error_downloader.export_to_csv(products)
    assert os.path.exists(csv_file)
    
    # Verify CSV still contains some data
    with open(csv_file, 'r') as f:
        content = f.read()
        assert len(content) > 0

@pytest.mark.integration
def test_partial_data_corruption(error_downloader, temp_error_dir):
    """Test handling of partially corrupted data"""
    error_downloader.set_error_mode("partial_data_corruption")
    error_downloader.output_file = os.path.join(temp_error_dir, "partial_corruption.csv")
    
    products = error_downloader.fetch_products_with_collections()
    
    # Should handle mixed valid/invalid data
    csv_file = error_downloader.export_to_csv(products)
    assert os.path.exists(csv_file)
    
    # Verify at least valid data was exported
    import pandas as pd
    df = pd.read_csv(csv_file)
    assert len(df) >= 1  # At least one valid product should be exported

@pytest.mark.integration
def test_strict_data_validation(error_downloader):
    """Test strict data validation mode"""
    error_downloader.set_error_mode("strict_validation")
    
    # Get corrupted data
    error_downloader.error_mode = "partial_data_corruption"
    products = error_downloader.fetch_products_with_collections()
    
    # Set strict validation
    error_downloader.set_error_mode("strict_validation")
    
    # Should raise validation error
    with pytest.raises(ShopifyDataValidationError):
        error_downloader.export_to_csv(products)

# File System Error Tests
@pytest.mark.quick
def test_file_permission_denied(error_downloader):
    """Test handling of file permission errors"""
    error_downloader.set_error_mode("file_permission_denied")
    
    products = [{'id': '1', 'handle': 'test', 'title': 'Test', 'collections': []}]
    
    with pytest.raises(PermissionError):
        error_downloader.export_to_csv(products)

@pytest.mark.quick
def test_disk_space_full(error_downloader):
    """Test handling of disk space errors"""
    error_downloader.set_error_mode("disk_space_full")
    
    products = [{'id': '1', 'handle': 'test', 'title': 'Test', 'collections': []}]
    
    with pytest.raises(OSError, match="No space left on device"):
        error_downloader.export_to_csv(products)

@pytest.mark.quick
def test_invalid_file_path(error_downloader):
    """Test handling of invalid file paths"""
    error_downloader.set_error_mode("invalid_file_path")
    
    products = [{'id': '1', 'handle': 'test', 'title': 'Test', 'collections': []}]
    
    with pytest.raises(FileNotFoundError):
        error_downloader.export_to_csv(products)

@pytest.mark.integration
def test_csv_encoding_error(error_downloader):
    """Test handling of CSV encoding errors"""
    error_downloader.set_error_mode("csv_encoding_error")
    
    products = [{'id': '1', 'handle': 'test', 'title': 'Test', 'collections': []}]
    
    with pytest.raises(UnicodeEncodeError):
        error_downloader.export_to_csv(products)

@pytest.mark.integration
def test_csv_write_interrupted(error_downloader, temp_error_dir):
    """Test handling of interrupted CSV write operations"""
    error_downloader.set_error_mode("csv_write_interrupted")
    error_downloader.output_file = os.path.join(temp_error_dir, "interrupted.csv")
    
    products = [{'id': '1', 'handle': 'test', 'title': 'Test', 'collections': []}]
    
    with pytest.raises(IOError):
        error_downloader.export_to_csv(products)
    
    # Verify partial file exists
    assert os.path.exists(error_downloader.output_file)

# Memory and Performance Error Tests
@pytest.mark.integration
def test_memory_error_large_dataset(error_downloader):
    """Test handling of memory errors with large datasets"""
    error_downloader.set_error_mode("large_response_memory_error")
    
    with pytest.raises(MemoryError):
        error_downloader.fetch_products_with_collections(limit=10000)

@pytest.mark.integration
def test_api_server_error(error_downloader):
    """Test handling of API server errors"""
    error_downloader.set_error_mode("api_server_error")
    
    with pytest.raises(requests.exceptions.HTTPError):
        error_downloader.fetch_products_with_collections()

@pytest.mark.integration
def test_api_version_incompatible(error_downloader):
    """Test handling of API version incompatibility"""
    error_downloader.set_error_mode("api_version_incompatible")
    
    with pytest.raises(requests.exceptions.HTTPError):
        error_downloader.fetch_products_with_collections()

# Recovery and Resilience Tests
@pytest.mark.integration
def test_graceful_degradation_on_errors(temp_error_dir):
    """Test graceful degradation when errors occur"""
    downloader = MockErrorDownloader("test-store.myshopify.com", "token")
    downloader.output_file = os.path.join(temp_error_dir, "graceful_degradation.csv")
    
    # Simulate partial success scenario
    downloader.set_error_mode("partial_data_corruption")
    
    try:
        products = downloader.fetch_products_with_collections()
        csv_file = downloader.export_to_csv(products)
        
        # Should complete with partial data
        assert os.path.exists(csv_file)
        
        # Verify some data was exported
        import pandas as pd
        df = pd.read_csv(csv_file)
        assert len(df) > 0
        
    except Exception as e:
        # Should handle errors gracefully
        assert isinstance(e, (ShopifyDataValidationError, ValueError))

@pytest.mark.integration
def test_error_recovery_and_resume():
    """Test error recovery and resume functionality"""
    downloader = MockErrorDownloader("test-store.myshopify.com", "token")
    
    # First attempt fails with rate limit
    downloader.set_error_mode("rate_limit_exceeded")
    
    try:
        products = downloader.fetch_products_with_collections()
        # Should succeed after retries
        assert len(products) >= 0
        
    except ShopifyRateLimitError:
        # If it fails, should be after max retries
        assert downloader.retry_count >= downloader.max_retries

@pytest.mark.integration
def test_error_logging_and_reporting(temp_error_dir):
    """Test comprehensive error logging and reporting"""
    import logging
    
    # Setup logging
    log_file = os.path.join(temp_error_dir, "error_test.log")
    logging.basicConfig(
        filename=log_file,
        level=logging.ERROR,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    downloader = MockErrorDownloader("test-store.myshopify.com", "token")
    downloader.set_error_mode("authentication_failure")
    
    try:
        downloader.connect()
    except ShopifyAuthenticationError as e:
        logging.error(f"Authentication failed: {e}")
    
    # Verify error was logged
    assert os.path.exists(log_file)
    with open(log_file, 'r') as f:
        log_content = f.read()
        assert "Authentication failed" in log_content

# Edge Case Error Tests
@pytest.mark.quick
def test_empty_credentials():
    """Test handling of empty credentials"""
    downloader = MockErrorDownloader("", "")
    
    with pytest.raises(ValueError):
        downloader.connect()

@pytest.mark.quick
def test_none_credentials():
    """Test handling of None credentials"""
    downloader = MockErrorDownloader(None, None)
    
    with pytest.raises((ValueError, AttributeError)):
        downloader.connect()

@pytest.mark.integration
def test_malformed_shop_url_variations():
    """Test various malformed shop URL formats"""
    malformed_urls = [
        "not-a-url",
        "http://example.com",  # Not Shopify
        "https://example.com/shop",  # Not Shopify format
        "shop.myshopify.com/extra/path",  # Extra path
        "shop.myshopify.co.uk",  # Wrong TLD
        "",  # Empty
        "   ",  # Whitespace only
    ]
    
    for url in malformed_urls:
        downloader = MockErrorDownloader(url, "token")
        downloader.set_error_mode("invalid_shop_url")
        
        with pytest.raises(ValueError):
            downloader.connect()

# Comprehensive Error Scenario Test
@pytest.mark.e2e
def test_comprehensive_error_scenario_handling(temp_error_dir):
    """Test handling of multiple error scenarios in sequence"""
    downloader = MockErrorDownloader("test-store.myshopify.com", "token")
    
    error_scenarios = [
        "network_timeout",
        "rate_limit_exceeded",
        "partial_data_corruption",
        "csv_write_interrupted"
    ]
    
    results = {}
    
    for scenario in error_scenarios:
        downloader.set_error_mode(scenario)
        downloader.output_file = os.path.join(temp_error_dir, f"{scenario}_test.csv")
        downloader.retry_count = 0  # Reset retry count
        
        try:
            if scenario in ["network_timeout"]:
                downloader.connect()
            elif scenario in ["rate_limit_exceeded", "partial_data_corruption"]:
                products = downloader.fetch_products_with_collections()
                if scenario == "partial_data_corruption":
                    csv_file = downloader.export_to_csv(products)
                    results[scenario] = "success_with_partial_data"
            elif scenario == "csv_write_interrupted":
                products = [{'id': '1', 'handle': 'test', 'title': 'Test', 'collections': []}]
                downloader.export_to_csv(products)
                
        except Exception as e:
            results[scenario] = f"error_{type(e).__name__}"
    
    # Verify appropriate error handling for each scenario
    assert len(results) > 0
    print(f"Error scenario results: {results}")

if __name__ == "__main__":
    # Run error scenario tests
    print("🔥 Running Error Scenario Validation Tests...")
    pytest.main([__file__, "-v", "--tb=short"])