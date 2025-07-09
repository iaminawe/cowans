"""
Enhanced Batch Icon Generation API with progress tracking and error recovery.
"""

import os
import logging
import asyncio
import json
import uuid
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from flask import Blueprint, jsonify, request, g
from sqlalchemy import and_, or_
import redis
from concurrent.futures import ThreadPoolExecutor
import traceback

from models import db
from icon_batch_models import IconGeneration, IconBatch, IconBatchItem
from icon_generator_openai import icon_generator_openai
from services.supabase_auth import supabase_jwt_required
from icon_generation_service import IconGenerationService, BatchGenerationRequest
from prompt_templates import IconStyle, IconColor
from websocket_events import emit_batch_progress, emit_icon_generated, emit_batch_completed

logger = logging.getLogger(__name__)

# Redis client for progress tracking
redis_client = redis.Redis(
    host=os.getenv('REDIS_HOST', 'localhost'),
    port=int(os.getenv('REDIS_PORT', 6379)),
    db=0,
    decode_responses=True
)

batch_icon_bp = Blueprint('batch_icon_api', __name__)

# Thread pool for parallel processing
executor = ThreadPoolExecutor(max_workers=5)

class BatchIconProcessor:
    """Handles batch icon generation with progress tracking and error recovery."""
    
    def __init__(self):
        self.active_batches = {}
        self._loop = None
        
    async def initialize(self):
        """Initialize async resources."""
        if not icon_generator_openai.icon_service:
            await icon_generator_openai.initialize()
    
    def create_batch(self, user_id: str, categories: List[Dict], config: Dict) -> str:
        """Create a new batch job."""
        batch_id = str(uuid.uuid4())
        
        # Create batch record
        batch = IconBatch(
            id=batch_id,
            user_id=user_id,
            status='pending',
            total_items=len(categories),
            completed_items=0,
            failed_items=0,
            config=json.dumps(config),
            created_at=datetime.utcnow()
        )
        db.session.add(batch)
        
        # Create batch items
        for idx, category in enumerate(categories):
            item = IconBatchItem(
                batch_id=batch_id,
                category_id=category.get('id'),
                category_name=category.get('name'),
                status='pending',
                position=idx,
                metadata=json.dumps(category.get('metadata', {}))
            )
            db.session.add(item)
        
        db.session.commit()
        
        # Store in active batches
        self.active_batches[batch_id] = {
            'status': 'pending',
            'progress': 0,
            'current_item': None,
            'errors': []
        }
        
        # Store in Redis for distributed access
        self._update_redis_progress(batch_id, {
            'status': 'pending',
            'progress': 0,
            'total': len(categories),
            'completed': 0,
            'failed': 0,
            'current_category': None
        })
        
        return batch_id
    
    async def process_batch(self, batch_id: str, progress_callback: Optional[Callable] = None):
        """Process a batch of icon generations."""
        try:
            # Initialize if needed
            await self.initialize()
            
            # Get batch and items
            batch = IconBatch.query.get(batch_id)
            if not batch:
                raise ValueError(f"Batch {batch_id} not found")
            
            items = IconBatchItem.query.filter_by(
                batch_id=batch_id
            ).order_by(IconBatchItem.position).all()
            
            # Update status
            batch.status = 'processing'
            batch.started_at = datetime.utcnow()
            db.session.commit()
            
            config = json.loads(batch.config)
            total_items = len(items)
            completed = 0
            failed = 0
            
            # Process each item
            for idx, item in enumerate(items):
                try:
                    # Check if batch was cancelled
                    if self._is_cancelled(batch_id):
                        batch.status = 'cancelled'
                        db.session.commit()
                        break
                    
                    # Update current item
                    item.status = 'processing'
                    item.started_at = datetime.utcnow()
                    db.session.commit()
                    
                    # Update progress
                    progress = int((idx / total_items) * 100)
                    self._update_progress(batch_id, progress, item.category_name)
                    
                    # Emit WebSocket event
                    emit_batch_progress(batch_id, {
                        'progress': progress,
                        'current_category': item.category_name,
                        'completed': completed,
                        'failed': failed,
                        'total': total_items,
                        'status': 'processing'
                    })
                    
                    if progress_callback:
                        await progress_callback({
                            'batch_id': batch_id,
                            'progress': progress,
                            'current_category': item.category_name,
                            'completed': completed,
                            'total': total_items
                        })
                    
                    # Generate icon
                    result = await self._generate_icon_with_retry(
                        category_id=item.category_id,
                        category_name=item.category_name,
                        config=config,
                        max_retries=3
                    )
                    
                    if result['success']:
                        item.status = 'completed'
                        item.result = json.dumps({
                            'file_path': result.get('file_path'),
                            'url': result.get('url'),
                            'metadata': result.get('metadata')
                        })
                        completed += 1
                        
                        # Emit icon generated event
                        emit_icon_generated(batch_id, {
                            'category_id': item.category_id,
                            'category_name': item.category_name,
                            'url': result.get('url'),
                            'file_path': result.get('file_path')
                        })
                    else:
                        item.status = 'failed'
                        item.error = result.get('error', 'Unknown error')
                        failed += 1
                    
                    item.completed_at = datetime.utcnow()
                    db.session.commit()
                    
                except Exception as e:
                    logger.error(f"Error processing item {item.id}: {e}")
                    item.status = 'failed'
                    item.error = str(e)
                    item.completed_at = datetime.utcnow()
                    db.session.commit()
                    failed += 1
            
            # Update batch status
            batch.status = 'completed' if failed == 0 else 'completed_with_errors'
            batch.completed_items = completed
            batch.failed_items = failed
            batch.completed_at = datetime.utcnow()
            db.session.commit()
            
            # Final progress update
            self._update_progress(batch_id, 100, None)
            
            # Emit batch completion event
            emit_batch_completed(batch_id, {
                'status': batch.status,
                'total': total_items,
                'completed': completed,
                'failed': failed,
                'duration': (batch.completed_at - batch.started_at).total_seconds() if batch.started_at else 0
            })
            
        except Exception as e:
            logger.error(f"Batch processing error: {e}")
            logger.error(traceback.format_exc())
            
            batch = IconBatch.query.get(batch_id)
            if batch:
                batch.status = 'failed'
                batch.error = str(e)
                batch.completed_at = datetime.utcnow()
                db.session.commit()
    
    async def _generate_icon_with_retry(self, category_id: str, category_name: str, 
                                      config: Dict, max_retries: int = 3) -> Dict:
        """Generate icon with retry logic."""
        last_error = None
        
        for attempt in range(max_retries):
            try:
                # Use OpenAI if available
                if os.getenv("OPENAI_API_KEY") and config.get('use_ai', True):
                    result = await icon_generator_openai._generate_with_openai(
                        category_id=category_id,
                        category_name=category_name,
                        style=config.get('style', 'modern'),
                        color=config.get('color', '#3B82F6'),
                        description=config.get('description'),
                        keywords=config.get('keywords', [])
                    )
                else:
                    # Fallback to placeholder
                    result = icon_generator_openai._generate_placeholder(
                        category_id=category_id,
                        category_name=category_name,
                        style=config.get('style', 'modern'),
                        color=config.get('color', '#3B82F6'),
                        size=int(config.get('size', 128)),
                        background=config.get('background', 'transparent')
                    )
                
                if result['success']:
                    return result
                
                last_error = result.get('error', 'Unknown error')
                
                # Wait before retry
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    
            except Exception as e:
                last_error = str(e)
                logger.error(f"Icon generation attempt {attempt + 1} failed: {e}")
                
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
        
        return {
            'success': False,
            'error': f"Failed after {max_retries} attempts: {last_error}"
        }
    
    def _update_progress(self, batch_id: str, progress: int, current_category: Optional[str]):
        """Update batch progress."""
        if batch_id in self.active_batches:
            self.active_batches[batch_id]['progress'] = progress
            self.active_batches[batch_id]['current_item'] = current_category
        
        # Update Redis
        batch = IconBatch.query.get(batch_id)
        if batch:
            self._update_redis_progress(batch_id, {
                'status': batch.status,
                'progress': progress,
                'total': batch.total_items,
                'completed': batch.completed_items,
                'failed': batch.failed_items,
                'current_category': current_category
            })
    
    def _update_redis_progress(self, batch_id: str, data: Dict):
        """Update progress in Redis."""
        try:
            key = f"batch_progress:{batch_id}"
            redis_client.set(key, json.dumps(data), ex=3600)  # 1 hour expiry
        except Exception as e:
            logger.error(f"Redis update error: {e}")
    
    def _is_cancelled(self, batch_id: str) -> bool:
        """Check if batch was cancelled."""
        try:
            key = f"batch_cancel:{batch_id}"
            return redis_client.get(key) == "1"
        except:
            return False
    
    def cancel_batch(self, batch_id: str):
        """Cancel a batch."""
        try:
            # Set cancel flag
            key = f"batch_cancel:{batch_id}"
            redis_client.set(key, "1", ex=300)  # 5 minutes
            
            # Update database
            batch = IconBatch.query.get(batch_id)
            if batch and batch.status in ['pending', 'processing']:
                batch.status = 'cancelled'
                batch.completed_at = datetime.utcnow()
                db.session.commit()
            
            return True
        except Exception as e:
            logger.error(f"Error cancelling batch: {e}")
            return False

# Create processor instance
batch_processor = BatchIconProcessor()

@batch_icon_bp.route('/generate/batch', methods=['POST'])
@supabase_jwt_required
def create_batch_generation():
    """Create a new batch icon generation job."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"message": "Request data required"}), 400
        
        categories = data.get('categories', [])
        if not categories:
            return jsonify({"message": "At least one category is required"}), 400
        
        # Prepare config
        config = {
            'style': data.get('style', 'modern'),
            'color_scheme': data.get('color_scheme', 'brand_colors'),
            'size': data.get('size', 128),
            'format': data.get('format', 'png'),
            'use_ai': data.get('use_ai', True),
            'variations_per_category': data.get('variations_per_category', 1)
        }
        
        # Create batch
        batch_id = batch_processor.create_batch(
            user_id=g.user['id'],
            categories=categories,
            config=config
        )
        
        # Start processing in background
        async def process():
            await batch_processor.process_batch(batch_id)
        
        # Run in executor
        executor.submit(asyncio.run, process())
        
        return jsonify({
            'success': True,
            'batch_id': batch_id,
            'message': f'Batch generation started for {len(categories)} categories'
        })
        
    except Exception as e:
        logger.error(f"Batch creation error: {e}")
        return jsonify({"message": str(e)}), 500

@batch_icon_bp.route('/batch/<batch_id>/status', methods=['GET'])
@supabase_jwt_required
def get_batch_status(batch_id):
    """Get batch status and progress."""
    try:
        # Get from database
        batch = IconBatch.query.filter_by(
            id=batch_id,
            user_id=g.user['id']
        ).first()
        
        if not batch:
            return jsonify({"message": "Batch not found"}), 404
        
        # Get progress from Redis
        try:
            key = f"batch_progress:{batch_id}"
            progress_data = redis_client.get(key)
            if progress_data:
                progress = json.loads(progress_data)
            else:
                progress = {
                    'progress': 0,
                    'current_category': None
                }
        except:
            progress = {'progress': 0}
        
        # Get items summary
        items = IconBatchItem.query.filter_by(batch_id=batch_id).all()
        items_by_status = {
            'pending': sum(1 for i in items if i.status == 'pending'),
            'processing': sum(1 for i in items if i.status == 'processing'),
            'completed': sum(1 for i in items if i.status == 'completed'),
            'failed': sum(1 for i in items if i.status == 'failed')
        }
        
        return jsonify({
            'batch_id': batch.id,
            'status': batch.status,
            'progress': progress.get('progress', 0),
            'current_category': progress.get('current_category'),
            'total_items': batch.total_items,
            'completed_items': batch.completed_items,
            'failed_items': batch.failed_items,
            'items_by_status': items_by_status,
            'created_at': batch.created_at.isoformat(),
            'started_at': batch.started_at.isoformat() if batch.started_at else None,
            'completed_at': batch.completed_at.isoformat() if batch.completed_at else None,
            'error': batch.error
        })
        
    except Exception as e:
        logger.error(f"Error getting batch status: {e}")
        return jsonify({"message": str(e)}), 500

@batch_icon_bp.route('/batch/<batch_id>/items', methods=['GET'])
@supabase_jwt_required
def get_batch_items(batch_id):
    """Get detailed batch items."""
    try:
        # Verify ownership
        batch = IconBatch.query.filter_by(
            id=batch_id,
            user_id=g.user['id']
        ).first()
        
        if not batch:
            return jsonify({"message": "Batch not found"}), 404
        
        # Get items
        items = IconBatchItem.query.filter_by(
            batch_id=batch_id
        ).order_by(IconBatchItem.position).all()
        
        items_data = []
        for item in items:
            item_data = {
                'id': item.id,
                'category_id': item.category_id,
                'category_name': item.category_name,
                'status': item.status,
                'position': item.position,
                'started_at': item.started_at.isoformat() if item.started_at else None,
                'completed_at': item.completed_at.isoformat() if item.completed_at else None,
                'error': item.error
            }
            
            if item.result:
                item_data['result'] = json.loads(item.result)
            
            items_data.append(item_data)
        
        return jsonify({
            'batch_id': batch_id,
            'items': items_data
        })
        
    except Exception as e:
        logger.error(f"Error getting batch items: {e}")
        return jsonify({"message": str(e)}), 500

@batch_icon_bp.route('/batch/<batch_id>/cancel', methods=['POST'])
@supabase_jwt_required
def cancel_batch(batch_id):
    """Cancel a running batch."""
    try:
        # Verify ownership
        batch = IconBatch.query.filter_by(
            id=batch_id,
            user_id=g.user['id']
        ).first()
        
        if not batch:
            return jsonify({"message": "Batch not found"}), 404
        
        if batch.status not in ['pending', 'processing']:
            return jsonify({"message": f"Cannot cancel batch with status: {batch.status}"}), 400
        
        # Cancel batch
        if batch_processor.cancel_batch(batch_id):
            return jsonify({
                'success': True,
                'message': 'Batch cancellation requested'
            })
        else:
            return jsonify({"message": "Failed to cancel batch"}), 500
            
    except Exception as e:
        logger.error(f"Error cancelling batch: {e}")
        return jsonify({"message": str(e)}), 500

@batch_icon_bp.route('/batch/<batch_id>/retry', methods=['POST'])
@supabase_jwt_required
def retry_failed_items(batch_id):
    """Retry failed items in a batch."""
    try:
        # Verify ownership
        batch = IconBatch.query.filter_by(
            id=batch_id,
            user_id=g.user['id']
        ).first()
        
        if not batch:
            return jsonify({"message": "Batch not found"}), 404
        
        if batch.status not in ['completed_with_errors', 'failed']:
            return jsonify({"message": "Can only retry batches with errors"}), 400
        
        # Get failed items
        failed_items = IconBatchItem.query.filter_by(
            batch_id=batch_id,
            status='failed'
        ).all()
        
        if not failed_items:
            return jsonify({"message": "No failed items to retry"}), 400
        
        # Reset failed items
        for item in failed_items:
            item.status = 'pending'
            item.error = None
            item.result = None
            item.started_at = None
            item.completed_at = None
        
        # Reset batch counters
        batch.status = 'pending'
        batch.failed_items = 0
        batch.completed_at = None
        db.session.commit()
        
        # Start reprocessing
        async def reprocess():
            await batch_processor.process_batch(batch_id)
        
        executor.submit(asyncio.run, reprocess())
        
        return jsonify({
            'success': True,
            'message': f'Retrying {len(failed_items)} failed items'
        })
        
    except Exception as e:
        logger.error(f"Error retrying batch: {e}")
        return jsonify({"message": str(e)}), 500

@batch_icon_bp.route('/batches', methods=['GET'])
@supabase_jwt_required
def list_batches():
    """List user's batch jobs."""
    try:
        # Get query params
        status = request.args.get('status')
        limit = int(request.args.get('limit', 20))
        offset = int(request.args.get('offset', 0))
        
        # Build query
        query = IconBatch.query.filter_by(user_id=g.user['id'])
        
        if status:
            query = query.filter_by(status=status)
        
        # Get total count
        total = query.count()
        
        # Get batches
        batches = query.order_by(
            IconBatch.created_at.desc()
        ).limit(limit).offset(offset).all()
        
        batches_data = []
        for batch in batches:
            # Get progress from Redis if active
            progress = 0
            current_category = None
            
            if batch.status in ['pending', 'processing']:
                try:
                    key = f"batch_progress:{batch.id}"
                    progress_data = redis_client.get(key)
                    if progress_data:
                        pd = json.loads(progress_data)
                        progress = pd.get('progress', 0)
                        current_category = pd.get('current_category')
                except:
                    pass
            
            batches_data.append({
                'batch_id': batch.id,
                'status': batch.status,
                'progress': progress,
                'current_category': current_category,
                'total_items': batch.total_items,
                'completed_items': batch.completed_items,
                'failed_items': batch.failed_items,
                'created_at': batch.created_at.isoformat(),
                'completed_at': batch.completed_at.isoformat() if batch.completed_at else None
            })
        
        return jsonify({
            'batches': batches_data,
            'total': total,
            'limit': limit,
            'offset': offset
        })
        
    except Exception as e:
        logger.error(f"Error listing batches: {e}")
        return jsonify({"message": str(e)}), 500