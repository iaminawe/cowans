"""
Tests for Supabase authentication service
"""

import pytest
import jwt
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock
from flask import Flask, g

from services.supabase_auth import (
    SupabaseAuthService, supabase_jwt_required, supabase_jwt_optional,
    get_current_user_id, get_current_user_email, require_role
)


@pytest.fixture
def app():
    """Create a test Flask app."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    return app


@pytest.fixture
def mock_supabase_client():
    """Create a mock Supabase client."""
    client = Mock()
    return client


@pytest.fixture
def auth_service(mock_supabase_client):
    """Create an auth service with mocked Supabase client."""
    with patch('services.supabase_auth.create_client') as mock_create:
        mock_create.return_value = mock_supabase_client
        service = SupabaseAuthService()
        service.client = mock_supabase_client
        service.admin_client = mock_supabase_client
        return service


@pytest.fixture
def valid_jwt_token():
    """Create a valid JWT token for testing."""
    payload = {
        'sub': 'test-user-id',
        'email': 'test@example.com',
        'role': 'authenticated',
        'exp': (datetime.now(timezone.utc) + timedelta(hours=1)).timestamp(),
        'user_metadata': {
            'first_name': 'Test',
            'last_name': 'User'
        }
    }
    secret = 'your-super-secret-jwt-key-change-in-production-2024!'
    return jwt.encode(payload, secret, algorithm='HS256')


@pytest.fixture
def expired_jwt_token():
    """Create an expired JWT token for testing."""
    payload = {
        'sub': 'test-user-id',
        'email': 'test@example.com',
        'role': 'authenticated',
        'exp': (datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()
    }
    secret = 'your-super-secret-jwt-key-change-in-production-2024!'
    return jwt.encode(payload, secret, algorithm='HS256')


class TestSupabaseAuthService:
    """Test the Supabase authentication service."""
    
    def test_sign_up_success(self, auth_service, mock_supabase_client):
        """Test successful user sign up."""
        # Mock Supabase response
        mock_response = Mock()
        mock_response.user = Mock(
            id='new-user-id',
            email='new@example.com',
            created_at='2025-01-07T10:00:00Z',
            updated_at='2025-01-07T10:00:00Z',
            user_metadata={'first_name': 'New', 'last_name': 'User'}
        )
        mock_response.session = Mock(
            access_token='access-token',
            refresh_token='refresh-token',
            expires_in=3600,
            expires_at=1234567890,
            token_type='bearer'
        )
        
        mock_supabase_client.auth.sign_up.return_value = mock_response
        
        # Test sign up
        result = auth_service.sign_up(
            'new@example.com',
            'password123',
            {'first_name': 'New', 'last_name': 'User'}
        )
        
        assert result['user']['id'] == 'new-user-id'
        assert result['user']['email'] == 'new@example.com'
        assert result['session']['access_token'] == 'access-token'
    
    def test_sign_up_failure(self, auth_service, mock_supabase_client):
        """Test failed user sign up."""
        mock_supabase_client.auth.sign_up.side_effect = Exception('Sign up failed')
        
        with pytest.raises(Exception) as exc_info:
            auth_service.sign_up('fail@example.com', 'password123')
        
        assert 'Sign up failed' in str(exc_info.value)
    
    def test_sign_in_success(self, auth_service, mock_supabase_client):
        """Test successful user sign in."""
        # Mock Supabase response
        mock_response = Mock()
        mock_response.user = Mock(
            id='user-id',
            email='test@example.com'
        )
        mock_response.session = Mock(
            access_token='access-token',
            refresh_token='refresh-token'
        )
        
        mock_supabase_client.auth.sign_in_with_password.return_value = mock_response
        
        # Test sign in
        result = auth_service.sign_in('test@example.com', 'password123')
        
        assert result['user']['id'] == 'user-id'
        assert result['session']['access_token'] == 'access-token'
    
    def test_sign_out(self, auth_service, mock_supabase_client):
        """Test user sign out."""
        mock_supabase_client.auth.sign_out.return_value = None
        
        result = auth_service.sign_out('access-token')
        
        assert result is True
        mock_supabase_client.auth.set_session.assert_called_once_with('access-token', '')
        mock_supabase_client.auth.sign_out.assert_called_once()
    
    def test_verify_token_valid(self, auth_service, valid_jwt_token):
        """Test verification of valid JWT token."""
        is_valid, user_data = auth_service.verify_token(valid_jwt_token)
        
        assert is_valid is True
        assert user_data['id'] == 'test-user-id'
        assert user_data['email'] == 'test@example.com'
        assert user_data['role'] == 'authenticated'
    
    def test_verify_token_expired(self, auth_service, expired_jwt_token):
        """Test verification of expired JWT token."""
        is_valid, user_data = auth_service.verify_token(expired_jwt_token)
        
        assert is_valid is False
        assert user_data is None
    
    def test_verify_token_invalid(self, auth_service):
        """Test verification of invalid JWT token."""
        is_valid, user_data = auth_service.verify_token('invalid-token')
        
        assert is_valid is False
        assert user_data is None
    
    def test_refresh_token(self, auth_service, mock_supabase_client):
        """Test token refresh."""
        mock_response = Mock()
        mock_response.session = Mock(
            access_token='new-access-token',
            refresh_token='new-refresh-token'
        )
        
        mock_supabase_client.auth.refresh_session.return_value = mock_response
        
        result = auth_service.refresh_token('old-refresh-token')
        
        assert result['access_token'] == 'new-access-token'
        assert result['refresh_token'] == 'new-refresh-token'


class TestAuthDecorators:
    """Test authentication decorators."""
    
    def test_supabase_jwt_required_valid_token(self, app, valid_jwt_token):
        """Test JWT required decorator with valid token."""
        with app.test_request_context(
            headers={'Authorization': f'Bearer {valid_jwt_token}'}
        ):
            @supabase_jwt_required
            def protected_route():
                return {'user_id': g.current_user['id']}
            
            # Mock the auth service verify_token method
            with patch.object(auth_service, 'verify_token') as mock_verify:
                mock_verify.return_value = (True, {
                    'id': 'test-user-id',
                    'email': 'test@example.com',
                    'role': 'authenticated'
                })
                
                result = protected_route()
                assert result['user_id'] == 'test-user-id'
    
    def test_supabase_jwt_required_missing_token(self, app):
        """Test JWT required decorator with missing token."""
        with app.test_request_context():
            @supabase_jwt_required
            def protected_route():
                return {'data': 'protected'}
            
            response = protected_route()
            assert response[1] == 401  # Unauthorized
    
    def test_supabase_jwt_optional_with_token(self, app, valid_jwt_token):
        """Test JWT optional decorator with token."""
        with app.test_request_context(
            headers={'Authorization': f'Bearer {valid_jwt_token}'}
        ):
            @supabase_jwt_optional
            def public_route():
                user = g.get('current_user')
                return {'authenticated': user is not None}
            
            with patch.object(auth_service, 'verify_token') as mock_verify:
                mock_verify.return_value = (True, {
                    'id': 'test-user-id',
                    'email': 'test@example.com'
                })
                
                result = public_route()
                assert result['authenticated'] is True
    
    def test_supabase_jwt_optional_without_token(self, app):
        """Test JWT optional decorator without token."""
        with app.test_request_context():
            @supabase_jwt_optional
            def public_route():
                user = g.get('current_user')
                return {'authenticated': user is not None}
            
            result = public_route()
            assert result['authenticated'] is False
    
    def test_require_role_with_correct_role(self, app):
        """Test role requirement with correct role."""
        with app.test_request_context():
            g.current_user = {
                'id': 'test-user-id',
                'role': 'admin',
                'app_metadata': {'roles': ['admin', 'editor']}
            }
            
            @require_role('admin')
            def admin_route():
                return {'access': 'granted'}
            
            result = admin_route()
            assert result['access'] == 'granted'
    
    def test_require_role_with_wrong_role(self, app):
        """Test role requirement with wrong role."""
        with app.test_request_context():
            g.current_user = {
                'id': 'test-user-id',
                'role': 'authenticated',
                'app_metadata': {'roles': ['viewer']}
            }
            
            @require_role('admin')
            def admin_route():
                return {'access': 'granted'}
            
            response = admin_route()
            assert response[1] == 403  # Forbidden
    
    def test_get_current_user_id(self, app):
        """Test getting current user ID."""
        with app.test_request_context():
            g.current_user = {'id': 'test-user-id', 'email': 'test@example.com'}
            
            user_id = get_current_user_id()
            assert user_id == 'test-user-id'
    
    def test_get_current_user_email(self, app):
        """Test getting current user email."""
        with app.test_request_context():
            g.current_user = {'id': 'test-user-id', 'email': 'test@example.com'}
            
            email = get_current_user_email()
            assert email == 'test@example.com'


class TestIntegration:
    """Integration tests for Supabase authentication."""
    
    @pytest.mark.integration
    def test_full_auth_flow(self, auth_service, mock_supabase_client):
        """Test complete authentication flow."""
        # 1. Sign up
        signup_response = Mock()
        signup_response.user = Mock(id='new-user-id', email='new@example.com')
        signup_response.session = Mock(
            access_token='initial-token',
            refresh_token='initial-refresh'
        )
        mock_supabase_client.auth.sign_up.return_value = signup_response
        
        signup_result = auth_service.sign_up('new@example.com', 'password123')
        assert signup_result['user']['id'] == 'new-user-id'
        
        # 2. Sign in
        signin_response = Mock()
        signin_response.user = Mock(id='new-user-id', email='new@example.com')
        signin_response.session = Mock(
            access_token='login-token',
            refresh_token='login-refresh'
        )
        mock_supabase_client.auth.sign_in_with_password.return_value = signin_response
        
        signin_result = auth_service.sign_in('new@example.com', 'password123')
        assert signin_result['session']['access_token'] == 'login-token'
        
        # 3. Refresh token
        refresh_response = Mock()
        refresh_response.session = Mock(
            access_token='refreshed-token',
            refresh_token='refreshed-refresh'
        )
        mock_supabase_client.auth.refresh_session.return_value = refresh_response
        
        refresh_result = auth_service.refresh_token('login-refresh')
        assert refresh_result['access_token'] == 'refreshed-token'
        
        # 4. Sign out
        mock_supabase_client.auth.sign_out.return_value = None
        signout_result = auth_service.sign_out('refreshed-token')
        assert signout_result is True