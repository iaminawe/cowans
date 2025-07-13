"""Celery configuration for background task processing."""
from celery import Celery
from config import Config
import os

def make_celery(app_name=__name__):
    """Create and configure Celery instance."""
    celery = Celery(
        app_name,
        broker=Config.CELERY_BROKER_URL,
        backend=Config.CELERY_RESULT_BACKEND
    )
    
    # Update configuration - optimized for operations
    celery.conf.update(
        task_serializer=Config.CELERY_TASK_SERIALIZER,
        result_serializer=Config.CELERY_RESULT_SERIALIZER,
        accept_content=Config.CELERY_ACCEPT_CONTENT,
        timezone=Config.CELERY_TIMEZONE,
        enable_utc=Config.CELERY_ENABLE_UTC,
        task_track_started=True,
        task_send_sent_event=True,
        worker_send_task_events=True,
        result_expires=3600,  # Results expire after 1 hour
        task_acks_late=True,  # Acknowledge tasks after completion
        worker_prefetch_multiplier=1,  # One task at a time per worker
        worker_max_tasks_per_child=100,  # Restart workers after 100 tasks
        worker_disable_rate_limits=True,  # No rate limits for operations
        task_soft_time_limit=300,  # 5 minute soft limit
        task_time_limit=600,  # 10 minute hard limit
        result_compression='gzip',  # Compress large results
        task_routes={
            'tasks.shopify_sync_task': {'queue': 'sync', 'priority': 1},
            'tasks.icon_generation_task': {'queue': 'generation', 'priority': 2},
            'tasks.batch_update_task': {'queue': 'batch', 'priority': 3},
            'tasks.import_task': {'queue': 'import', 'priority': 4},
            'scripts.ftp_download': {'queue': 'download', 'priority': 5},
            'scripts.data_processing': {'queue': 'processing', 'priority': 5},
            'scripts.shopify_upload': {'queue': 'upload', 'priority': 5},
            'scripts.cleanup': {'queue': 'maintenance', 'priority': 9}
        },
        broker_transport_options={
            'visibility_timeout': 3600,
            'fanout_prefix': True,
            'fanout_patterns': True,
            'priority_steps': list(range(10)),  # 10 priority levels
            'queue_order_strategy': 'priority',
        }
    )
    
    return celery

# Create Celery instance
celery_app = make_celery()

# Import tasks
import tasks