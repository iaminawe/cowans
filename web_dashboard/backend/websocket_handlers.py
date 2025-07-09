"""
WebSocket handlers with Supabase authentication

This module contains WebSocket event handlers that validate Supabase tokens.
"""

import logging
from flask import request
from flask_socketio import emit, disconnect
from functools import wraps

from services.supabase_auth import auth_service

logger = logging.getLogger(__name__)


def require_socket_auth(f):
    """Decorator to require valid Supabase authentication for WebSocket events."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get auth data from the connection
        auth_data = getattr(request, 'event', {}).get('auth', {})
        token = auth_data.get('token')
        
        if not token:
            logger.warning(f"WebSocket connection without auth token: {request.sid}")
            emit('error', {'message': 'Authentication required'})
            disconnect()
            return
        
        # Verify the token
        is_valid, user_data = auth_service.verify_token(token)
        
        if not is_valid or not user_data:
            logger.warning(f"WebSocket connection with invalid token: {request.sid}")
            emit('error', {'message': 'Invalid authentication token'})
            disconnect()
            return
        
        # Store user data on request for use in handlers
        request.supabase_user = user_data
        
        return f(*args, **kwargs)
    
    return decorated_function


def handle_connect_with_supabase(auth):
    """Handle WebSocket connection with Supabase authentication."""
    try:
        logger.info(f"WebSocket connection attempt: {request.sid}")
        
        # Auth parameter contains the authentication data from client
        if not auth or 'token' not in auth:
            logger.warning(f"WebSocket connection without auth token: {request.sid}")
            return True  # Allow connection but without auth
        
        token = auth['token']
        
        # Verify the Supabase token
        try:
            is_valid, user_data = auth_service.verify_token(token)
        except Exception as e:
            logger.error(f"Error verifying token: {e}")
            return True  # Allow connection anyway
        
        if not is_valid or not user_data:
            logger.warning(f"WebSocket connection with invalid token: {request.sid}")
            return True  # Allow connection anyway
        
        # Connection accepted
        logger.info(f"WebSocket connected: {request.sid} (user: {user_data.get('email')})")
        
        # Store user data for this connection
        request.supabase_user = user_data
        
        # Get the WebSocket service instance
        try:
            from app import websocket_service
            websocket_service.register_client(request.sid, user_data.get('id'))
        except Exception as e:
            logger.error(f"Error registering client: {e}")
            # Don't fail connection for this
        
        return True  # Accept connection
    except Exception as e:
        logger.error(f"Error in WebSocket connection handler: {e}")
        return True  # Allow connection anyway


def handle_disconnect_with_supabase():
    """Handle WebSocket disconnection."""
    logger.info(f"WebSocket disconnected: {request.sid}")
    
    # Get the WebSocket service instance
    from app import websocket_service
    websocket_service.unregister_client(request.sid)


def handle_execute_with_auth(data):
    """Execute a script with authentication check."""
    # Get user from request (set during connection)
    user_data = getattr(request, 'supabase_user', None)
    
    if not user_data:
        emit('error', {'message': 'Authentication required'})
        return
    
    script_id = data.get('scriptId')
    parameters = data.get('parameters', {})
    
    logger.info(f"User {user_data.get('email')} executing script: {script_id}")
    
    # Import here to avoid circular imports
    from app import handle_script_execution
    
    # Execute the script
    handle_script_execution(script_id, parameters, request.sid)


def handle_join_operation(data):
    """Join an operation room with authentication."""
    user_data = getattr(request, 'supabase_user', None)
    
    if not user_data:
        emit('error', {'message': 'Authentication required'})
        return
    
    operation_id = data.get('operation_id')
    if not operation_id:
        emit('error', {'message': 'Operation ID required'})
        return
    
    # Get the WebSocket service instance
    from app import websocket_service
    websocket_service.join_operation_room(request.sid, operation_id)
    
    emit('joined_operation', {
        'operation_id': operation_id,
        'message': f'Joined operation room: {operation_id}'
    })


def handle_leave_operation(data):
    """Leave an operation room with authentication."""
    user_data = getattr(request, 'supabase_user', None)
    
    if not user_data:
        emit('error', {'message': 'Authentication required'})
        return
    
    operation_id = data.get('operation_id')
    if not operation_id:
        emit('error', {'message': 'Operation ID required'})
        return
    
    # Get the WebSocket service instance
    from app import websocket_service
    websocket_service.leave_operation_room(request.sid, operation_id)
    
    emit('left_operation', {
        'operation_id': operation_id,
        'message': f'Left operation room: {operation_id}'
    })


def handle_post_connect():
    """Handle post-connection tasks after authentication is successful."""
    user_data = getattr(request, 'supabase_user', None)
    if user_data:
        # Send success response after connection is established
        emit('connected', {
            'message': 'Connected to server',
            'sid': request.sid,
            'authenticated': True,
            'user': {
                'id': user_data.get('id'),
                'email': user_data.get('email'),
                'role': user_data.get('role')
            }
        })

def register_websocket_handlers(socketio):
    """Register all WebSocket event handlers with Supabase authentication."""
    
    # Connection handlers
    socketio.on_event('connect', handle_connect_with_supabase)
    socketio.on_event('disconnect', handle_disconnect_with_supabase)
    
    # Post-connection handler
    socketio.on_event('post_connect', handle_post_connect)
    
    # Script execution
    socketio.on_event('execute', handle_execute_with_auth)
    
    # Operation room management
    socketio.on_event('join_operation', handle_join_operation)
    socketio.on_event('leave_operation', handle_leave_operation)
    
    logger.info("WebSocket handlers registered with Supabase authentication")