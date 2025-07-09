from flask import Flask, jsonify, request, send_file, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
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
    SyncHistorySchema, ScriptDefinitionSchema
)
from job_manager import JobManager
from script_registry import (
    get_script_info, get_all_scripts, validate_script_parameters
)

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

# Mock user for testing (replace with Supabase later)
MOCK_USER = {
    "email": "test@example.com",
    "password": "test123"
}

# Schemas
login_schema = LoginSchema()
script_execution_schema = ScriptExecutionSchema()
job_status_schema = JobStatusSchema()
sync_history_schema = SyncHistorySchema()
script_definition_schema = ScriptDefinitionSchema()

# Helper function to run async functions in Flask
def run_async(coro):
    """Run async function in Flask context."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

@app.route("/api/auth/login", methods=["POST"])
def login():
    """Handle user login."""
    try:
        data = login_schema.load(request.get_json())
    except Exception as e:
        return jsonify({"message": "Invalid request data", "errors": str(e)}), 400
        
    if data["email"] == MOCK_USER["email"] and data["password"] == MOCK_USER["password"]:
        access_token = create_access_token(identity=data["email"])
        app.logger.info(f"User logged in: {data['email']}")
        return jsonify({
            "access_token": access_token,
            "user": {"email": data["email"]}
        })
    
    app.logger.warning(f"Failed login attempt for: {data['email']}")
    return jsonify({"message": "Invalid credentials"}), 401

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
    
    if job_manager:
        job_id = job_manager.create_job(
            script_name=data['script_name'],
            parameters=data['parameters'],
            user_id=user_id
        )
        
        # Execute job asynchronously
        job_manager.execute_job(job_id, socketio)
        
        app.logger.info(f"Job created: {job_id} for script: {data['script_name']} by user: {user_id}")
        
        return jsonify({
            "job_id": job_id,
            "message": "Job created successfully"
        }), 201
    else:
        # Fallback without Redis
        import uuid
        job_id = str(uuid.uuid4())
        app.logger.info(f"Simple execution: {job_id} for script: {data['script_name']} by user: {user_id}")
        
        return jsonify({
            "job_id": job_id,
            "message": "Script execution started (Redis not available)"
        }), 201

@app.route("/api/jobs/<job_id>", methods=["GET"])
@jwt_required()
def get_job_status(job_id):
    """Get status of a specific job (mock for development)."""
    return jsonify({
        "job_id": job_id,
        "status": "completed",
        "script_name": "mock_script",
        "progress": 100,
        "message": "Job completed successfully"
    })

@app.route("/api/jobs/<job_id>/cancel", methods=["POST"])
@jwt_required()
def cancel_job(job_id):
    """Cancel a running job (mock for development)."""
    return jsonify({"message": "Job cancelled successfully"})

@app.route("/api/jobs/<job_id>/logs", methods=["GET"])
@jwt_required()
def get_job_logs(job_id):
    """Get log file for a job (mock for development)."""
    return jsonify({"message": "Log file not found"}), 404

@app.route("/api/jobs", methods=["GET"])
@jwt_required()
def get_user_jobs():
    """Get jobs for the current user (mock for development)."""
    return jsonify([])

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
    """Get sync history (mock data for development)."""
    from datetime import datetime, timedelta
    
    # Mock sync history data
    history = [
        {
            "id": 1,
            "timestamp": (datetime.now() - timedelta(hours=2)).isoformat(),
            "status": "success",
            "message": "Sync completed successfully",
            "duration": 120
        },
        {
            "id": 2,
            "timestamp": (datetime.now() - timedelta(days=1)).isoformat(),
            "status": "success", 
            "message": "Sync completed successfully",
            "duration": 95
        }
    ]
    
    return jsonify(history)

# Icon Generation API Endpoints

@app.route("/api/icons/generate", methods=["POST"])
@jwt_required()
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
        user_id = get_jwt_identity()
        
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
@jwt_required()
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
                    user_id=get_jwt_identity(),
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

@app.route("/api/icons/batch/<batch_id>/status", methods=["GET"])
@jwt_required()
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
@jwt_required()
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
@jwt_required()
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
@jwt_required()
def list_user_batches():
    """List user's batch generation jobs."""
    try:
        user_id = get_jwt_identity()
        
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
@jwt_required()
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
@jwt_required()
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
@jwt_required()
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
@jwt_required()
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
        images_path = Path(app.config['IMAGES_STORAGE_PATH'])
        return send_from_directory(images_path, filename)
    except Exception as e:
        app.logger.error(f"Error serving image: {e}")
        return jsonify({"message": "Image not found"}), 404

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

@socketio.on('join_batch')
def handle_join_batch(data):
    """Join a batch room for progress updates."""
    batch_id = data.get('batch_id')
    if batch_id:
        join_room(batch_id)
        app.logger.info(f"Client {request.sid} joined batch room {batch_id}")

@socketio.on('leave_batch')
def handle_leave_batch(data):
    """Leave a batch room."""
    batch_id = data.get('batch_id')
    if batch_id:
        leave_room(batch_id)
        app.logger.info(f"Client {request.sid} left batch room {batch_id}")

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
    
    # Check OpenAI API key
    openai_status = "configured" if os.getenv('OPENAI_API_KEY') else "not_configured"
    
    return jsonify({
        "status": "healthy",
        "services": {
            "redis": redis_status,
            "flask": "healthy",
            "openai": openai_status
        }
    })

if __name__ == "__main__":
    # Run with SocketIO
    socketio.run(app, debug=True, port=3560, allow_unsafe_werkzeug=True)