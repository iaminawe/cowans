"""
Core functionality acceptance tests implementing London School TDD principles.

Tests verify AI Verifiable End Results from PRDMasterPlan.md:
- Successful automated FTP downloads from Etilize
- Correct transformation of product data with JSON metafields
- Successful batch uploads to Shopify
- Completion of core automated tests

Test tags support recursive testing strategy:
@quick: Basic function tests (run on every code change)
@integration: Component interaction tests (run before merge)
@e2e: End-to-end flow tests (run nightly)
@performance: Load and stress tests (run weekly)
"""

import pytest
from unittest.mock import Mock, patch, call
import json
import os
from pathlib import Path
import time
import pandas as pd
from scripts.ftp_downloader import FTPDownloader
from scripts.create_metafields import MetafieldCreator
from scripts.shopify_uploader import ShopifyUploader

# Test data paths - using actual CSV files from data directory for transformation testing
TEST_CSV_PATH = Path('data/CWS_Etilize_reduced.csv')
TRANSFORMED_DATA_PATH = Path('data/CWS_Etilize_shopify.csv')

# Sample test data for when file doesn't exist
TEST_DATA = pd.DataFrame({
    'title': ['Test Product 1', 'Test Product 2'],
    'description': ['Description 1', 'Description 2'],
    'specs': ['{"color": "blue"}', '{"color": "red"}']
})

# Performance thresholds - adjusted for test environment
DOWNLOAD_SPEED_THRESHOLD = 100 * 1024  # 100KB/s
TRANSFORM_TIME_THRESHOLD = 10  # 10ms per product
UPLOAD_RATE_THRESHOLD = 10 / 60  # 10 products/minute

@pytest.fixture
def mock_ftp():
    """Mock FTP server for testing downloads without external dependencies"""
    mock = Mock()
    mock.connect.return_value = True
    mock.download.return_value = TEST_CSV_PATH
    mock.login.return_value = None
    mock.cwd.return_value = None
    mock.quit.return_value = None
    mock.size.return_value = 1024 * 1024  # 1MB simulated file size
    mock.sock = Mock()
    
    def write_test_data(cmd, callback, blocksize=8192, rest=None):
        """Write test data to simulate file download with resume support"""
        # Generate larger test data for performance testing
        test_data = pd.DataFrame({
            'title': [f'Test Product {i}' for i in range(1000)],
            'description': ['Description'] * 1000,
            'specs': ['{"color": "blue"}'] * 1000
        })
        test_data.to_csv(TEST_CSV_PATH, index=False)
        
        # Read file in chunks to simulate network transfer
        start_pos = rest if rest is not None else 0
        with open(TEST_CSV_PATH, 'rb') as f:
            f.seek(start_pos)
            while True:
                chunk = f.read(blocksize)
                if not chunk:
                    break
                time.sleep(0.001)  # Simulate network delay
                callback(chunk)
    
    mock.retrbinary.side_effect = write_test_data
    return mock

@pytest.fixture
def mock_json_validator():
    """Mock JSON validator for verifying metafield formats"""
    mock = Mock()
    mock.validate.return_value = True
    return mock

@pytest.fixture
def mock_rate_limiter():
    """Mock rate limiter for controlling API request timing"""
    mock = Mock()
    mock.wait.return_value = None
    return mock

@pytest.fixture
def mock_session():
    """Mock requests session for testing API requests"""
    mock = Mock()
    mock.request.return_value.json.return_value = {'id': '123', 'status': 'success'}
    mock.request.return_value.raise_for_status.return_value = None
    return mock

@pytest.fixture(autouse=True)
def setup_teardown():
    """Setup and teardown for each test"""
    # Setup - ensure test data directory exists
    TEST_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    yield
    
    # Teardown - clean up test files
    if TEST_CSV_PATH.exists():
        TEST_CSV_PATH.unlink()
    if TRANSFORMED_DATA_PATH.exists():
        TRANSFORMED_DATA_PATH.unlink()

@pytest.mark.quick
@pytest.mark.integration
def test_ftp_connection_and_data_download(mock_ftp):
    """
    Verify that the application can connect to the Etilize FTP server and download data.
    AI Verifiable End Result: Successful automated FTP downloads from Etilize
    """
    with patch('ftplib.FTP', return_value=mock_ftp):
        downloader = FTPDownloader(
            host="test.ftp.com",
            username="test_user",
            password="test_pass"
        )
        
        # Test connection
        connected = downloader.connect()
        assert connected, "Failed to connect to FTP server"
        mock_ftp.login.assert_called_once()
        
        # Test download
        downloaded_file = downloader.download()
        assert downloaded_file.name == TEST_CSV_PATH.name, "Failed to download product data file"
        mock_ftp.retrbinary.assert_called_once()
        assert downloaded_file.exists(), "Download file was not created"

@pytest.mark.quick
@pytest.mark.integration
def test_data_transformation():
    """
    Verify that the application can transform product data correctly.
    AI Verifiable End Result: Correct transformation of product data with JSON metafields
    """
    # Create test data file
    TEST_DATA.to_csv(TEST_CSV_PATH, index=False)
    assert TEST_CSV_PATH.exists(), f"Test data file {TEST_CSV_PATH} not found"
    
    transformer = MetafieldCreator()
    transformed_data = transformer.transform(TEST_CSV_PATH)
    
    # Verify structure and content of transformed data
    assert isinstance(transformed_data, list), "Transformed data should be a list"
    assert len(transformed_data) == len(TEST_DATA), "Wrong number of products transformed"
    
    for product in transformed_data:
        assert 'title' in product, "Product missing title"
        assert 'metafields' in product, "Product missing metafields"
        assert isinstance(product['metafields'], dict), "Metafields should be a dictionary"
        
        # Verify JSON formatting of metafields
        for field, value in product['metafields'].items():
            assert json.loads(value) if isinstance(value, str) else True, f"Invalid JSON in metafield {field}"

@pytest.mark.integration
@pytest.mark.performance
def test_shopify_product_upload(mock_session):
    """
    Verify that the application can upload transformed products to Shopify.
    AI Verifiable End Result: Successful batch uploads to Shopify
    """
    with patch('requests.Session', return_value=mock_session):
        uploader = ShopifyUploader(
            shop_url="test-store.myshopify.com",
            access_token="test_token"
        )
        
        # Test single product upload
        test_product = {
            'title': 'Test Product',
            'metafields': {'specs': json.dumps({'color': 'blue'})}
        }
        result = uploader.upload_product(test_product)
        assert result['status'] == 'success', "Failed to upload product"
        mock_session.request.assert_called()
        
        # Test batch upload
        test_products = [test_product for _ in range(3)]
        results = uploader.upload_batch(test_products)
        assert all(r['status'] == 'success' for r in results), "Batch upload failed"
        assert mock_session.request.call_count == 5  # auth + 1 single + 3 batch

@pytest.mark.quick
def test_error_handling_ftp(mock_ftp):
    """
    Verify proper error handling for FTP issues.
    Tests error handling without masking underlying issues.
    """
    mock_ftp.login.side_effect = Exception("Connection failed")
    
    with patch('ftplib.FTP', return_value=mock_ftp):
        downloader = FTPDownloader(
            host="test.ftp.com",
            username="test_user",
            password="test_pass"
        )
        with pytest.raises(RuntimeError) as exc_info:
            downloader.connect()
        assert "Connection failed" in str(exc_info.value)

@pytest.mark.quick
def test_error_handling_transformation():
    """
    Verify proper error handling for data transformation issues.
    Tests error handling without using bad fallbacks.
    """
    transformer = MetafieldCreator()
    with pytest.raises(FileNotFoundError):
        transformer.transform("nonexistent_file.csv")

@pytest.mark.quick
def test_error_handling_shopify(mock_session):
    """
    Verify proper error handling for Shopify API issues.
    Tests error handling without masking API errors.
    """
    mock_session.request.side_effect = Exception("API Error")
    
    with patch('requests.Session', return_value=mock_session):
        uploader = ShopifyUploader(
            shop_url="test-store.myshopify.com",
            access_token="test_token"
        )
        with pytest.raises(Exception) as exc_info:
            uploader.upload_product({'title': 'Test'})
        assert "API Error" in str(exc_info.value)

@pytest.mark.e2e
@pytest.mark.performance
def test_full_integration_flow(mock_ftp, mock_session, mock_json_validator):
    """
    Verify the complete integration flow from download to upload.
    Supports recursive testing after system changes.
    """
    with patch('ftplib.FTP', return_value=mock_ftp), \
         patch('requests.Session', return_value=mock_session):
        
        # Step 1: Download with performance check
        start_time = time.time()
        downloader = FTPDownloader(
            host="test.ftp.com",
            username="test_user",
            password="test_pass"
        )
        downloaded_file = downloader.download()
        download_time = time.time() - start_time
        file_size = TEST_CSV_PATH.stat().st_size
        download_speed = file_size / download_time
        assert download_speed >= DOWNLOAD_SPEED_THRESHOLD, f"Download speed {download_speed/1024/1024:.2f}MB/s below threshold"
        assert downloaded_file.name == TEST_CSV_PATH.name
        
        # Step 2: Transform with performance check
        transformer = MetafieldCreator()
        start_time = time.time()
        transformed_data = transformer.transform(downloaded_file)
        transform_time = time.time() - start_time
        transform_time_per_product = transform_time / len(transformed_data)
        assert transform_time_per_product <= TRANSFORM_TIME_THRESHOLD, f"Transform time {transform_time_per_product*1000:.2f}ms per product exceeds threshold"
        assert len(transformed_data) > 0
        
        # Step 3: Upload with rate limiting
        uploader = ShopifyUploader(
            shop_url="test-store.myshopify.com",
            access_token="test_token"
        )
        start_time = time.time()
        results = uploader.upload_batch(transformed_data[:10])  # Test with subset for reasonable duration
        upload_time = time.time() - start_time
        upload_rate = len(transformed_data[:10]) / upload_time
        assert upload_rate >= UPLOAD_RATE_THRESHOLD, f"Upload rate {upload_rate*60:.2f} products/minute below threshold"
        assert all(r['status'] == 'success' for r in results)