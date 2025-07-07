"""
Supabase Authentication Service

This module provides authentication functionality using Supabase,
replacing the previous mock JWT authentication system.
"""

import os
import jwt
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timezone
from functools import wraps
from flask import request, jsonify, g
from supabase import create_client, Client
from supabase.lib.client_options import ClientOptions
import logging

logger = logging.getLogger(__name__)


class SupabaseAuthService:
    """Manages authentication using Supabase"""
    
    def __init__(self):
        """Initialize Supabase client"""
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_anon_key = os.getenv('SUPABASE_ANON_KEY')
        self.supabase_service_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
        
        if not all([self.supabase_url, self.supabase_anon_key]):
            raise ValueError("Missing required Supabase configuration")
        
        # Client for regular auth operations
        self.client: Client = create_client(
            self.supabase_url,
            self.supabase_anon_key,
            options=ClientOptions(
                auto_refresh_token=True,
                persist_session=True
            )
        )
        
        # Admin client for service operations
        self.admin_client: Client = create_client(
            self.supabase_url,
            self.supabase_service_key or self.supabase_anon_key
        )
        
        # Get JWT secret from Supabase for token verification
        self.jwt_secret = os.getenv('SUPABASE_JWT_SECRET', 'your-super-secret-jwt-key-change-in-production-2024!')
    
    def sign_up(self, email: str, password: str, metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Register a new user with Supabase
        
        Args:
            email: User's email address
            password: User's password
            metadata: Additional user metadata
            
        Returns:
            Dict containing user info and session
        """
        try:
            response = self.client.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "data": metadata or {}
                }
            })
            
            if response.user:
                logger.info(f"User registered successfully: {email}")
                return {
                    "user": self._serialize_user(response.user),
                    "session": self._serialize_session(response.session) if response.session else None
                }
            else:
                raise Exception("Registration failed - no user returned")
                
        except Exception as e:
            logger.error(f"Registration error: {str(e)}")
            raise
    
    def sign_in(self, email: str, password: str) -> Dict[str, Any]:
        """
        Sign in a user with email and password
        
        Args:
            email: User's email address
            password: User's password
            
        Returns:
            Dict containing user info and session
        """
        try:
            response = self.client.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            if response.user and response.session:
                logger.info(f"User signed in successfully: {email}")
                return {
                    "user": self._serialize_user(response.user),
                    "session": self._serialize_session(response.session)
                }
            else:
                raise Exception("Sign in failed - invalid credentials")
                
        except Exception as e:
            logger.error(f"Sign in error: {str(e)}")
            raise
    
    def sign_out(self, access_token: str) -> bool:
        """
        Sign out a user
        
        Args:
            access_token: User's access token
            
        Returns:
            True if successful
        """
        try:
            # Set the session for the client
            self.client.auth.set_session(access_token, "")
            self.client.auth.sign_out()
            logger.info("User signed out successfully")
            return True
        except Exception as e:
            logger.error(f"Sign out error: {str(e)}")
            return False
    
    def verify_token(self, token: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Verify a JWT token from Supabase
        
        Args:
            token: JWT access token
            
        Returns:
            Tuple of (is_valid, user_data)
        """
        try:
            # Decode and verify the JWT
            payload = jwt.decode(
                token,
                self.jwt_secret,
                algorithms=["HS256"],
                options={"verify_aud": False}  # Supabase doesn't use audience
            )
            
            # Check expiration
            exp = payload.get('exp', 0)
            if datetime.now(timezone.utc).timestamp() > exp:
                return False, None
            
            # Extract user info
            user_data = {
                "id": payload.get('sub'),
                "email": payload.get('email'),
                "role": payload.get('role'),
                "user_metadata": payload.get('user_metadata', {})
            }
            
            return True, user_data
            
        except jwt.InvalidTokenError as e:
            logger.error(f"Token verification error: {str(e)}")
            return False, None
        except Exception as e:
            logger.error(f"Unexpected token verification error: {str(e)}")
            return False, None
    
    def get_user_by_token(self, access_token: str) -> Optional[Dict[str, Any]]:
        """
        Get user details from access token
        
        Args:
            access_token: User's access token
            
        Returns:
            User data if valid, None otherwise
        """
        try:
            # Set the session for the client
            self.client.auth.set_session(access_token, "")
            user = self.client.auth.get_user()
            
            if user:
                return self._serialize_user(user)
            return None
            
        except Exception as e:
            logger.error(f"Get user error: {str(e)}")
            return None
    
    def refresh_token(self, refresh_token: str) -> Optional[Dict[str, Any]]:
        """
        Refresh an access token
        
        Args:
            refresh_token: User's refresh token
            
        Returns:
            New session data if successful
        """
        try:
            response = self.client.auth.refresh_session(refresh_token)
            
            if response.session:
                return self._serialize_session(response.session)
            return None
            
        except Exception as e:
            logger.error(f"Token refresh error: {str(e)}")
            return None
    
    def update_user_metadata(self, user_id: str, metadata: Dict[str, Any]) -> bool:
        """
        Update user metadata (requires service role key)
        
        Args:
            user_id: User's ID
            metadata: Metadata to update
            
        Returns:
            True if successful
        """
        try:
            # Use admin client for this operation
            self.admin_client.auth.admin.update_user_by_id(
                user_id,
                {"user_metadata": metadata}
            )
            return True
        except Exception as e:
            logger.error(f"Update metadata error: {str(e)}")
            return False
    
    def _serialize_user(self, user) -> Dict[str, Any]:
        """Serialize Supabase user object"""
        return {
            "id": user.id,
            "email": user.email,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
            "user_metadata": user.user_metadata or {},
            "app_metadata": getattr(user, 'app_metadata', {})
        }
    
    def _serialize_session(self, session) -> Dict[str, Any]:
        """Serialize Supabase session object"""
        return {
            "access_token": session.access_token,
            "refresh_token": session.refresh_token,
            "expires_in": session.expires_in,
            "expires_at": session.expires_at,
            "token_type": session.token_type
        }


# Create a singleton instance
auth_service = SupabaseAuthService()


def supabase_jwt_required(f):
    """
    Decorator to require valid Supabase JWT token
    
    Usage:
        @app.route('/protected')
        @supabase_jwt_required
        def protected_route():
            user = g.current_user
            return jsonify({"user_id": user["id"]})
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get token from Authorization header
        auth_header = request.headers.get('Authorization', '')
        
        if not auth_header.startswith('Bearer '):
            return jsonify({"error": "Missing or invalid authorization header"}), 401
        
        token = auth_header.split(' ')[1]
        
        # Verify token
        is_valid, user_data = auth_service.verify_token(token)
        
        if not is_valid or not user_data:
            return jsonify({"error": "Invalid or expired token"}), 401
        
        # Store user data in g for access in the route
        g.current_user = user_data
        g.access_token = token
        
        return f(*args, **kwargs)
    
    return decorated_function


def supabase_jwt_optional(f):
    """
    Decorator to optionally check for Supabase JWT token
    
    Usage:
        @app.route('/public')
        @supabase_jwt_optional
        def public_route():
            user = g.get('current_user')
            if user:
                return jsonify({"message": f"Hello {user['email']}"})
            return jsonify({"message": "Hello anonymous"})
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get token from Authorization header
        auth_header = request.headers.get('Authorization', '')
        
        if auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            
            # Verify token but don't fail if invalid
            is_valid, user_data = auth_service.verify_token(token)
            
            if is_valid and user_data:
                g.current_user = user_data
                g.access_token = token
        
        return f(*args, **kwargs)
    
    return decorated_function


def get_current_user_id() -> Optional[str]:
    """
    Get the current user's Supabase ID from the request context
    
    Returns:
        User ID if authenticated, None otherwise
    """
    user = g.get('current_user')
    return user.get('id') if user else None


def get_current_user_email() -> Optional[str]:
    """
    Get the current user's email from the request context
    
    Returns:
        User email if authenticated, None otherwise
    """
    user = g.get('current_user')
    return user.get('email') if user else None


def require_role(role: str):
    """
    Decorator to require a specific role
    
    Usage:
        @app.route('/admin')
        @supabase_jwt_required
        @require_role('admin')
        def admin_route():
            return jsonify({"message": "Admin access granted"})
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = g.get('current_user')
            if not user:
                return jsonify({"error": "Authentication required"}), 401
            
            user_role = user.get('role', 'authenticated')
            app_metadata = user.get('app_metadata', {})
            user_roles = app_metadata.get('roles', [])
            
            # Check if user has the required role
            if role not in user_roles and user_role != role:
                return jsonify({"error": f"Role '{role}' required"}), 403
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator