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
    
    # Update configuration
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
        worker_prefetch_multiplier=1,  # Disable prefetching for better job distribution
        task_routes={
            'scripts.ftp_download': {'queue': 'download'},
            'scripts.data_processing': {'queue': 'processing'},
            'scripts.shopify_upload': {'queue': 'upload'},
            'scripts.cleanup': {'queue': 'maintenance'}
        }
    )
    
    return celery

# Create Celery instance
celery_app = make_celery()

# Import tasks
import tasks