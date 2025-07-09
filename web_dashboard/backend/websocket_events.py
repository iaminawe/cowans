"""
WebSocket event handlers for real-time updates.
"""

import os
import logging
import json
from flask_socketio import emit, join_room, leave_room
from flask import request
import redis

logger = logging.getLogger(__name__)

# Redis client for pub/sub
redis_client = redis.Redis(
    host=os.getenv('REDIS_HOST', 'localhost'),
    port=int(os.getenv('REDIS_PORT', 6379)),
    db=0,
    decode_responses=True
)

def register_websocket_events(socketio):
    """Register WebSocket event handlers."""
    
    @socketio.on('connect')
    def handle_connect():
        """Handle client connection."""
        client_id = request.sid
        logger.info(f"Client connected: {client_id}")
        emit('connected', {'client_id': client_id})
    
    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle client disconnection."""
        client_id = request.sid
        logger.info(f"Client disconnected: {client_id}")
    
    @socketio.on('subscribe_batch')
    def handle_subscribe_batch(data):
        """Subscribe to batch progress updates."""
        batch_id = data.get('batch_id')
        if batch_id:
            room = f"batch_{batch_id}"
            join_room(room)
            logger.info(f"Client {request.sid} subscribed to batch {batch_id}")
            emit('subscribed', {'batch_id': batch_id, 'room': room})
    
    @socketio.on('unsubscribe_batch')
    def handle_unsubscribe_batch(data):
        """Unsubscribe from batch progress updates."""
        batch_id = data.get('batch_id')
        if batch_id:
            room = f"batch_{batch_id}"
            leave_room(room)
            logger.info(f"Client {request.sid} unsubscribed from batch {batch_id}")
            emit('unsubscribed', {'batch_id': batch_id})
    
    @socketio.on('subscribe_all_batches')
    def handle_subscribe_all_batches():
        """Subscribe to all batch updates for the user."""
        join_room('all_batches')
        logger.info(f"Client {request.sid} subscribed to all batches")
        emit('subscribed', {'room': 'all_batches'})
    
    # Redis pub/sub listener for batch updates
    def redis_listener():
        """Listen for Redis pub/sub messages and emit to WebSocket clients."""
        pubsub = redis_client.pubsub()
        pubsub.subscribe('batch_updates')
        
        for message in pubsub.listen():
            if message['type'] == 'message':
                try:
                    data = json.loads(message['data'])
                    batch_id = data.get('batch_id')
                    
                    if batch_id:
                        # Emit to specific batch room
                        room = f"batch_{batch_id}"
                        socketio.emit('batch_progress', data, room=room)
                        
                        # Also emit to all_batches room
                        socketio.emit('batch_update', data, room='all_batches')
                        
                except Exception as e:
                    logger.error(f"Error processing Redis message: {e}")
    
    # Start Redis listener in background
    socketio.start_background_task(redis_listener)

def emit_batch_progress(batch_id: str, progress_data: dict):
    """Emit batch progress update via Redis pub/sub."""
    try:
        message = {
            'batch_id': batch_id,
            **progress_data
        }
        redis_client.publish('batch_updates', json.dumps(message))
    except Exception as e:
        logger.error(f"Error emitting batch progress: {e}")

def emit_icon_generated(batch_id: str, icon_data: dict):
    """Emit icon generation completion event."""
    try:
        message = {
            'batch_id': batch_id,
            'event': 'icon_generated',
            'icon': icon_data
        }
        redis_client.publish('batch_updates', json.dumps(message))
    except Exception as e:
        logger.error(f"Error emitting icon generated event: {e}")

def emit_batch_completed(batch_id: str, summary: dict):
    """Emit batch completion event."""
    try:
        message = {
            'batch_id': batch_id,
            'event': 'batch_completed',
            'summary': summary
        }
        redis_client.publish('batch_updates', json.dumps(message))
    except Exception as e:
        logger.error(f"Error emitting batch completed event: {e}")