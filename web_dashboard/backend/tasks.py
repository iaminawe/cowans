"""Celery tasks for background processing."""
from celery import current_task
from celery_app import celery_app
import subprocess
import os
import sys
from datetime import datetime
from config import Config
import json
from icon_generator import IconGenerator
from icon_storage import IconStorage

@celery_app.task(bind=True, name='scripts.execute')
def execute_script(self, script_name, parameters, job_id):
    """Execute a script as a Celery task."""
    # Update task state
    current_task.update_state(
        state='PROGRESS',
        meta={
            'current': 0,
            'total': 100,
            'status': 'Starting script execution...'
        }
    )
    
    try:
        # Map script names to actual script paths
        script_mapping = {
            'ftp_download': 'utilities/ftp_downloader.py',
            'filter_products': 'data_processing/filter_products.py',
            'create_metafields': 'data_processing/create_metafields.py',
            'shopify_upload': 'shopify/shopify_uploader_new.py',
            'cleanup_duplicates': 'cleanup/cleanup_duplicate_images.py',
            'categorize_products': 'data_processing/categorize_products.py',
            'full_import': 'run_import.py'
        }
        
        script_path = os.path.join(
            Config.SCRIPTS_BASE_PATH,
            script_mapping.get(script_name, script_name)
        )
        
        if not os.path.exists(script_path):
            raise FileNotFoundError(f"Script not found: {script_path}")
        
        # Build command
        cmd = [sys.executable, script_path]
        
        # Add parameters
        for param in parameters:
            if param['type'] == 'boolean' and param['value']:
                cmd.append(f"--{param['name']}")
            elif param['type'] != 'boolean':
                cmd.append(f"--{param['name']}")
                cmd.append(str(param['value']))
        
        # Create log file
        log_file = os.path.join(Config.LOG_PATH, f"job_{job_id}.log")
        
        # Execute script
        output_lines = []
        with open(log_file, 'w') as log:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            line_count = 0
            for line in process.stdout:
                log.write(line)
                log.flush()
                output_lines.append(line.strip())
                line_count += 1
                
                # Update progress periodically
                if line_count % 10 == 0:
                    current_task.update_state(
                        state='PROGRESS',
                        meta={
                            'current': min(line_count, 90),
                            'total': 100,
                            'status': f'Processing... ({line_count} lines)',
                            'latest_output': output_lines[-10:]  # Last 10 lines
                        }
                    )
                
                # Parse progress if available
                if 'progress:' in line.lower():
                    try:
                        progress = int(line.split('progress:')[1].strip().split()[0])
                        current_task.update_state(
                            state='PROGRESS',
                            meta={
                                'current': progress,
                                'total': 100,
                                'status': f'Progress: {progress}%',
                                'latest_output': output_lines[-10:]
                            }
                        )
                    except:
                        pass
            
            process.wait()
            
            if process.returncode == 0:
                return {
                    'status': 'completed',
                    'returncode': 0,
                    'output': output_lines,
                    'log_file': log_file
                }
            else:
                raise subprocess.CalledProcessError(process.returncode, cmd)
                
    except Exception as e:
        # Log the error
        current_task.update_state(
            state='FAILURE',
            meta={
                'exc_type': type(e).__name__,
                'exc_message': str(e),
                'status': 'Failed'
            }
        )
        raise

@celery_app.task(bind=True, name='icons.generate_batch')
def generate_icon_batch_task(self, categories, options, job_id):
    """Generate icons for multiple categories as a batch task."""
    # Update task state
    current_task.update_state(
        state='PROGRESS',
        meta={
            'current': 0,
            'total': len(categories),
            'status': 'Starting batch icon generation...'
        }
    )
    
    try:
        icon_generator = IconGenerator()
        icon_storage = IconStorage()
        
        results = []
        failed_count = 0
        
        for i, category in enumerate(categories):
            try:
                # Update progress
                current_task.update_state(
                    state='PROGRESS',
                    meta={
                        'current': i,
                        'total': len(categories),
                        'status': f'Generating icon for {category["name"]}...'
                    }
                )
                
                # Generate icon
                result = icon_generator.generate_category_icon(
                    category_id=category['id'],
                    category_name=category['name'],
                    style=options.get('style', 'modern'),
                    color=options.get('color', '#3B82F6'),
                    size=options.get('size', 128),
                    background=options.get('background', 'transparent')
                )
                
                if result['success']:
                    # Save icon record
                    icon_record = icon_storage.save_icon(
                        category_id=category['id'],
                        category_name=category['name'],
                        file_path=result['file_path'],
                        metadata={
                            'style': options.get('style', 'modern'),
                            'color': options.get('color', '#3B82F6'),
                            'size': options.get('size', 128),
                            'background': options.get('background', 'transparent'),
                            'batch_job_id': job_id
                        }
                    )
                    results.append({
                        'category_id': category['id'],
                        'category_name': category['name'],
                        'success': True,
                        'icon': icon_record
                    })
                else:
                    failed_count += 1
                    results.append({
                        'category_id': category['id'],
                        'category_name': category['name'],
                        'success': False,
                        'error': result.get('error', 'Unknown error')
                    })
                    
            except Exception as e:
                failed_count += 1
                results.append({
                    'category_id': category['id'],
                    'category_name': category['name'],
                    'success': False,
                    'error': str(e)
                })
        
        # Final update
        success_count = len(categories) - failed_count
        return {
            'status': 'completed',
            'total_categories': len(categories),
            'success_count': success_count,
            'failed_count': failed_count,
            'results': results
        }
        
    except Exception as e:
        # Log the error
        current_task.update_state(
            state='FAILURE',
            meta={
                'exc_type': type(e).__name__,
                'exc_message': str(e),
                'status': 'Failed'
            }
        )
        raise

@celery_app.task(name='scripts.cleanup_old_jobs')
def cleanup_old_jobs():
    """Periodic task to clean up old job data."""
    from job_manager import JobManager
    import redis
    
    redis_client = redis.from_url(Config.REDIS_URL)
    job_manager = JobManager(redis_client)
    
    count = job_manager.cleanup_old_jobs()
    return f"Cleaned up {count} old jobs"

@celery_app.task(name='icons.cleanup_old_icons')
def cleanup_old_icons():
    """Periodic task to clean up orphaned icon files."""
    icon_storage = IconStorage()
    count = icon_storage.cleanup_orphaned_files()
    return f"Cleaned up {count} orphaned icon files"

# Celery beat schedule for periodic tasks
from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    'cleanup-old-jobs': {
        'task': 'scripts.cleanup_old_jobs',
        'schedule': crontab(hour=3, minute=0),  # Run daily at 3 AM
    },
    'cleanup-old-icons': {
        'task': 'icons.cleanup_old_icons',
        'schedule': crontab(hour=3, minute=30),  # Run daily at 3:30 AM
    },
}