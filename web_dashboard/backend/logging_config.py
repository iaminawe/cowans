"""Comprehensive logging configuration for the backend."""
import logging
import logging.handlers
import os
import json
from datetime import datetime
from pythonjsonlogger import jsonlogger

class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter for structured logging."""
    
    def add_fields(self, log_record, record, message_dict):
        super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)
        log_record['timestamp'] = datetime.utcnow().isoformat()
        log_record['level'] = record.levelname
        log_record['logger'] = record.name
        log_record['module'] = record.module
        log_record['function'] = record.funcName
        log_record['line'] = record.lineno

class JobLogHandler(logging.Handler):
    """Custom handler for job-specific logging."""
    
    def __init__(self, job_id, redis_client, socketio=None):
        super().__init__()
        self.job_id = job_id
        self.redis = redis_client
        self.socketio = socketio
        self.logs = []
        
    def emit(self, record):
        """Emit a log record."""
        try:
            # Format the record
            msg = self.format(record)
            
            # Store in memory
            self.logs.append({
                'timestamp': datetime.utcnow().isoformat(),
                'level': record.levelname,
                'message': msg,
                'module': record.module,
                'function': record.funcName,
                'line': record.lineno
            })
            
            # Store in Redis (keep last 1000 logs per job)
            self.redis.lpush(f"job_logs:{self.job_id}", json.dumps({
                'timestamp': datetime.utcnow().isoformat(),
                'level': record.levelname,
                'message': msg
            }))
            self.redis.ltrim(f"job_logs:{self.job_id}", 0, 999)
            
            # Emit to WebSocket if available
            if self.socketio:
                self.socketio.emit('job_log', {
                    'job_id': self.job_id,
                    'level': record.levelname,
                    'message': msg,
                    'timestamp': datetime.utcnow().isoformat()
                }, room=self.job_id)
                
        except Exception:
            self.handleError(record)

def setup_app_logging(app, log_path):
    """Setup application-wide logging."""
    # Ensure log directory exists
    os.makedirs(log_path, exist_ok=True)
    
    # Remove default handlers
    app.logger.handlers = []
    
    # Console handler with color
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    
    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_path, 'app.log'),
        maxBytes=10485760,  # 10MB
        backupCount=10
    )
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(file_formatter)
    
    # JSON file handler for structured logs
    json_handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_path, 'app.json.log'),
        maxBytes=10485760,  # 10MB
        backupCount=10
    )
    json_handler.setLevel(logging.INFO)
    json_formatter = CustomJsonFormatter()
    json_handler.setFormatter(json_formatter)
    
    # Error file handler
    error_handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_path, 'errors.log'),
        maxBytes=10485760,  # 10MB
        backupCount=10
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_formatter)
    
    # Add handlers
    app.logger.addHandler(console_handler)
    app.logger.addHandler(file_handler)
    app.logger.addHandler(json_handler)
    app.logger.addHandler(error_handler)
    
    # Set level
    app.logger.setLevel(logging.INFO)
    
    # Log startup
    app.logger.info('Application logging configured')

def get_job_logger(job_id, redis_client, socketio=None):
    """Get a logger configured for a specific job."""
    logger = logging.getLogger(f'job.{job_id}')
    logger.setLevel(logging.DEBUG)
    
    # Remove existing handlers
    logger.handlers = []
    
    # Add job-specific handler
    job_handler = JobLogHandler(job_id, redis_client, socketio)
    job_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(levelname)s - %(message)s')
    job_handler.setFormatter(formatter)
    logger.addHandler(job_handler)
    
    # Also log to file
    log_file = os.path.join('logs', 'jobs', f'{job_id}.log')
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    ))
    logger.addHandler(file_handler)
    
    return logger

class LogStreamHandler:
    """Handler for streaming logs in real-time."""
    
    def __init__(self, redis_client):
        self.redis = redis_client
        self.subscribers = {}
        
    def subscribe(self, job_id, callback):
        """Subscribe to job logs."""
        if job_id not in self.subscribers:
            self.subscribers[job_id] = []
        self.subscribers[job_id].append(callback)
        
    def unsubscribe(self, job_id, callback):
        """Unsubscribe from job logs."""
        if job_id in self.subscribers:
            self.subscribers[job_id].remove(callback)
            if not self.subscribers[job_id]:
                del self.subscribers[job_id]
                
    def get_logs(self, job_id, start=0, count=100):
        """Get logs for a job."""
        logs = self.redis.lrange(f"job_logs:{job_id}", start, start + count - 1)
        return [json.loads(log) for log in logs]
    
    def stream_logs(self, job_id):
        """Stream logs for a job using Redis pub/sub."""
        pubsub = self.redis.pubsub()
        pubsub.subscribe(f"job_logs_stream:{job_id}")
        
        for message in pubsub.listen():
            if message['type'] == 'message':
                yield json.loads(message['data'])