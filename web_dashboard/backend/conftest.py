"""Pytest configuration and fixtures for the test suite."""
import pytest
import tempfile
import os
from unittest.mock import Mock, patch
from flask import Flask
from flask_jwt_extended import JWTManager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import db_manager, Base
from batch_processor import BatchProcessor, BatchConfig
from conflict_detector import ConflictDetector
from memory_optimizer import MemoryMonitor


@pytest.fixture(scope="session")
def test_app():
    """Create a test Flask application."""
    app = Flask(__name__)
    app.config.update({
        'TESTING': True,
        'JWT_SECRET_KEY': 'test-secret-key',
        'SQLALCHEMY_DATABASE_URL': 'sqlite:///:memory:',
        'REDIS_URL': 'redis://localhost:6379/1'  # Test Redis DB
    })
    
    # Initialize JWT
    jwt = JWTManager(app)
    
    return app


@pytest.fixture(scope="session")
def test_db():
    """Create a test database."""
    # Create in-memory SQLite database for testing
    engine = create_engine('sqlite:///:memory:', echo=False)
    Base.metadata.create_all(engine)
    
    Session = sessionmaker(bind=engine)
    return Session


@pytest.fixture
def db_session(test_db):
    """Create a database session for a test."""
    session = test_db()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def mock_websocket_service():
    """Create a mock WebSocket service."""
    mock = Mock()
    mock.emit = Mock()
    mock.emit_to_room = Mock()
    return mock


@pytest.fixture
def batch_config():
    """Create a test batch configuration."""
    return BatchConfig(
        batch_size=10,
        max_workers=2,
        timeout_seconds=30,
        retry_attempts=2,
        retry_delay=0.1,
        memory_limit_mb=128,
        enable_parallel=True,
        checkpoint_interval=5
    )


@pytest.fixture
def batch_processor(batch_config, mock_websocket_service):
    """Create a test batch processor."""
    processor = BatchProcessor(config=batch_config)
    # Clear any existing batches
    processor.active_batches.clear()
    processor.batch_results.clear()
    return processor


@pytest.fixture
def conflict_detector():
    """Create a test conflict detector."""
    detector = ConflictDetector()
    # Clear any existing conflicts
    detector.detected_conflicts.clear()
    return detector


@pytest.fixture
def memory_monitor():
    """Create a test memory monitor."""
    return MemoryMonitor(warning_threshold_mb=64, critical_threshold_mb=128)


@pytest.fixture
def sample_batch_items():
    """Sample items for batch processing tests."""
    return [
        {"id": "item_1", "title": "Product 1", "sku": "SKU001", "price": 29.99},
        {"id": "item_2", "title": "Product 2", "sku": "SKU002", "price": 39.99},
        {"id": "item_3", "title": "Product 3", "sku": "SKU003", "price": 49.99},
        {"id": "item_4", "title": "Product 4", "sku": "SKU004", "price": 59.99},
        {"id": "item_5", "title": "Product 5", "sku": "SKU005", "price": 69.99}
    ]


@pytest.fixture
def sample_conflict_records():
    """Sample records for conflict detection tests."""
    source_record = {
        "id": "product_123",
        "title": "Original Product",
        "price": 29.99,
        "description": "Original description",
        "updated_at": "2024-01-01T10:00:00Z"
    }
    
    target_record = {
        "id": "product_123",
        "title": "Modified Product",  # Conflict: different title
        "price": 29.99,              # No conflict: same price
        "description": "Updated description",  # Conflict: different description
        "updated_at": "2024-01-02T10:00:00Z"   # Conflict: different timestamp
    }
    
    return source_record, target_record


@pytest.fixture
def test_client(test_app):
    """Create a test client for API testing."""
    with test_app.test_client() as client:
        with test_app.app_context():
            yield client


@pytest.fixture
def auth_headers(test_app):
    """Create authentication headers for API testing."""
    with test_app.app_context():
        from flask_jwt_extended import create_access_token
        access_token = create_access_token(identity="test-user")
        return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture(autouse=True)
def mock_redis():
    """Mock Redis for tests that don't need actual Redis."""
    with patch('redis.from_url') as mock_redis_client:
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.get.return_value = None
        mock_client.set.return_value = True
        mock_client.delete.return_value = True
        mock_redis_client.return_value = mock_client
        yield mock_client


@pytest.fixture
def temp_file():
    """Create a temporary file for testing."""
    with tempfile.NamedTemporaryFile(mode='w+', delete=False) as f:
        yield f.name
    os.unlink(f.name)


@pytest.fixture
def mock_psutil():
    """Mock psutil for memory monitoring tests."""
    with patch('psutil.virtual_memory') as mock_vm, \
         patch('psutil.Process') as mock_process:
        
        # Mock virtual memory
        mock_vm.return_value.total = 8 * 1024 * 1024 * 1024  # 8GB
        mock_vm.return_value.available = 4 * 1024 * 1024 * 1024  # 4GB
        mock_vm.return_value.percent = 50.0
        
        # Mock process memory
        mock_proc_instance = Mock()
        mock_proc_instance.memory_info.return_value.rss = 256 * 1024 * 1024  # 256MB
        mock_process.return_value = mock_proc_instance
        
        yield {
            'virtual_memory': mock_vm,
            'process': mock_process
        }


def sample_processor_function(items):
    """Sample processor function for testing."""
    results = []
    for item in items:
        if not item.get('title'):
            results.append({
                'id': item.get('id', 'unknown'),
                'status': 'error',
                'error': 'Missing title'
            })
        else:
            results.append({
                'id': item.get('id', 'unknown'),
                'status': 'success',
                'processed_item': {**item, 'processed': True}
            })
    return results