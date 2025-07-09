# Shopify Sync Testing Guide

## Overview

This guide provides comprehensive testing recommendations for validating the Shopify sync system functionality, performance, and reliability.

## Testing Strategy

### Test Levels

1. **Unit Tests** - Individual component testing
2. **Integration Tests** - API and service interaction testing  
3. **End-to-End Tests** - Complete workflow testing
4. **Performance Tests** - Load and stress testing
5. **User Acceptance Tests** - Business scenario validation

## Unit Testing

### Backend Unit Tests

#### 1. Sync Service Tests

```python
# tests/test_sync_service.py
import pytest
from unittest.mock import Mock, patch
from services.shopify_sync_service import ShopifySyncService
from models import Product

class TestShopifySyncService:
    
    @pytest.fixture
    def sync_service(self):
        return ShopifySyncService()
    
    def test_calculate_sync_status(self, sync_service):
        """Test sync status calculation logic"""
        # Product with Shopify ID should be considered synced
        product = Product(shopify_product_id="gid://shopify/Product/123")
        assert sync_service.get_sync_status(product) == "synced"
        
        # Product without Shopify ID should be not synced
        product = Product(shopify_product_id=None)
        assert sync_service.get_sync_status(product) == "not_synced"
    
    def test_prepare_product_for_shopify(self, sync_service):
        """Test product data transformation"""
        product = Product(
            name="Test Product",
            description="Test Description",
            price=29.99,
            sku="TEST-001"
        )
        
        shopify_data = sync_service.prepare_for_shopify(product)
        
        assert shopify_data["title"] == "Test Product"
        assert shopify_data["description"] == "Test Description"
        assert shopify_data["variants"][0]["price"] == "29.99"
        assert shopify_data["variants"][0]["sku"] == "TEST-001"
    
    @patch('services.shopify_sync_service.ShopifyAPIBase')
    def test_sync_product_success(self, mock_shopify, sync_service):
        """Test successful product sync"""
        mock_client = Mock()
        mock_shopify.return_value = mock_client
        mock_client.execute_graphql.return_value = {
            'data': {
                'productCreate': {
                    'product': {
                        'id': 'gid://shopify/Product/123',
                        'handle': 'test-product'
                    },
                    'userErrors': []
                }
            }
        }
        
        product = Product(name="Test Product")
        result = sync_service.sync_product(product)
        
        assert result['success'] is True
        assert result['shopify_id'] == 'gid://shopify/Product/123'
```

#### 2. WebSocket Service Tests

```python
# tests/test_websocket_service.py
import pytest
from unittest.mock import Mock, MagicMock
from websocket_service import WebSocketService, WebSocketEvent

class TestWebSocketService:
    
    @pytest.fixture
    def websocket_service(self):
        mock_socketio = Mock()
        return WebSocketService(mock_socketio)
    
    def test_register_client(self, websocket_service):
        """Test client registration"""
        websocket_service.register_client('test-sid', user_id=1)
        
        assert 'test-sid' in websocket_service.connected_clients
        assert websocket_service.connected_clients['test-sid']['user_id'] == 1
    
    def test_emit_sync_status(self, websocket_service):
        """Test sync status emission"""
        mock_socketio = websocket_service.socketio
        
        status = {
            'products_synced': 100,
            'products_pending': 50,
            'last_sync': '2025-01-09T10:00:00Z'
        }
        
        websocket_service.emit_sync_status('sync-123', status)
        
        mock_socketio.emit.assert_called_once()
        call_args = mock_socketio.emit.call_args[1]
        assert call_args['event'] == 'sync_status'
        assert call_args['data']['data']['sync_id'] == 'sync-123'
```

#### 3. Staging System Tests

```python
# tests/test_staging_system.py
import pytest
from models import Product, StagedProductChange
from services.staging_service import StagingService

class TestStagingSystem:
    
    def test_create_staged_change(self):
        """Test staging a product change"""
        service = StagingService()
        
        current_data = {'name': 'Old Name', 'price': 10.00}
        new_data = {'name': 'New Name', 'price': 15.00}
        
        staged = service.create_staged_change(
            product_id=1,
            current_data=current_data,
            new_data=new_data
        )
        
        assert staged.operation_type == 'UPDATE'
        assert staged.changes == {
            'name': {'old': 'Old Name', 'new': 'New Name'},
            'price': {'old': 10.00, 'new': 15.00}
        }
    
    def test_approve_staged_change(self):
        """Test approving a staged change"""
        service = StagingService()
        staged = StagedProductChange(
            id=1,
            status='pending',
            operation_type='UPDATE'
        )
        
        approved = service.approve_change(staged)
        
        assert approved.status == 'approved'
        assert approved.approved_at is not None
```

### Frontend Unit Tests

#### 1. Component Tests

```typescript
// tests/ProductsTable.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { ProductsTable } from '@/components/ProductsTable';
import { Product } from '@/types';

describe('ProductsTable', () => {
  const mockProducts: Product[] = [
    {
      id: 1,
      name: 'Test Product 1',
      shopify_product_id: 'gid://shopify/Product/123',
      shopify_sync_status: 'synced'
    },
    {
      id: 2,
      name: 'Test Product 2',
      shopify_product_id: null,
      shopify_sync_status: null
    }
  ];
  
  test('displays correct sync status icons', () => {
    render(<ProductsTable products={mockProducts} />);
    
    // First product should show green checkmark
    const syncedIcon = screen.getByTestId('sync-status-1');
    expect(syncedIcon).toHaveClass('text-green-500');
    
    // Second product should show gray X
    const notSyncedIcon = screen.getByTestId('sync-status-2');
    expect(notSyncedIcon).toHaveClass('text-gray-400');
  });
  
  test('handles bulk selection', () => {
    const onSelectionChange = jest.fn();
    render(
      <ProductsTable 
        products={mockProducts} 
        onSelectionChange={onSelectionChange}
      />
    );
    
    // Select all checkbox
    const selectAllCheckbox = screen.getByRole('checkbox', { name: /select all/i });
    fireEvent.click(selectAllCheckbox);
    
    expect(onSelectionChange).toHaveBeenCalledWith([1, 2]);
  });
});
```

#### 2. WebSocket Context Tests

```typescript
// tests/WebSocketContext.test.tsx
import { renderHook, act } from '@testing-library/react';
import { useWebSocket, WebSocketProvider } from '@/contexts/WebSocketContext';
import { io } from 'socket.io-client';

jest.mock('socket.io-client');

describe('WebSocketContext', () => {
  test('connects with auth token', () => {
    const mockSocket = {
      on: jest.fn(),
      emit: jest.fn(),
      connected: true
    };
    
    (io as jest.Mock).mockReturnValue(mockSocket);
    localStorage.setItem('auth_token', 'test-token');
    
    const { result } = renderHook(() => useWebSocket(), {
      wrapper: ({ children }) => (
        <WebSocketProvider enableWebSocket={true}>
          {children}
        </WebSocketProvider>
      )
    });
    
    expect(io).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        auth: { token: 'test-token' }
      })
    );
  });
  
  test('handles disconnection gracefully', () => {
    const mockSocket = {
      on: jest.fn((event, handler) => {
        if (event === 'disconnect') {
          handler();
        }
      }),
      emit: jest.fn(),
      connected: false
    };
    
    (io as jest.Mock).mockReturnValue(mockSocket);
    
    const { result } = renderHook(() => useWebSocket(), {
      wrapper: WebSocketProvider
    });
    
    expect(result.current.isConnected).toBe(false);
  });
});
```

## Integration Testing

### API Integration Tests

```python
# tests/integration/test_sync_api.py
import pytest
from flask import Flask
from web_dashboard.backend.app import app
from database import db_session

class TestSyncAPI:
    
    @pytest.fixture
    def client(self):
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client
    
    @pytest.fixture
    def auth_headers(self):
        # Mock authentication
        return {'Authorization': 'Bearer test-token'}
    
    def test_start_sync_down(self, client, auth_headers):
        """Test starting a sync down operation"""
        response = client.post(
            '/api/shopify/sync-down/start',
            json={'sync_type': 'incremental'},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'sync_id' in data or 'batch_id' in data
        assert data['success'] is True
    
    def test_get_sync_status(self, client, auth_headers):
        """Test retrieving sync status"""
        # Start a sync first
        sync_response = client.post(
            '/api/shopify/sync-down/start',
            json={'sync_type': 'full'},
            headers=auth_headers
        )
        sync_id = sync_response.get_json().get('sync_id')
        
        # Get status
        status_response = client.get(
            f'/api/shopify/sync-down/status/{sync_id}',
            headers=auth_headers
        )
        
        assert status_response.status_code == 200
        status_data = status_response.get_json()
        assert 'status' in status_data
        assert 'progress' in status_data
```

### Database Integration Tests

```python
# tests/integration/test_database_operations.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Product, SyncBatch, StagedProductChange

class TestDatabaseOperations:
    
    @pytest.fixture
    def session(self):
        engine = create_engine('sqlite:///:memory:')
        Session = sessionmaker(bind=engine)
        # Create tables
        Base.metadata.create_all(engine)
        session = Session()
        yield session
        session.close()
    
    def test_sync_batch_creation(self, session):
        """Test creating a sync batch with products"""
        batch = SyncBatch(
            batch_type='full_sync',
            source='shopify',
            status='running'
        )
        session.add(batch)
        session.commit()
        
        # Add products to batch
        products = [
            Product(name=f'Product {i}', batch_id=batch.id)
            for i in range(5)
        ]
        session.add_all(products)
        session.commit()
        
        # Verify
        assert batch.id is not None
        assert session.query(Product).filter_by(batch_id=batch.id).count() == 5
    
    def test_staged_changes_workflow(self, session):
        """Test the complete staging workflow"""
        # Create product
        product = Product(name='Test Product', price=10.00)
        session.add(product)
        session.commit()
        
        # Stage a change
        staged = StagedProductChange(
            product_id=product.id,
            operation_type='UPDATE',
            change_data={'price': 15.00},
            status='pending'
        )
        session.add(staged)
        session.commit()
        
        # Approve change
        staged.status = 'approved'
        session.commit()
        
        # Apply change
        product.price = 15.00
        staged.status = 'applied'
        session.commit()
        
        assert product.price == 15.00
        assert staged.status == 'applied'
```

## End-to-End Testing

### Complete Sync Workflow Test

```python
# tests/e2e/test_sync_workflow.py
import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class TestSyncWorkflow:
    
    @pytest.fixture
    def driver(self):
        driver = webdriver.Chrome()
        driver.implicitly_wait(10)
        yield driver
        driver.quit()
    
    def test_complete_sync_workflow(self, driver):
        """Test complete sync workflow from UI"""
        # Login
        driver.get("http://localhost:3055")
        driver.find_element(By.ID, "email").send_keys("test@example.com")
        driver.find_element(By.ID, "password").send_keys("password")
        driver.find_element(By.ID, "login-button").click()
        
        # Navigate to sync dashboard
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.LINK_TEXT, "Sync"))
        ).click()
        
        # Start sync down
        driver.find_element(By.ID, "sync-down-tab").click()
        driver.find_element(By.ID, "start-sync-button").click()
        
        # Wait for sync to complete
        WebDriverWait(driver, 60).until(
            EC.text_to_be_present_in_element(
                (By.ID, "sync-status"), 
                "Completed"
            )
        )
        
        # Review staged changes
        driver.find_element(By.ID, "staged-changes-tab").click()
        staged_count = driver.find_element(By.ID, "staged-count").text
        assert int(staged_count) > 0
        
        # Approve all changes
        driver.find_element(By.ID, "bulk-approve-button").click()
        driver.find_element(By.ID, "confirm-approve").click()
        
        # Push to Shopify
        driver.find_element(By.ID, "sync-up-tab").click()
        driver.find_element(By.ID, "push-to-shopify").click()
        
        # Verify completion
        WebDriverWait(driver, 60).until(
            EC.text_to_be_present_in_element(
                (By.ID, "push-status"), 
                "Success"
            )
        )
```

### WebSocket Real-time Updates Test

```javascript
// tests/e2e/websocket-updates.test.js
describe('WebSocket Real-time Updates', () => {
  beforeEach(() => {
    cy.login('test@example.com', 'password');
    cy.visit('/sync');
  });
  
  it('shows real-time sync progress', () => {
    // Start sync operation
    cy.get('[data-testid="sync-down-tab"]').click();
    cy.get('[data-testid="start-sync"]').click();
    
    // Verify WebSocket connection indicator
    cy.get('[data-testid="connection-status"]')
      .should('have.class', 'bg-green-500');
    
    // Check for progress updates
    cy.get('[data-testid="sync-progress"]', { timeout: 10000 })
      .should('be.visible')
      .and('contain', '%');
    
    // Verify operation logs appear
    cy.get('[data-testid="operation-logs"]')
      .should('contain', 'Sync started')
      .and('contain', 'Fetching products');
    
    // Wait for completion
    cy.get('[data-testid="sync-status"]', { timeout: 60000 })
      .should('contain', 'Completed');
  });
});
```

## Performance Testing

### Load Testing Script

```python
# tests/performance/load_test.py
import asyncio
import aiohttp
import time
from statistics import mean, stdev

class LoadTester:
    
    def __init__(self, base_url, auth_token):
        self.base_url = base_url
        self.headers = {'Authorization': f'Bearer {auth_token}'}
        self.results = []
    
    async def sync_product(self, session, product_id):
        """Simulate syncing a single product"""
        start_time = time.time()
        
        try:
            async with session.post(
                f'{self.base_url}/api/sync/products/{product_id}',
                headers=self.headers
            ) as response:
                await response.json()
                success = response.status == 200
        except Exception as e:
            success = False
            
        duration = time.time() - start_time
        self.results.append({
            'duration': duration,
            'success': success,
            'product_id': product_id
        })
    
    async def run_load_test(self, num_products=100, concurrency=10):
        """Run load test with specified concurrency"""
        async with aiohttp.ClientSession() as session:
            tasks = []
            
            for i in range(num_products):
                task = self.sync_product(session, i)
                tasks.append(task)
                
                # Control concurrency
                if len(tasks) >= concurrency:
                    await asyncio.gather(*tasks)
                    tasks = []
            
            # Process remaining tasks
            if tasks:
                await asyncio.gather(*tasks)
    
    def print_results(self):
        """Print load test results"""
        successful = [r for r in self.results if r['success']]
        failed = [r for r in self.results if not r['success']]
        durations = [r['duration'] for r in successful]
        
        print(f"Total Requests: {len(self.results)}")
        print(f"Successful: {len(successful)}")
        print(f"Failed: {len(failed)}")
        print(f"Success Rate: {len(successful)/len(self.results)*100:.2f}%")
        
        if durations:
            print(f"Average Duration: {mean(durations):.3f}s")
            print(f"Min Duration: {min(durations):.3f}s")
            print(f"Max Duration: {max(durations):.3f}s")
            print(f"Std Deviation: {stdev(durations):.3f}s")

# Run the test
async def main():
    tester = LoadTester('http://localhost:3560', 'test-token')
    
    print("Running load test...")
    start = time.time()
    await tester.run_load_test(num_products=1000, concurrency=20)
    total_time = time.time() - start
    
    print(f"\nTotal Test Duration: {total_time:.2f}s")
    tester.print_results()

if __name__ == '__main__':
    asyncio.run(main())
```

### Memory Usage Testing

```python
# tests/performance/memory_test.py
import psutil
import requests
import time
import matplotlib.pyplot as plt

def monitor_memory_during_sync():
    """Monitor memory usage during sync operation"""
    process = psutil.Process()
    memory_usage = []
    timestamps = []
    
    # Start sync operation
    response = requests.post(
        'http://localhost:3560/api/shopify/sync-down/start',
        json={'sync_type': 'full'},
        headers={'Authorization': 'Bearer test-token'}
    )
    sync_id = response.json()['sync_id']
    
    # Monitor memory while sync runs
    start_time = time.time()
    while True:
        memory_mb = process.memory_info().rss / 1024 / 1024
        memory_usage.append(memory_mb)
        timestamps.append(time.time() - start_time)
        
        # Check if sync completed
        status_response = requests.get(
            f'http://localhost:3560/api/shopify/sync-down/status/{sync_id}',
            headers={'Authorization': 'Bearer test-token'}
        )
        
        if status_response.json()['status'] in ['completed', 'error']:
            break
            
        time.sleep(1)
    
    # Plot results
    plt.figure(figsize=(10, 6))
    plt.plot(timestamps, memory_usage)
    plt.xlabel('Time (seconds)')
    plt.ylabel('Memory Usage (MB)')
    plt.title('Memory Usage During Full Sync')
    plt.grid(True)
    plt.savefig('memory_usage.png')
    
    print(f"Peak Memory: {max(memory_usage):.2f} MB")
    print(f"Average Memory: {sum(memory_usage)/len(memory_usage):.2f} MB")
```

## User Acceptance Testing

### Test Scenarios

#### Scenario 1: First-time Product Sync

**Objective**: Verify new products can be synced to Shopify

**Steps**:
1. Login as admin user
2. Navigate to Products page
3. Select products without Shopify ID (gray X icon)
4. Click "Sync to Shopify" button
5. Review staged changes
6. Approve all changes
7. Execute sync
8. Verify products now show green checkmark

**Expected Results**:
- Products successfully created in Shopify
- Sync status updated to show green checkmark
- Shopify product IDs populated in database
- Activity log shows successful sync

#### Scenario 2: Bulk Update Products

**Objective**: Verify bulk product updates work correctly

**Steps**:
1. Select multiple products using checkboxes
2. Choose "Update in Shopify" from bulk actions
3. Make changes (price, description, etc.)
4. Review changes in staging area
5. Approve and push to Shopify
6. Verify updates in Shopify admin

**Expected Results**:
- All selected products updated
- Changes reflected in Shopify
- Sync timestamps updated
- No data loss or corruption

#### Scenario 3: Handle Sync Errors

**Objective**: Verify system handles errors gracefully

**Steps**:
1. Attempt to sync with invalid data
2. Simulate network interruption during sync
3. Exceed rate limits
4. Try to sync deleted products

**Expected Results**:
- Clear error messages displayed
- Partial success handled correctly
- Failed items can be retried
- System remains stable

## Automated Test Execution

### CI/CD Pipeline Configuration

```yaml
# .github/workflows/test.yml
name: Shopify Sync Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:13
        env:
          POSTGRES_PASSWORD: testpass
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      
      redis:
        image: redis:6
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-cov pytest-asyncio
    
    - name: Run unit tests
      run: |
        pytest tests/unit -v --cov=web_dashboard
    
    - name: Run integration tests
      env:
        DATABASE_URL: postgresql://postgres:testpass@localhost/test_db
        REDIS_URL: redis://localhost:6379
      run: |
        pytest tests/integration -v
    
    - name: Run E2E tests
      run: |
        npm install
        npm run test:e2e
    
    - name: Upload coverage
      uses: codecov/codecov-action@v1
```

### Test Execution Commands

```bash
# Run all tests
make test

# Run specific test suites
pytest tests/unit -v
pytest tests/integration -v
npm run test:frontend
npm run test:e2e

# Run with coverage
pytest --cov=web_dashboard --cov-report=html

# Run performance tests
python tests/performance/load_test.py
python tests/performance/memory_test.py

# Run in watch mode (frontend)
npm run test:watch
```

## Test Data Management

### Test Data Fixtures

```python
# tests/fixtures/test_data.py
import factory
from factory.alchemy import SQLAlchemyModelFactory
from models import Product, Category

class CategoryFactory(SQLAlchemyModelFactory):
    class Meta:
        model = Category
    
    name = factory.Sequence(lambda n: f"Category {n}")
    description = factory.Faker('sentence')

class ProductFactory(SQLAlchemyModelFactory):
    class Meta:
        model = Product
    
    name = factory.Faker('product_name')
    description = factory.Faker('paragraph')
    sku = factory.Sequence(lambda n: f"SKU-{n:05d}")
    price = factory.Faker('pyfloat', positive=True, max_value=1000)
    category = factory.SubFactory(CategoryFactory)
    shopify_product_id = factory.Maybe(
        factory.Faker('boolean'),
        yes_declaration=factory.Sequence(lambda n: f"gid://shopify/Product/{n}"),
        no_declaration=None
    )
```

### Database Seeding

```python
# tests/seed_test_data.py
def seed_test_database():
    """Seed database with test data"""
    # Create categories
    categories = [
        CategoryFactory(name="Electronics"),
        CategoryFactory(name="Clothing"),
        CategoryFactory(name="Books")
    ]
    
    # Create products
    for category in categories:
        for i in range(100):
            ProductFactory(
                category=category,
                shopify_product_id=f"gid://shopify/Product/{i}" if i % 2 == 0 else None
            )
    
    print("Test data seeded successfully")
```

## Test Reporting

### Generate Test Reports

```bash
# HTML test report
pytest --html=report.html --self-contained-html

# JUnit XML for CI
pytest --junitxml=test-results.xml

# Coverage report
coverage html -d coverage_report
open coverage_report/index.html

# Performance report
python tests/performance/generate_report.py
```

### Test Metrics Dashboard

Create a dashboard to track:
- Test execution time trends
- Test coverage percentage
- Flaky test identification
- Performance regression detection
- Error rate by test category

## Best Practices

1. **Test Isolation**: Each test should be independent
2. **Test Data**: Use factories, not hard-coded data
3. **Mocking**: Mock external services (Shopify API)
4. **Assertions**: Be specific about expected outcomes
5. **Naming**: Use descriptive test names
6. **Documentation**: Document complex test scenarios
7. **Maintenance**: Regular test suite cleanup
8. **Performance**: Keep tests fast (<5 minutes total)

---

*Last Updated: January 2025*
*Test Coverage Target: 80%*
*Performance Baseline: 1000 products/minute*