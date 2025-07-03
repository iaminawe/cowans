from flask import Flask, jsonify, request, send_file, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from functools import wraps
from flask_socketio import SocketIO, emit, join_room, leave_room
from datetime import timedelta
import os
import redis
import logging
import time
import asyncio
import json
import uuid
from pathlib import Path
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

# Icon generation imports
from icon_generation_service import (
    IconGenerationService, BatchGenerationRequest, 
    BatchJobStatus, BatchGenerationResult
)
from prompt_templates import IconStyle, IconColor
from openai_client import ImageGenerationRequest

from config import config
from schemas import (
    LoginSchema, ScriptExecutionSchema, JobStatusSchema,
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
from models import ProductStatus, IconStatus, JobStatus

load_dotenv()

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

# Initialize database
try:
    app.logger.info("Backend startup")
    init_database(create_tables=True)
    app.logger.info("Database initialized successfully")
except Exception as e:
    app.logger.error(f"Failed to initialize database: {e}")
    # Continue anyway for development

# Initialize Icon Generation Service (global instance)
icon_service = None

# Initialize Icon Storage and Generator (create instances if needed)
try:
    icon_storage = IconStorage(base_path="data/category_icons")
    # Try to use OpenAI-powered generator if available
    if os.getenv("OPENAI_API_KEY"):
        from icon_generator_openai import icon_generator_openai
        icon_generator = icon_generator_openai
        app.logger.info("Using OpenAI-powered icon generator")
    else:
        icon_generator = IconGenerator()
        app.logger.warning("No OpenAI API key found, using placeholder icon generator")
except Exception as e:
    app.logger.warning(f"Icon storage/generator not available: {e}")
    icon_storage = None
    icon_generator = None

# Development mode auth bypass
DEV_MODE = os.getenv('FLASK_ENV', 'development') == 'development'
if DEV_MODE:
    app.logger.warning("Running in development mode - authentication bypassed")

def dev_jwt_required():
    """JWT required decorator that bypasses auth in development mode"""
    def decorator(fn):
        if DEV_MODE:
            @wraps(fn)
            def wrapper(*args, **kwargs):
                return fn(*args, **kwargs)
            return wrapper
        else:
            return jwt_required()(fn)
    return decorator

# Replace jwt_required with our dev version
jwt_required = dev_jwt_required

# Also bypass get_jwt_identity in dev mode
original_get_jwt_identity = get_jwt_identity
def dev_get_jwt_identity():
    """Get JWT identity with dev mode bypass"""
    if DEV_MODE:
        return "dev-user"  # Return a dummy user ID
    else:
        return original_get_jwt_identity()

get_jwt_identity = dev_get_jwt_identity

def get_user_id():
    """Helper function to get numeric user ID, handling dev mode."""
    jwt_identity = get_jwt_identity()
    if jwt_identity == "dev-user":
        # In development mode, use a dummy user ID
        return None  # Allow NULL for dev mode
    else:
        try:
            return int(jwt_identity)
        except (ValueError, TypeError):
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
    app.logger.info("Database initialized successfully")
except Exception as e:
    app.logger.error(f"Failed to initialize database: {e}")
    # Continue anyway for development

# Schemas
login_schema = LoginSchema()
script_execution_schema = ScriptExecutionSchema()
job_status_schema = JobStatusSchema()
sync_history_schema = SyncHistorySchema()
script_definition_schema = ScriptDefinitionSchema()
category_icon_schema = CategoryIconSchema()
icon_generation_schema = IconGenerationSchema()

@app.route("/api/auth/login", methods=["POST"])
def login():
    """Handle user login."""
    try:
        data = login_schema.load(request.get_json())
    except Exception as e:
        return jsonify({"message": "Invalid request data", "errors": str(e)}), 400
    
    try:
        with db_session_scope() as session:
            user_repo = UserRepository(session)
            user = user_repo.get_by_email(data["email"])
            
            if user and user.is_active and user_repo.verify_password(user, data["password"]):
                # Update last login
                user_repo.update_last_login(user.id)
                session.commit()
                
                access_token = create_access_token(identity=str(user.id))
                app.logger.info(f"User logged in: {user.email}")
                return jsonify({
                    "access_token": access_token,
                    "user": {
                        "id": user.id,
                        "email": user.email,
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                        "is_admin": user.is_admin
                    }
                })
            
            app.logger.warning(f"Failed login attempt for: {data['email']}")
            return jsonify({"message": "Invalid credentials"}), 401
            
    except SQLAlchemyError as e:
        app.logger.error(f"Database error during login: {e}")
        return jsonify({"message": "Login failed"}), 500

@app.route("/api/scripts", methods=["GET"])
@jwt_required()
def get_scripts():
    """Get available scripts organized by category."""
    scripts = get_all_scripts()
    return jsonify(scripts)

@app.route("/api/scripts/<script_name>", methods=["GET"])
@jwt_required()
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
@jwt_required()
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
@jwt_required()
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
@jwt_required()
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
@jwt_required()
def get_job_logs(job_id):
    """Get log file for a job (mock for development)."""
    return jsonify({"message": "Log file not found"}), 404

@app.route("/api/jobs", methods=["GET"])
@jwt_required()
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
@jwt_required()
def trigger_sync():
    """Trigger full sync workflow (backward compatibility)."""
    import uuid
    from datetime import datetime
    
    user_id = get_jwt_identity()
    job_id = str(uuid.uuid4())
    
    app.logger.info(f"Sync triggered by user: {user_id}")
    
    return jsonify({
        "message": "Sync triggered successfully",
        "job_id": job_id
    })

@app.route("/api/sync/history", methods=["GET"])
@jwt_required()
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
        return jsonify({"message": "Failed to retrieve sync history"}), 500

# WebSocket event handlers
@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    app.logger.info(f"WebSocket connected: {request.sid}")
    emit('connected', {'message': 'Connected to server'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    app.logger.info(f"WebSocket disconnected: {request.sid}")

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

# Product API Endpoints
@app.route("/api/products", methods=["GET"])
@jwt_required()
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
@jwt_required()
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
@jwt_required()
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
@jwt_required()
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
@jwt_required()
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
@jwt_required()
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
@jwt_required()
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
@jwt_required()
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
@jwt_required()
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
@jwt_required()
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
@jwt_required()
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
            icon = icon_repo.create(
                category_id=category_id,
                filename=f"category_{category_id}_icon.png",
                file_path="",  # Will be updated after generation
                prompt=f"Icon for {category_name} category",
                style=data.get('style', 'modern'),
                color=data.get('color', '#3B82F6'),
                background=data.get('background', 'transparent'),
                model=data.get('model', 'gpt-image-1'),
                status=IconStatus.GENERATING.value,
                created_by=user_id
            )
            session.commit()
            
            # Generate icon
            result = icon_generator.generate_category_icon(
                category_id=category_id,
                category_name=category_name,
                style=data.get('style', 'modern'),
                color=data.get('color', '#3B82F6'),
                size=data.get('size', 128),
                background=data.get('background', 'transparent'),
                model=data.get('model', 'gpt-image-1')
            )
            
            if result['success']:
                # Update icon record with file details
                icon_repo.update(
                    icon.id,
                    file_path=result['file_path'],
                    filename=os.path.basename(result['file_path']),
                    status=IconStatus.ACTIVE.value,
                    generation_time=result.get('generation_time'),
                    width=result.get('width', 128),
                    height=result.get('height', 128),
                    format='PNG'
                )
                
                # Deactivate other icons for this category
                icon_repo.deactivate_category_icons(category_id, except_icon_id=icon.id)
                
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
                icon_repo.update_status(icon.id, IconStatus.FAILED.value, result.get('error'))
                session.commit()
                
                return jsonify({
                    "message": "Icon generation failed",
                    "error": result.get('error')
                }), 500
                
    except Exception as e:
        app.logger.error(f"Error generating icon: {e}")
        return jsonify({"message": "Failed to generate icon"}), 500

@app.route("/api/icons/generate/batch", methods=["POST"])
@jwt_required()
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
                        icon = icon_repo.create(
                            category_id=category['id'],
                            filename=f"category_{category['id']}_icon.png",
                            file_path="",
                            prompt=f"Icon for {category['name']} category",
                            style=options.get('style', 'modern'),
                            color=options.get('color', '#3B82F6'),
                            background=options.get('background', 'transparent'),
                            model=options.get('model', 'gpt-image-1'),
                            status=IconStatus.GENERATING.value,
                            generation_batch_id=batch_id,
                            created_by=user_id
                        )
                        
                        # Generate icon
                        result = icon_generator.generate_category_icon(
                            category_id=category['id'],
                            category_name=category['name'],
                            style=options.get('style', 'modern'),
                            color=options.get('color', '#3B82F6')
                        )
                        
                        if result['success']:
                            icon_repo.update(
                                icon.id,
                                file_path=result['file_path'],
                                filename=os.path.basename(result['file_path']),
                                status=IconStatus.ACTIVE.value
                            )
                            results.append({'category_id': category['id'], 'success': True})
                        else:
                            icon_repo.update_status(icon.id, IconStatus.FAILED.value, result.get('error'))
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
@jwt_required()
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
@jwt_required()
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
@jwt_required()
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
@jwt_required()
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

# Shopify Collections Endpoints (syncs with categories)
@app.route("/api/collections", methods=["GET"])
@jwt_required()
def get_collections():
    """Get all collections (categories) with their Shopify status."""
    try:
        with db_session_scope() as session:
            category_repo = CategoryRepository(session)
            icon_repo = IconRepository(session)
            
            categories = category_repo.get_all()
            
            collections = []
            for category in categories:
                # Get active icon for category
                icon = icon_repo.get_active_by_category(category.id)
                
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
@jwt_required()
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
@jwt_required()
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
@jwt_required()
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
@jwt_required()
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
@jwt_required()
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

if __name__ == "__main__":
    # Run with SocketIO
    socketio.run(app, debug=True, port=3560, allow_unsafe_werkzeug=True)