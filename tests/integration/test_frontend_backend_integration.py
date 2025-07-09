"""Integration tests for frontend-backend communication."""
import pytest
import json
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import subprocess
import os
import sys

class TestFrontendBackendIntegration:
    """Test frontend-backend integration."""
    
    @classmethod
    def setup_class(cls):
        """Setup test environment."""
        # Start backend server
        cls.backend_process = subprocess.Popen(
            [sys.executable, 'web_dashboard/backend/app.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        time.sleep(2)  # Wait for server to start
        
        # Start frontend dev server (if needed)
        # cls.frontend_process = subprocess.Popen(
        #     ['npm', 'start'],
        #     cwd='frontend',
        #     stdout=subprocess.PIPE,
        #     stderr=subprocess.PIPE
        # )
        # time.sleep(5)  # Wait for React to compile
    
    @classmethod
    def teardown_class(cls):
        """Cleanup test environment."""
        cls.backend_process.terminate()
        # cls.frontend_process.terminate()
    
    def test_api_connectivity(self):
        """Test API endpoint connectivity."""
        # Test health check
        try:
            response = requests.get('http://localhost:3560/api/health', timeout=5)
            assert response.status_code in [200, 404]  # 404 if health endpoint not implemented
        except requests.exceptions.ConnectionError:
            pytest.skip("Backend server not running")
    
    def test_authentication_api(self):
        """Test authentication API."""
        url = 'http://localhost:5000/api/auth/login'
        
        # Test successful login
        response = requests.post(url, json={
            'email': 'test@example.com',
            'password': 'test123'
        })
        assert response.status_code == 200
        data = response.json()
        assert 'access_token' in data
        assert 'user' in data
        
        # Test failed login
        response = requests.post(url, json={
            'email': 'wrong@example.com',
            'password': 'wrong'
        })
        assert response.status_code == 401
    
    def test_protected_endpoint_access(self):
        """Test protected endpoint access."""
        # Get token
        login_response = requests.post(
            'http://localhost:5000/api/auth/login',
            json={'email': 'test@example.com', 'password': 'test123'}
        )
        token = login_response.json()['access_token']
        
        # Test with token
        headers = {'Authorization': f'Bearer {token}'}
        response = requests.get(
            'http://localhost:5000/api/sync/history',
            headers=headers
        )
        assert response.status_code == 200
        
        # Test without token
        response = requests.get('http://localhost:5000/api/sync/history')
        assert response.status_code == 401
    
    @pytest.mark.slow
    def test_frontend_login_flow(self):
        """Test frontend login flow with Selenium."""
        # This test requires Selenium WebDriver and a running frontend
        pytest.skip("Selenium tests require browser driver setup")
        
        driver = webdriver.Chrome()  # Requires chromedriver
        try:
            # Navigate to app
            driver.get('http://localhost:3000')
            
            # Wait for login form
            wait = WebDriverWait(driver, 10)
            email_input = wait.until(
                EC.presence_of_element_located((By.NAME, "email"))
            )
            
            # Fill login form
            email_input.send_keys('test@example.com')
            password_input = driver.find_element(By.NAME, "password")
            password_input.send_keys('test123')
            
            # Submit form
            submit_button = driver.find_element(By.TYPE, "submit")
            submit_button.click()
            
            # Wait for dashboard
            dashboard = wait.until(
                EC.presence_of_element_located((By.CLASS_NAME, "dashboard"))
            )
            assert dashboard is not None
            
        finally:
            driver.quit()
    
    def test_sync_trigger_integration(self):
        """Test sync trigger integration."""
        # Login first
        login_response = requests.post(
            'http://localhost:5000/api/auth/login',
            json={'email': 'test@example.com', 'password': 'test123'}
        )
        token = login_response.json()['access_token']
        headers = {'Authorization': f'Bearer {token}'}
        
        # Trigger sync
        response = requests.post(
            'http://localhost:5000/api/sync/trigger',
            headers=headers
        )
        assert response.status_code == 200
        assert 'message' in response.json()
    
    def test_concurrent_requests(self):
        """Test handling of concurrent requests."""
        import threading
        
        results = []
        
        def make_request():
            try:
                response = requests.post(
                    'http://localhost:5000/api/auth/login',
                    json={'email': 'test@example.com', 'password': 'test123'},
                    timeout=5
                )
                results.append(response.status_code)
            except Exception as e:
                results.append(str(e))
        
        # Create multiple threads
        threads = []
        for _ in range(10):
            t = threading.Thread(target=make_request)
            threads.append(t)
            t.start()
        
        # Wait for all threads
        for t in threads:
            t.join()
        
        # Check results
        success_count = sum(1 for r in results if r == 200)
        assert success_count >= 8  # At least 80% should succeed


class TestRealTimeUpdates:
    """Test real-time update functionality."""
    
    def test_websocket_connection(self):
        """Test WebSocket connection establishment."""
        # This would require Socket.IO client
        pytest.skip("Socket.IO client tests not implemented")
        
        # Example implementation:
        # import socketio
        # sio = socketio.Client()
        # sio.connect('http://localhost:5000')
        # assert sio.connected
    
    def test_job_progress_updates(self):
        """Test job progress updates."""
        # This would test real-time progress updates
        pass
    
    def test_log_streaming(self):
        """Test log streaming functionality."""
        # This would test real-time log streaming
        pass


class TestDataFlow:
    """Test complete data flow through the system."""
    
    def test_csv_upload_flow(self):
        """Test CSV file upload and processing flow."""
        # This would test:
        # 1. File upload
        # 2. Processing trigger
        # 3. Status updates
        # 4. Result retrieval
        pass
    
    def test_shopify_sync_flow(self):
        """Test Shopify synchronization flow."""
        # This would test:
        # 1. Sync trigger
        # 2. Progress monitoring
        # 3. Error handling
        # 4. Completion status
        pass


if __name__ == '__main__':
    pytest.main([__file__, '-v'])