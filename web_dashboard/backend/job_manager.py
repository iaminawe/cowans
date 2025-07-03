"""Job management system for script execution."""
import uuid
import json
import subprocess
import threading
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import redis
from config import Config

class JobManager:
    """Manages script execution jobs."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.jobs = {}  # In-memory job tracking
        self.job_threads = {}
        
    def create_job(self, script_name: str, parameters: List[Dict], user_id: str) -> str:
        """Create a new job."""
        job_id = str(uuid.uuid4())
        job_data = {
            'job_id': job_id,
            'script_name': script_name,
            'parameters': parameters,
            'user_id': user_id,
            'status': 'pending',
            'created_at': datetime.utcnow().isoformat(),
            'started_at': None,
            'completed_at': None,
            'progress': 0,
            'current_stage': None,
            'output': [],
            'error': None,
            'result': None
        }
        
        # Store in Redis
        self.redis.setex(
            f"job:{job_id}",
            timedelta(days=Config.JOB_RETENTION_DAYS),
            json.dumps(job_data)
        )
        
        # Store in memory for quick access
        self.jobs[job_id] = job_data
        
        return job_id
    
    def get_job(self, job_id: str) -> Optional[Dict]:
        """Get job details."""
        # Try memory first
        if job_id in self.jobs:
            return self.jobs[job_id]
        
        # Try Redis
        job_data = self.redis.get(f"job:{job_id}")
        if job_data:
            return json.loads(job_data)
        
        return None
    
    def update_job(self, job_id: str, updates: Dict) -> bool:
        """Update job status."""
        job = self.get_job(job_id)
        if not job:
            return False
        
        job.update(updates)
        
        # Update in Redis
        self.redis.setex(
            f"job:{job_id}",
            timedelta(days=Config.JOB_RETENTION_DAYS),
            json.dumps(job)
        )
        
        # Update in memory
        if job_id in self.jobs:
            self.jobs[job_id] = job
        
        return True
    
    def execute_job(self, job_id: str, socketio=None) -> None:
        """Execute a job in a separate thread."""
        job = self.get_job(job_id)
        if not job:
            return
        
        thread = threading.Thread(
            target=self._run_job,
            args=(job_id, socketio)
        )
        thread.daemon = True
        thread.start()
        
        self.job_threads[job_id] = thread
    
    def _run_job(self, job_id: str, socketio=None) -> None:
        """Run the actual job."""
        job = self.get_job(job_id)
        if not job:
            return
        
        # Update status to running
        self.update_job(job_id, {
            'status': 'running',
            'started_at': datetime.utcnow().isoformat()
        })
        
        try:
            # Handle icon generation batch task
            if job['script_name'] == 'icon_generation_batch':
                self._run_icon_batch_job(job_id, job, socketio)
                return
            
            # Handle Shopify collection icon generation task
            if job['script_name'] == 'shopify_collection_icon_generation':
                self._run_shopify_collection_icon_job(job_id, job, socketio)
                return
            
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
                script_mapping.get(job['script_name'], job['script_name'])
            )
            
            if not os.path.exists(script_path):
                raise FileNotFoundError(f"Script not found: {script_path}")
            
            # Build command
            cmd = [sys.executable, script_path]
            
            # Add parameters
            for param in job['parameters']:
                if param['type'] == 'boolean' and param['value']:
                    cmd.append(f"--{param['name']}")
                elif param['type'] != 'boolean':
                    cmd.append(f"--{param['name']}")
                    cmd.append(str(param['value']))
            
            # Create log file
            log_file = os.path.join(Config.LOG_PATH, f"job_{job_id}.log")
            
            # Execute script
            with open(log_file, 'w') as log:
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
                
                # Stream output
                for line in process.stdout:
                    log.write(line)
                    log.flush()
                    
                    # Update job output
                    job['output'].append(line.strip())
                    self.update_job(job_id, {'output': job['output']})
                    
                    # Emit to websocket if available
                    if socketio:
                        socketio.emit('job_output', {
                            'job_id': job_id,
                            'line': line.strip()
                        }, room=job_id)
                    
                    # Parse progress if available
                    if 'progress:' in line.lower():
                        try:
                            progress = int(line.split('progress:')[1].strip().split()[0])
                            self.update_job(job_id, {'progress': progress})
                            
                            if socketio:
                                socketio.emit('job_progress', {
                                    'job_id': job_id,
                                    'progress': progress
                                }, room=job_id)
                        except:
                            pass
                    
                    # Parse stage if available
                    if 'stage:' in line.lower():
                        stage = line.split('stage:')[1].strip()
                        self.update_job(job_id, {'current_stage': stage})
                        
                        if socketio:
                            socketio.emit('job_stage', {
                                'job_id': job_id,
                                'stage': stage
                            }, room=job_id)
                
                process.wait()
                
                if process.returncode == 0:
                    self.update_job(job_id, {
                        'status': 'completed',
                        'completed_at': datetime.utcnow().isoformat(),
                        'progress': 100
                    })
                    
                    if socketio:
                        socketio.emit('job_completed', {
                            'job_id': job_id
                        }, room=job_id)
                else:
                    raise subprocess.CalledProcessError(process.returncode, cmd)
                    
        except Exception as e:
            error_msg = str(e)
            self.update_job(job_id, {
                'status': 'failed',
                'completed_at': datetime.utcnow().isoformat(),
                'error': error_msg
            })
            
            if socketio:
                socketio.emit('job_failed', {
                    'job_id': job_id,
                    'error': error_msg
                }, room=job_id)
    
    def _run_icon_batch_job(self, job_id: str, job: Dict[str, Any], socketio=None) -> None:
        """Run icon generation batch job."""
        from icon_generator import IconGenerator
        from icon_storage import IconStorage
        
        try:
            # Extract parameters
            categories = None
            options = {}
            
            for param in job['parameters']:
                if param['name'] == 'categories':
                    categories = param['value']
                elif param['name'] == 'options':
                    options = param['value']
            
            if not categories:
                raise ValueError("No categories provided for batch icon generation")
            
            icon_generator = IconGenerator()
            icon_storage = IconStorage()
            
            total_categories = len(categories)
            results = []
            failed_count = 0
            
            for i, category in enumerate(categories):
                try:
                    # Update progress
                    progress = int((i / total_categories) * 100)
                    self.update_job(job_id, {
                        'progress': progress,
                        'current_stage': f'Generating icon for {category["name"]}'
                    })
                    
                    if socketio:
                        socketio.emit('job_progress', {
                            'job_id': job_id,
                            'progress': progress,
                            'stage': f'Generating icon for {category["name"]}'
                        }, room=job_id)
                    
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
                        
                        if socketio:
                            socketio.emit('job_output', {
                                'job_id': job_id,
                                'line': f'✓ Generated icon for {category["name"]}'
                            }, room=job_id)
                    else:
                        failed_count += 1
                        results.append({
                            'category_id': category['id'],
                            'category_name': category['name'],
                            'success': False,
                            'error': result.get('error', 'Unknown error')
                        })
                        
                        if socketio:
                            socketio.emit('job_output', {
                                'job_id': job_id,
                                'line': f'✗ Failed to generate icon for {category["name"]}: {result.get("error", "Unknown error")}'
                            }, room=job_id)
                
                except Exception as e:
                    failed_count += 1
                    error_msg = str(e)
                    results.append({
                        'category_id': category['id'],
                        'category_name': category['name'],
                        'success': False,
                        'error': error_msg
                    })
                    
                    if socketio:
                        socketio.emit('job_output', {
                            'job_id': job_id,
                            'line': f'✗ Error generating icon for {category["name"]}: {error_msg}'
                        }, room=job_id)
            
            # Complete the job
            success_count = total_categories - failed_count
            self.update_job(job_id, {
                'status': 'completed',
                'completed_at': datetime.utcnow().isoformat(),
                'progress': 100,
                'result': {
                    'total_categories': total_categories,
                    'success_count': success_count,
                    'failed_count': failed_count,
                    'results': results
                }
            })
            
            if socketio:
                socketio.emit('job_completed', {
                    'job_id': job_id,
                    'summary': f'Batch icon generation completed: {success_count} successful, {failed_count} failed'
                }, room=job_id)
        
        except Exception as e:
            error_msg = str(e)
            self.update_job(job_id, {
                'status': 'failed',
                'completed_at': datetime.utcnow().isoformat(),
                'error': error_msg
            })
            
            if socketio:
                socketio.emit('job_failed', {
                    'job_id': job_id,
                    'error': error_msg
                }, room=job_id)
    
    def _run_shopify_collection_icon_job(self, job_id: str, job: Dict[str, Any], socketio=None) -> None:
        """Run Shopify collection icon generation job."""
        from tasks_shopify_collections import generate_shopify_collection_icons_task
        
        try:
            # Extract parameters
            categories = None
            options = {}
            shop_url = None
            access_token = None
            
            for param in job['parameters']:
                if param['name'] == 'categories':
                    categories = param['value']
                elif param['name'] == 'options':
                    options = param['value']
                elif param['name'] == 'shop_url':
                    shop_url = param['value']
                elif param['name'] == 'access_token':
                    access_token = param['value']
            
            if not categories:
                raise ValueError("No categories provided for Shopify collection icon generation")
            if not shop_url or not access_token:
                raise ValueError("Shopify credentials not provided")
            
            # Update job status
            self.update_job(job_id, {
                'status': 'running',
                'started_at': datetime.utcnow().isoformat(),
                'current_stage': 'Starting Shopify collection icon generation'
            })
            
            # Run the task
            result = generate_shopify_collection_icons_task(
                categories=categories,
                options=options,
                shop_url=shop_url,
                access_token=access_token,
                job_id=job_id,
                socketio=socketio
            )
            
            # Update job with results
            self.update_job(job_id, {
                'status': result['status'],
                'completed_at': datetime.utcnow().isoformat(),
                'result': result.get('results'),
                'error': result.get('error')
            })
            
        except Exception as e:
            error_msg = str(e)
            self.update_job(job_id, {
                'status': 'failed',
                'completed_at': datetime.utcnow().isoformat(),
                'error': error_msg
            })
            
            if socketio:
                socketio.emit('job_failed', {
                    'job_id': job_id,
                    'error': error_msg
                }, room=job_id)
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a running job."""
        job = self.get_job(job_id)
        if not job or job['status'] not in ['pending', 'running']:
            return False
        
        # TODO: Implement process termination
        
        self.update_job(job_id, {
            'status': 'cancelled',
            'completed_at': datetime.utcnow().isoformat()
        })
        
        return True
    
    def get_user_jobs(self, user_id: str, limit: int = 50) -> List[Dict]:
        """Get jobs for a specific user."""
        # In production, this would query Redis more efficiently
        user_jobs = []
        
        # Search in Redis
        for key in self.redis.scan_iter(match="job:*"):
            job_data = self.redis.get(key)
            if job_data:
                job = json.loads(job_data)
                if job.get('user_id') == user_id:
                    user_jobs.append(job)
        
        # Sort by created_at descending
        user_jobs.sort(key=lambda x: x['created_at'], reverse=True)
        
        return user_jobs[:limit]
    
    def cleanup_old_jobs(self) -> int:
        """Clean up jobs older than retention period."""
        count = 0
        cutoff_date = datetime.utcnow() - timedelta(days=Config.JOB_RETENTION_DAYS)
        
        for key in self.redis.scan_iter(match="job:*"):
            job_data = self.redis.get(key)
            if job_data:
                job = json.loads(job_data)
                created_at = datetime.fromisoformat(job['created_at'])
                if created_at < cutoff_date:
                    self.redis.delete(key)
                    count += 1
        
        return count