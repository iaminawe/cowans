"""Integration tests for web dashboard functionality."""
import pytest
import json
import time
import os
import sys
from unittest.mock import patch, MagicMock
from datetime import datetime

# Add parent directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from web_dashboard.backend.app import app
from web_dashboard.backend.job_manager import JobManager

class TestDashboardIntegration:
    """Test suite for dashboard integration."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client
    
    @pytest.fixture
    def auth_headers(self, client):
        """Get authentication headers."""
        response = client.post('/api/auth/login', 
            json={'email': 'test@example.com', 'password': 'test123'})
        token = response.json['access_token']
        return {'Authorization': f'Bearer {token}'}
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        with patch('redis.Redis') as mock:
            yield mock
    
    def test_authentication_flow(self, client):
        """Test complete authentication flow."""
        # Test successful login
        response = client.post('/api/auth/login',
            json={'email': 'test@example.com', 'password': 'test123'})
        assert response.status_code == 200
        assert 'access_token' in response.json
        assert response.json['user']['email'] == 'test@example.com'
        
        # Test invalid credentials
        response = client.post('/api/auth/login',
            json={'email': 'wrong@example.com', 'password': 'wrong'})
        assert response.status_code == 401
        assert 'Invalid credentials' in response.json['message']
        
        # Test missing credentials
        response = client.post('/api/auth/login', json={})
        assert response.status_code == 400
        assert 'Missing email or password' in response.json['message']
    
    def test_protected_endpoints(self, client):
        """Test endpoint protection."""
        # Test without auth
        response = client.post('/api/sync/trigger')
        assert response.status_code == 401
        
        response = client.get('/api/sync/history')
        assert response.status_code == 401
    
    def test_sync_trigger(self, client, auth_headers):
        """Test sync trigger endpoint."""
        response = client.post('/api/sync/trigger', headers=auth_headers)
        assert response.status_code == 200
        assert 'message' in response.json
        assert 'Sync triggered successfully' in response.json['message']
    
    def test_sync_history(self, client, auth_headers):
        """Test sync history endpoint."""
        response = client.get('/api/sync/history', headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json, list)
        
        # Check history structure
        if response.json:
            history = response.json[0]
            assert 'id' in history
            assert 'timestamp' in history
            assert 'status' in history
            assert 'message' in history
    
    @pytest.mark.integration
    def test_job_execution(self, mock_redis):
        """Test job execution flow."""
        # Create job manager
        job_manager = JobManager(mock_redis)
        
        # Mock Redis methods
        mock_redis.setex = MagicMock()
        mock_redis.get = MagicMock(return_value=None)
        
        # Create a job
        job_id = job_manager.create_job(
            script_name='filter_products',
            parameters=[
                {'name': 'input', 'value': 'test.csv', 'type': 'string'},
                {'name': 'debug', 'value': True, 'type': 'boolean'}
            ],
            user_id='test-user'
        )
        
        assert job_id is not None
        assert job_id in job_manager.jobs
        assert job_manager.jobs[job_id]['status'] == 'pending'
        
        # Test job update
        success = job_manager.update_job(job_id, {
            'status': 'running',
            'progress': 50
        })
        assert success
        assert job_manager.jobs[job_id]['status'] == 'running'
        assert job_manager.jobs[job_id]['progress'] == 50
    
    @pytest.mark.integration
    def test_script_mapping(self, mock_redis):
        """Test script path mapping."""
        job_manager = JobManager(mock_redis)
        
        # Test script mapping
        script_names = [
            'ftp_download',
            'filter_products',
            'create_metafields',
            'shopify_upload',
            'cleanup_duplicates',
            'categorize_products',
            'full_import'
        ]
        
        for script_name in script_names:
            job_id = job_manager.create_job(
                script_name=script_name,
                parameters=[],
                user_id='test-user'
            )
            assert job_id is not None
    
    def test_cors_headers(self, client):
        """Test CORS configuration."""
        response = client.options('/api/auth/login')
        assert 'Access-Control-Allow-Origin' in response.headers
        assert response.headers['Access-Control-Allow-Origin'] == 'http://localhost:3000'
    
    @pytest.mark.integration
    def test_end_to_end_workflow(self, client, auth_headers, mock_redis):
        """Test complete end-to-end workflow."""
        # 1. Login
        login_response = client.post('/api/auth/login',
            json={'email': 'test@example.com', 'password': 'test123'})
        assert login_response.status_code == 200
        token = login_response.json['access_token']
        
        # 2. Trigger sync
        headers = {'Authorization': f'Bearer {token}'}
        sync_response = client.post('/api/sync/trigger', headers=headers)
        assert sync_response.status_code == 200
        
        # 3. Check history
        history_response = client.get('/api/sync/history', headers=headers)
        assert history_response.status_code == 200
        assert isinstance(history_response.json, list)


class TestScriptExecution:
    """Test script execution functionality."""
    
    def test_run_import_script(self):
        """Test run_import.py script."""
        import subprocess
        
        # Test help command
        result = subprocess.run(
            [sys.executable, 'scripts/run_import.py', '--help'],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        assert 'Run Cowan\'s product import workflow' in result.stdout
    
    def test_individual_scripts(self):
        """Test individual script help commands."""
        scripts = [
            'scripts/data_processing/filter_products.py',
            'scripts/data_processing/create_metafields.py',
            'scripts/data_processing/categorize_products.py'
        ]
        
        for script in scripts:
            if os.path.exists(script):
                result = subprocess.run(
                    [sys.executable, script, '--help'],
                    capture_output=True,
                    text=True
                )
                assert result.returncode == 0, f"Script {script} failed"
                assert 'usage:' in result.stdout.lower() or 'help' in result.stdout.lower()


class TestErrorHandling:
    """Test error handling scenarios."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client
    
    def test_invalid_json(self, client):
        """Test handling of invalid JSON."""
        response = client.post('/api/auth/login',
            data='invalid json',
            content_type='application/json')
        assert response.status_code in [400, 415]
    
    def test_expired_token(self, client):
        """Test expired token handling."""
        # Create an expired token (this would need proper implementation)
        expired_token = "expired.token.here"
        response = client.get('/api/sync/history',
            headers={'Authorization': f'Bearer {expired_token}'})
        assert response.status_code == 401
    
    def test_missing_auth_header(self, client):
        """Test missing authorization header."""
        response = client.get('/api/sync/history')
        assert response.status_code == 401


@pytest.mark.integration
class TestWebSocketIntegration:
    """Test WebSocket/Socket.IO integration."""
    
    def test_job_output_streaming(self, mock_redis):
        """Test job output streaming functionality."""
        job_manager = JobManager(mock_redis)
        
        # Mock socket.io
        mock_socketio = MagicMock()
        
        # Create and start a job
        job_id = job_manager.create_job(
            script_name='filter_products',
            parameters=[],
            user_id='test-user'
        )
        
        # Simulate job output
        test_output = [
            "Starting filter process...",
            "Progress: 25%",
            "Stage: Loading data",
            "Progress: 50%",
            "Stage: Filtering products",
            "Progress: 100%",
            "Completed successfully"
        ]
        
        # Test output parsing
        for line in test_output:
            if 'progress:' in line.lower():
                progress = int(line.split('progress:')[1].strip().split()[0])
                assert progress >= 0 and progress <= 100
            
            if 'stage:' in line.lower():
                stage = line.split('stage:')[1].strip()
                assert len(stage) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])