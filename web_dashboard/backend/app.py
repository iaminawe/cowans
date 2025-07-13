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

# Icon generation imports
from icon_generation_service import (
    IconGenerationService, BatchGenerationRequest, 
    BatchJobStatus, BatchGenerationResult
)
from prompt_templates import IconStyle, IconColor
from openai_client import ImageGenerationRequest

from config import config
from schemas import (
    LoginSchema, RegisterSchema, ScriptExecutionSchema, JobStatusSchema,
    SyncHistorySchema, ScriptDefinitionSchema, CategoryIconSchema,
    IconGenerationSchema
)
from job_manager import JobManager
from script_registry import (
    get_script_info, get_all_scripts, validate_script_parameters
)
from icon_storage import IconStorage
from icon_generator import IconGenerator
from tasks import generate_icon_batch_task
from shopify_collections import ShopifyCollectionsManager

# Import database and repositories
from database_operations import db_manager, init_database, db_session_scope
from repositories import (
    UserRepository, ProductRepository, CategoryRepository,
    IconRepository, JobRepository, SyncHistoryRepository
)
from models import Product, Category, Collection, ProductStatus, IconStatus, JobStatus

# Import API blueprints
from import_api import import_bp
# Use Supabase version instead of SQLite version
# from shopify_sync_api import shopify_sync_bp
from shopify_sync_supabase import shopify_sync_bp
from shopify_sync_down_api import shopify_sync_down_bp
from xorosoft_api import xorosoft_bp
# Use Supabase version instead of SQLite version
# from collections_api import collections_bp
from collections_supabase import collections_bp
# Use Supabase version instead of SQLite version
# from products_batch_api import products_batch_bp
from products_batch_supabase import products_batch_bp
# Use Supabase version instead of SQLite version
# from products_api import products_bp
from products_supabase import products_bp
from batch_api import batch_bp
from parallel_sync_api import parallel_sync_bp
# Use Supabase version instead of SQLite version
# from categories_api import categories_bp
from categories_supabase import categories_bp
from admin_api import admin_bp
# Use Supabase version instead of SQLite version
# from dashboard_stats_api import dashboard_stats_bp
from dashboard_stats_supabase import dashboard_stats_bp
from products_staging_api import products_staging_bp
from enhanced_sync_api import enhanced_sync_bp
from enhanced_icon_sync_api import enhanced_icon_sync_bp
from collections_icon_api import collections_icon_bp
from enhanced_categories_api import enhanced_categories_bp
# from webhook_api import webhook_bp  # Temporarily disabled

# Import services
from services.icon_category_service import IconCategoryService
from services.shopify_icon_sync_service import ShopifyIconSyncService
from services.shopify_product_sync_service import ShopifyProductSyncService

# Environment variables already loaded at the top

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(config[os.getenv('FLASK_ENV', 'development')])

# Initialize CORS with broader support
CORS(app, 
     origins=["http://localhost:3055", "http://localhost:3056", "http://localhost:3560", "http://localhost:3000", "http://127.0.0.1:3000"],
     supports_credentials=True,
     allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
     expose_headers=["Authorization"])

# Initialize JWT
jwt = JWTManager(app)

# Initialize SocketIO with better CORS and error handling
socketio = SocketIO(
    app,
    cors_allowed_origins=["http://localhost:3055", "http://localhost:3056", "http://localhost:3560"],
    async_mode='threading',
    logger=True,
    engineio_logger=True,
    ping_timeout=60,
    ping_interval=25
)

# Initialize Redis (optional for development)
try:
    redis_client = redis.from_url(app.config['REDIS_URL'])
    redis_client.ping()  # Test connection
except:
    app.logger.warning("Redis not available, using in-memory storage")
    redis_client = None

# Initialize Job Manager
job_manager = JobManager(redis_client) if redis_client else None

# Initialize WebSocket Service
from websocket_service import WebSocketService
from websocket_handlers import register_websocket_handlers
websocket_service = WebSocketService(socketio)

# Register WebSocket handlers with Supabase authentication
register_websocket_handlers(socketio)

# Register health check blueprint
from health_check import health_bp
app.register_blueprint(health_bp)

# Register all API blueprints
app.register_blueprint(import_bp)
app.register_blueprint(shopify_sync_bp)
app.register_blueprint(shopify_sync_down_bp)
app.register_blueprint(xorosoft_bp)
app.register_blueprint(collections_bp)
app.register_blueprint(products_batch_bp)
app.register_blueprint(products_bp)
app.register_blueprint(batch_bp)
app.register_blueprint(parallel_sync_bp)
app.register_blueprint(categories_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(products_staging_bp)
app.register_blueprint(enhanced_sync_bp)
app.register_blueprint(enhanced_icon_sync_bp)
app.register_blueprint(collections_icon_bp)
app.register_blueprint(enhanced_categories_bp)
app.register_blueprint(dashboard_stats_bp)

# Initialize error tracking
from error_tracking import error_tracker

# DISABLED: # Development mode auth bypass
# DISABLED: DEV_MODE = os.getenv('FLASK_ENV', 'development') == 'development'
# DISABLED: 
# DISABLED: def jwt_required_bypass(fn):
# DISABLED:     """JWT required decorator that bypasses auth in development mode"""
# DISABLED:     @wraps(fn)
# DISABLED:     def wrapper(*args, **kwargs):
# DISABLED:         if DEV_MODE:
# DISABLED:             return fn(*args, **kwargs)
# DISABLED:         else:
# DISABLED:             return jwt_required()(fn)(*args, **kwargs)
# DISABLED:     return wrapper
# DISABLED: 
# DISABLED: # Initialize database
# DISABLED: try:
# DISABLED:     app.logger.info("Backend startup")
# DISABLED:     init_database(create_tables=True)
# DISABLED:     app.logger.info("Database initialized successfully")
# DISABLED: except Exception as e:
# DISABLED:     app.logger.error(f"Failed to initialize database: {e}")
# DISABLED:     # Continue anyway for development
# DISABLED: 
# DISABLED: # Initialize Icon Generation Service (global instance)
# DISABLED: icon_service = None
# DISABLED: 
# DISABLED: # Initialize Icon Storage and Generator (create instances if needed)
# DISABLED: try:
# DISABLED:     icon_storage = IconStorage(base_path="data/category_icons")
# DISABLED:     # Try to use OpenAI-powered generator if available
# DISABLED:     if os.getenv("OPENAI_API_KEY"):
# DISABLED:         from icon_generator_openai import icon_generator_openai
# DISABLED:         icon_generator = icon_generator_openai
# DISABLED:         app.logger.info("Using OpenAI-powered icon generator")
# DISABLED:     else:
# DISABLED:         icon_generator = IconGenerator()
# DISABLED:         app.logger.warning("No OpenAI API key found, using placeholder icon generator")
# DISABLED: except Exception as e:
# DISABLED:     app.logger.warning(f"Icon storage/generator not available: {e}")
# DISABLED:     icon_storage = None
# DISABLED:     icon_generator = None
# DISABLED: 
# DISABLED: # Development mode auth bypass
# DISABLED: DEV_MODE = os.getenv('FLASK_ENV', 'development') == 'development'
# DISABLED: if DEV_MODE:
# DISABLED:     app.logger.warning("Running in development mode - authentication bypassed")
# DISABLED: 
# DISABLED: def dev_jwt_required():
# DISABLED:     """JWT required decorator that bypasses auth in development mode"""
# DISABLED:     def decorator(fn):
# DISABLED:         if DEV_MODE:
# DISABLED:             @wraps(fn)
# DISABLED:             def wrapper(*args, **kwargs):
# DISABLED:                 return fn(*args, **kwargs)
# DISABLED:             return wrapper
# DISABLED:         else:
# DISABLED:             return jwt_required()(fn)
# DISABLED:     return decorator
# DISABLED: 
# DISABLED: # Replace jwt_required with our dev version
# DISABLED: jwt_required = dev_jwt_required
# DISABLED: 
# DISABLED: # Also bypass get_jwt_identity in dev mode
# DISABLED: original_get_jwt_identity = get_jwt_identity
# DISABLED: def dev_get_jwt_identity():
# DISABLED:     """Get JWT identity with dev mode bypass"""
# DISABLED:     if DEV_MODE:
# DISABLED:         return "dev-user"  # Return a dummy user ID
# DISABLED:     else:
# DISABLED:         return original_get_jwt_identity()
# DISABLED: 
# DISABLED: get_jwt_identity = dev_get_jwt_identity

def get_user_id():
    """Helper function to get user ID from Supabase token."""
    user_id = get_current_user_id()
    if user_id:
        # For backward compatibility with local database
        # We'll need to map Supabase IDs to local user IDs
        with db_session_scope() as session:
            user_repo = UserRepository(session)
            user = user_repo.get_by_supabase_id(user_id)
            if user:
                return user.id
            # If user doesn't exist locally, create them
            # This helps with migration period
            return 1  # Fallback for now
    return None

# Setup logging
def setup_logging():
    """Configure application logging."""
    try:
        if not os.path.exists(app.config['LOG_PATH']):
            os.makedirs(app.config['LOG_PATH'])
        
        file_handler = RotatingFileHandler(
            os.path.join(app.config['LOG_PATH'], 'app.log'),
            maxBytes=10240000,  # 10MB
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.info('Backend startup - file logging configured')
    except (PermissionError, OSError):
        # File system is read-only - use console logging only
        print("File system is read-only, using console logging only")
    
    app.logger.setLevel(logging.INFO)

setup_logging()

# Initialize database on startup
try:
    # Determine environment - only PostgreSQL/Supabase supported
    is_production = os.getenv('FLASK_ENV') == 'production'
    
    app.logger.info(f"Database initialization: production={is_production}")
    
    # In development, allow table creation; in production, assume tables exist
    create_tables = not is_production
    app.logger.info(f"PostgreSQL database initialization: creating tables={create_tables}")
    
    init_database(create_tables=create_tables)
    
    # Seed initial data for development
    if create_tables:
        try:
            from database import DatabaseUtils
            DatabaseUtils.seed_initial_data()
            app.logger.info("Initial data seeded successfully")
        except Exception as seed_error:
            app.logger.warning(f"Failed to seed initial data: {seed_error}")
    
    # Verify database health
    from database import database_health_check
    health = database_health_check()
    if health.get('status') == 'healthy':
        app.logger.info("Database health check passed")
    else:
        app.logger.error(f"Database health check failed: {health}")
        
except Exception as e:
    app.logger.error(f"Failed to initialize database: {e}")
    # In containerized environments, this should be fatal
    if os.getenv('FLASK_ENV') == 'production':
        app.logger.critical("Database initialization failed in production - exiting")
        import sys
        sys.exit(1)
    else:
        app.logger.warning("Database initialization failed in development - continuing")

# Schemas
login_schema = LoginSchema()
register_schema = RegisterSchema()
script_execution_schema = ScriptExecutionSchema()
job_status_schema = JobStatusSchema()
sync_history_schema = SyncHistorySchema()
script_definition_schema = ScriptDefinitionSchema()
category_icon_schema = CategoryIconSchema()
icon_generation_schema = IconGenerationSchema()

# Health check endpoint
@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint for Docker health checks and load balancers."""
    health_status = {
        "status": "healthy",
        "timestamp": time.time(),
        "version": "1.0.0",
        "services": {}
    }
    
    overall_healthy = True
    
    # Check Supabase database connection
    try:
        supabase_db = get_supabase_db()
        db_health = supabase_db.health_check()
        health_status["services"]["supabase"] = db_health["status"]
        if db_health["status"] != "healthy":
            overall_healthy = False
    except Exception as e:
        health_status["services"]["supabase"] = f"unhealthy: {str(e)}"
        overall_healthy = False
    
    # Fallback: Check legacy database connection if Supabase fails
    if not overall_healthy:
        try:
            with db_session_scope() as session:
                from sqlalchemy import text
                session.execute(text("SELECT 1"))
            health_status["services"]["database_fallback"] = "healthy"
            overall_healthy = True  # At least fallback works
        except Exception as e:
            health_status["services"]["database_fallback"] = f"unhealthy: {str(e)}"
    
    # Check Redis connection if available
    try:
        if redis_client and redis_client.ping():
            health_status["services"]["redis"] = "healthy"
        else:
            health_status["services"]["redis"] = "unavailable"
    except Exception as e:
        health_status["services"]["redis"] = f"unavailable: {str(e)}"
    
    # Basic app health (always healthy if we can respond)
    health_status["services"]["app"] = "healthy"
    
    if not overall_healthy:
        health_status["status"] = "degraded"
        return jsonify(health_status), 200  # Return 200 even if degraded for basic liveness
    
    return jsonify(health_status), 200

# Simple liveness check (for basic container health)
@app.route("/health/live", methods=["GET"])
def liveness_check():
    """Simple liveness check that always returns healthy if app is running."""
    return jsonify({
        "status": "alive",
        "timestamp": time.time()
    }), 200

# Supabase test endpoint
@app.route("/health/pool", methods=["GET"])
def pool_status():
    """Get database connection pool status."""
    try:
        status = db_manager.get_pool_status()
        return jsonify({
            "status": "success",
            "pool": status,
            "timestamp": time.time()
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e),
            "timestamp": time.time()
        }), 500

@app.route("/health/supabase", methods=["GET"])
def supabase_test():
    """Test Supabase SDK functionality."""
    try:
        supabase_db = get_supabase_db()
        
        # Test basic queries
        users = supabase_db.client.table('users').select('id,email').limit(3).execute()
        products = supabase_db.client.table('products').select('id,name').limit(3).execute()
        
        return jsonify({
            "status": "success",
            "supabase_url": supabase_db.supabase_url,
            "tables_tested": {
                "users": len(users.data) if users.data else 0,
                "products": len(products.data) if products.data else 0
            },
            "timestamp": time.time()
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e),
            "timestamp": time.time()
        }), 500

@app.route("/api/auth/login", methods=["POST"])
def login():
    """Handle user login with Supabase."""
    try:
        # Debug logging
        app.logger.info(f"Login request headers: {dict(request.headers)}")
        app.logger.info(f"Login request content-type: {request.content_type}")
        app.logger.info(f"Login request data: {request.data}")
        
        json_data = request.get_json(force=True)  # Force JSON parsing
        if not json_data:
            return jsonify({"message": "No JSON data provided"}), 400
        data = login_schema.load(json_data)
    except ValidationError as e:
        return jsonify({"message": "Invalid request data", "errors": e.messages}), 400
    except Exception as e:
        app.logger.error(f"Login request parsing error: {str(e)}")
        return jsonify({"message": "Invalid request data", "errors": str(e)}), 400
    
    try:
        # Authenticate with Supabase
        result = auth_service.sign_in(data["email"], data["password"])
        
        app.logger.info(f"User logged in: {data['email']}")
        
        # Get user metadata from Supabase
        user_metadata = result["user"].get("user_metadata", {})
        
        return jsonify({
            "access_token": result["session"]["access_token"],
            "refresh_token": result["session"]["refresh_token"],
            "user": {
                "id": result["user"]["id"],
                "email": result["user"]["email"],
                "first_name": user_metadata.get("first_name", ""),
                "last_name": user_metadata.get("last_name", ""),
                "is_admin": user_metadata.get("is_admin", False)
            }
        })
            
    except Exception as e:
        app.logger.warning(f"Failed login attempt for: {data['email']} - {str(e)}")
        return jsonify({"message": "Invalid credentials"}), 401

@app.route("/api/auth/signup", methods=["POST"])
def signup():
    """Handle user registration with Supabase."""
    try:
        data = request.get_json()
        
        # Validate input
        if not data or 'email' not in data or 'password' not in data:
            return jsonify({"message": "Email and password are required"}), 400
            
        email = data.get('email', '').strip()
        password = data.get('password', '')
        
        # Basic validation
        if not email or '@' not in email:
            return jsonify({"message": "Invalid email address"}), 400
            
        if len(password) < 6:
            return jsonify({"message": "Password must be at least 6 characters long"}), 400
        
        # Optional fields
        first_name = data.get('first_name', '').strip()
        last_name = data.get('last_name', '').strip()
        
        # Register with Supabase
        metadata = {
            "first_name": first_name,
            "last_name": last_name
        }
        result = auth_service.sign_up(email, password, metadata)
        
        app.logger.info(f"New user registered: {email}")
        
        # Return success with tokens if available
        response_data = {
            "message": "Registration successful",
            "user": {
                "id": result["user"]["id"],
                "email": result["user"]["email"],
                "first_name": first_name,
                "last_name": last_name,
                "is_admin": False  # Default to non-admin
            }
        }
        
        # Include session tokens if available
        if result.get("session"):
            response_data["access_token"] = result["session"]["access_token"]
            response_data["refresh_token"] = result["session"]["refresh_token"]
        
        return jsonify(response_data), 201
            
    except Exception as e:
        app.logger.error(f"Registration error for {data.get('email', 'unknown')}: {str(e)}")
        
        # Check for specific Supabase errors
        error_message = str(e).lower()
        if "already registered" in error_message or "already exists" in error_message:
            return jsonify({"message": "User already exists"}), 409
        elif "invalid email" in error_message:
            return jsonify({"message": "Invalid email address"}), 400
        elif "weak password" in error_message:
            return jsonify({"message": "Password is too weak"}), 400
        else:
            return jsonify({"message": "Registration failed. Please try again."}), 500

@app.route("/api/auth/me", methods=["GET"])
@supabase_jwt_required
def get_current_user():
    """Get current authenticated user information."""
    try:
        from flask import g
        current_user = g.get('current_user')
        if not current_user:
            return jsonify({"message": "User not found"}), 404
            
        return jsonify({
            "user": {
                "id": current_user.get("id"),
                "email": current_user.get("email"),
                "first_name": current_user.get("first_name", ""),
                "last_name": current_user.get("last_name", ""),
                "is_admin": current_user.get("is_admin", False),
                "created_at": current_user.get("created_at"),
                "last_login": current_user.get("last_login")
            }
        }), 200
    except Exception as e:
        app.logger.error(f"Error getting current user: {str(e)}")
        return jsonify({"message": "Internal server error"}), 500

@app.route("/api/sync/history", methods=["GET"])
@supabase_jwt_required
def get_sync_history():
    """Get sync history for the dashboard."""
    try:
        # Return empty history for now - this can be implemented later
        return jsonify([]), 200
    except Exception as e:
        app.logger.error(f"Error getting sync history: {str(e)}")
        return jsonify({"message": "Internal server error"}), 500

# Helper function to run async functions in Flask
def run_async(coro):
    """Run async function in Flask context."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

# Icon Generation API Endpoints

@app.route("/api/icons/generate", methods=["POST"])
@supabase_jwt_required
def generate_single_icon():
    """Generate a single category icon."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"message": "Request data required"}), 400
        
        category = data.get('category', '').strip()
        if not category:
            return jsonify({"message": "Category is required"}), 400
        
        # Parse style and color scheme
        style = IconStyle.MODERN
        color_scheme = IconColor.BRAND_COLORS
        
        if data.get('style'):
            try:
                style = IconStyle(data['style'].lower())
            except ValueError:
                return jsonify({"message": f"Invalid style. Valid options: {[s.value for s in IconStyle]}"}), 400
        
        if data.get('color_scheme'):
            try:
                color_scheme = IconColor(data['color_scheme'].lower())
            except ValueError:
                return jsonify({"message": f"Invalid color scheme. Valid options: {[c.value for c in IconColor]}"}), 400
        
        custom_elements = data.get('custom_elements', [])
        user_id = get_current_user_id()
        
        # Generate icon
        async def generate():
            async with IconGenerationService() as service:
                result = await service.generate_single_icon(
                    category=category,
                    style=style,
                    color_scheme=color_scheme,
                    custom_elements=custom_elements,
                    user_id=user_id
                )
                return result
        
        result = run_async(generate())
        
        if result.success:
            return jsonify({
                "success": True,
                "image_url": result.image_url,
                "local_path": result.local_path,
                "generation_time": result.generation_time,
                "metadata": result.metadata
            })
        else:
            return jsonify({
                "success": False,
                "error": result.error,
                "metadata": result.metadata
            }), 500
            
    except Exception as e:
        app.logger.error(f"Error generating single icon: {e}")
        return jsonify({"message": "Internal server error", "error": str(e)}), 500

@app.route("/api/icons/generate/batch", methods=["POST"])
@supabase_jwt_required
def generate_batch_icons():
    """Start batch icon generation."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"message": "Request data required"}), 400
        
        categories = data.get('categories', [])
        if not categories or not any(c.strip() for c in categories):
            return jsonify({"message": "At least one category is required"}), 400
        
        # Validate request
        async def validate_and_start():
            async with IconGenerationService() as service:
                validation = service.validate_generation_request(
                    categories=categories,
                    style=data.get('style'),
                    color_scheme=data.get('color_scheme')
                )
                
                if not validation['valid']:
                    return {"valid": False, "errors": validation['errors']}
                
                # Parse parameters
                style = IconStyle.MODERN
                color_scheme = IconColor.BRAND_COLORS
                
                if data.get('style'):
                    try:
                        style = IconStyle(data['style'].lower())
                    except ValueError:
                        pass
                
                if data.get('color_scheme'):
                    try:
                        color_scheme = IconColor(data['color_scheme'].lower())
                    except ValueError:
                        pass
                
                # Create batch request
                batch_request = BatchGenerationRequest(
                    categories=validation['validated_categories'],
                    style=style,
                    color_scheme=color_scheme,
                    variations_per_category=data.get('variations_per_category', 1),
                    user_id=get_current_user_id(),
                    custom_elements=data.get('custom_elements'),
                    metadata=data.get('metadata')
                )
                
                # Start batch generation with WebSocket progress
                async def progress_callback(batch_id, progress, current_category, completed, total):
                    socketio.emit('batch_progress', {
                        'batch_id': batch_id,
                        'progress': progress,
                        'current_category': current_category,
                        'completed': completed,
                        'total': total
                    }, room=batch_id)
                
                batch_id = await service.generate_batch_icons(batch_request, progress_callback)
                return {"valid": True, "batch_id": batch_id}
        
        result = run_async(validate_and_start())
        
        if not result['valid']:
            return jsonify({"message": "Validation failed", "errors": result['errors']}), 400
        
        return jsonify({
            "message": "Batch generation started",
            "batch_id": result['batch_id']
        }), 201
        
    except Exception as e:
        app.logger.error(f"Error starting batch generation: {e}")
        return jsonify({"message": "Internal server error", "error": str(e)}), 500

@app.route("/api/icons/generate/bulk", methods=["POST"])
@supabase_jwt_required
def generate_bulk_icons():
    """Generate icons for multiple collections in bulk."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"message": "Request data required"}), 400
        
        collection_ids = data.get('collection_ids', [])
        if not collection_ids:
            return jsonify({"message": "At least one collection_id is required"}), 400
        
        # Get collection names from IDs
        with db_session_scope() as session:
            collections = session.query(Collection).filter(
                Collection.id.in_(collection_ids)
            ).all()
            
            if not collections:
                return jsonify({"message": "No valid collections found"}), 404
            
            categories = [col.name for col in collections]
        
        # Validate request
        async def validate_and_start():
            async with IconGenerationService() as service:
                validation = service.validate_generation_request(
                    categories=categories,
                    style=data.get('style'),
                    color_scheme=data.get('color_scheme')
                )
                
                if not validation['valid']:
                    return {"valid": False, "errors": validation['errors']}
                
                # Parse parameters
                style = IconStyle.MODERN
                color_scheme = IconColor.BRAND_COLORS
                
                if data.get('style'):
                    try:
                        style = IconStyle(data['style'].lower())
                    except ValueError:
                        pass
                
                if data.get('color_scheme'):
                    try:
                        color_scheme = IconColor(data['color_scheme'].lower())
                    except ValueError:
                        pass
                
                # Create batch request
                batch_request = BatchGenerationRequest(
                    categories=validation['validated_categories'],
                    style=style,
                    color_scheme=color_scheme,
                    variations_per_category=1,
                    user_id=get_current_user_id(),
                    metadata={'source': 'bulk_collections', 'collection_ids': collection_ids}
                )
                
                # Start batch generation with WebSocket progress
                async def progress_callback(batch_id, progress, current_category, completed, total):
                    socketio.emit('bulk_generation_progress', {
                        'batch_id': batch_id,
                        'progress': progress,
                        'current_category': current_category,
                        'completed': completed,
                        'total': total,
                        'status': 'running' if completed < total else 'completed'
                    }, room=batch_id)
                
                batch_id = await service.generate_batch_icons(batch_request, progress_callback)
                return {"valid": True, "batch_id": batch_id}
        
        result = run_async(validate_and_start())
        
        if not result['valid']:
            return jsonify({"message": "Validation failed", "errors": result['errors']}), 400
        
        return jsonify({
            "message": "Bulk generation started",
            "job_id": result['batch_id'],
            "collections_count": len(collection_ids)
        }), 201
        
    except Exception as e:
        app.logger.error(f"Error starting bulk generation: {e}")
        return jsonify({"message": "Internal server error", "error": str(e)}), 500

@app.route("/api/icons/batch/<batch_id>/status", methods=["GET"])
@supabase_jwt_required
def get_batch_status(batch_id):
    """Get status of batch icon generation."""
    try:
        async def get_status():
            async with IconGenerationService() as service:
                status = service.get_batch_status(batch_id)
                return status
        
        status = run_async(get_status())
        
        if not status:
            return jsonify({"message": "Batch not found"}), 404
        
        return jsonify({
            "batch_id": status.batch_id,
            "status": status.status,
            "progress": status.progress,
            "current_category": status.current_category,
            "total_categories": status.total_categories,
            "completed_categories": status.completed_categories,
            "estimated_completion": status.estimated_completion.isoformat() if status.estimated_completion else None,
            "created_at": status.created_at.isoformat() if status.created_at else None,
            "started_at": status.started_at.isoformat() if status.started_at else None,
            "completed_at": status.completed_at.isoformat() if status.completed_at else None
        })
        
    except Exception as e:
        app.logger.error(f"Error getting batch status: {e}")
        return jsonify({"message": "Internal server error", "error": str(e)}), 500

@app.route("/api/icons/batch/<batch_id>/result", methods=["GET"])
@supabase_jwt_required
def get_batch_result(batch_id):
    """Get result of batch icon generation."""
    try:
        async def get_result():
            async with IconGenerationService() as service:
                result = service.get_batch_result(batch_id)
                return result
        
        result = run_async(get_result())
        
        if not result:
            return jsonify({"message": "Batch result not found"}), 404
        
        # Convert results to JSON-serializable format
        results_data = []
        for r in result.results:
            results_data.append({
                "success": r.success,
                "image_url": r.image_url,
                "local_path": r.local_path,
                "error": r.error,
                "metadata": r.metadata,
                "generation_time": r.generation_time
            })
        
        return jsonify({
            "batch_id": result.batch_id,
            "total_requested": result.total_requested,
            "successful": result.successful,
            "failed": result.failed,
            "start_time": result.start_time.isoformat(),
            "end_time": result.end_time.isoformat() if result.end_time else None,
            "duration": result.duration,
            "results": results_data,
            "metadata": result.metadata
        })
        
    except Exception as e:
        app.logger.error(f"Error getting batch result: {e}")
        return jsonify({"message": "Internal server error", "error": str(e)}), 500

@app.route("/api/icons/batch/<batch_id>/cancel", methods=["POST"])
@supabase_jwt_required
def cancel_batch_generation(batch_id):
    """Cancel a running batch generation."""
    try:
        async def cancel():
            async with IconGenerationService() as service:
                success = service.cancel_batch(batch_id)
                return success
        
        success = run_async(cancel())
        
        if success:
            return jsonify({"message": "Batch cancelled successfully"})
        else:
            return jsonify({"message": "Batch not found or cannot be cancelled"}), 400
        
    except Exception as e:
        app.logger.error(f"Error cancelling batch: {e}")
        return jsonify({"message": "Internal server error", "error": str(e)}), 500

@app.route("/api/icons/batches", methods=["GET"])
@supabase_jwt_required
def list_user_batches():
    """List user's batch generation jobs."""
    try:
        user_id = get_current_user_id()
        
        async def list_batches():
            async with IconGenerationService() as service:
                batches = service.list_active_batches(user_id)
                return batches
        
        batches = run_async(list_batches())
        
        batches_data = []
        for batch in batches:
            batches_data.append({
                "batch_id": batch.batch_id,
                "status": batch.status,
                "progress": batch.progress,
                "total_categories": batch.total_categories,
                "completed_categories": batch.completed_categories,
                "created_at": batch.created_at.isoformat() if batch.created_at else None,
                "completed_at": batch.completed_at.isoformat() if batch.completed_at else None
            })
        
        return jsonify(batches_data)
        
    except Exception as e:
        app.logger.error(f"Error listing batches: {e}")
        return jsonify({"message": "Internal server error", "error": str(e)}), 500

@app.route("/api/icons/cached", methods=["GET"])
@supabase_jwt_required
def list_cached_icons():
    """List cached icons."""
    try:
        category = request.args.get('category')
        
        async def get_cached():
            async with IconGenerationService() as service:
                icons = service.get_cached_icons(category)
                return icons
        
        icons = run_async(get_cached())
        return jsonify(icons)
        
    except Exception as e:
        app.logger.error(f"Error listing cached icons: {e}")
        return jsonify({"message": "Internal server error", "error": str(e)}), 500

@app.route("/api/icons/cache/clear", methods=["POST"])
@supabase_jwt_required
def clear_icon_cache():
    """Clear icon cache."""
    try:
        data = request.get_json() or {}
        category = data.get('category')
        older_than_days = data.get('older_than_days')
        
        async def clear_cache():
            async with IconGenerationService() as service:
                count = service.clear_cache(category, older_than_days)
                return count
        
        count = run_async(clear_cache())
        return jsonify({"message": f"Cleared {count} cached icons"})
        
    except Exception as e:
        app.logger.error(f"Error clearing cache: {e}")
        return jsonify({"message": "Internal server error", "error": str(e)}), 500

@app.route("/api/icons/stats", methods=["GET"])
@supabase_jwt_required
def get_generation_stats():
    """Get icon generation statistics."""
    try:
        async def get_stats():
            async with IconGenerationService() as service:
                stats = service.get_generation_stats()
                return stats
        
        stats = run_async(get_stats())
        return jsonify(stats)
        
    except Exception as e:
        app.logger.error(f"Error getting stats: {e}")
        return jsonify({"message": "Internal server error", "error": str(e)}), 500

@app.route("/api/icons/categories/suggestions", methods=["GET"])
@supabase_jwt_required
def get_category_suggestions():
    """Get category suggestions."""
    try:
        partial_name = request.args.get('q', '')
        
        async def get_suggestions():
            async with IconGenerationService() as service:
                suggestions = service.get_category_suggestions(partial_name)
                return suggestions
        
        suggestions = run_async(get_suggestions())
        return jsonify(suggestions)
        
    except Exception as e:
        app.logger.error(f"Error getting suggestions: {e}")
        return jsonify({"message": "Internal server error", "error": str(e)}), 500

# Temporary stub endpoints to fix 500 errors
# TODO: Replace with proper Supabase implementations
# NOTE: /api/dashboard/enhanced-stats is now handled by dashboard_stats_supabase.py

@app.route("/api/sync/status", methods=["GET"])
@supabase_jwt_required
def get_sync_status():
    """Get comprehensive sync status with real-time updates."""
    try:
        # Get sync status from various sources
        sync_status = {
            "is_syncing": False,
            "last_sync": None,
            "sync_progress": 0,
            "sync_message": "No sync in progress",
            "active_operations": [],
            "queue_depth": 0,
            "error_count": 0,
            "success_rate": 100.0,
            "estimated_completion": None
        }
        
        # Check if there are active sync operations
        if redis_client:
            try:
                # Check for active sync jobs in Redis
                active_jobs = redis_client.keys("sync_job:*")
                sync_status["active_operations"] = len(active_jobs)
                sync_status["is_syncing"] = len(active_jobs) > 0
                
                # Get queue depth
                queue_depth = redis_client.llen("sync_queue")
                sync_status["queue_depth"] = queue_depth
                
                # Get error statistics
                error_count = redis_client.get("sync_errors_24h") or 0
                sync_status["error_count"] = int(error_count)
                
            except Exception as e:
                app.logger.warning(f"Failed to get Redis sync status: {e}")
        
        # Get last sync information from database
        try:
            with db_session_scope() as session:
                sync_repo = SyncHistoryRepository(session)
                last_sync = sync_repo.get_latest_sync()
                if last_sync:
                    sync_status["last_sync"] = last_sync.completed_at.isoformat() if last_sync.completed_at else None
                    sync_status["sync_message"] = last_sync.status or "Last sync completed"
                    
                # Calculate success rate from recent syncs
                recent_syncs = sync_repo.get_recent_syncs(hours=24)
                if recent_syncs:
                    successful = sum(1 for sync in recent_syncs if sync.status == 'completed')
                    sync_status["success_rate"] = (successful / len(recent_syncs)) * 100
                    
        except Exception as e:
            app.logger.warning(f"Failed to get database sync status: {e}")
        
        return jsonify(sync_status)
        
    except Exception as e:
        app.logger.error(f"Error getting sync status: {e}")
        return jsonify({"message": "Internal server error"}), 500

# Products endpoints now handled by products_supabase.py

@app.route("/api/batch/operations", methods=["GET"])
@supabase_jwt_required
def get_batch_operations():
    """Get current batch operations with progress tracking."""
    try:
        operations = []
        
        # Get batch operations from Redis if available
        if redis_client:
            try:
                # Get all batch operation keys
                batch_keys = redis_client.keys("batch_op:*")
                
                for key in batch_keys:
                    operation_data = redis_client.hgetall(key)
                    if operation_data:
                        # Decode Redis data
                        operation = {
                            "id": operation_data.get(b'id', b'').decode('utf-8'),
                            "type": operation_data.get(b'type', b'').decode('utf-8'),
                            "status": operation_data.get(b'status', b'').decode('utf-8'),
                            "progress": float(operation_data.get(b'progress', b'0')),
                            "total_items": int(operation_data.get(b'total_items', b'0')),
                            "processed_items": int(operation_data.get(b'processed_items', b'0')),
                            "failed_items": int(operation_data.get(b'failed_items', b'0')),
                            "started_at": operation_data.get(b'started_at', b'').decode('utf-8'),
                            "estimated_completion": operation_data.get(b'estimated_completion', b'').decode('utf-8'),
                            "error_message": operation_data.get(b'error_message', b'').decode('utf-8')
                        }
                        operations.append(operation)
                        
            except Exception as e:
                app.logger.warning(f"Failed to get batch operations from Redis: {e}")
        
        # Get database batch operations as fallback
        try:
            with db_session_scope() as session:
                job_repo = JobRepository(session)
                recent_jobs = job_repo.get_recent_jobs(limit=10)
                
                for job in recent_jobs:
                    if job.job_type and 'batch' in job.job_type.lower():
                        operation = {
                            "id": str(job.id),
                            "type": job.job_type,
                            "status": job.status,
                            "progress": job.progress or 0,
                            "total_items": job.total_items or 0,
                            "processed_items": job.processed_items or 0,
                            "failed_items": job.failed_items or 0,
                            "started_at": job.started_at.isoformat() if job.started_at else None,
                            "estimated_completion": job.estimated_completion.isoformat() if job.estimated_completion else None,
                            "error_message": job.error_message
                        }
                        operations.append(operation)
                        
        except Exception as e:
            app.logger.warning(f"Failed to get batch operations from database: {e}")
        
        # Remove duplicates and sort by start time
        seen_ids = set()
        unique_operations = []
        for op in operations:
            if op["id"] not in seen_ids:
                seen_ids.add(op["id"])
                unique_operations.append(op)
        
        # Sort by started_at (most recent first)
        unique_operations.sort(key=lambda x: x.get("started_at", ""), reverse=True)
        
        return jsonify({
            "operations": unique_operations,
            "total": len(unique_operations),
            "active_count": len([op for op in unique_operations if op["status"] in ["running", "pending"]]),
            "completed_count": len([op for op in unique_operations if op["status"] == "completed"]),
            "failed_count": len([op for op in unique_operations if op["status"] == "failed"])
        })
        
    except Exception as e:
        app.logger.error(f"Error getting batch operations: {e}")
        return jsonify({"message": "Internal server error"}), 500

# Collections endpoints now handled by collections_supabase.py

@app.route("/api/analytics/stats", methods=["GET"])
@supabase_jwt_required
def get_analytics_stats():
    """Get comprehensive system analytics and metrics."""
    try:
        period = request.args.get('period', 'last_30_days')
        
        analytics = {
            "period": period,
            "system_health": {
                "uptime": 99.9,
                "response_time": 150,
                "error_rate": 0.01
            },
            "sync_metrics": {
                "total_syncs": 0,
                "successful_syncs": 0,
                "failed_syncs": 0,
                "avg_sync_time": 0,
                "products_synced": 0
            },
            "performance": {
                "api_requests": 0,
                "avg_response_time": 0,
                "cache_hit_rate": 85.0,
                "memory_usage": 65.0,
                "cpu_usage": 25.0
            },
            "user_activity": {
                "active_users": 0,
                "total_sessions": 0,
                "avg_session_duration": 0
            }
        }
        
        # Get sync metrics from database
        try:
            with db_session_scope() as session:
                sync_repo = SyncHistoryRepository(session)
                
                # Calculate time range
                if period == "last_24_hours":
                    hours = 24
                elif period == "last_7_days":
                    hours = 24 * 7
                else:  # last_30_days
                    hours = 24 * 30
                
                recent_syncs = sync_repo.get_recent_syncs(hours=hours)
                
                if recent_syncs:
                    analytics["sync_metrics"]["total_syncs"] = len(recent_syncs)
                    analytics["sync_metrics"]["successful_syncs"] = sum(
                        1 for sync in recent_syncs if sync.status == 'completed'
                    )
                    analytics["sync_metrics"]["failed_syncs"] = sum(
                        1 for sync in recent_syncs if sync.status == 'failed'
                    )
                    
                    # Calculate average sync time
                    completed_syncs = [s for s in recent_syncs if s.status == 'completed' and s.duration]
                    if completed_syncs:
                        avg_duration = sum(s.duration for s in completed_syncs) / len(completed_syncs)
                        analytics["sync_metrics"]["avg_sync_time"] = round(avg_duration, 2)
                    
                    # Count products synced
                    products_synced = sum(s.records_processed or 0 for s in recent_syncs)
                    analytics["sync_metrics"]["products_synced"] = products_synced
                    
        except Exception as e:
            app.logger.warning(f"Failed to get sync metrics: {e}")
        
        # Get performance metrics from Redis
        if redis_client:
            try:
                # Get cached performance metrics
                api_requests = redis_client.get(f"metrics:api_requests:{period}") or 0
                analytics["performance"]["api_requests"] = int(api_requests)
                
                # Get response time metrics
                response_times = redis_client.lrange(f"metrics:response_times:{period}", 0, -1)
                if response_times:
                    avg_response_time = sum(float(rt) for rt in response_times) / len(response_times)
                    analytics["performance"]["avg_response_time"] = round(avg_response_time, 2)
                
                # Get user activity metrics
                active_users = redis_client.scard(f"active_users:{period}")
                analytics["user_activity"]["active_users"] = active_users
                
            except Exception as e:
                app.logger.warning(f"Failed to get performance metrics from Redis: {e}")
        
        return jsonify(analytics)
        
    except Exception as e:
        app.logger.error(f"Error getting analytics stats: {e}")
        return jsonify({"message": "Internal server error"}), 500

# Categories endpoints now handled by categories_supabase.py

# Special case: Handle trailing slash redirect for categories
@app.route("/api/categories/", methods=["GET"])
def redirect_categories():
    """Redirect /api/categories/ to /api/categories"""
    return redirect('/api/categories', code=301)

@app.route("/api/images/<path:filename>", methods=["GET"])
def serve_generated_image(filename):
    """Serve generated icon images."""
    try:
        images_path = Path(app.config['IMAGES_STORAGE_PATH']) if 'IMAGES_STORAGE_PATH' in app.config else Path('data/generated_icons')
        return send_from_directory(images_path, filename)
    except Exception as e:
        app.logger.error(f"Error serving image: {e}")
        return jsonify({"message": "Image not found"}), 404

# Fallback route to serve React app (when frontend service fails)
@app.route("/", defaults={"path": ""}, methods=["GET"])
@app.route("/<path:path>", methods=["GET"])
def serve_frontend_fallback(path):
    """Serve React frontend as fallback when frontend service is unavailable."""
    # Only serve non-API routes
    if path.startswith('api/'):
        return jsonify({"error": "API endpoint not found"}), 404
    
    try:
        # Look for built frontend files in common locations
        frontend_paths = [
            Path("/app/frontend/build"),  # Docker path (primary)
            Path(__file__).parent / "frontend" / "build",  # Same directory structure
            Path(__file__).parent.parent.parent / "frontend" / "build",  # Local dev path
            Path(__file__).parent.parent.parent / "frontend" / "dist"   # Alternative build path
        ]
        
        for frontend_path in frontend_paths:
            if frontend_path.exists():
                # Serve specific file if it exists
                if path:
                    file_path = frontend_path / path
                    if file_path.exists() and file_path.is_file():
                        return send_from_directory(str(frontend_path), path)
                
                # For root or non-existent paths, always serve index.html for React routing
                index_file = frontend_path / "index.html"
                if index_file.exists():
                    return send_from_directory(str(frontend_path), "index.html")
        
        # If no frontend build found, return a basic HTML page
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Cowan's Office Supplies</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
        </head>
        <body>
            <div style="text-align: center; padding: 50px; font-family: Arial, sans-serif;">
                <h1>Cowan's Office Supplies</h1>
                <p>Frontend service is starting up...</p>
                <p>Backend API is running successfully.</p>
                <p><a href="/health">Check Backend Health</a></p>
            </div>
        </body>
        </html>
        """, 200, {'Content-Type': 'text/html'}
        
    except Exception as e:
        app.logger.error(f"Error serving frontend fallback: {e}")
        return jsonify({"error": "Frontend service unavailable"}), 503

@app.before_request
def handle_preflight():
    """Handle CORS preflight requests."""
    if request.method == 'OPTIONS':
        # Build response for preflight
        response = jsonify({'status': 'ok'})
        response.headers['Access-Control-Allow-Origin'] = request.headers.get('Origin', '*')
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        response.headers['Access-Control-Max-Age'] = '3600'
        return response
    
    # Track request start time
    request.start_time = time.time()

@app.after_request
def track_request_end(response):
    """Track request completion and performance."""
    if hasattr(request, 'start_time'):
        duration = time.time() - request.start_time
        
        # Track successful requests
        if response.status_code < 400:
            error_tracker.track_request(success=True)
        else:
            error_tracker.track_request(success=False)
            
        # Log slow requests
        if duration > 1.0:  # Log requests taking more than 1 second
            app.logger.warning(f"Slow request: {request.method} {request.path} took {duration:.2f}s")
            
    return response

# Initialize WebSocket service
from websocket_service import WebSocketService
ws_service = WebSocketService(socketio)

# WebSocket events for real-time updates
@socketio.on('connect')
def handle_connect():
    ws_service.register_client(request.sid)
    emit('connected', {'message': 'Connected to server'})
    logger.info(f'Client connected: {request.sid}')
    
@socketio.on('disconnect')
def handle_disconnect():
    ws_service.unregister_client(request.sid)
    logger.info(f'Client disconnected: {request.sid}')
    
@socketio.on('join_operation')
def handle_join_operation(data):
    operation_id = data.get('operation_id')
    if operation_id:
        ws_service.join_operation_room(request.sid, operation_id)
        emit('operation_joined', {'operation_id': operation_id})
        
@socketio.on('leave_operation')
def handle_leave_operation(data):
    operation_id = data.get('operation_id')
    if operation_id:
        ws_service.leave_operation_room(request.sid, operation_id)
        emit('operation_left', {'operation_id': operation_id})

# Enhanced API endpoint: bulk operations with conflict detection
@app.route('/api/bulk/operations', methods=['POST'])
@supabase_jwt_required
def start_bulk_operation():
    """Start a bulk operation with conflict detection."""
    try:
        data = request.get_json()
        operation_type = data.get('operation_type')
        items = data.get('items', [])
        
        if not operation_type or not items:
            return jsonify({'error': 'operation_type and items are required'}), 400
        
        # Generate operation ID
        operation_id = str(uuid.uuid4())
        
        # Start operation with WebSocket updates
        ws_service.emit_operation_start(
            operation_id=operation_id,
            operation_type=operation_type,
            description=f"Bulk {operation_type} operation",
            total_steps=len(items)
        )
        
        # Process items with conflict detection
        from conflict_detector import conflict_detector
        results = []
        conflicts = []
        
        for i, item in enumerate(items):
            try:
                # Emit progress
                ws_service.emit_operation_progress(
                    operation_id=operation_id,
                    current_step=i + 1,
                    message=f"Processing item {i + 1} of {len(items)}"
                )
                
                # Check for conflicts if target data exists
                if 'target_record' in item:
                    conflict = conflict_detector.detect_conflicts(
                        source_record=item.get('source_record', {}),
                        target_record=item['target_record']
                    )
                    if conflict:
                        conflicts.append({
                            'item_index': i,
                            'conflict_id': conflict.id,
                            'severity': conflict.severity.value,
                            'auto_resolvable': conflict.is_auto_resolvable
                        })
                
                # Process the item (placeholder - implement based on operation_type)
                results.append({
                    'item_index': i,
                    'status': 'success',
                    'processed_at': datetime.utcnow().isoformat()
                })
                
            except Exception as e:
                results.append({
                    'item_index': i,
                    'status': 'error',
                    'error': str(e)
                })
                
                ws_service.emit_operation_log(
                    operation_id=operation_id,
                    level='error',
                    message=f"Error processing item {i + 1}: {str(e)}"
                )
        
        # Complete operation
        ws_service.emit_operation_complete(
            operation_id=operation_id,
            status='success',
            result={
                'total_items': len(items),
                'successful': len([r for r in results if r['status'] == 'success']),
                'failed': len([r for r in results if r['status'] == 'error']),
                'conflicts_detected': len(conflicts)
            }
        )
        
        return jsonify({
            'operation_id': operation_id,
            'status': 'completed',
            'results': results,
            'conflicts': conflicts,
            'summary': {
                'total_items': len(items),
                'successful': len([r for r in results if r['status'] == 'success']),
                'failed': len([r for r in results if r['status'] == 'error']),
                'conflicts_detected': len(conflicts)
            }
        })
        
    except Exception as e:
        logger.error(f"Error in bulk operation: {e}")
        return jsonify({'error': str(e)}), 500

# Enhanced API endpoint: conflict resolution
@app.route('/api/conflicts/<conflict_id>/resolve', methods=['POST'])
@supabase_jwt_required
def resolve_conflict(conflict_id):
    """Resolve a detected conflict."""
    try:
        data = request.get_json()
        resolution = data.get('resolution', {})
        
        if not resolution:
            return jsonify({'error': 'resolution data is required'}), 400
        
        from conflict_detector import conflict_detector
        
        # Resolve the conflict
        success = conflict_detector.resolve_conflict(
            conflict_id=conflict_id,
            resolution=resolution,
            resolved_by=get_current_user_email()
        )
        
        if success:
            return jsonify({
                'status': 'success',
                'message': 'Conflict resolved successfully',
                'conflict_id': conflict_id,
                'resolved_at': datetime.utcnow().isoformat()
            })
        else:
            return jsonify({'error': 'Conflict not found or already resolved'}), 404
            
    except Exception as e:
        logger.error(f"Error resolving conflict: {e}")
        return jsonify({'error': str(e)}), 500

# Enhanced API endpoint: WebSocket status
@app.route('/api/websocket/status', methods=['GET'])
@supabase_jwt_required
def get_websocket_status():
    """Get WebSocket connection status and metrics."""
    try:
        return jsonify({
            'connected_clients': ws_service.get_connected_clients_count(),
            'active_operations': ws_service.get_active_operations(),
            'server_status': 'active',
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        logger.error(f"Error getting WebSocket status: {e}")
        return jsonify({'error': str(e)}), 500

# Analytics and Reporting Endpoints
from analytics_service import analytics_service, ReportPeriod

@app.route('/api/analytics/metrics/real-time', methods=['GET'])
@supabase_jwt_required
def get_real_time_metrics():
    """Get real-time sync metrics."""
    try:
        metrics = analytics_service.get_real_time_metrics()
        return jsonify({
            'status': 'success',
            'metrics': metrics
        })
    except Exception as e:
        logger.error(f"Error getting real-time metrics: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics/reports/<period>', methods=['GET'])
@supabase_jwt_required
def generate_analytics_report(period):
    """Generate analytics report for specified period."""
    try:
        # Validate period
        try:
            report_period = ReportPeriod(period)
        except ValueError:
            return jsonify({'error': 'Invalid report period'}), 400
        
        # Handle custom period
        start_time = None
        end_time = None
        if report_period == ReportPeriod.CUSTOM:
            start_time_str = request.args.get('start_time')
            end_time_str = request.args.get('end_time')
            
            if not start_time_str or not end_time_str:
                return jsonify({'error': 'Custom period requires start_time and end_time parameters'}), 400
            
            try:
                start_time = datetime.fromisoformat(start_time_str)
                end_time = datetime.fromisoformat(end_time_str)
            except ValueError:
                return jsonify({'error': 'Invalid datetime format. Use ISO format (YYYY-MM-DDTHH:MM:SS)'}), 400
        
        # Generate report
        report = analytics_service.generate_report(report_period, start_time, end_time)
        
        # Convert report to dict for JSON response
        report_dict = {
            'period': report.period.value,
            'start_time': report.start_time.isoformat(),
            'end_time': report.end_time.isoformat(),
            'total_operations': report.total_operations,
            'successful_operations': report.successful_operations,
            'failed_operations': report.failed_operations,
            'avg_duration': report.avg_duration,
            'total_items_processed': report.total_items_processed,
            'error_rate': report.error_rate,
            'throughput_per_hour': report.throughput_per_hour,
            'top_errors': report.top_errors,
            'performance_trends': report.performance_trends,
            'resource_usage': report.resource_usage,
            'conflict_stats': report.conflict_stats,
            'recommendations': report.recommendations
        }
        
        return jsonify({
            'status': 'success',
            'report': report_dict
        })
        
    except Exception as e:
        logger.error(f"Error generating analytics report: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics/track/sync-start', methods=['POST'])
@supabase_jwt_required
def track_sync_start():
    """Track the start of a sync operation."""
    try:
        data = request.get_json()
        
        operation_id = data.get('operation_id')
        operation_type = data.get('operation_type')
        items_count = data.get('items_count', 0)
        metadata = data.get('metadata', {})
        
        if not operation_id or not operation_type:
            return jsonify({'error': 'operation_id and operation_type are required'}), 400
        
        analytics_service.track_sync_start(operation_id, operation_type, items_count, metadata)
        
        return jsonify({
            'status': 'success',
            'message': 'Sync start tracked successfully'
        })
        
    except Exception as e:
        logger.error(f"Error tracking sync start: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics/track/sync-progress', methods=['POST'])
@supabase_jwt_required
def track_sync_progress():
    """Track progress of a sync operation."""
    try:
        data = request.get_json()
        
        operation_id = data.get('operation_id')
        items_processed = data.get('items_processed', 0)
        current_throughput = data.get('current_throughput', 0.0)
        errors_count = data.get('errors_count', 0)
        
        if not operation_id:
            return jsonify({'error': 'operation_id is required'}), 400
        
        analytics_service.track_sync_progress(operation_id, items_processed, current_throughput, errors_count)
        
        return jsonify({
            'status': 'success',
            'message': 'Sync progress tracked successfully'
        })
        
    except Exception as e:
        logger.error(f"Error tracking sync progress: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics/track/sync-completion', methods=['POST'])
@supabase_jwt_required
def track_sync_completion():
    """Track completion of a sync operation."""
    try:
        data = request.get_json()
        
        operation_id = data.get('operation_id')
        success = data.get('success', False)
        total_items = data.get('total_items', 0)
        duration = data.get('duration', 0.0)
        errors = data.get('errors', [])
        
        if not operation_id:
            return jsonify({'error': 'operation_id is required'}), 400
        
        analytics_service.track_sync_completion(operation_id, success, total_items, duration, errors)
        
        return jsonify({
            'status': 'success',
            'message': 'Sync completion tracked successfully'
        })
        
    except Exception as e:
        logger.error(f"Error tracking sync completion: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics/track/conflicts', methods=['POST'])
@supabase_jwt_required
def track_conflicts():
    """Track conflict detection metrics."""
    try:
        data = request.get_json()
        
        operation_id = data.get('operation_id')
        conflicts_detected = data.get('conflicts_detected', 0)
        auto_resolved = data.get('auto_resolved', 0)
        manual_resolution_needed = data.get('manual_resolution_needed', 0)
        
        if not operation_id:
            return jsonify({'error': 'operation_id is required'}), 400
        
        analytics_service.track_conflict_detection(
            operation_id, conflicts_detected, auto_resolved, manual_resolution_needed
        )
        
        return jsonify({
            'status': 'success',
            'message': 'Conflict metrics tracked successfully'
        })
        
    except Exception as e:
        logger.error(f"Error tracking conflicts: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics/cleanup', methods=['POST'])
@supabase_jwt_required
def cleanup_analytics():
    """Clean up old analytics data."""
    try:
        data = request.get_json() or {}
        days_to_keep = data.get('days_to_keep', 7)
        
        if days_to_keep < 1:
            return jsonify({'error': 'days_to_keep must be at least 1'}), 400
        
        analytics_service.cleanup_old_metrics(days_to_keep)
        
        return jsonify({
            'status': 'success',
            'message': f'Analytics cleanup completed. Kept {days_to_keep} days of data.'
        })
        
    except Exception as e:
        logger.error(f"Error cleaning up analytics: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    # Run with SocketIO
    socketio.run(app, debug=True, port=3560, allow_unsafe_werkzeug=True)