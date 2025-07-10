import os
from dotenv import load_dotenv

# Load environment variables FIRST before any other imports
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

from flask import Flask, jsonify, request, send_file, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from services.supabase_auth import (
    auth_service, supabase_jwt_required, supabase_jwt_optional,
    get_current_user_id, get_current_user_email, require_role
)
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
from database import db_manager, init_database, db_session_scope
from repositories import (
    UserRepository, ProductRepository, CategoryRepository,
    IconRepository, JobRepository, SyncHistoryRepository
)
from models import Product, Category, Collection, ProductStatus, IconStatus, JobStatus

# Import API blueprints
from import_api import import_bp
from shopify_sync_api import shopify_sync_bp
from shopify_sync_down_api import shopify_sync_down_bp
from xorosoft_api import xorosoft_bp
from collections_api import collections_bp
from products_batch_api import products_batch_bp
from batch_api import batch_bp
from parallel_sync_api import parallel_sync_bp
from categories_api import categories_bp
from admin_api import admin_bp
from dashboard_stats_api import dashboard_stats_bp
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
CORS(app, resources={
    r"/api/*": {
        "origins": ["http://localhost:3055", "http://localhost:3056", "http://localhost:3560"],
        "supports_credentials": True,
        "allow_headers": ["Content-Type", "Authorization"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    }
})

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
    app.logger.setLevel(logging.INFO)
    app.logger.info('Backend startup')

setup_logging()

# Initialize database on startup (no table creation in production)
try:
    # In production with Supabase, tables should already exist
    create_tables = os.getenv('FLASK_ENV') != 'production'
    init_database(create_tables=create_tables)
    
    # Only seed data in development environments
    if os.getenv('FLASK_ENV') != 'production':
        from database import DatabaseUtils
        DatabaseUtils.seed_initial_data()
        
    # Database initialization logging is handled by DatabaseManager
except Exception as e:
    app.logger.error(f"Failed to initialize database: {e}")
    # Continue anyway for development

# Schemas
login_schema = LoginSchema()
register_schema = RegisterSchema()
script_execution_schema = ScriptExecutionSchema()
job_status_schema = JobStatusSchema()
sync_history_schema = SyncHistorySchema()
script_definition_schema = ScriptDefinitionSchema()
category_icon_schema = CategoryIconSchema()
icon_generation_schema = IconGenerationSchema()

@app.route("/api/auth/login", methods=["POST"])
def login():
    """Handle user login with Supabase."""
    try:
        data = login_schema.load(request.get_json())
    except Exception as e:
        return jsonify({"message": "Invalid request data", "errors": str(e)}), 400
    
    try:
        # Authenticate with Supabase
        result = auth_service.sign_in(data["email"], data["password"])
        
        # Sync user with local database
        with db_session_scope() as session:
            user_repo = UserRepository(session)
            user = user_repo.get_by_email(data["email"])
            
            if not user:
                # Create local user record
                user = user_repo.create_user(
                    email=data["email"],
                    password="",  # No password stored locally
                    first_name=result["user"].get("user_metadata", {}).get("first_name", ""),
                    last_name=result["user"].get("user_metadata", {}).get("last_name", ""),
                    supabase_id=result["user"]["id"]
                )
                session.commit()
            elif not user.supabase_id:
                # Update existing user with Supabase ID
                user.supabase_id = result["user"]["id"]
                session.commit()
            
            app.logger.info(f"User logged in: {user.email}")
            
            return jsonify({
                "access_token": result["session"]["access_token"],
                "refresh_token": result["session"]["refresh_token"],
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "is_admin": user.is_admin
                }
            })
            
    except Exception as e:
        app.logger.warning(f"Failed login attempt for: {data['email']} - {str(e)}")
        return jsonify({"message": "Invalid credentials"}), 401

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

@app.route("/api/images/<path:filename>", methods=["GET"])
def serve_generated_image(filename):
    """Serve generated icon images."""
    try:
        images_path = Path(app.config['IMAGES_STORAGE_PATH']) if 'IMAGES_STORAGE_PATH' in app.config else Path('data/generated_icons')
        return send_from_directory(images_path, filename)
    except Exception as e:
        app.logger.error(f"Error serving image: {e}")
        return jsonify({"message": "Image not found"}), 404

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

if __name__ == "__main__":
    # Run with SocketIO
    socketio.run(app, debug=True, port=3560, allow_unsafe_werkzeug=True)