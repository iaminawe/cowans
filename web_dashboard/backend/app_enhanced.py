from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_socketio import SocketIO, emit
from datetime import timedelta
import os
import subprocess
import threading
import time
import json
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "http://localhost:3055"}})
socketio = SocketIO(app, cors_allowed_origins="http://localhost:3055")

# JWT Configuration
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "dev-secret-key")
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=1)
jwt = JWTManager(app)

# Mock user for testing
MOCK_USER = {
    "email": "test@example.com",
    "password": "test123"
}

# Script execution tracking
active_scripts = {}

@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json()
    
    if not data or not data.get("email") or not data.get("password"):
        return jsonify({"message": "Missing email or password"}), 400
        
    if data["email"] == MOCK_USER["email"] and data["password"] == MOCK_USER["password"]:
        access_token = create_access_token(identity=data["email"])
        return jsonify({
            "access_token": access_token,
            "user": {"email": data["email"]}
        })
    
    return jsonify({"message": "Invalid credentials"}), 401

@app.route("/api/sync/trigger", methods=["POST"])
@jwt_required()
def trigger_sync():
    """Trigger the full import workflow"""
    def run_sync():
        try:
            # Emit initial status
            socketio.emit('status', {
                'type': 'status',
                'data': {'status': 'starting', 'message': 'Initializing sync process...'},
                'timestamp': time.time()
            })
            
            # Define stages for progress tracking
            stages = [
                {'id': 'download', 'name': 'FTP Download', 'status': 'pending'},
                {'id': 'filter', 'name': 'Filter Products', 'status': 'pending'},
                {'id': 'metafields', 'name': 'Create Metafields', 'status': 'pending'},
                {'id': 'upload', 'name': 'Upload to Shopify', 'status': 'pending'}
            ]
            
            socketio.emit('progress', {
                'type': 'progress',
                'data': {'stages': stages},
                'timestamp': time.time()
            })
            
            # Simulate stage execution
            for i, stage in enumerate(stages):
                # Update stage status
                stages[i]['status'] = 'running'
                stages[i]['startTime'] = time.time()
                stages[i]['progress'] = 0
                
                socketio.emit('progress', {
                    'type': 'progress',
                    'data': {'stages': stages},
                    'timestamp': time.time()
                })
                
                # Simulate progress
                for progress in range(0, 101, 20):
                    time.sleep(1)  # Simulate work
                    stages[i]['progress'] = progress
                    
                    socketio.emit('progress', {
                        'type': 'progress',
                        'data': {'stages': stages},
                        'timestamp': time.time()
                    })
                    
                    socketio.emit('log', {
                        'type': 'log',
                        'data': {
                            'level': 'info',
                            'message': f"{stage['name']}: Processing... {progress}%",
                            'source': 'sync'
                        },
                        'timestamp': time.time()
                    })
                
                # Complete stage
                stages[i]['status'] = 'completed'
                stages[i]['endTime'] = time.time()
                stages[i]['progress'] = 100
                
                socketio.emit('progress', {
                    'type': 'progress',
                    'data': {'stages': stages},
                    'timestamp': time.time()
                })
            
            socketio.emit('complete', {
                'type': 'complete',
                'data': {'status': 'success', 'message': 'Sync completed successfully'},
                'timestamp': time.time()
            })
                
        except Exception as e:
            socketio.emit('error', {
                'type': 'error',
                'data': {'status': 'error', 'message': str(e)},
                'timestamp': time.time()
            })
    
    # Start sync in background thread
    thread = threading.Thread(target=run_sync)
    thread.start()
    
    return jsonify({"message": "Sync triggered successfully"})

@app.route("/api/sync/history", methods=["GET"])
@jwt_required()
def get_sync_history():
    # Mock sync history
    history = [
        {
            "id": "1",
            "timestamp": "2025-05-29T16:00:00Z",
            "status": "success",
            "message": "Successfully synced 100 products"
        }
    ]
    return jsonify(history)

# WebSocket event handlers
@socketio.on('connect')
def handle_connect():
    print(f"Client connected: {request.sid}")
    emit('connected', {'data': 'Connected to server'})

@socketio.on('disconnect')
def handle_disconnect():
    print(f"Client disconnected: {request.sid}")

@socketio.on('execute')
def handle_execute(data):
    """Execute a script with the provided parameters"""
    script_id = data.get('scriptId')
    parameters = data.get('parameters', {})
    
    # Map script IDs to actual script paths
    script_map = {
        'ftp_download': 'scripts/utilities/ftp_downloader.py',
        'filter_products': 'scripts/data_processing/filter_products.py',
        'create_metafields': 'scripts/data_processing/create_metafields.py',
        'shopify_upload': 'scripts/shopify/shopify_uploader_new.py',
        'cleanup_duplicates': 'scripts/cleanup/cleanup_duplicate_images.py',
        'full_import': 'scripts/run_import.py'
    }
    
    script_path = script_map.get(script_id)
    if not script_path:
        emit('error', {
            'type': 'error',
            'data': {'message': f'Unknown script: {script_id}'},
            'timestamp': time.time()
        })
        return
    
    def run_script():
        try:
            # Build command based on script and parameters
            cmd = ['python', script_path]
            
            # Add parameters based on script type
            if script_id == 'filter_products':
                if parameters.get('inputFile'):
                    cmd.append(parameters['inputFile'])
                if parameters.get('referenceFile'):
                    cmd.append(parameters['referenceFile'])
                if parameters.get('debug'):
                    cmd.append('--debug')
            elif script_id == 'shopify_upload':
                if parameters.get('csvFile'):
                    cmd.append(parameters['csvFile'])
                cmd.extend(['--shop-url', os.getenv('SHOPIFY_SHOP_URL', '')])
                cmd.extend(['--access-token', os.getenv('SHOPIFY_ACCESS_TOKEN', '')])
                if parameters.get('skipImages'):
                    cmd.append('--skip-images')
                if parameters.get('batchSize'):
                    cmd.extend(['--batch-size', str(parameters['batchSize'])])
            elif script_id == 'full_import':
                cmd.append('--no-sound')
                if parameters.get('skipDownload'):
                    cmd.append('--skip-download')
                if parameters.get('skipFilter'):
                    cmd.append('--skip-filter')
                if parameters.get('skipMetafields'):
                    cmd.append('--skip-metafields')
                if parameters.get('skipUpload'):
                    cmd.append('--skip-upload')
            
            # Emit start event
            emit('status', {
                'type': 'status',
                'data': {'status': 'starting', 'script': script_id},
                'timestamp': time.time()
            })
            
            # For demo purposes, simulate script execution
            emit('log', {
                'type': 'log',
                'data': {
                    'level': 'info',
                    'message': f'Starting {script_id} with parameters: {json.dumps(parameters)}',
                    'source': script_id
                },
                'timestamp': time.time()
            })
            
            # Simulate some output
            for i in range(5):
                time.sleep(1)
                emit('log', {
                    'type': 'log',
                    'data': {
                        'level': 'info',
                        'message': f'Processing step {i+1}/5...',
                        'source': script_id
                    },
                    'timestamp': time.time()
                })
            
            # Complete
            emit('complete', {
                'type': 'complete',
                'data': {'status': 'success', 'script': script_id},
                'timestamp': time.time()
            })
                
        except Exception as e:
            emit('error', {
                'type': 'error',
                'data': {'message': str(e), 'script': script_id},
                'timestamp': time.time()
            })
    
    # Run script in background thread
    thread = threading.Thread(target=run_script)
    thread.start()

if __name__ == "__main__":
    socketio.run(app, debug=True, port=3560)