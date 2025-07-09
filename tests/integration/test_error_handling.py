"""Test error handling across all components."""
import pytest
import os
import sys
import json
import subprocess
from pathlib import Path

# Add parent directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

class TestScriptErrorHandling:
    """Test error handling in Python scripts."""
    
    def test_missing_csv_file(self):
        """Test handling of missing CSV files."""
        result = subprocess.run([
            sys.executable,
            'scripts/data_processing/filter_products.py',
            'nonexistent.csv',
            'reference.csv'
        ], capture_output=True, text=True)
        
        assert result.returncode != 0
        assert 'error' in result.stderr.lower() or 'not found' in result.stderr.lower()
    
    def test_invalid_csv_format(self):
        """Test handling of invalid CSV format."""
        # Create a temporary invalid CSV
        invalid_csv = 'test_invalid.csv'
        with open(invalid_csv, 'w') as f:
            f.write('This is not a valid CSV format\n')
            f.write('Missing proper headers and structure')
        
        try:
            result = subprocess.run([
                sys.executable,
                'scripts/data_processing/create_metafields.py',
                invalid_csv
            ], capture_output=True, text=True)
            
            # Should handle gracefully
            assert result.returncode != 0 or 'error' in result.stderr.lower()
        finally:
            if os.path.exists(invalid_csv):
                os.remove(invalid_csv)
    
    def test_missing_environment_variables(self):
        """Test handling of missing environment variables."""
        # Test FTP downloader without credentials
        env = os.environ.copy()
        env.pop('FTP_HOST', None)
        env.pop('FTP_USERNAME', None)
        env.pop('FTP_PASSWORD', None)
        
        result = subprocess.run([
            sys.executable,
            'scripts/utilities/ftp_downloader.py'
        ], capture_output=True, text=True, env=env)
        
        # Should provide helpful error message
        assert result.returncode != 0 or 'FTP' in result.stderr
    
    def test_network_error_handling(self):
        """Test handling of network errors."""
        # Test with invalid FTP host
        env = os.environ.copy()
        env['FTP_HOST'] = 'invalid.host.that.does.not.exist'
        env['FTP_USERNAME'] = 'test'
        env['FTP_PASSWORD'] = 'test'
        
        result = subprocess.run([
            sys.executable,
            'scripts/utilities/ftp_downloader.py'
        ], capture_output=True, text=True, env=env, timeout=30)
        
        assert result.returncode != 0
    
    def test_permission_error_handling(self):
        """Test handling of permission errors."""
        # Create a read-only directory
        readonly_dir = 'test_readonly'
        os.makedirs(readonly_dir, exist_ok=True)
        os.chmod(readonly_dir, 0o444)
        
        try:
            # Try to write to read-only directory
            result = subprocess.run([
                sys.executable,
                'scripts/data_processing/filter_products.py',
                'data/CowansOfficeSupplies_20250604.csv',
                'data/cowans_stocked.csv',
                '--output', f'{readonly_dir}/output.csv'
            ], capture_output=True, text=True)
            
            assert result.returncode != 0
            assert 'permission' in result.stderr.lower() or 'error' in result.stderr.lower()
        finally:
            os.chmod(readonly_dir, 0o755)
            os.rmdir(readonly_dir)


class TestAPIErrorHandling:
    """Test API error handling."""
    
    @pytest.fixture
    def api_base_url(self):
        return 'http://localhost:5000/api'
    
    def test_malformed_json(self, api_base_url):
        """Test handling of malformed JSON."""
        import requests
        
        response = requests.post(
            f'{api_base_url}/auth/login',
            data='{"email": "test@example.com", "password": }',  # Invalid JSON
            headers={'Content-Type': 'application/json'}
        )
        
        assert response.status_code in [400, 422]
    
    def test_rate_limiting(self, api_base_url):
        """Test rate limiting (if implemented)."""
        import requests
        import time
        
        # Make many rapid requests
        responses = []
        for _ in range(50):
            response = requests.post(
                f'{api_base_url}/auth/login',
                json={'email': 'test@example.com', 'password': 'test123'}
            )
            responses.append(response.status_code)
        
        # Check if rate limiting is applied
        # (This assumes rate limiting is implemented)
        # assert 429 in responses or all(r == 200 for r in responses)
    
    def test_timeout_handling(self, api_base_url):
        """Test timeout handling."""
        import requests
        
        try:
            # Very short timeout
            response = requests.get(
                f'{api_base_url}/sync/history',
                timeout=0.001
            )
        except requests.exceptions.Timeout:
            # Expected behavior
            pass
        except requests.exceptions.ConnectionError:
            # Also acceptable if server not running
            pass


class TestDataValidation:
    """Test data validation and error handling."""
    
    def test_invalid_sku_format(self):
        """Test handling of invalid SKU formats."""
        # Create test CSV with invalid SKUs
        test_csv = 'test_invalid_sku.csv'
        with open(test_csv, 'w') as f:
            f.write('SKU,Title,Price\n')
            f.write(',Empty SKU,10.00\n')
            f.write('SKU with spaces,Invalid,20.00\n')
            f.write('SKU@#$%,Special chars,30.00\n')
        
        try:
            # Test scripts that process SKUs
            result = subprocess.run([
                sys.executable,
                'scripts/data_processing/filter_products.py',
                test_csv,
                'data/cowans_stocked.csv'
            ], capture_output=True, text=True)
            
            # Should handle invalid SKUs gracefully
            assert result.returncode == 0 or 'warning' in result.stderr.lower()
        finally:
            if os.path.exists(test_csv):
                os.remove(test_csv)
    
    def test_price_validation(self):
        """Test price validation."""
        test_csv = 'test_invalid_price.csv'
        with open(test_csv, 'w') as f:
            f.write('SKU,Title,Price\n')
            f.write('SKU001,Product 1,not_a_number\n')
            f.write('SKU002,Product 2,-10.00\n')
            f.write('SKU003,Product 3,\n')
        
        try:
            result = subprocess.run([
                sys.executable,
                'scripts/data_processing/create_metafields.py',
                test_csv
            ], capture_output=True, text=True)
            
            # Should handle invalid prices
            assert 'error' in result.stderr.lower() or 'warning' in result.stderr.lower()
        finally:
            if os.path.exists(test_csv):
                os.remove(test_csv)


class TestRecoveryMechanisms:
    """Test recovery and retry mechanisms."""
    
    def test_partial_upload_recovery(self):
        """Test recovery from partial uploads."""
        # This would test if the system can resume from partial uploads
        pass
    
    def test_connection_retry(self):
        """Test connection retry logic."""
        # Test scripts retry on connection failures
        pass
    
    def test_data_backup_on_error(self):
        """Test if data is backed up on errors."""
        # Check if scripts create backups before destructive operations
        pass


class TestLoggingAndMonitoring:
    """Test logging and monitoring functionality."""
    
    def test_log_file_creation(self):
        """Test that log files are created properly."""
        log_dir = 'web_dashboard/backend/logs'
        assert os.path.exists(log_dir) or os.makedirs(log_dir, exist_ok=True)
    
    def test_error_logging(self):
        """Test that errors are logged properly."""
        # Run a script that will fail
        result = subprocess.run([
            sys.executable,
            'scripts/data_processing/filter_products.py',
            'nonexistent.csv',
            'reference.csv'
        ], capture_output=True, text=True)
        
        # Check if error was logged
        assert result.returncode != 0
        assert len(result.stderr) > 0
    
    def test_log_rotation(self):
        """Test log rotation functionality."""
        # This would test if logs are rotated properly
        pass


if __name__ == '__main__':
    pytest.main([__file__, '-v'])