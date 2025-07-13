import os
from dotenv import load_dotenv

# Load environment variables FIRST before any other imports
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

from flask import Flask, jsonify, request, send_file, send_from_directory, redirect
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from services.supabase_auth import (
    auth_service, supabase_jwt_required, supabase_jwt_optional,
    get_current_user_id, get_current_user_email, require_role
)
from services.supabase_database import get_supabase_db
from functools import wraps
from flask_socketio import SocketIO, emit, join_room, leave_room
from datetime import timedelta
import redis
import logging
import time
import asyncio
import json
import uuid
from pathlib import Path
from logging.handlers import RotatingFileHandler
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from marshmallow import ValidationError

# Conditional imports based on environment
from config import config

# Lazy load heavy modules only when needed
icon_generation_service = None
prompt_templates = None
openai_client = None

def lazy_load_icon_services():
    """Lazy load icon generation services only when needed."""
    global icon_generation_service, prompt_templates, openai_client
    if icon_generation_service is None:
        from icon_generation_service import (
            IconGenerationService, BatchGenerationRequest, 
            BatchJobStatus, BatchGenerationResult
        )
        from prompt_templates import IconStyle, IconColor
        from openai_client import ImageGenerationRequest
        icon_generation_service = IconGenerationService
        prompt_templates = (IconStyle, IconColor)
        openai_client = ImageGenerationRequest

# Core imports that are always needed
from schemas import (
    LoginSchema, RegisterSchema, ScriptExecutionSchema, JobStatusSchema,
    SyncHistorySchema, ScriptDefinitionSchema, CategoryIconSchema,
    IconGenerationSchema
)
from database import db_manager, init_database, db_session_scope
from models import Product, Category, Collection, ProductStatus, IconStatus, JobStatus

# Lazy load API blueprints
def register_blueprints(app):
    """Register blueprints lazily to reduce startup time."""
    # Critical blueprints - always load
    from shopify_sync_supabase import shopify_sync_bp
    from products_supabase import products_bp
    from categories_supabase import categories_bp
    from dashboard_stats_supabase import dashboard_stats_bp
    
    app.register_blueprint(shopify_sync_bp, url_prefix='/api')
    app.register_blueprint(products_bp, url_prefix='/api')
    app.register_blueprint(categories_bp, url_prefix='/api')
    app.register_blueprint(dashboard_stats_bp, url_prefix='/api')
    
    # Optional blueprints - load based on features enabled
    if config.get('ENABLE_IMPORT_API', True):
        from import_api import import_bp
        app.register_blueprint(import_bp, url_prefix='/api')
    
    if config.get('ENABLE_COLLECTIONS_API', True):
        from collections_supabase import collections_bp
        app.register_blueprint(collections_bp, url_prefix='/api')
    
    if config.get('ENABLE_BATCH_API', True):
        from products_batch_supabase import products_batch_bp
        from batch_api import batch_bp
        app.register_blueprint(products_batch_bp, url_prefix='/api')
        app.register_blueprint(batch_bp, url_prefix='/api')
    
    if config.get('ENABLE_ADMIN_API', True):
        from admin_api import admin_bp
        app.register_blueprint(admin_bp, url_prefix='/api')

# Setup logging - simpler in production
def setup_logging(app):
    """Setup application logging."""
    if not app.debug:
        # Production logging - minimal
        logging.basicConfig(
            level=logging.WARNING,
            format='%(asctime)s %(levelname)s: %(message)s'
        )
    else:
        # Development logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s %(name)s %(levelname)s: %(message)s'
        )

# Redis connection with lazy loading
redis_client = None

def get_redis_client():
    """Get Redis client with lazy initialization."""
    global redis_client
    if redis_client is None:
        try:
            redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
            redis_client = redis.from_url(redis_url, decode_responses=True)
            redis_client.ping()
            logging.info("Redis connected successfully")
        except Exception as e:
            logging.warning(f"Redis not available: {e}")
            redis_client = None
    return redis_client

# Disable memory monitoring in production
def init_memory_monitoring():
    """Initialize memory monitoring only in development."""
    if os.getenv('MEMORY_MONITOR_ENABLED', 'true').lower() == 'true' and os.getenv('FLASK_ENV') != 'production':
        from memory_optimizer import memory_monitor
        memory_monitor.start_monitoring(interval=30.0)  # Less frequent monitoring
    else:
        logging.info("Memory monitoring disabled in production")

def create_app():
    """Create and configure the Flask application with optimizations."""
    app = Flask(__name__)
    
    # Basic configuration
    app.config.from_object(config)
    
    # JWT Configuration
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'your-secret-key-here')
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)
    
    # Disable debug in production
    if os.getenv('FLASK_ENV') == 'production':
        app.debug = False
        app.config['PROPAGATE_EXCEPTIONS'] = False
    
    # Setup logging
    setup_logging(app)
    
    # Initialize JWT
    jwt = JWTManager(app)
    
    # Initialize CORS
    CORS(app, origins=["http://localhost:3000", "http://localhost:3055", "https://cowans.apps.iaminawe.net"])
    
    # Initialize SocketIO only if WebSocket is enabled
    socketio = None
    if os.getenv('ENABLE_WEBSOCKET', 'false').lower() == 'true':
        socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
        from websocket_handlers import register_websocket_handlers
        register_websocket_handlers(socketio)
        logging.info("WebSocket enabled")
    
    # Initialize database
    init_database(create_tables=True)
    
    # Register blueprints
    register_blueprints(app)
    
    # Initialize memory monitoring (disabled in production)
    init_memory_monitoring()
    
    # Health check endpoint
    @app.route('/health')
    @app.route('/api/health')
    def health_check():
        """Simple health check endpoint."""
        try:
            # Quick database check
            with db_session_scope() as session:
                from sqlalchemy import text
                session.execute(text("SELECT 1")).scalar()
            
            return jsonify({
                'status': 'healthy',
                'timestamp': int(time.time())
            }), 200
        except Exception as e:
            return jsonify({
                'status': 'unhealthy',
                'error': str(e)
            }), 503
    
    # Authentication endpoints
    @app.route('/api/auth/login', methods=['POST'])
    def login():
        """User login endpoint."""
        try:
            schema = LoginSchema()
            data = schema.load(request.json)
            
            result = auth_service.sign_in(data['email'], data['password'])
            
            if result['success']:
                return jsonify({
                    'access_token': result['access_token'],
                    'refresh_token': result.get('refresh_token'),
                    'user': result['user']
                }), 200
            else:
                return jsonify({'message': result.get('error', 'Login failed')}), 401
                
        except ValidationError as e:
            return jsonify({'message': 'Invalid input', 'errors': e.messages}), 400
        except Exception as e:
            logging.error(f"Login error: {e}")
            return jsonify({'message': 'Internal server error'}), 500
    
    @app.route('/api/auth/register', methods=['POST'])
    def register():
        """User registration endpoint."""
        try:
            schema = RegisterSchema()
            data = schema.load(request.json)
            
            result = auth_service.sign_up(
                email=data['email'],
                password=data['password'],
                user_metadata={
                    'first_name': data['first_name'],
                    'last_name': data['last_name']
                }
            )
            
            if result['success']:
                return jsonify({
                    'message': 'Registration successful',
                    'user': result['user']
                }), 201
            else:
                return jsonify({'message': result.get('error', 'Registration failed')}), 400
                
        except ValidationError as e:
            return jsonify({'message': 'Invalid input', 'errors': e.messages}), 400
        except Exception as e:
            logging.error(f"Registration error: {e}")
            return jsonify({'message': 'Internal server error'}), 500
    
    @app.route('/api/auth/logout', methods=['POST'])
    @supabase_jwt_required
    def logout():
        """User logout endpoint."""
        try:
            auth_service.sign_out()
            return jsonify({'message': 'Logged out successfully'}), 200
        except Exception as e:
            logging.error(f"Logout error: {e}")
            return jsonify({'message': 'Internal server error'}), 500
    
    @app.route('/api/auth/refresh', methods=['POST'])
    def refresh_token():
        """Refresh access token."""
        try:
            refresh_token = request.json.get('refresh_token')
            if not refresh_token:
                return jsonify({'message': 'Refresh token required'}), 400
            
            result = auth_service.refresh_session(refresh_token)
            
            if result['success']:
                return jsonify({
                    'access_token': result['access_token'],
                    'refresh_token': result.get('refresh_token'),
                    'user': result['user']
                }), 200
            else:
                return jsonify({'message': result.get('error', 'Token refresh failed')}), 401
                
        except Exception as e:
            logging.error(f"Token refresh error: {e}")
            return jsonify({'message': 'Internal server error'}), 500
    
    @app.route('/api/auth/me', methods=['GET'])
    @supabase_jwt_required
    def get_current_user():
        """Get current user information."""
        try:
            user_id = get_current_user_id()
            user_email = get_current_user_email()
            
            # Get user from Supabase auth
            user_data = auth_service.get_user()
            
            if user_data:
                return jsonify({
                    'user': {
                        'id': user_id,
                        'email': user_email,
                        'first_name': user_data.get('user_metadata', {}).get('first_name'),
                        'last_name': user_data.get('user_metadata', {}).get('last_name'),
                        'is_admin': user_data.get('user_metadata', {}).get('is_admin', False),
                        'created_at': user_data.get('created_at'),
                        'last_login': user_data.get('last_sign_in_at')
                    }
                }), 200
            else:
                return jsonify({'message': 'User not found'}), 404
                
        except Exception as e:
            logging.error(f"Get current user error: {e}")
            return jsonify({'message': 'Internal server error'}), 500
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'message': 'Resource not found'}), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        logging.error(f"Internal error: {error}")
        return jsonify({'message': 'Internal server error'}), 500
    
    return app, socketio

# Application instance
app, socketio = create_app()

if __name__ == '__main__':
    port = int(os.getenv('PORT', 3560))
    
    if os.getenv('FLASK_ENV') == 'production':
        # In production, let gunicorn handle the server
        logging.info("Application ready for production server")
    else:
        # Development mode
        if socketio:
            socketio.run(app, host='0.0.0.0', port=port, debug=True)
        else:
            app.run(host='0.0.0.0', port=port, debug=True)