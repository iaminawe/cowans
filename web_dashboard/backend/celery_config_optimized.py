"""
Optimized Celery configuration for many concurrent operations with few users
"""

import os
from kombu import Queue, Exchange

# Broker settings - Redis with optimizations
broker_url = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
result_backend = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')

# Task execution settings optimized for operations
task_always_eager = False
task_eager_propagates = True
task_acks_late = True  # Acknowledge after task completion
task_reject_on_worker_lost = True
task_ignore_result = False

# Worker settings for concurrent operations
worker_prefetch_multiplier = 1  # Each worker gets 1 task at a time
worker_max_tasks_per_child = 100  # Restart after 100 tasks to prevent memory leaks
worker_disable_rate_limits = True
worker_concurrency = 4  # 4 concurrent workers for operations

# Pool settings
worker_pool = 'prefork'  # Better for CPU-bound operations
worker_pool_restarts = True

# Task routing for different operation types
task_routes = {
    'tasks.shopify_sync_task': {'queue': 'sync'},
    'tasks.icon_generation_task': {'queue': 'generation'},
    'tasks.batch_update_task': {'queue': 'batch'},
    'tasks.import_task': {'queue': 'import'},
}

# Queue configuration with priorities
task_queues = (
    Queue('sync', Exchange('sync'), routing_key='sync', priority=1),
    Queue('generation', Exchange('generation'), routing_key='generation', priority=2),
    Queue('batch', Exchange('batch'), routing_key='batch', priority=3),
    Queue('import', Exchange('import'), routing_key='import', priority=4),
    Queue('default', Exchange('default'), routing_key='default', priority=5),
)

# Task time limits
task_soft_time_limit = 300  # 5 minutes soft limit
task_time_limit = 600  # 10 minutes hard limit

# Result backend settings
result_expires = 3600  # Results expire after 1 hour
result_persistent = True
result_compression = 'gzip'  # Compress large results

# Serialization
task_serializer = 'json'
result_serializer = 'json'
accept_content = ['json']

# Performance optimizations
task_track_started = True
task_send_sent_event = True
worker_send_task_events = True

# Database connection pooling for Celery
database_engine_options = {
    'pool_size': 2,
    'max_overflow': 4,
    'pool_pre_ping': True,
    'pool_recycle': 300,
}

# Beat schedule for periodic tasks
beat_schedule = {
    'cleanup-old-results': {
        'task': 'tasks.cleanup_old_results',
        'schedule': 3600.0,  # Every hour
    },
    'sync-shopify-products': {
        'task': 'tasks.shopify_sync_task',
        'schedule': 1800.0,  # Every 30 minutes
        'options': {'queue': 'sync'}
    },
    'close-idle-connections': {
        'task': 'tasks.close_idle_db_connections',
        'schedule': 600.0,  # Every 10 minutes
    },
}

# Monitoring
worker_hijacking_timeout = 1800  # 30 minutes
worker_log_format = '[%(asctime)s: %(levelname)s/%(processName)s] %(message)s'
worker_task_log_format = '[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s'

# Redis optimizations
broker_transport_options = {
    'visibility_timeout': 3600,
    'fanout_prefix': True,
    'fanout_patterns': True,
    'priority_steps': list(range(10)),  # 10 priority levels
    'sep': ':',
    'queue_order_strategy': 'priority',
}

# Result backend optimizations
result_backend_transport_options = {
    'master_name': 'mymaster',
    'visibility_timeout': 3600,
    'fanout_prefix': True,
    'fanout_patterns': True,
}

# Error handling
task_annotations = {
    '*': {
        'rate_limit': '100/m',  # Max 100 tasks per minute per type
        'time_limit': 600,
        'soft_time_limit': 300,
        'max_retries': 3,
        'default_retry_delay': 60,
    }
}