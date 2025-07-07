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
from models import Product, Category, ProductStatus, IconStatus, JobStatus

# Import API blueprints
from import_api import import_bp
from shopify_sync_api import shopify_sync_bp
from xorosoft_api import xorosoft_bp
from collections_api import collections_bp
from products_batch_api import products_batch_bp

# Import services
from services.icon_category_service import IconCategoryService
from services.shopify_icon_sync_service import ShopifyIconSyncService
from services.shopify_product_sync_service import ShopifyProductSyncService

# Environment variables already loaded at the top

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(config[os.getenv('FLASK_ENV', 'development')])

# Initialize CORS
CORS(app, resources={
    r"/api/*": {
        "origins": ["http://localhost:3055", "http://localhost:3056"],
        "supports_credentials": True
    }
})

# Initialize JWT
jwt = JWTManager(app)

# Initialize SocketIO (without Redis for development)
socketio = SocketIO(
    app,
    cors_allowed_origins=["http://localhost:3055", "http://localhost:3056"],
    async_mode='threading'
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
    supabase_user_id = get_current_user_id()
    if supabase_user_id:
        with db_session_scope() as session:
            user_repo = UserRepository(session)
            user = user_repo.get_by_supabase_id(supabase_user_id)
            if user:
                return user.id
            # For migration period, return fallback
            app.logger.warning(f"No local user found for Supabase ID: {supabase_user_id}")
            return 1
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

# Initialize database on startup
try:
    init_database(create_tables=True)
    # Seed initial data including default dev user
    from database import DatabaseUtils
    DatabaseUtils.seed_initial_data()
    app.logger.info("Database initialized successfully")
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
            
            # Update last login
            user_repo.update_last_login(user.id)
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

@app.route("/api/auth/register", methods=["POST"])
def register():
    """Handle user registration with Supabase."""
    try:
        data = register_schema.load(request.get_json())
    except Exception as e:
        return jsonify({"message": "Invalid request data", "errors": str(e)}), 400
    
    try:
        # Register with Supabase
        metadata = {
            "first_name": data["first_name"],
            "last_name": data["last_name"]
        }
        result = auth_service.sign_up(data["email"], data["password"], metadata)
        
        # Create local user record
        with db_session_scope() as session:
            user_repo = UserRepository(session)
            
            # Check if user already exists locally
            existing_user = user_repo.get_by_email(data["email"])
            if existing_user:
                return jsonify({"message": "User with this email already exists"}), 409
            
            # Create new user
            user = user_repo.create_user(
                email=data["email"],
                password="",  # No password stored locally
                first_name=data["first_name"],
                last_name=data["last_name"],
                is_admin=False,
                supabase_id=result["user"]["id"]
            )
            session.commit()
            
            app.logger.info(f"New user registered: {user.email}")
            
            return jsonify({
                "message": "User registered successfully",
                "access_token": result["session"]["access_token"] if result.get("session") else None,
                "refresh_token": result["session"]["refresh_token"] if result.get("session") else None,
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "is_admin": user.is_admin
                }
            }), 201
            
    except Exception as e:
        app.logger.error(f"Registration failed: {str(e)}")
        return jsonify({"message": "Registration failed"}), 500

@app.route("/api/auth/me", methods=["GET"])
@supabase_jwt_required
def get_current_user():
    """Get current user profile."""
    try:
        user_id = get_user_id()
        with db_session_scope() as session:
            user_repo = UserRepository(session)
            user = user_repo.get(user_id)
            
            if not user or not user.is_active:
                return jsonify({"message": "User not found"}), 404
            
            return jsonify({
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "is_admin": user.is_admin,
                    "created_at": user.created_at.isoformat() if user.created_at else None,
                    "last_login": user.last_login.isoformat() if user.last_login else None
                }
            })
            
    except (ValueError, SQLAlchemyError) as e:
        app.logger.error(f"Error getting current user: {e}")
        return jsonify({"message": "Failed to get user profile"}), 500

@app.route("/api/auth/refresh", methods=["POST"])
def refresh_token():
    """Refresh access token using refresh token."""
    try:
        data = request.get_json()
        refresh_token = data.get("refresh_token")
        
        if not refresh_token:
            return jsonify({"message": "Refresh token required"}), 400
        
        result = auth_service.refresh_token(refresh_token)
        
        if result:
            return jsonify({
                "access_token": result["access_token"],
                "refresh_token": result["refresh_token"]
            })
        else:
            return jsonify({"message": "Invalid refresh token"}), 401
            
    except Exception as e:
        app.logger.error(f"Token refresh error: {str(e)}")
        return jsonify({"message": "Token refresh failed"}), 500

@app.route("/api/auth/logout", methods=["POST"])
@supabase_jwt_required
def logout():
    """Handle user logout (client-side token removal)."""
    # Note: JWT tokens are stateless, so logout is handled client-side
    # In production, you might want to implement a token blacklist
    user_id = get_jwt_identity()
    app.logger.info(f"User logged out: {user_id}")
    return jsonify({"message": "Logged out successfully"})

@app.route("/api/auth/debug", methods=["GET"])
@supabase_jwt_required
def debug_auth():
    """Debug authentication to see what's happening."""
    try:
        user_id_str = get_jwt_identity()
        app.logger.info(f"JWT Identity: {user_id_str}")
        
        user_id = int(user_id_str)
        app.logger.info(f"Parsed user_id: {user_id}")
        
        with db_session_scope() as session:
            user_repo = UserRepository(session)
            app.logger.info(f"UserRepository created")
            
            user = user_repo.get(user_id)
            app.logger.info(f"User query result: {user}")
            
            if user:
                return jsonify({
                    "success": True,
                    "user_id": user_id,
                    "user_email": user.email,
                    "user_active": user.is_active
                })
            else:
                return jsonify({
                    "success": False,
                    "user_id": user_id,
                    "message": "User not found in database"
                })
                
    except Exception as e:
        app.logger.error(f"Debug auth error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e),
            "user_id_str": get_jwt_identity() if 'get_jwt_identity' in locals() else "N/A"
        })

@app.route("/api/scripts", methods=["GET"])
@supabase_jwt_required
def get_scripts():
    """Get available scripts organized by category."""
    scripts = get_all_scripts()
    return jsonify(scripts)

@app.route("/api/scripts/<script_name>", methods=["GET"])
@supabase_jwt_required
def get_script_details(script_name):
    """Get details for a specific script."""
    script_info = get_script_info(script_name)
    if not script_info:
        return jsonify({"message": "Script not found"}), 404
    
    return jsonify({
        "name": script_name,
        **script_info
    })

@app.route("/api/scripts/execute", methods=["POST"])
@supabase_jwt_required
def execute_script():
    """Execute a script with given parameters."""
    try:
        data = script_execution_schema.load(request.get_json())
    except Exception as e:
        return jsonify({"message": "Invalid request data", "errors": str(e)}), 400
    
    # Validate script parameters
    valid, message = validate_script_parameters(data['script_name'], data['parameters'])
    if not valid:
        return jsonify({"message": message}), 400
    
    # Create job
    user_id = get_jwt_identity()
    
    # Create job in database
    with db_session_scope() as session:
        job_repo = JobRepository(session)
        
        # Create job record
        job = job_repo.create_job(
            script_name=data['script_name'],
            user_id=int(user_id),
            parameters=data['parameters'],
            display_name=get_script_info(data['script_name']).get('display_name')
        )
        session.commit()
        
        job_id = job.job_uuid
        
        # Create sync history record if this is a sync job
        if 'sync' in data['script_name']:
            sync_repo = SyncHistoryRepository(session)
            sync_record = sync_repo.create_sync_record(
                sync_type=data['script_name'],
                user_id=int(user_id),
                job_id=job.id
            )
            session.commit()
        
        if job_manager:
            # Execute job asynchronously with job manager
            job_manager.execute_job(job_id, socketio)
        else:
            # Simple execution without job manager
            # Update job to running state
            job_repo.start_job(job.id)
            session.commit()
        
        app.logger.info(f"Job created: {job_id} for script: {data['script_name']} by user: {user_id}")
        
        return jsonify({
            "job_id": job_id,
            "message": "Job created successfully"
        }), 201

@app.route("/api/jobs/<job_id>", methods=["GET"])
@supabase_jwt_required
def get_job_status(job_id):
    """Get status of a specific job."""
    try:
        with db_session_scope() as session:
            job_repo = JobRepository(session)
            
            # Try to get by ID first, then by UUID
            try:
                job_id_int = int(job_id)
                job = job_repo.get(job_id_int)
            except ValueError:
                job = job_repo.get_by_uuid(job_id)
            
            if not job:
                return jsonify({"message": "Job not found"}), 404
            
            return jsonify({
                "job_id": job.job_uuid,
                "status": job.status,
                "script_name": job.script_name,
                "display_name": job.display_name,
                "description": job.description,
                "progress": job.progress,
                "current_stage": job.current_stage,
                "created_at": job.created_at.isoformat(),
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "duration": job.actual_duration,
                "error_message": job.error_message,
                "result": job.result
            })
            
    except Exception as e:
        app.logger.error(f"Error getting job {job_id}: {e}")
        return jsonify({"message": "Failed to retrieve job status"}), 500

@app.route("/api/jobs/<job_id>/cancel", methods=["POST"])
@supabase_jwt_required
def cancel_job(job_id):
    """Cancel a running job."""
    try:
        with db_session_scope() as session:
            job_repo = JobRepository(session)
            
            # Try to get by ID first, then by UUID
            try:
                job_id_int = int(job_id)
                job = job_repo.get(job_id_int)
            except ValueError:
                job = job_repo.get_by_uuid(job_id)
            
            if not job:
                return jsonify({"message": "Job not found"}), 404
            
            # Cancel the job
            cancelled_job = job_repo.cancel_job(job.id)
            if cancelled_job:
                session.commit()
                return jsonify({"message": "Job cancelled successfully"})
            else:
                return jsonify({"message": "Job cannot be cancelled"}), 400
                
    except Exception as e:
        app.logger.error(f"Error cancelling job {job_id}: {e}")
        return jsonify({"message": "Failed to cancel job"}), 500

@app.route("/api/jobs/<job_id>/logs", methods=["GET"])
@supabase_jwt_required
def get_job_logs(job_id):
    """Get log file for a job (mock for development)."""
    return jsonify({"message": "Log file not found"}), 404

@app.route("/api/jobs", methods=["GET"])
@supabase_jwt_required
def get_user_jobs():
    """Get jobs for the current user."""
    try:
        user_id = get_user_id()
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        status = request.args.get('status')
        
        with db_session_scope() as session:
            job_repo = JobRepository(session)
            
            # Get user's jobs
            jobs = job_repo.get_user_jobs(user_id, limit=per_page * page, status=status)
            
            # Manual pagination
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            page_jobs = jobs[start_idx:end_idx]
            
            # Serialize jobs
            job_list = []
            for job in page_jobs:
                job_list.append({
                    'id': job.id,
                    'job_uuid': job.job_uuid,
                    'script_name': job.script_name,
                    'display_name': job.display_name,
                    'status': job.status,
                    'progress': job.progress,
                    'created_at': job.created_at.isoformat(),
                    'started_at': job.started_at.isoformat() if job.started_at else None,
                    'completed_at': job.completed_at.isoformat() if job.completed_at else None,
                    'duration': job.actual_duration,
                    'error_message': job.error_message
                })
            
            return jsonify({
                'jobs': job_list,
                'pagination': {
                    'total': len(jobs),
                    'page': page,
                    'per_page': per_page,
                    'total_pages': (len(jobs) + per_page - 1) // per_page,
                    'has_prev': page > 1,
                    'has_next': end_idx < len(jobs)
                }
            })
            
    except Exception as e:
        app.logger.error(f"Error getting user jobs: {e}")
        return jsonify({"message": "Failed to retrieve jobs"}), 500

@app.route("/api/sync/trigger", methods=["POST"])
@supabase_jwt_required
def trigger_sync():
    """Trigger full sync workflow (backward compatibility)."""
    import uuid
    from datetime import datetime
    import threading
    
    user_id = get_jwt_identity()
    job_id = str(uuid.uuid4())
    
    app.logger.info(f"Sync triggered by user: {user_id}")
    
    # Start async sync process with WebSocket updates
    def run_sync_with_updates():
        try:
            # Emit start event
            websocket_service.emit_operation_start(
                operation_id=job_id,
                operation_type='sync',
                description='Full product synchronization',
                total_steps=5
            )
            
            # Simulate sync steps
            steps = [
                (1, "Connecting to FTP server..."),
                (2, "Downloading product data..."),
                (3, "Processing and filtering products..."),
                (4, "Uploading to Shopify..."),
                (5, "Sync complete!")
            ]
            
            for step, message in steps:
                time.sleep(2)  # Simulate work
                websocket_service.emit_operation_progress(
                    operation_id=job_id,
                    current_step=step,
                    message=message
                )
                
                # Emit some logs
                websocket_service.emit_operation_log(
                    operation_id=job_id,
                    level='info',
                    message=f"Step {step}: {message}",
                    source='sync_engine'
                )
            
            # Emit completion
            websocket_service.emit_operation_complete(
                operation_id=job_id,
                status='success',
                result={
                    'products_synced': 150,
                    'products_updated': 45,
                    'products_failed': 2
                }
            )
            
            # Store in sync history
            with db_session_scope() as session:
                sync_repo = SyncHistoryRepository(session)
                sync_repo.create(
                    sync_type='full_sync',
                    source='manual_trigger',
                    status='success',
                    message='Sync completed successfully',
                    items_processed=197,
                    items_successful=195,
                    items_failed=2,
                    duration=10.0,
                    user_id=get_user_id()
                )
                
        except Exception as e:
            app.logger.error(f"Sync error: {str(e)}")
            websocket_service.emit_operation_complete(
                operation_id=job_id,
                status='error',
                error=str(e)
            )
    
    # Start sync in background thread
    thread = threading.Thread(target=run_sync_with_updates)
    thread.start()
    
    return jsonify({
        "message": "Sync triggered successfully",
        "job_id": job_id
    })

@app.route("/api/sync/history", methods=["GET"])
@supabase_jwt_required
def get_sync_history():
    """Get sync history."""
    try:
        limit = int(request.args.get('limit', 20))
        sync_type = request.args.get('type')
        
        with db_session_scope() as session:
            sync_repo = SyncHistoryRepository(session)
            syncs = sync_repo.get_recent_syncs(sync_type=sync_type, days=30, limit=limit)
            
            history = []
            for sync in syncs:
                history.append({
                    "id": sync.id,
                    "timestamp": sync.started_at.isoformat(),
                    "status": sync.status,
                    "type": sync.sync_type,
                    "message": sync.message or sync.error_message,
                    "duration": sync.duration,
                    "items_processed": sync.items_processed,
                    "items_successful": sync.items_successful,
                    "items_failed": sync.items_failed
                })
            
            return jsonify(history)
            
    except Exception as e:
        app.logger.error(f"Error getting sync history: {e}")
        
        # Check if it's a database corruption error
        if "database disk image is malformed" in str(e):
            return jsonify({
                "message": "Database corruption detected. Please contact administrator.",
                "error": "DATABASE_CORRUPTED"
            }), 503
        
        return jsonify({"message": "Failed to retrieve sync history"}), 500

# WebSocket event handlers
@socketio.on('connect')
def handle_connect(auth=None):
    """Handle client connection with optional Supabase authentication."""
    app.logger.info(f"WebSocket connected: {request.sid}")
    
    # Try to authenticate if auth data provided
    user_id = None
    user_email = None
    
    if auth and isinstance(auth, dict):
        token = auth.get('token')
        if token:
            is_valid, user_data = auth_service.verify_token(token)
            if is_valid and user_data:
                # Get user from local database
                with db_session_scope() as session:
                    user_repo = UserRepository(session)
                    user = user_repo.get_by_supabase_id(user_data.get('id'))
                    if user:
                        user_id = user.id
                        user_email = user.email
                    app.logger.info(f"WebSocket authenticated for user: {user_email}")
    
    # Register client with WebSocket service
    websocket_service.register_client(request.sid, user_id)
    emit('connected', {
        'message': 'Connected to server',
        'sid': request.sid,
        'authenticated': user_id is not None,
        'user_email': user_email
    })

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    app.logger.info(f"WebSocket disconnected: {request.sid}")
    websocket_service.unregister_client(request.sid)

@socketio.on('execute')
def handle_execute(data):
    """Execute a script with the provided parameters"""
    script_id = data.get('scriptId')
    parameters = data.get('parameters', {})
    
    app.logger.info(f"Executing script: {script_id} with parameters: {parameters}")
    
    # For now, just emit a simple response
    emit('status', {
        'type': 'status',
        'data': {'status': 'starting', 'script': script_id},
        'timestamp': time.time()
    })
    
    # Simulate some execution
    import time
    import threading
    
    def simulate_execution():
        time.sleep(1)
        emit('log', {
            'type': 'log',
            'data': {
                'level': 'info',
                'message': f'Starting {script_id}...',
                'source': script_id
            },
            'timestamp': time.time()
        })
        
        time.sleep(2)
        emit('complete', {
            'type': 'complete',
            'data': {'status': 'success', 'script': script_id},
            'timestamp': time.time()
        })
    
    thread = threading.Thread(target=simulate_execution)
    thread.start()

# Error tracking endpoints
@app.route("/api/errors/summary", methods=["GET"])
@supabase_jwt_required
def get_error_summary():
    """Get error tracking summary (admin only)."""
    user_id = get_user_id()
    
    # Check if user is admin
    with db_session_scope() as session:
        user_repo = UserRepository(session)
        user = user_repo.get_by_id(user_id)
        
        if not user or not user.is_admin:
            return jsonify({"message": "Admin access required"}), 403
            
    summary = error_tracker.get_error_summary()
    return jsonify(summary)

@app.route("/api/errors/recent", methods=["GET"])
@supabase_jwt_required
def get_recent_errors():
    """Get recent errors (admin only)."""
    user_id = get_user_id()
    limit = int(request.args.get('limit', 20))
    
    # Check if user is admin
    with db_session_scope() as session:
        user_repo = UserRepository(session)
        user = user_repo.get_by_id(user_id)
        
        if not user or not user.is_admin:
            return jsonify({"message": "Admin access required"}), 403
            
    errors = error_tracker.get_recent_errors(limit=limit)
    return jsonify({"errors": errors})

# Product API Endpoints
@app.route("/api/products", methods=["GET"])
@supabase_jwt_required
def get_products():
    """Get products with pagination and filtering."""
    try:
        # Parse query parameters
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        
        # Parse filters
        filters = {}
        if request.args.get('category_id'):
            filters['category_id'] = int(request.args.get('category_id'))
        if request.args.get('status'):
            filters['status'] = request.args.get('status')
        if request.args.get('brand'):
            filters['brand'] = request.args.get('brand')
        if request.args.get('synced'):
            filters['synced'] = request.args.get('synced').lower() == 'true'
        
        with db_session_scope() as session:
            product_repo = ProductRepository(session)
            
            # Advanced search if query provided
            if request.args.get('q'):
                result = product_repo.search_advanced(
                    filters={'query': request.args.get('q'), **filters},
                    sort_by=request.args.get('sort_by', 'created_at'),
                    sort_order=request.args.get('sort_order', 'desc'),
                    page=page,
                    per_page=per_page
                )
            else:
                result = product_repo.paginate(page=page, per_page=per_page, filters=filters)
            
            # Serialize products
            products = []
            for product in result['items']:
                products.append({
                    'id': product.id,
                    'sku': product.sku,
                    'name': product.name,
                    'description': product.description,
                    'price': product.price,
                    'brand': product.brand,
                    'manufacturer': product.manufacturer,
                    'category_id': product.category_id,
                    'status': product.status,
                    'inventory_quantity': product.inventory_quantity,
                    'featured_image_url': product.featured_image_url,
                    'shopify_product_id': product.shopify_product_id,
                    'shopify_synced_at': product.shopify_synced_at.isoformat() if product.shopify_synced_at else None,
                    'created_at': product.created_at.isoformat(),
                    'updated_at': product.updated_at.isoformat()
                })
            
            return jsonify({
                'products': products,
                'pagination': {
                    'total': result['total'],
                    'page': result['page'],
                    'per_page': result['per_page'],
                    'total_pages': result['total_pages'],
                    'has_prev': result['has_prev'],
                    'has_next': result['has_next']
                }
            })
            
    except Exception as e:
        app.logger.error(f"Error getting products: {e}")
        return jsonify({"message": "Failed to retrieve products"}), 500

@app.route("/api/products/<int:product_id>", methods=["GET"])
@supabase_jwt_required
def get_product(product_id):
    """Get a single product by ID."""
    try:
        with db_session_scope() as session:
            product_repo = ProductRepository(session)
            product = product_repo.get_with_category(product_id)
            
            if not product:
                return jsonify({"message": "Product not found"}), 404
            
            return jsonify({
                'id': product.id,
                'sku': product.sku,
                'name': product.name,
                'description': product.description,
                'short_description': product.short_description,
                'price': product.price,
                'compare_at_price': product.compare_at_price,
                'cost_price': product.cost_price,
                'brand': product.brand,
                'manufacturer': product.manufacturer,
                'manufacturer_part_number': product.manufacturer_part_number,
                'upc': product.upc,
                'weight': product.weight,
                'weight_unit': product.weight_unit,
                'dimensions': {
                    'length': product.length,
                    'width': product.width,
                    'height': product.height,
                    'unit': product.dimension_unit
                },
                'inventory': {
                    'quantity': product.inventory_quantity,
                    'track': product.track_inventory,
                    'continue_when_out_of_stock': product.continue_selling_when_out_of_stock
                },
                'seo': {
                    'title': product.seo_title,
                    'description': product.seo_description
                },
                'status': product.status,
                'category': {
                    'id': product.category.id,
                    'name': product.category.name,
                    'slug': product.category.slug
                } if product.category else None,
                'shopify': {
                    'product_id': product.shopify_product_id,
                    'variant_id': product.shopify_variant_id,
                    'handle': product.shopify_handle,
                    'synced_at': product.shopify_synced_at.isoformat() if product.shopify_synced_at else None,
                    'sync_status': product.shopify_sync_status
                },
                'images': {
                    'featured': product.featured_image_url,
                    'additional': product.additional_images or []
                },
                'metafields': product.metafields,
                'custom_attributes': product.custom_attributes,
                'created_at': product.created_at.isoformat(),
                'updated_at': product.updated_at.isoformat()
            })
            
    except Exception as e:
        app.logger.error(f"Error getting product {product_id}: {e}")
        return jsonify({"message": "Failed to retrieve product"}), 500

@app.route("/api/products/search", methods=["POST"])
@supabase_jwt_required
def search_products():
    """Search products by various criteria."""
    try:
        data = request.get_json()
        query = data.get('query', '')
        limit = data.get('limit', 50)
        
        with db_session_scope() as session:
            product_repo = ProductRepository(session)
            products = product_repo.search(query, limit=limit)
            
            results = []
            for product in products:
                results.append({
                    'id': product.id,
                    'sku': product.sku,
                    'name': product.name,
                    'brand': product.brand,
                    'price': product.price,
                    'category_id': product.category_id,
                    'status': product.status,
                    'featured_image_url': product.featured_image_url
                })
            
            return jsonify({
                'results': results,
                'count': len(results)
            })
            
    except Exception as e:
        app.logger.error(f"Error searching products: {e}")
        return jsonify({"message": "Search failed"}), 500

# Category API Endpoints
@app.route("/api/categories", methods=["GET"])
@supabase_jwt_required
def get_categories():
    """Get all categories or category tree."""
    try:
        tree_view = request.args.get('tree', 'false').lower() == 'true'
        
        with db_session_scope() as session:
            category_repo = CategoryRepository(session)
            
            if tree_view:
                categories = category_repo.get_tree()
            else:
                categories = category_repo.get_all()
                categories = [{
                    'id': cat.id,
                    'name': cat.name,
                    'slug': cat.slug,
                    'description': cat.description,
                    'parent_id': cat.parent_id,
                    'level': cat.level,
                    'path': cat.path,
                    'sort_order': cat.sort_order,
                    'shopify_collection_id': cat.shopify_collection_id,
                    'shopify_handle': cat.shopify_handle,
                    'shopify_synced_at': cat.shopify_synced_at.isoformat() if cat.shopify_synced_at else None,
                    'created_at': cat.created_at.isoformat(),
                    'updated_at': cat.updated_at.isoformat()
                } for cat in categories]
            
            return jsonify({
                'categories': categories,
                'total': len(categories)
            })
            
    except Exception as e:
        app.logger.error(f"Error getting categories: {e}")
        return jsonify({"message": "Failed to retrieve categories"}), 500

@app.route("/api/categories/<int:category_id>", methods=["GET"])
@supabase_jwt_required
def get_category(category_id):
    """Get a single category with optional products."""
    try:
        include_products = request.args.get('include_products', 'false').lower() == 'true'
        product_limit = int(request.args.get('product_limit', 20))
        
        with db_session_scope() as session:
            category_repo = CategoryRepository(session)
            
            if include_products:
                result = category_repo.get_with_products(category_id, limit=product_limit)
                if not result:
                    return jsonify({"message": "Category not found"}), 404
                
                category = result['category']
                products = [{
                    'id': p.id,
                    'sku': p.sku,
                    'name': p.name,
                    'price': p.price,
                    'status': p.status,
                    'featured_image_url': p.featured_image_url
                } for p in result['products']]
                
                response = {
                    'id': category.id,
                    'name': category.name,
                    'slug': category.slug,
                    'description': category.description,
                    'parent_id': category.parent_id,
                    'level': category.level,
                    'products': products,
                    'product_count': result['product_count']
                }
            else:
                category = category_repo.get(category_id)
                if not category:
                    return jsonify({"message": "Category not found"}), 404
                
                response = {
                    'id': category.id,
                    'name': category.name,
                    'slug': category.slug,
                    'description': category.description,
                    'parent_id': category.parent_id,
                    'level': category.level,
                    'path': category.path,
                    'sort_order': category.sort_order,
                    'shopify_collection_id': category.shopify_collection_id,
                    'shopify_handle': category.shopify_handle,
                    'created_at': category.created_at.isoformat(),
                    'updated_at': category.updated_at.isoformat()
                }
            
            return jsonify(response)
            
    except Exception as e:
        app.logger.error(f"Error getting category {category_id}: {e}")
        return jsonify({"message": "Failed to retrieve category"}), 500

@app.route("/api/categories/<int:category_id>/products", methods=["GET"])
@supabase_jwt_required
def get_category_products(category_id):
    """Get products in a category with pagination."""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        status = request.args.get('status')
        
        with db_session_scope() as session:
            category_repo = CategoryRepository(session)
            product_repo = ProductRepository(session)
            
            # Check if category exists
            category = category_repo.get(category_id)
            if not category:
                return jsonify({"message": "Category not found"}), 404
            
            # Get paginated products
            offset = (page - 1) * per_page
            products = product_repo.get_by_category(
                category_id, 
                status=status, 
                limit=per_page, 
                offset=offset
            )
            
            total = product_repo.count({'category_id': category_id, 'status': status} if status else {'category_id': category_id})
            
            # Serialize products
            product_list = [{
                'id': p.id,
                'sku': p.sku,
                'name': p.name,
                'price': p.price,
                'brand': p.brand,
                'status': p.status,
                'inventory_quantity': p.inventory_quantity,
                'featured_image_url': p.featured_image_url,
                'shopify_product_id': p.shopify_product_id
            } for p in products]
            
            return jsonify({
                'category': {
                    'id': category.id,
                    'name': category.name,
                    'slug': category.slug
                },
                'products': product_list,
                'pagination': {
                    'total': total,
                    'page': page,
                    'per_page': per_page,
                    'total_pages': (total + per_page - 1) // per_page,
                    'has_prev': page > 1,
                    'has_next': page < (total + per_page - 1) // per_page
                }
            })
            
    except Exception as e:
        app.logger.error(f"Error getting products for category {category_id}: {e}")
        return jsonify({"message": "Failed to retrieve category products"}), 500

# Sync Logs API Endpoints
@app.route("/api/sync-logs", methods=["GET"])
@supabase_jwt_required
def get_sync_logs():
    """Get sync history with filtering."""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        sync_type = request.args.get('type')
        status = request.args.get('status')
        days = int(request.args.get('days', 30))
        
        with db_session_scope() as session:
            sync_repo = SyncHistoryRepository(session)
            
            # Get filtered syncs
            syncs = sync_repo.get_recent_syncs(sync_type=sync_type, days=days, limit=per_page * page)
            
            # Manual pagination
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            page_syncs = syncs[start_idx:end_idx]
            
            # Serialize sync records
            sync_list = []
            for sync in page_syncs:
                sync_list.append({
                    'id': sync.id,
                    'type': sync.sync_type,
                    'source': sync.sync_source,
                    'target': sync.sync_target,
                    'status': sync.status,
                    'started_at': sync.started_at.isoformat(),
                    'completed_at': sync.completed_at.isoformat() if sync.completed_at else None,
                    'duration': sync.duration,
                    'items': {
                        'total': sync.total_items,
                        'processed': sync.items_processed,
                        'successful': sync.items_successful,
                        'failed': sync.items_failed,
                        'skipped': sync.items_skipped
                    },
                    'counts': {
                        'products': sync.products_synced,
                        'categories': sync.categories_synced,
                        'icons': sync.icons_synced
                    },
                    'message': sync.message,
                    'error_message': sync.error_message,
                    'warnings': sync.warnings,
                    'errors': sync.errors
                })
            
            return jsonify({
                'sync_logs': sync_list,
                'pagination': {
                    'total': len(syncs),
                    'page': page,
                    'per_page': per_page,
                    'total_pages': (len(syncs) + per_page - 1) // per_page,
                    'has_prev': page > 1,
                    'has_next': end_idx < len(syncs)
                }
            })
            
    except Exception as e:
        app.logger.error(f"Error getting sync logs: {e}")
        return jsonify({"message": "Failed to retrieve sync logs"}), 500

# Error handlers
@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({'message': 'Resource not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    app.logger.error(f"Internal error: {error}")
    return jsonify({'message': 'Internal server error'}), 500

# Icon Generation API Endpoints
@app.route("/api/icons/stats", methods=["GET"])
@supabase_jwt_required
def get_icon_stats():
    """Get icon generation statistics."""
    try:
        with db_session_scope() as session:
            icon_repo = IconRepository(session)
            stats = icon_repo.get_statistics()
            return jsonify(stats)
    except Exception as e:
        app.logger.error(f"Error getting icon stats: {e}")
        return jsonify({"message": "Failed to retrieve statistics"}), 500

@app.route("/api/icons/categories/<int:category_id>", methods=["GET"])
@supabase_jwt_required
def get_category_icons(category_id):
    """Get all icons for a category."""
    try:
        with db_session_scope() as session:
            icon_repo = IconRepository(session)
            icons = icon_repo.get_by_category(category_id)
            
            icon_list = []
            for icon in icons:
                icon_list.append({
                    'id': icon.id,
                    'filename': icon.filename,
                    'file_path': icon.file_path,
                    'width': icon.width,
                    'height': icon.height,
                    'format': icon.format,
                    'style': icon.style,
                    'color': icon.color,
                    'status': icon.status,
                    'is_active': icon.is_active,
                    'shopify_image_url': icon.shopify_image_url,
                    'shopify_synced_at': icon.shopify_synced_at.isoformat() if icon.shopify_synced_at else None,
                    'created_at': icon.created_at.isoformat()
                })
            
            return jsonify({
                'category_id': category_id,
                'icons': icon_list,
                'count': len(icon_list)
            })
    except Exception as e:
        app.logger.error(f"Error getting icons for category {category_id}: {e}")
        return jsonify({"message": "Failed to retrieve category icons"}), 500

@app.route("/api/icons/categories/<int:category_id>/icon", methods=["GET"])
@supabase_jwt_required
def serve_category_icon(category_id):
    """Serve category icon file."""
    try:
        icon_path = icon_storage.get_icon_path(category_id)
        if not icon_path or not os.path.exists(icon_path):
            return jsonify({"message": "Icon not found"}), 404
        return send_file(icon_path, mimetype='image/png')
    except Exception as e:
        app.logger.error(f"Error serving icon for category {category_id}: {e}")
        return jsonify({"message": "Failed to serve icon"}), 500

@app.route("/api/icons/generate", methods=["POST"])
@supabase_jwt_required
def generate_icon():
    """Generate icon for a single category."""
    try:
        data = icon_generation_schema.load(request.get_json())
    except Exception as e:
        return jsonify({"message": "Invalid request data", "errors": str(e)}), 400
    
    try:
        category_id = data['category_id']
        category_name = data['category_name']
        user_id = get_user_id()
        
        with db_session_scope() as session:
            icon_repo = IconRepository(session)
            category_repo = CategoryRepository(session)
            
            # Verify category exists
            category = category_repo.get(category_id)
            if not category:
                return jsonify({"message": "Category not found"}), 404
            
            # Create icon record first
            icon = icon_repo.create_icon({
                'category_id': category_id,
                'filename': f"category_{category_id}_icon.png",
                'file_path': "",  # Will be updated after generation
                'prompt': f"Icon for {category_name} category",
                'style': data.get('style', 'modern'),
                'color': data.get('color', '#3B82F6'),
                'background': data.get('background', 'transparent'),
                'model': data.get('model', 'gpt-image-1'),
                'status': IconStatus.GENERATING.value,
                'created_by': user_id
            })
            session.commit()
            
            # Generate icon
            result = icon_generator.generate_category_icon(
                category_id=category_id,
                category_name=category_name,
                style=data.get('style', 'modern'),
                color=data.get('color', '#3B82F6'),
                size=data.get('size', 128),
                background=data.get('background', 'transparent')
            )
            
            if result['success']:
                # Update icon record with file details
                icon_repo.update_icon(
                    icon.id,
                    {
                        'file_path': result['file_path'],
                        'filename': os.path.basename(result['file_path']),
                        'status': IconStatus.ACTIVE.value,
                        'generation_time': result.get('generation_time'),
                        'width': result.get('width', 128),
                        'height': result.get('height', 128),
                        'format': 'PNG'
                    }
                )
                
                # TODO: Deactivate other icons for this category
                # icon_repo.deactivate_category_icons(category_id, except_icon_id=icon.id)
                
                session.commit()
                
                app.logger.info(f"Icon generated for category {category_id} by user {user_id}")
                return jsonify({
                    "message": "Icon generated successfully",
                    "icon": {
                        'id': icon.id,
                        'category_id': icon.category_id,
                        'filename': icon.filename,
                        'file_path': icon.file_path,
                        'status': icon.status,
                        'style': icon.style,
                        'color': icon.color,
                        'created_at': icon.created_at.isoformat()
                    }
                }), 201
            else:
                # Update icon status to failed
                icon_repo.update_icon(icon.id, {
                    'status': IconStatus.FAILED.value,
                    'meta_data': {'error': result.get('error')}
                })
                session.commit()
                
                return jsonify({
                    "message": "Icon generation failed",
                    "error": result.get('error')
                }), 500
                
    except Exception as e:
        app.logger.error(f"Error generating icon: {e}")
        return jsonify({"message": "Failed to generate icon"}), 500

@app.route("/api/icons/generate/batch", methods=["POST"])
@supabase_jwt_required
def generate_icons_batch():
    """Generate icons for multiple categories."""
    try:
        data = request.get_json()
        categories = data.get('categories', [])
        options = data.get('options', {})
        
        if not categories:
            return jsonify({"message": "No categories provided"}), 400
        
        user_id = get_user_id()
        
        # Create job in database
        with db_session_scope() as session:
            job_repo = JobRepository(session)
            
            # Create batch job record
            job = job_repo.create_job(
                script_name='icon_generation_batch',
                user_id=user_id,
                parameters={
                    'categories': categories,
                    'options': options
                },
                display_name='Batch Icon Generation',
                description=f'Generate icons for {len(categories)} categories'
            )
            session.commit()
            
            job_uuid = job.job_uuid
            
            if job_manager:
                # Execute job asynchronously
                job_manager.execute_job(job_uuid, socketio)
            else:
                # Create batch ID for tracking
                import uuid
                batch_id = str(uuid.uuid4())
                
                # Start job
                job_repo.start_job(job.id)
                session.commit()
                
                # Generate icons synchronously
                icon_repo = IconRepository(session)
                results = []
                
                for idx, category in enumerate(categories):
                    try:
                        # Create icon record
                        icon = icon_repo.create_icon({
                            'category_id': category['id'],
                            'filename': f"category_{category['id']}_icon.png",
                            'file_path': "",
                            'prompt': f"Icon for {category['name']} category",
                            'style': options.get('style', 'modern'),
                            'color': options.get('color', '#3B82F6'),
                            'background': options.get('background', 'transparent'),
                            'model': options.get('model', 'gpt-image-1'),
                            'status': IconStatus.GENERATING.value,
                            'generation_batch_id': batch_id,
                            'created_by': user_id
                        })
                        
                        # Generate icon
                        result = icon_generator.generate_category_icon(
                            category_id=category['id'],
                            category_name=category['name'],
                            style=options.get('style', 'modern'),
                            color=options.get('color', '#3B82F6')
                        )
                        
                        if result['success']:
                            icon_repo.update_icon(
                                icon.id,
                                {
                                    'file_path': result['file_path'],
                                    'filename': os.path.basename(result['file_path']),
                                    'status': IconStatus.ACTIVE.value
                                }
                            )
                            results.append({'category_id': category['id'], 'success': True})
                        else:
                            icon_repo.update_icon(icon.id, {
                                'status': IconStatus.FAILED.value,
                                'meta_data': {'error': result.get('error')}
                            })
                            results.append({'category_id': category['id'], 'error': result.get('error')})
                        
                        # Update job progress
                        progress = int((idx + 1) / len(categories) * 100)
                        job_repo.update_progress(job.id, progress)
                        
                    except Exception as e:
                        results.append({'category_id': category['id'], 'error': str(e)})
                
                # Complete job
                job_repo.complete_job(job.id, result={'results': results})
                session.commit()
            
            app.logger.info(f"Batch icon generation job {job_uuid} created for {len(categories)} categories by user {user_id}")
            
            return jsonify({
                "job_id": job_uuid,
                "message": f"Batch icon generation started for {len(categories)} categories"
            }), 201
            
    except Exception as e:
        app.logger.error(f"Error in batch icon generation: {e}")
        return jsonify({"message": "Failed to start batch icon generation"}), 500

@app.route("/api/icons/categories/<int:category_id>", methods=["DELETE"])
@supabase_jwt_required
def delete_category_icon(category_id):
    """Delete category icon."""
    try:
        success = icon_storage.delete_icon(category_id)
        if success:
            app.logger.info(f"Icon deleted for category {category_id}")
            return jsonify({"message": "Icon deleted successfully"})
        else:
            return jsonify({"message": "Icon not found"}), 404
    except Exception as e:
        app.logger.error(f"Error deleting icon for category {category_id}: {e}")
        return jsonify({"message": "Failed to delete icon"}), 500

@app.route("/api/icons/categories/<int:category_id>/regenerate", methods=["POST"])
@supabase_jwt_required
def regenerate_category_icon(category_id):
    """Regenerate icon for a category."""
    try:
        data = request.get_json() or {}
        
        # Get existing category info
        category = icon_storage.get_category(category_id)
        if not category:
            return jsonify({"message": "Category not found"}), 404
        
        user_id = get_jwt_identity()
        
        # Generate new icon
        result = icon_generator.generate_category_icon(
            category_id=category_id,
            category_name=category['name'],
            style=data.get('style', 'modern'),
            color=data.get('color', '#3B82F6')
        )
        
        if result['success']:
            # Update icon record
            icon_record = icon_storage.save_icon(
                category_id=category_id,
                category_name=category['name'],
                file_path=result['file_path'],
                metadata={
                    'style': data.get('style', 'modern'),
                    'color': data.get('color', '#3B82F6'),
                    'generated_by': user_id,
                    'regenerated': True
                }
            )
            
            app.logger.info(f"Icon regenerated for category {category_id} by user {user_id}")
            return jsonify({
                "message": "Icon regenerated successfully",
                "icon": icon_record
            })
        else:
            return jsonify({
                "message": "Icon regeneration failed",
                "error": result.get('error')
            }), 500
            
    except Exception as e:
        app.logger.error(f"Error regenerating icon for category {category_id}: {e}")
        return jsonify({"message": "Failed to regenerate icon"}), 500

@app.route("/api/icons/<int:icon_id>", methods=["GET"])
@supabase_jwt_required
def get_icon(icon_id):
    """Get a specific icon by ID."""
    try:
        with db_session_scope() as session:
            icon_repo = IconRepository(session)
            icon = icon_repo.get_with_category(icon_id)
            
            if not icon:
                return jsonify({"message": "Icon not found"}), 404
            
            return jsonify({
                'id': icon.id,
                'category': {
                    'id': icon.category.id,
                    'name': icon.category.name,
                    'slug': icon.category.slug
                },
                'filename': icon.filename,
                'file_path': icon.file_path,
                'file_size': icon.file_size,
                'dimensions': {
                    'width': icon.width,
                    'height': icon.height
                },
                'format': icon.format,
                'generation': {
                    'prompt': icon.prompt,
                    'style': icon.style,
                    'color': icon.color,
                    'background': icon.background,
                    'model': icon.model,
                    'time': icon.generation_time,
                    'cost': icon.generation_cost
                },
                'status': icon.status,
                'is_active': icon.is_active,
                'shopify': {
                    'image_id': icon.shopify_image_id,
                    'image_url': icon.shopify_image_url,
                    'synced_at': icon.shopify_synced_at.isoformat() if icon.shopify_synced_at else None,
                    'sync_status': icon.shopify_sync_status
                },
                'created_by': icon.created_by,
                'created_at': icon.created_at.isoformat(),
                'updated_at': icon.updated_at.isoformat()
            })
            
    except Exception as e:
        app.logger.error(f"Error getting icon {icon_id}: {e}")
        return jsonify({"message": "Failed to retrieve icon"}), 500

@app.route("/api/icons/search", methods=["POST"])
@supabase_jwt_required
def search_icons():
    """Search for icons by query and filters."""
    try:
        data = request.get_json()
        query = data.get('query', '')
        filters = data.get('filters', {})
        
        with db_session_scope() as session:
            icon_repo = IconRepository(session)
            icons = icon_repo.search(query, filters=filters, limit=filters.get('limit', 50))
            
            icon_list = []
            for icon in icons:
                icon_list.append({
                    'id': icon.id,
                    'category_id': icon.category_id,
                    'filename': icon.filename,
                    'file_path': icon.file_path,
                    'style': icon.style,
                    'color': icon.color,
                    'status': icon.status,
                    'is_active': icon.is_active,
                    'shopify_synced': icon.shopify_image_id is not None,
                    'created_at': icon.created_at.isoformat()
                })
            
            return jsonify({
                "icons": icon_list,
                "count": len(icon_list)
            })
        
    except Exception as e:
        app.logger.error(f"Error searching icons: {e}")
        return jsonify({"message": "Failed to search icons"}), 500

@app.route("/api/icons", methods=["GET"])
@supabase_jwt_required
def get_all_icons():
    """Get all icons with pagination."""
    try:
        query = request.args.get('query', '')
        status = request.args.get('status')
        synced = request.args.get('synced')
        model = request.args.get('model')
        style = request.args.get('style')
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))
        
        # Convert synced string to boolean if provided
        synced_bool = None
        if synced is not None:
            synced_bool = synced.lower() in ('true', '1', 'yes')
        
        with db_session_scope() as session:
            icon_repo = IconRepository(session)
            icons, total = icon_repo.search_icons(
                query=query,
                status=status,
                synced=synced_bool,
                model=model,
                style=style,
                limit=limit,
                offset=offset
            )
            
            icon_list = []
            for icon in icons:
                icon_list.append({
                    'id': icon.id,
                    'category_id': icon.category_id,
                    'category_name': icon.category.name if icon.category else 'Unknown',
                    'filename': icon.filename,
                    'file_path': icon.file_path,
                    'width': icon.width,
                    'height': icon.height,
                    'format': icon.format,
                    'style': icon.style,
                    'color': icon.color,
                    'status': icon.status,
                    'is_active': icon.is_active,
                    'shopify_image_url': icon.shopify_image_url,
                    'shopify_synced_at': icon.shopify_synced_at.isoformat() if icon.shopify_synced_at else None,
                    'created_at': icon.created_at.isoformat(),
                    'isFavorite': icon.meta_data.get('favorite', False) if icon.meta_data else False
                })
            
            return jsonify({
                'icons': icon_list,
                'total': total,
                'limit': limit,
                'offset': offset,
                'count': len(icon_list)
            })
            
    except Exception as e:
        app.logger.error(f"Error getting all icons: {e}")
        return jsonify({"message": "Failed to retrieve icons"}), 500

@app.route("/api/icons/<int:icon_id>/favorite", methods=["PUT"])
@supabase_jwt_required
def toggle_icon_favorite(icon_id):
    """Toggle favorite status of an icon."""
    try:
        data = request.get_json()
        is_favorite = data.get('favorite', False)
        
        with db_session_scope() as session:
            icon_repo = IconRepository(session)
            icon = icon_repo.get_icon_by_id(icon_id)
            
            if not icon:
                return jsonify({"message": "Icon not found"}), 404
            
            # Update metadata with favorite status
            meta_data = icon.meta_data or {}
            meta_data['favorite'] = is_favorite
            
            icon_repo.update_icon(icon_id, {'meta_data': meta_data})
            session.commit()
            
            return jsonify({
                "message": "Icon favorite status updated",
                "icon_id": icon_id,
                "favorite": is_favorite
            })
            
    except Exception as e:
        app.logger.error(f"Error toggling icon favorite: {e}")
        return jsonify({"message": "Failed to update favorite status"}), 500

@app.route("/api/icons/<int:icon_id>", methods=["DELETE"])
@supabase_jwt_required
def delete_icon(icon_id):
    """Delete an icon."""
    try:
        with db_session_scope() as session:
            icon_repo = IconRepository(session)
            icon = icon_repo.get_icon_by_id(icon_id)
            
            if not icon:
                return jsonify({"message": "Icon not found"}), 404
            
            # Delete from database (includes file deletion)
            success = icon_repo.delete_icon(icon_id, hard_delete=True)
            
            if success:
                app.logger.info(f"Icon {icon_id} deleted successfully")
                return jsonify({"message": "Icon deleted successfully"})
            else:
                return jsonify({"message": "Failed to delete icon"}), 500
            
    except Exception as e:
        app.logger.error(f"Error deleting icon {icon_id}: {e}")
        return jsonify({"message": "Failed to delete icon"}), 500

@app.route("/api/icons/bulk", methods=["DELETE"])
@supabase_jwt_required
def bulk_delete_icons():
    """Delete multiple icons."""
    try:
        data = request.get_json()
        icon_ids = data.get('icon_ids', [])
        
        if not icon_ids:
            return jsonify({"message": "No icon IDs provided"}), 400
        
        with db_session_scope() as session:
            icon_repo = IconRepository(session)
            deleted_count = 0
            
            for icon_id in icon_ids:
                if icon_repo.delete_icon(icon_id, hard_delete=True):
                    deleted_count += 1
            
            app.logger.info(f"Bulk deleted {deleted_count} icons")
            return jsonify({
                "message": f"Successfully deleted {deleted_count} icons",
                "deleted_count": deleted_count
            })
            
    except Exception as e:
        app.logger.error(f"Error in bulk delete icons: {e}")
        return jsonify({"message": "Failed to delete icons"}), 500

# Shopify Collections Endpoints (syncs with categories)
@app.route("/api/collections", methods=["GET"])
@supabase_jwt_required
def get_collections():
    """Get all collections (categories) with their Shopify status."""
    try:
        with db_session_scope() as session:
            category_repo = CategoryRepository(session)
            icon_repo = IconRepository(session)
            
            categories = category_repo.get_all()
            
            collections = []
            for category in categories:
                # Get active icon for category using direct query
                from models import Icon, IconStatus
                icon = session.query(Icon).filter(
                    Icon.category_id == category.id,
                    Icon.status == IconStatus.ACTIVE.value,
                    Icon.is_active == True
                ).first()
                
                collections.append({
                    'id': category.id,
                    'name': category.name,
                    'slug': category.slug,
                    'description': category.description,
                    'parent_id': category.parent_id,
                    'level': category.level,
                    'has_icon': icon is not None,
                    'icon_id': icon.id if icon else None,
                    'icon_url': icon.file_path if icon else None,
                    'shopify_collection_id': category.shopify_collection_id,
                    'shopify_handle': category.shopify_handle,
                    'shopify_synced': category.shopify_collection_id is not None,
                    'shopify_synced_at': category.shopify_synced_at.isoformat() if category.shopify_synced_at else None
                })
            
            return jsonify({
                'collections': collections,
                'total': len(collections)
            })
            
    except Exception as e:
        app.logger.error(f"Error getting collections: {e}")
        return jsonify({"message": "Failed to retrieve collections"}), 500

# Shopify Collections Endpoints
@app.route("/api/shopify/status", methods=["GET"])
@supabase_jwt_required
def get_shopify_status():
    """Check Shopify API connection status."""
    try:
        shop_url = os.getenv('SHOPIFY_SHOP_URL')
        access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
        
        if not shop_url or not access_token:
            return jsonify({"connected": False, "message": "Shopify credentials not configured"})
        
        # Try to initialize and test connection
        shopify_manager = ShopifyCollectionsManager(shop_url, access_token)
        shopify_manager.test_auth()
        
        return jsonify({"connected": True, "message": "Connected to Shopify"})
        
    except Exception as e:
        app.logger.error(f"Shopify connection test failed: {e}")
        return jsonify({"connected": False, "message": str(e)})

@app.route("/api/shopify/collections", methods=["GET"])
@supabase_jwt_required
def get_shopify_collections():
    """Get all Shopify collections."""
    try:
        # Get Shopify credentials from environment
        shop_url = os.getenv('SHOPIFY_SHOP_URL')
        access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
        
        if not shop_url or not access_token:
            return jsonify({"message": "Shopify credentials not configured"}), 503
        
        # Initialize Shopify manager
        shopify_manager = ShopifyCollectionsManager(shop_url, access_token)
        
        # Get all collections
        collections = shopify_manager.get_all_collections()
        
        # Transform collections for frontend
        transformed_collections = []
        for collection in collections:
            transformed_collections.append({
                "id": collection['numeric_id'],
                "graphql_id": collection['id'],
                "handle": collection['handle'],
                "title": collection['title'],
                "description": collection.get('description', ''),
                "products_count": collection.get('productsCount', {}).get('count', 0),
                "image_url": collection.get('image', {}).get('url') if collection.get('image') else None,
                "has_icon": bool(collection.get('image')),
                "updated_at": collection.get('updatedAt'),
                "metafields": collection.get('metafields', {})
            })
        
        return jsonify({
            "collections": transformed_collections,
            "total": len(transformed_collections)
        })
        
    except Exception as e:
        app.logger.error(f"Error fetching Shopify collections: {e}")
        return jsonify({"message": "Failed to fetch collections"}), 500

@app.route("/api/shopify/collections/<collection_id>/upload-icon", methods=["POST"])
@supabase_jwt_required
def upload_shopify_collection_icon(collection_id):
    """Upload a generated icon to a Shopify collection."""
    try:
        data = request.get_json()
        icon_path = data.get('icon_path')
        
        if not icon_path or not os.path.exists(icon_path):
            return jsonify({"message": "Invalid icon path"}), 400
        
        # Get Shopify credentials
        shop_url = os.getenv('SHOPIFY_SHOP_URL')
        access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
        
        if not shop_url or not access_token:
            return jsonify({"message": "Shopify credentials not configured"}), 503
        
        # Initialize Shopify manager
        shopify_manager = ShopifyCollectionsManager(shop_url, access_token)
        
        # Convert numeric ID to GraphQL ID format
        graphql_id = f"gid://shopify/Collection/{collection_id}"
        
        # Upload the icon
        result = shopify_manager.upload_collection_icon(
            collection_id=graphql_id,
            image_path=icon_path,
            alt_text=data.get('alt_text', 'Collection icon')
        )
        
        if result['success']:
            # Update metadata
            metadata = {
                'icon_style': data.get('style', 'modern'),
                'icon_color': data.get('color', '#3B82F6'),
                'generated_at': datetime.now().isoformat(),
                'keywords': data.get('keywords', [])
            }
            
            metadata_result = shopify_manager.update_collection_metadata(
                collection_id=graphql_id,
                metadata=metadata
            )
            
            return jsonify({
                "message": "Icon uploaded successfully",
                "collection": result['collection'],
                "image_url": result['image_url'],
                "metadata_updated": metadata_result['success']
            })
        else:
            return jsonify({
                "message": "Failed to upload icon",
                "error": result['error']
            }), 500
            
    except Exception as e:
        app.logger.error(f"Error uploading icon to Shopify: {e}")
        return jsonify({"message": "Failed to upload icon"}), 500

@app.route("/api/shopify/collections/generate-all", methods=["POST"])
@supabase_jwt_required
def generate_all_collection_icons():
    """Generate icons for all Shopify collections."""
    try:
        data = request.get_json()
        options = data.get('options', {})
        
        # Get Shopify credentials
        shop_url = os.getenv('SHOPIFY_SHOP_URL')
        access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
        
        if not shop_url or not access_token:
            return jsonify({"message": "Shopify credentials not configured"}), 503
        
        # Initialize Shopify manager
        shopify_manager = ShopifyCollectionsManager(shop_url, access_token)
        
        # Get all collections
        collections = shopify_manager.get_all_collections()
        
        # Filter collections without icons if requested
        if options.get('only_missing', True):
            collections = [c for c in collections if not c.get('image')]
        
        if not collections:
            return jsonify({"message": "No collections require icon generation"}), 200
        
        # Prepare categories for batch generation
        categories = []
        for collection in collections:
            categories.append({
                'id': collection['numeric_id'],
                'name': collection['title'],
                'description': collection.get('description', ''),
                'graphql_id': collection['id']
            })
        
        user_id = get_jwt_identity()
        
        if job_manager:
            # Create batch job for background processing
            job_id = job_manager.create_job(
                script_name='shopify_collection_icon_generation',
                parameters=[
                    {'name': 'categories', 'value': categories, 'type': 'object'},
                    {'name': 'options', 'value': options, 'type': 'object'},
                    {'name': 'shop_url', 'value': shop_url, 'type': 'string'},
                    {'name': 'access_token', 'value': access_token, 'type': 'string'}
                ],
                user_id=user_id
            )
            
            # Execute job asynchronously
            job_manager.execute_job(job_id, socketio)
            
            app.logger.info(f"Shopify collection icon generation job {job_id} created for {len(categories)} collections by user {user_id}")
            
            return jsonify({
                "job_id": job_id,
                "message": f"Icon generation started for {len(categories)} collections"
            }), 201
        else:
            return jsonify({"message": "Background job processing not available"}), 503
            
    except Exception as e:
        app.logger.error(f"Error starting collection icon generation: {e}")
        return jsonify({"message": "Failed to start icon generation"}), 500

@app.route("/api/shopify/collections/<collection_id>/sync", methods=["POST"])
@supabase_jwt_required
def sync_collection_icon(collection_id):
    """Sync a locally generated icon with a Shopify collection."""
    try:
        data = request.get_json()
        local_icon_id = data.get('local_icon_id')
        
        if not local_icon_id:
            return jsonify({"message": "Local icon ID required"}), 400
        
        # Get icon details from local storage
        icon_details = icon_storage.get_icon_by_id(local_icon_id)
        if not icon_details:
            return jsonify({"message": "Icon not found"}), 404
        
        # Get Shopify credentials
        shop_url = os.getenv('SHOPIFY_SHOP_URL')
        access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
        
        if not shop_url or not access_token:
            return jsonify({"message": "Shopify credentials not configured"}), 503
        
        # Initialize Shopify manager
        shopify_manager = ShopifyCollectionsManager(shop_url, access_token)
        
        # Convert collection ID to GraphQL format
        graphql_id = f"gid://shopify/Collection/{collection_id}"
        
        # Upload the icon
        result = shopify_manager.upload_collection_icon(
            collection_id=graphql_id,
            image_path=icon_details['file_path'],
            alt_text=f"{icon_details.get('category_name', 'Collection')} icon"
        )
        
        if result['success']:
            # Update local storage with sync status
            icon_storage.update_sync_status(
                icon_id=local_icon_id,
                synced=True,
                shopify_collection_id=collection_id,
                shopify_image_url=result['image_url']
            )
            
            return jsonify({
                "message": "Icon synced successfully",
                "shopify_image_url": result['image_url']
            })
        else:
            return jsonify({
                "message": "Failed to sync icon",
                "error": result['error']
            }), 500
            
    except Exception as e:
        app.logger.error(f"Error syncing icon with Shopify: {e}")
        return jsonify({"message": "Failed to sync icon"}), 500

# Health check endpoint
@app.route("/api/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    try:
        # Check Redis connection
        if redis_client:
            redis_client.ping()
            redis_status = "healthy"
        else:
            redis_status = "not_configured"
    except:
        redis_status = "unhealthy"
    
    # Check database connection
    try:
        db_health = db_manager.health_check()
        database_status = db_health['status']
    except:
        database_status = "unhealthy"
    
    # Check icon storage
    try:
        if icon_storage:
            icon_storage.health_check()
            icon_storage_status = "healthy"
        else:
            icon_storage_status = "not_configured"
    except:
        icon_storage_status = "unhealthy"
    
    return jsonify({
        "status": "healthy",
        "services": {
            "redis": redis_status,
            "database": database_status,
            "flask": "healthy",
            "icon_storage": icon_storage_status
        }
    })

# Icon-Category Association Endpoints
@app.route("/api/icons/<int:icon_id>/assign", methods=["PUT"])
@supabase_jwt_required
def assign_icon_to_category(icon_id):
    """Assign an icon to a category."""
    try:
        data = request.get_json()
        category_id = data.get('category_id')
        
        if not category_id:
            return jsonify({"message": "Category ID is required"}), 400
        
        with db_session_scope() as session:
            service = IconCategoryService(session)
            result = service.assign_icon_to_category(icon_id, category_id)
            
            if result['success']:
                return jsonify(result), 200
            else:
                return jsonify(result), 400
                
    except Exception as e:
        app.logger.error(f"Error assigning icon {icon_id} to category: {e}")
        return jsonify({"message": "Failed to assign icon to category"}), 500

@app.route("/api/categories/<int:category_id>/unassign-icon", methods=["DELETE"])
@supabase_jwt_required
def unassign_icon_from_category(category_id):
    """Remove icon assignment from a category."""
    try:
        with db_session_scope() as session:
            service = IconCategoryService(session)
            result = service.unassign_icon_from_category(category_id)
            
            if result['success']:
                return jsonify(result), 200
            else:
                return jsonify(result), 400
                
    except Exception as e:
        app.logger.error(f"Error unassigning icon from category {category_id}: {e}")
        return jsonify({"message": "Failed to unassign icon from category"}), 500

@app.route("/api/categories/<int:category_id>/icon-history", methods=["GET"])
@supabase_jwt_required
def get_category_icon_history(category_id):
    """Get icon history for a category."""
    try:
        with db_session_scope() as session:
            service = IconCategoryService(session)
            result = service.get_category_icon_history(category_id)
            
            if result['success']:
                return jsonify(result), 200
            else:
                return jsonify(result), 404
                
    except Exception as e:
        app.logger.error(f"Error getting icon history for category {category_id}: {e}")
        return jsonify({"message": "Failed to get icon history"}), 500

@app.route("/api/icons/<int:icon_id>/sync-shopify", methods=["POST"])
@supabase_jwt_required
def sync_icon_to_shopify(icon_id):
    """Sync an icon to Shopify."""
    try:
        data = request.get_json() or {}
        collection_id = data.get('collection_id')
        
        with db_session_scope() as session:
            service = IconCategoryService(session)
            result = service.sync_icon_to_shopify(icon_id, collection_id)
            
            if result['success']:
                return jsonify(result), 200
            else:
                return jsonify(result), 400
                
    except Exception as e:
        app.logger.error(f"Error syncing icon {icon_id} to Shopify: {e}")
        return jsonify({"message": "Failed to sync icon to Shopify"}), 500

@app.route("/api/categories/without-icons", methods=["GET"])
@supabase_jwt_required
def get_categories_without_icons():
    """Get categories that don't have active icons."""
    try:
        with db_session_scope() as session:
            service = IconCategoryService(session)
            categories = service.get_categories_without_icons()
            
            return jsonify({
                "categories": categories,
                "count": len(categories)
            }), 200
            
    except Exception as e:
        app.logger.error(f"Error getting categories without icons: {e}")
        return jsonify({"message": "Failed to get categories without icons"}), 500

@app.route("/api/icons/bulk-assign", methods=["POST"])
@supabase_jwt_required
def bulk_assign_icons():
    """Bulk assign icons to categories."""
    try:
        data = request.get_json()
        assignments = data.get('assignments', [])
        
        if not assignments:
            return jsonify({"message": "No assignments provided"}), 400
        
        with db_session_scope() as session:
            service = IconCategoryService(session)
            result = service.bulk_assign_icons(assignments)
            
            if result['success']:
                return jsonify(result), 200
            else:
                return jsonify(result), 400
                
    except Exception as e:
        app.logger.error(f"Error in bulk icon assignment: {e}")
        return jsonify({"message": "Failed to bulk assign icons"}), 500

# Shopify Icon Sync Endpoints
@app.route("/api/icons/<int:icon_id>/sync-to-shopify", methods=["POST"])
@supabase_jwt_required
def sync_icon_to_shopify_collection(icon_id):
    """Upload an icon to Shopify collection."""
    try:
        data = request.get_json() or {}
        collection_id = data.get('collection_id')
        
        with db_session_scope() as session:
            service = ShopifyIconSyncService(session)
            result = service.upload_icon_to_collection(icon_id, collection_id)
            
            if result['success']:
                return jsonify(result), 200
            else:
                return jsonify(result), 400
                
    except Exception as e:
        app.logger.error(f"Error syncing icon {icon_id} to Shopify: {e}")
        return jsonify({"message": "Failed to sync icon to Shopify"}), 500

@app.route("/api/categories/<int:category_id>/sync-icons-to-shopify", methods=["POST"])
@supabase_jwt_required
def sync_category_icons_to_shopify_collection(category_id):
    """Sync all category icons to Shopify."""
    try:
        with db_session_scope() as session:
            service = ShopifyIconSyncService(session)
            result = service.sync_category_icons_to_shopify(category_id)
            
            if result['success']:
                return jsonify(result), 200
            else:
                return jsonify(result), 400
                
    except Exception as e:
        app.logger.error(f"Error syncing category {category_id} icons to Shopify: {e}")
        return jsonify({"message": "Failed to sync category icons to Shopify"}), 500

@app.route("/api/icons/<int:icon_id>/remove-from-shopify", methods=["DELETE"])
@supabase_jwt_required
def remove_icon_from_shopify_collection(icon_id):
    """Remove an icon from Shopify collection."""
    try:
        with db_session_scope() as session:
            service = ShopifyIconSyncService(session)
            result = service.remove_icon_from_shopify(icon_id)
            
            if result['success']:
                return jsonify(result), 200
            else:
                return jsonify(result), 400
                
    except Exception as e:
        app.logger.error(f"Error removing icon {icon_id} from Shopify: {e}")
        return jsonify({"message": "Failed to remove icon from Shopify"}), 500

@app.route("/api/shopify/sync-status", methods=["GET"])
@supabase_jwt_optional
def get_shopify_sync_status():
    """Get summary of Shopify sync status."""
    try:
        with db_session_scope() as session:
            service = ShopifyIconSyncService(session)
            result = service.get_sync_status_summary()
            
            if result['success']:
                return jsonify(result), 200
            else:
                return jsonify(result), 500
                
    except Exception as e:
        app.logger.error(f"Error getting Shopify sync status: {e}")
        return jsonify({"message": "Failed to get sync status"}), 500

@app.route("/api/shopify/collection/<collection_id>", methods=["GET"])
@supabase_jwt_required
def get_shopify_collection_info(collection_id):
    """Get Shopify collection information."""
    try:
        with db_session_scope() as session:
            service = ShopifyIconSyncService(session)
            result = service.get_collection_by_id(collection_id)
            
            if result['success']:
                return jsonify(result), 200
            else:
                return jsonify(result), 404 if result.get('error_code') == 'NOT_FOUND' else 500
                
    except Exception as e:
        app.logger.error(f"Error getting Shopify collection {collection_id}: {e}")
        return jsonify({"message": "Failed to get collection information"}), 500

# Shopify Product Sync Endpoints
@app.route("/api/shopify/products/sync", methods=["POST"])
@supabase_jwt_optional
def sync_all_shopify_products():
    """Sync all products from Shopify to database."""
    try:
        data = request.get_json() or {}
        include_draft = data.get('include_draft', True)
        
        with db_session_scope() as session:
            service = ShopifyProductSyncService(session)
            result = service.sync_all_products(include_draft=include_draft)
            
            if result['success']:
                return jsonify(result), 200
            else:
                return jsonify(result), 400
                
    except Exception as e:
        app.logger.error(f"Error syncing Shopify products: {e}")
        return jsonify({"message": "Failed to sync Shopify products"}), 500

@app.route("/api/shopify/products/<shopify_product_id>/sync", methods=["POST"])
@supabase_jwt_required
def sync_single_shopify_product(shopify_product_id):
    """Sync a single product from Shopify."""
    try:
        with db_session_scope() as session:
            service = ShopifyProductSyncService(session)
            result = service.sync_single_product_by_id(shopify_product_id)
            
            if result['success']:
                return jsonify(result), 200
            else:
                return jsonify(result), 400
                
    except Exception as e:
        app.logger.error(f"Error syncing single product {shopify_product_id}: {e}")
        return jsonify({"message": "Failed to sync product"}), 500

@app.route("/api/shopify/products/sync-status", methods=["GET"])
@supabase_jwt_optional
def get_shopify_product_sync_status():
    """Get Shopify product sync status and statistics."""
    try:
        with db_session_scope() as session:
            service = ShopifyProductSyncService(session)
            result = service.get_sync_status()
            
            if result['success']:
                return jsonify(result), 200
            else:
                return jsonify(result), 500
                
    except Exception as e:
        app.logger.error(f"Error getting sync status: {e}")
        return jsonify({"message": "Failed to get sync status"}), 500

@app.route("/api/shopify/test-connection", methods=["GET"])
@supabase_jwt_required
def test_shopify_connection():
    """Test Shopify API connection."""
    try:
        with db_session_scope() as session:
            service = ShopifyProductSyncService(session)
            
            # Test basic connection by making a simple request
            result = service._make_shopify_request('shop.json')
            
            if result['success']:
                shop_data = result['data']['shop']
                return jsonify({
                    "success": True,
                    "message": "Successfully connected to Shopify",
                    "shop": {
                        "name": shop_data.get('name'),
                        "domain": shop_data.get('domain'),
                        "plan": shop_data.get('plan_name'),
                        "currency": shop_data.get('currency'),
                        "timezone": shop_data.get('timezone')
                    }
                }), 200
            else:
                return jsonify({
                    "success": False,
                    "message": "Failed to connect to Shopify",
                    "error": result['error']
                }), 400
                
    except Exception as e:
        app.logger.error(f"Error testing Shopify connection: {e}")
        return jsonify({"message": "Failed to test connection"}), 500

# Temporary test endpoint without auth for debugging
@app.route("/api/shopify/test-connection-debug", methods=["GET"])
def test_shopify_connection_debug():
    """Test Shopify API connection without authentication (DEBUG ONLY)."""
    try:
        # Check if Shopify credentials are set
        shop_url = os.getenv('SHOPIFY_SHOP_URL')
        access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
        
        if not shop_url or not access_token:
            return jsonify({
                "success": False,
                "message": "Shopify credentials not found in environment variables",
                "debug": {
                    "shop_url_set": bool(shop_url),
                    "access_token_set": bool(access_token)
                }
            }), 400
        
        with db_session_scope() as session:
            service = ShopifyProductSyncService(session)
            
            # Test basic connection by making a simple request
            result = service._make_shopify_request('shop.json')
            
            if result['success']:
                shop_data = result['data']['shop']
                return jsonify({
                    "success": True,
                    "message": "Successfully connected to Shopify",
                    "shop": {
                        "name": shop_data.get('name'),
                        "domain": shop_data.get('domain'),
                        "plan": shop_data.get('plan_name'),
                        "currency": shop_data.get('currency'),
                        "timezone": shop_data.get('timezone')
                    }
                }), 200
            else:
                return jsonify({
                    "success": False,
                    "message": "Failed to connect to Shopify",
                    "error": result['error'],
                    "error_code": result.get('error_code', 'UNKNOWN')
                }), 400
                
    except Exception as e:
        app.logger.error(f"Error testing Shopify connection: {e}")
        return jsonify({
            "success": False,
            "message": "Failed to test connection",
            "error": str(e)
        }), 500

# Enhanced Product Management Endpoints with Shopify Integration
@app.route("/api/products/with-shopify-data", methods=["GET"])
@supabase_jwt_required
def get_products_with_shopify_data():
    """Get products with enhanced Shopify sync information."""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        sync_status = request.args.get('sync_status')
        category_id = request.args.get('category_id', type=int)
        
        with db_session_scope() as session:
            product_repo = ProductRepository(session)
            
            # Build query with filters
            query = session.query(Product).options(joinedload(Product.category))
            
            if sync_status:
                query = query.filter(Product.shopify_sync_status == sync_status)
            if category_id:
                query = query.filter(Product.category_id == category_id)
            
            # Count total for pagination
            total = query.count()
            
            # Apply pagination
            offset = (page - 1) * per_page
            products = query.offset(offset).limit(per_page).all()
            
            # Calculate pagination info
            total_pages = (total + per_page - 1) // per_page
            has_prev = page > 1
            has_next = page < total_pages
            
            # Enhance with sync information
            enhanced_products = []
            for product in products:
                enhanced_products.append({
                    'id': product.id,
                    'sku': product.sku,
                    'name': product.name,
                    'description': product.description,
                    'price': float(product.price) if product.price else None,
                    'compare_at_price': float(product.compare_at_price) if product.compare_at_price else None,
                    'inventory_quantity': product.inventory_quantity,
                    'status': product.status,
                    'category_id': product.category_id,
                    'category_name': product.category.name if product.category else None,
                    'shopify_product_id': product.shopify_product_id,
                    'shopify_variant_id': product.shopify_variant_id,
                    'shopify_handle': product.shopify_handle,
                    'shopify_synced_at': product.shopify_synced_at.isoformat() if product.shopify_synced_at else None,
                    'shopify_sync_status': product.shopify_sync_status,
                    'featured_image_url': product.featured_image_url,
                    'brand': product.brand,
                    'manufacturer': product.manufacturer,
                    'created_at': product.created_at.isoformat(),
                    'updated_at': product.updated_at.isoformat()
                })
            
            return jsonify({
                'products': enhanced_products,
                'pagination': {
                    'total': total,
                    'page': page,
                    'per_page': per_page,
                    'total_pages': total_pages,
                    'has_prev': has_prev,
                    'has_next': has_next
                }
            })
            
    except Exception as e:
        app.logger.error(f"Error getting products with Shopify data: {e}")
        return jsonify({"message": "Failed to retrieve products"}), 500

# Product Type and Collection Management Endpoints
@app.route("/api/products/product-types-summary", methods=["GET"])
@supabase_jwt_required
def get_product_types_summary():
    """Get summary of product types with statistics."""
    try:
        with db_session_scope() as session:
            product_repo = ProductRepository(session)
            
            # Get category statistics (using categories as product types)
            result = session.query(
                Category.name,
                func.count(Product.id).label('product_count'),
                func.avg(Product.price).label('avg_price')
            ).join(Product, Category.id == Product.category_id)\
             .group_by(Category.name)\
             .all()
            
            product_types = []
            for row in result:
                # Get additional data for each category
                products_in_category = session.query(Product).filter(
                    Product.category_id == session.query(Category.id).filter(
                        Category.name == row.name
                    ).scalar_subquery()
                ).all()
                
                # Extract unique vendors (using brand and manufacturer)
                vendors = list(set([
                    p.brand for p in products_in_category if p.brand
                ] + [
                    p.manufacturer for p in products_in_category if p.manufacturer
                ]))
                
                sample_products = [p.name for p in products_in_category[:5] if p.name]
                
                product_types.append({
                    'name': row.name,
                    'product_count': row.product_count,
                    'avg_price': float(row.avg_price or 0),
                    'vendors': vendors,
                    'categories': [row.name],  # Category itself
                    'sample_products': sample_products,
                    'collection_status': 'none'  # Will be updated based on existing collections
                })
            
            return jsonify({
                'product_types': product_types,
                'total': len(product_types)
            })
            
    except Exception as e:
        app.logger.error(f"Error getting product types summary: {e}")
        return jsonify({"message": "Failed to retrieve product types summary"}), 500

@app.route("/api/collections/managed", methods=["GET"])
@supabase_jwt_required
def get_managed_collections():
    """Get all locally managed collections."""
    try:
        with db_session_scope() as session:
            category_repo = CategoryRepository(session)
            
            # Get categories that represent collections
            categories = category_repo.get_all()
            
            collections = []
            for category in categories:
                # Get product count for this category
                product_count = session.query(Product).filter(
                    Product.category_id == category.id
                ).count()
                
                collections.append({
                    'id': str(category.id),
                    'name': category.name,
                    'description': category.description or '',
                    'handle': category.slug,
                    'product_count': product_count,
                    'product_types': [category.name],  # Use category name as product type
                    'created_locally': True,
                    'shopify_collection_id': category.shopify_collection_id,
                    'shopify_synced_at': category.shopify_synced_at.isoformat() if category.shopify_synced_at else None,
                    'status': 'synced' if category.shopify_collection_id else 'draft',
                    'ai_generated': False,  # Could be stored in metadata
                    'rules': {
                        'type': 'manual',
                        'conditions': []
                    }
                })
            
            return jsonify({
                'collections': collections,
                'total': len(collections)
            })
            
    except Exception as e:
        app.logger.error(f"Error getting managed collections: {e}")
        return jsonify({"message": "Failed to retrieve collections"}), 500

@app.route("/api/collections/ai-suggestions", methods=["POST"])
@supabase_jwt_required
def generate_ai_collection_suggestions():
    """Generate AI-powered collection suggestions for product types."""
    try:
        data = request.get_json()
        product_types = data.get('product_types', [])
        
        if not product_types:
            return jsonify({"message": "No product types provided"}), 400
        
        # For now, generate simple rule-based suggestions
        # In the future, this could integrate with OpenAI or other AI services
        suggestions = []
        
        for product_type in product_types:
            # Simple rule-based collection naming
            collection_name = f"{product_type} Collection"
            description = f"All products in the {product_type} category, curated for quality and variety."
            
            # Add some intelligence based on common patterns
            if 'office' in product_type.lower():
                collection_name = f"Office {product_type}"
                description = f"Professional {product_type.lower()} for modern workspaces and home offices."
            elif 'tech' in product_type.lower() or 'electronic' in product_type.lower():
                collection_name = f"Tech {product_type}"
                description = f"Latest {product_type.lower()} with cutting-edge features and reliability."
            elif 'furniture' in product_type.lower():
                collection_name = f"Premium {product_type}"
                description = f"Stylish and functional {product_type.lower()} for every space."
            
            suggestions.append({
                'product_type': product_type,
                'collection_name': collection_name,
                'description': description,
                'confidence': 0.85  # Placeholder confidence score
            })
        
        app.logger.info(f"Generated AI suggestions for {len(product_types)} product types")
        
        return jsonify({
            'suggestions': suggestions,
            'total': len(suggestions)
        })
        
    except Exception as e:
        app.logger.error(f"Error generating AI suggestions: {e}")
        return jsonify({"message": "Failed to generate AI suggestions"}), 500

@app.route("/api/collections/create", methods=["POST"])
@supabase_jwt_required
def create_collection():
    """Create a new collection (category)."""
    try:
        data = request.get_json()
        
        required_fields = ['name', 'description']
        for field in required_fields:
            if not data.get(field):
                return jsonify({"message": f"Missing required field: {field}"}), 400
        
        with db_session_scope() as session:
            category_repo = CategoryRepository(session)
            
            # Generate unique slug
            base_slug = data.get('handle', data['name'].lower().replace(' ', '-'))
            slug = base_slug
            counter = 1
            
            # Check if slug already exists and generate a unique one
            while category_repo.get_by_slug(slug):
                slug = f"{base_slug}-{counter}"
                counter += 1
            
            try:
                # Create the category using the repository create method
                category = category_repo.create(
                    name=data['name'],
                    slug=slug,
                    description=data['description'],
                    parent_id=data.get('parent_id')
                )
                
                # Commit the transaction
                session.commit()
            except Exception as e:
                session.rollback()
                app.logger.error(f"Error creating category: {e}")
                return jsonify({"message": "Failed to create collection", "error": str(e)}), 500
            
            # If this collection has automatic rules, apply them
            rules = data.get('rules')
            if rules and rules.get('type') == 'automatic':
                product_repo = ProductRepository(session)
                conditions = rules.get('conditions', [])
                
                # Apply rules to assign products
                for condition in conditions:
                    if condition['field'] == 'product_type' and condition['operator'] == 'equals':
                        # Update products of this type to belong to this category
                        products = session.query(Product).filter(
                            Product.product_type == condition['value']
                        ).all()
                        
                        for product in products:
                            product.category_id = category.id
                        
                        session.commit()
            
            app.logger.info(f"Created collection: {data['name']} (ID: {category.id})")
            
            return jsonify({
                "message": "Collection created successfully",
                "collection": {
                    'id': str(category.id),
                    'name': category.name,
                    'description': category.description,
                    'handle': category.slug,
                    'created_at': category.created_at.isoformat()
                }
            }), 201
            
    except Exception as e:
        app.logger.error(f"Error creating collection: {e}")
        return jsonify({"message": "Failed to create collection"}), 500

@app.route("/api/collections/<collection_id>/sync-to-shopify", methods=["POST"])
@supabase_jwt_required
def sync_collection_to_shopify(collection_id):
    """Sync a collection to Shopify as a collection."""
    try:
        with db_session_scope() as session:
            category_repo = CategoryRepository(session)
            product_repo = ProductRepository(session)
            category = category_repo.get(int(collection_id))
            
            if not category:
                return jsonify({"message": "Collection not found"}), 404
            
            # Get Shopify credentials
            shop_url = os.getenv('SHOPIFY_SHOP_URL')
            access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
            
            if not shop_url or not access_token:
                return jsonify({"message": "Shopify credentials not configured"}), 500
            
            # Initialize ShopifyCollectionsManager
            from shopify_collections import ShopifyCollectionsManager
            shopify_manager = ShopifyCollectionsManager(shop_url, access_token, debug=True)
            
            # Prepare collection data
            collection_data = {
                "title": category.name,
                "handle": category.slug.replace("_", "-") if category.slug else category.name.lower().replace(" ", "-"),
                "description": category.description or f"Products in the {category.name} category",
                "sortOrder": "BEST_SELLING"
            }
            
            # Get products in this category for syncing
            products_in_category = product_repo.get_by_category(category.id)
            product_ids = []
            
            for product in products_in_category:
                if product.shopify_product_id and product.shopify_product_id.startswith('gid://shopify/Product/'):
                    product_ids.append(product.shopify_product_id)
                elif product.shopify_product_id:
                    # Convert numeric ID to GraphQL format
                    product_ids.append(f"gid://shopify/Product/{product.shopify_product_id}")
            
            try:
                # Create or update collection in Shopify
                if category.shopify_collection_id:
                    # Update existing collection
                    result = shopify_manager.update_collection(category.shopify_collection_id, collection_data)
                    operation = "updated"
                else:
                    # Create new collection
                    result = shopify_manager.create_collection(collection_data)
                    operation = "created"
                
                if not result.get('success'):
                    app.logger.error(f"Shopify collection sync failed: {result.get('error')}")
                    return jsonify({
                        "message": "Failed to sync collection to Shopify",
                        "error": result.get('error')
                    }), 500
                
                collection = result.get('collection')
                shopify_collection_id = collection['id']
                numeric_id = collection.get('numeric_id', shopify_collection_id.split('/')[-1])
                
                # Add products to collection if any exist
                if product_ids:
                    add_result = shopify_manager.add_products_to_collection(shopify_collection_id, product_ids)
                    if not add_result.get('success'):
                        app.logger.warning(f"Failed to add products to collection: {add_result.get('error')}")
                
                # Update category with Shopify info
                category_repo.update_category(category.id, {
                    'shopify_collection_id': shopify_collection_id,
                    'shopify_handle': collection.get('handle'),
                    'shopify_synced_at': datetime.now(timezone.utc)
                })
                
                app.logger.info(f"Successfully {operation} collection {collection_id} in Shopify as {numeric_id}")
                
                return jsonify({
                    "message": f"Collection {operation} in Shopify successfully",
                    "shopify_collection_id": numeric_id,
                    "shopify_handle": collection.get('handle'),
                    "products_added": len(product_ids),
                    "operation": operation
                })
                
            except Exception as shopify_error:
                app.logger.error(f"Shopify API error: {str(shopify_error)}")
                return jsonify({
                    "message": "Failed to sync collection to Shopify",
                    "error": str(shopify_error)
                }), 500
            
    except Exception as e:
        app.logger.error(f"Error syncing collection {collection_id} to Shopify: {e}")
        return jsonify({"message": "Failed to sync collection to Shopify", "error": str(e)}), 500


# Test endpoints for sync verification


@app.route("/api/test/sync-product/<product_id>", methods=["POST"])
@supabase_jwt_required
def test_sync_product(product_id):
    """Test syncing a single product to Shopify."""
    try:
        with db_session_scope() as session:
            product_repo = ProductRepository(session)
            product = product_repo.get(int(product_id))
            
            if not product:
                return jsonify({"success": False, "message": "Product not found"}), 404
            
            # Get Shopify credentials
            shop_url = os.getenv('SHOPIFY_SHOP_URL')
            access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
            
            if not shop_url or not access_token:
                return jsonify({"success": False, "message": "Shopify credentials not configured"}), 500
            
            # Create sync configuration
            from services.shopify_sync_service import SyncConfiguration, SyncMode, SyncFlags
            config = SyncConfiguration(
                mode=SyncMode.FULL_SYNC,
                flags=[SyncFlags.DEBUG],
                shop_url=shop_url,
                access_token=access_token
            )
            
            # Initialize sync service
            sync_service = ShopifySyncService(session)
            
            # Test single product sync
            result = sync_service._full_sync(product, config)
            
            return jsonify({
                "success": result.get('success', False),
                "product_id": product_id,
                "result": result
            })
            
    except Exception as e:
        app.logger.error(f"Test product sync failed: {e}")
        return jsonify({
            "success": False,
            "message": "Test product sync failed",
            "error": str(e)
        }), 500


@app.route("/api/test/sync-collection/<collection_id>", methods=["POST"])  
@supabase_jwt_required
def test_sync_collection(collection_id):
    """Test syncing a single collection to Shopify."""
    try:
        with db_session_scope() as session:
            category_repo = CategoryRepository(session)
            category = category_repo.get(int(collection_id))
            
            if not category:
                return jsonify({"success": False, "message": "Collection not found"}), 404
            
            # Get Shopify credentials
            shop_url = os.getenv('SHOPIFY_SHOP_URL')
            access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
            
            if not shop_url or not access_token:
                return jsonify({"success": False, "message": "Shopify credentials not configured"}), 500
            
            from shopify_collections import ShopifyCollectionsManager
            shopify_manager = ShopifyCollectionsManager(shop_url, access_token, debug=True)
            
            # Convert category to dictionary format
            category_data = {
                "id": category.id,
                "name": category.name,
                "slug": category.slug,
                "description": category.description,
                "shopify_collection_id": category.shopify_collection_id
            }
            
            # Test collection sync
            result = shopify_manager.sync_category_to_collection(category_data)
            
            if result.get('success'):
                # Update category with Shopify info if successful
                collection = result.get('collection')
                category_repo.update_category(category.id, {
                    'shopify_collection_id': collection['id'],
                    'shopify_handle': collection.get('handle'),
                    'shopify_synced_at': datetime.now(timezone.utc)
                })
            
            return jsonify({
                "success": result.get('success', False),
                "collection_id": collection_id,
                "result": result
            })
            
    except Exception as e:
        app.logger.error(f"Test collection sync failed: {e}")
        return jsonify({
            "success": False,
            "message": "Test collection sync failed", 
            "error": str(e)
        }), 500


# Register blueprints
app.register_blueprint(import_bp)
app.register_blueprint(shopify_sync_bp)
app.register_blueprint(xorosoft_bp)
app.register_blueprint(collections_bp)
app.register_blueprint(products_batch_bp)

# Register batch processing blueprint
from batch_api import batch_bp
app.register_blueprint(batch_bp)

# Register conflict detection blueprint
from conflict_api import conflict_bp
app.register_blueprint(conflict_bp)

# Error handling middleware
@app.errorhandler(Exception)
def handle_error(e):
    """Global error handler with tracking."""
    from werkzeug.exceptions import HTTPException
    
    # Track the error
    error_tracker.track_error(
        error=e,
        endpoint=request.endpoint,
        method=request.method,
        user_id=get_user_id() if hasattr(request, 'jwt_identity') else None,
        context={
            'url': request.url,
            'remote_addr': request.remote_addr,
            'user_agent': request.user_agent.string
        }
    )
    
    # Log the error
    app.logger.error(f"Unhandled exception: {str(e)}", exc_info=True)
    
    # Return appropriate error response
    if isinstance(e, HTTPException):
        return jsonify({"message": e.description}), e.code
    
    # Don't expose internal errors in production
    if app.debug:
        return jsonify({
            "message": "Internal server error",
            "error": str(e),
            "type": type(e).__name__
        }), 500
    else:
        return jsonify({"message": "Internal server error"}), 500

@app.before_request
def track_request_start():
    """Track request start time."""
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