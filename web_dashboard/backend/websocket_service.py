"""WebSocket service for real-time updates."""
import time
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from flask_socketio import emit, join_room, leave_room

logger = logging.getLogger(__name__)


@dataclass
class WebSocketEvent:
    """Represents a WebSocket event."""
    type: str
    data: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    room: Optional[str] = None
    broadcast: bool = False


class WebSocketService:
    """Service for managing WebSocket communications."""
    
    def __init__(self, socketio):
        """Initialize WebSocket service.
        
        Args:
            socketio: Flask-SocketIO instance
        """
        self.socketio = socketio
        self.connected_clients: Dict[str, Dict[str, Any]] = {}
        self.active_operations: Dict[str, Dict[str, Any]] = {}
        
    def register_client(self, sid: str, user_id: Optional[int] = None) -> None:
        """Register a connected client.
        
        Args:
            sid: Socket ID
            user_id: Optional user ID for authenticated clients
        """
        self.connected_clients[sid] = {
            'connected_at': datetime.utcnow(),
            'user_id': user_id,
            'rooms': set()
        }
        logger.info(f"Client registered: {sid} (user_id: {user_id})")
        
    def unregister_client(self, sid: str) -> None:
        """Unregister a disconnected client.
        
        Args:
            sid: Socket ID
        """
        if sid in self.connected_clients:
            del self.connected_clients[sid]
            logger.info(f"Client unregistered: {sid}")
            
    def join_operation_room(self, sid: str, operation_id: str) -> None:
        """Join a client to an operation-specific room.
        
        Args:
            sid: Socket ID
            operation_id: Operation ID
        """
        room = f"operation:{operation_id}"
        join_room(room, sid=sid)
        if sid in self.connected_clients:
            self.connected_clients[sid]['rooms'].add(room)
        logger.info(f"Client {sid} joined room {room}")
        
    def leave_operation_room(self, sid: str, operation_id: str) -> None:
        """Remove a client from an operation-specific room.
        
        Args:
            sid: Socket ID
            operation_id: Operation ID
        """
        room = f"operation:{operation_id}"
        leave_room(room, sid=sid)
        if sid in self.connected_clients:
            self.connected_clients[sid]['rooms'].discard(room)
        logger.info(f"Client {sid} left room {room}")
        
    def emit_event(self, event: WebSocketEvent) -> None:
        """Emit a WebSocket event.
        
        Args:
            event: WebSocketEvent instance
        """
        emit_args = {
            'event': event.type,
            'data': {
                'type': event.type,
                'data': event.data,
                'timestamp': event.timestamp
            }
        }
        
        if event.room:
            emit_args['room'] = event.room
        
        if event.broadcast:
            emit_args['broadcast'] = True
            
        self.socketio.emit(**emit_args)
        
    def emit_operation_start(self, operation_id: str, operation_type: str, 
                           description: str, total_steps: Optional[int] = None) -> None:
        """Emit operation start event.
        
        Args:
            operation_id: Unique operation ID
            operation_type: Type of operation (sync, import, etc.)
            description: Human-readable description
            total_steps: Optional total number of steps
        """
        self.active_operations[operation_id] = {
            'type': operation_type,
            'description': description,
            'started_at': datetime.utcnow(),
            'total_steps': total_steps,
            'current_step': 0,
            'status': 'running'
        }
        
        event = WebSocketEvent(
            type='operation_start',
            data={
                'operation_id': operation_id,
                'type': operation_type,
                'description': description,
                'total_steps': total_steps
            },
            room=f"operation:{operation_id}"
        )
        self.emit_event(event)
        
    def emit_operation_progress(self, operation_id: str, current_step: int, 
                              message: str, progress_percentage: Optional[float] = None) -> None:
        """Emit operation progress event.
        
        Args:
            operation_id: Operation ID
            current_step: Current step number
            message: Progress message
            progress_percentage: Optional progress percentage (0-100)
        """
        if operation_id in self.active_operations:
            self.active_operations[operation_id]['current_step'] = current_step
            
        if progress_percentage is None and operation_id in self.active_operations:
            total = self.active_operations[operation_id].get('total_steps')
            if total:
                progress_percentage = (current_step / total) * 100
                
        event = WebSocketEvent(
            type='operation_progress',
            data={
                'operation_id': operation_id,
                'current_step': current_step,
                'message': message,
                'progress_percentage': progress_percentage
            },
            room=f"operation:{operation_id}"
        )
        self.emit_event(event)
        
    def emit_operation_log(self, operation_id: str, level: str, message: str, 
                         source: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> None:
        """Emit operation log event.
        
        Args:
            operation_id: Operation ID
            level: Log level (info, warning, error, debug)
            message: Log message
            source: Optional source identifier
            details: Optional additional details
        """
        event = WebSocketEvent(
            type='operation_log',
            data={
                'operation_id': operation_id,
                'level': level,
                'message': message,
                'source': source,
                'details': details
            },
            room=f"operation:{operation_id}"
        )
        self.emit_event(event)
        
    def emit_operation_complete(self, operation_id: str, status: str, 
                              result: Optional[Dict[str, Any]] = None, error: Optional[str] = None) -> None:
        """Emit operation complete event.
        
        Args:
            operation_id: Operation ID
            status: Final status (success, error, cancelled)
            result: Optional result data
            error: Optional error message
        """
        if operation_id in self.active_operations:
            self.active_operations[operation_id]['status'] = status
            self.active_operations[operation_id]['completed_at'] = datetime.utcnow()
            
        event = WebSocketEvent(
            type='operation_complete',
            data={
                'operation_id': operation_id,
                'status': status,
                'result': result,
                'error': error
            },
            room=f"operation:{operation_id}"
        )
        self.emit_event(event)
        
        # Clean up after a delay
        if operation_id in self.active_operations:
            # In production, use a scheduled task to clean up
            # For now, just mark as completed
            pass
            
    def emit_sync_status(self, sync_id: str, status: Dict[str, Any]) -> None:
        """Emit sync status update.
        
        Args:
            sync_id: Sync operation ID
            status: Status dictionary with sync details
        """
        event = WebSocketEvent(
            type='sync_status',
            data={
                'sync_id': sync_id,
                **status
            },
            broadcast=True  # Broadcast to all connected clients
        )
        self.emit_event(event)
        
    def emit_import_status(self, import_id: str, status: Dict[str, Any]) -> None:
        """Emit import status update.
        
        Args:
            import_id: Import operation ID
            status: Status dictionary with import details
        """
        event = WebSocketEvent(
            type='import_status',
            data={
                'import_id': import_id,
                **status
            },
            broadcast=True
        )
        self.emit_event(event)
        
    def emit_error(self, error_type: str, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Emit error event.
        
        Args:
            error_type: Type of error
            message: Error message
            details: Optional error details
        """
        event = WebSocketEvent(
            type='error',
            data={
                'error_type': error_type,
                'message': message,
                'details': details
            },
            broadcast=True
        )
        self.emit_event(event)
        
    def get_active_operations(self) -> List[Dict[str, Any]]:
        """Get list of active operations.
        
        Returns:
            List of active operation details
        """
        return [
            {
                'operation_id': op_id,
                **op_data
            }
            for op_id, op_data in self.active_operations.items()
            if op_data.get('status') == 'running'
        ]
        
    def get_connected_clients_count(self) -> int:
        """Get count of connected clients.
        
        Returns:
            Number of connected clients
        """
        return len(self.connected_clients)