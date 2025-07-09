"""
Products Staging Layer API
Comprehensive API for product management with visual sync flags, versioning, and batch operations
"""

import json
import uuid
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify
from sqlalchemy import and_, or_, func, desc
from sqlalchemy.orm import joinedload

from services.supabase_auth import supabase_jwt_required, get_current_user_id
from database import db_session_scope
from models import (
    Product, Category, SyncQueue, ProductChangeLog, 
    ShopifySync, User, BatchOperation
)

# Create blueprint
products_staging_bp = Blueprint('products_staging', __name__, url_prefix='/api/products')

@products_staging_bp.route('', methods=['GET'])
@supabase_jwt_required
def get_products():
    """Get products with staging layer information including sync status and changes."""
    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 50))
        search = request.args.get('search', '').strip()
        status_filter = request.args.get('status', '').strip()
        sync_filter = request.args.get('sync_status', '').strip()
        include_changes = request.args.get('include_changes', 'false').lower() == 'true'
        
        with db_session_scope() as session:
            # Base query with eager loading
            query = session.query(Product).options(
                joinedload(Product.category)
            )
            
            # Apply filters
            if search:
                search_term = f"%{search}%"
                query = query.filter(or_(
                    Product.name.ilike(search_term),
                    Product.sku.ilike(search_term),
                    Product.brand.ilike(search_term)
                ))
            
            if status_filter and status_filter != 'all':
                query = query.filter(Product.status == status_filter)
            
            if sync_filter and sync_filter != 'all':
                query = query.filter(Product.shopify_sync_status == sync_filter)
            
            # Get total count for pagination
            total_count = query.count()
            
            # Apply pagination and ordering
            offset = (page - 1) * limit
            products = query.order_by(desc(Product.updated_at)).offset(offset).limit(limit).all()
            
            # Build response with staging layer information
            products_data = []
            for product in products:
                # Check for pending changes
                has_changes = False
                change_summary = None
                
                if include_changes:
                    # Get latest changes for this product
                    latest_change = session.query(ProductChangeLog).filter(
                        ProductChangeLog.product_id == product.id
                    ).order_by(desc(ProductChangeLog.created_at)).first()
                    
                    if latest_change and latest_change.created_at > (product.shopify_synced_at or datetime.min):
                        has_changes = True
                        
                        # Get modified fields from recent changes
                        recent_changes = session.query(ProductChangeLog).filter(
                            and_(
                                ProductChangeLog.product_id == product.id,
                                ProductChangeLog.created_at > (product.shopify_synced_at or datetime.min)
                            )
                        ).all()
                        
                        modified_fields = list(set([change.field_name for change in recent_changes if change.field_name]))
                        
                        change_summary = {
                            'modified_fields': modified_fields,
                            'last_change_at': latest_change.created_at.isoformat(),
                            'last_change_by': latest_change.user.email if latest_change.user else 'System'
                        }
                
                # Check for sync conflicts
                sync_conflicts = []
                if product.shopify_sync_status == 'conflict':
                    # Get conflict details from sync queue
                    conflicts = session.query(SyncQueue).filter(
                        and_(
                            SyncQueue.item_id == product.id,
                            SyncQueue.item_type == 'product',
                            SyncQueue.status == 'conflict'
                        )
                    ).all()
                    sync_conflicts = [conflict.last_error for conflict in conflicts if conflict.last_error]
                
                # Determine the sync status
                # If product has never been synced and has no changes, it's "in sync" (nothing to sync)
                # If product has been synced to Shopify, use the actual status
                # If product has changes or no Shopify ID, it needs syncing
                if product.shopify_sync_status:
                    sync_status = product.shopify_sync_status
                elif product.shopify_id and not has_changes:
                    sync_status = 'synced'
                elif not product.shopify_id and not has_changes:
                    sync_status = 'in_sync'  # Initial state - nothing to sync
                else:
                    sync_status = 'pending'
                
                product_data = {
                    'id': product.id,
                    'sku': product.sku,
                    'name': product.name,
                    'brand': product.brand,
                    'price': float(product.price) if product.price else 0.0,
                    'inventory_quantity': product.inventory_quantity or 0,
                    'status': product.status,
                    'shopify_id': product.shopify_id,
                    'shopify_handle': product.shopify_handle,
                    'shopify_sync_status': sync_status,
                    'shopify_synced_at': product.shopify_synced_at.isoformat() if product.shopify_synced_at else None,
                    'last_modified': product.updated_at.isoformat() if product.updated_at else None,
                    'has_changes': has_changes,
                    'change_summary': change_summary,
                    'sync_conflicts': sync_conflicts,
                    'featured_image_url': product.featured_image_url,
                    'category': {
                        'id': product.category.id,
                        'name': product.category.name
                    } if product.category else None
                }
                
                products_data.append(product_data)
            
            return jsonify({
                'success': True,
                'products': products_data,
                'total': total_count,
                'page': page,
                'limit': limit,
                'total_pages': (total_count + limit - 1) // limit
            })
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@products_staging_bp.route('/sync/status', methods=['GET'])
@supabase_jwt_required
def get_sync_status():
    """Get overall sync status and statistics."""
    try:
        with db_session_scope() as session:
            # Count products by sync status
            sync_stats = session.query(
                Product.shopify_sync_status,
                func.count(Product.id).label('count')
            ).group_by(Product.shopify_sync_status).all()
            
            # Count pending changes (products modified after last sync)
            pending_changes = session.query(Product).filter(
                or_(
                    Product.shopify_synced_at.is_(None),
                    Product.updated_at > Product.shopify_synced_at
                )
            ).count()
            
            # Count conflicts
            conflicts = session.query(Product).filter(
                Product.shopify_sync_status == 'conflict'
            ).count()
            
            # Count items in sync queue
            queue_size = session.query(SyncQueue).filter(
                SyncQueue.status.in_(['pending', 'running'])
            ).count()
            
            # Count active operations
            active_operations = session.query(SyncQueue).filter(
                SyncQueue.status == 'running'
            ).count()
            
            # Get last successful sync
            last_sync = session.query(Product.shopify_synced_at).filter(
                Product.shopify_synced_at.isnot(None)
            ).order_by(desc(Product.shopify_synced_at)).first()
            
            # Calculate sync rate (products synced in last 24 hours)
            yesterday = datetime.utcnow() - timedelta(days=1)
            recent_syncs = session.query(Product).filter(
                Product.shopify_synced_at >= yesterday
            ).count()
            
            # Build sync status breakdown with proper handling of null values
            sync_status_breakdown = {}
            for stat in sync_stats:
                status_key = stat.shopify_sync_status if stat.shopify_sync_status else 'in_sync'
                sync_status_breakdown[status_key] = stat.count
            
            return jsonify({
                'success': True,
                'pending_changes': pending_changes,
                'conflicts': conflicts,
                'queue_size': queue_size,
                'active_operations': active_operations,
                'last_sync': last_sync[0].isoformat() if last_sync and last_sync[0] else None,
                'sync_rate': recent_syncs,
                'sync_status_breakdown': sync_status_breakdown
            })
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@products_staging_bp.route('/<int:product_id>/sync', methods=['POST'])
@supabase_jwt_required
def sync_product(product_id):
    """Sync a single product to Shopify."""
    try:
        user_id = get_current_user_id()
        
        with db_session_scope() as session:
            product = session.query(Product).get(product_id)
            if not product:
                return jsonify({'success': False, 'error': 'Product not found'}), 404
            
            # Check if already in queue
            existing_queue_item = session.query(SyncQueue).filter(
                and_(
                    SyncQueue.item_id == product_id,
                    SyncQueue.item_type == 'product',
                    SyncQueue.status.in_(['pending', 'running'])
                )
            ).first()
            
            if existing_queue_item:
                return jsonify({
                    'success': False, 
                    'error': 'Product is already queued for sync'
                }), 400
            
            # Create sync queue item
            queue_item = SyncQueue(
                queue_uuid=str(uuid.uuid4()),
                item_type='product',
                item_id=product_id,
                target_system='shopify',
                operation_type='update' if product.shopify_id else 'create',
                operation_data={
                    'product_id': product_id,
                    'sync_fields': ['name', 'description', 'price', 'inventory_quantity', 'status']
                },
                priority=50,  # Normal priority
                status='pending'
            )
            
            session.add(queue_item)
            
            # Update product sync status
            product.shopify_sync_status = 'pending'
            
            session.commit()
            
            return jsonify({
                'success': True,
                'message': 'Product queued for sync',
                'queue_id': queue_item.queue_uuid
            })
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@products_staging_bp.route('/sync/batch', methods=['POST'])
@supabase_jwt_required
def batch_sync():
    """Start a batch sync operation for multiple products."""
    try:
        data = request.get_json()
        product_ids = data.get('product_ids', [])
        operation = data.get('operation', 'sync')
        
        if not product_ids:
            return jsonify({'success': False, 'error': 'No products specified'}), 400
        
        user_id = get_current_user_id()
        batch_id = str(uuid.uuid4())
        
        with db_session_scope() as session:
            # Verify all products exist
            products = session.query(Product).filter(Product.id.in_(product_ids)).all()
            if len(products) != len(product_ids):
                return jsonify({'success': False, 'error': 'Some products not found'}), 404
            
            # Create batch operation record
            batch_operation = {
                'id': batch_id,
                'type': operation,
                'status': 'pending',
                'progress': 0,
                'total': len(product_ids),
                'started_at': datetime.utcnow().isoformat(),
                'estimated_completion': (datetime.utcnow() + timedelta(minutes=len(product_ids) * 2)).isoformat()
            }
            
            # Create individual sync queue items
            for product in products:
                queue_item = SyncQueue(
                    queue_uuid=str(uuid.uuid4()),
                    item_type='product',
                    item_id=product.id,
                    target_system='shopify',
                    operation_type=operation,
                    operation_data={
                        'product_id': product.id,
                        'batch_id': batch_id,
                        'sync_fields': ['name', 'description', 'price', 'inventory_quantity', 'status']
                    },
                    priority=30,  # Higher priority for batch operations
                    status='pending'
                )
                session.add(queue_item)
                
                # Update product sync status
                product.shopify_sync_status = 'pending'
            
            session.commit()
            
            return jsonify({
                'success': True,
                'message': f'Batch {operation} started for {len(product_ids)} products',
                'operation': batch_operation
            })
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@products_staging_bp.route('/sync/operations', methods=['GET'])
@supabase_jwt_required
def get_batch_operations():
    """Get active batch operations."""
    try:
        with db_session_scope() as session:
            # Get batch operations by grouping sync queue items
            batch_operations = []
            
            # Get distinct batch IDs from operation_data
            # Use raw SQL to handle JSON operations properly
            from sqlalchemy import text
            
            # Get all sync queue items with operation_data containing batch_id
            batch_items_query = session.query(SyncQueue).filter(
                SyncQueue.operation_data.isnot(None)
            ).all()
            
            # Group by batch_id in Python to avoid JSON operator issues
            batch_groups = {}
            for item in batch_items_query:
                if item.operation_data:
                    try:
                        # Handle both dict and string representations of JSON
                        if isinstance(item.operation_data, dict):
                            batch_data = item.operation_data
                        else:
                            batch_data = json.loads(item.operation_data)
                        
                        batch_id = batch_data.get('batch_id')
                        if batch_id:
                            if batch_id not in batch_groups:
                                batch_groups[batch_id] = []
                            batch_groups[batch_id].append(item)
                    except (json.JSONDecodeError, TypeError):
                        continue
            
            # Process each batch group
            for batch_id, batch_items in batch_groups.items():
                
                if not batch_items:
                    continue
                
                # Calculate progress
                total = len(batch_items)
                completed = len([item for item in batch_items if item.status in ['completed', 'failed']])
                running = len([item for item in batch_items if item.status == 'running'])
                failed = len([item for item in batch_items if item.status == 'failed'])
                
                # Determine overall status
                if completed == total:
                    status = 'completed' if failed == 0 else 'failed'
                elif running > 0:
                    status = 'running'
                else:
                    status = 'pending'
                
                # Get timing info
                started_times = [item.started_at for item in batch_items if item.started_at]
                completed_times = [item.completed_at for item in batch_items if item.completed_at]
                
                operation = {
                    'id': batch_id,
                    'type': batch_items[0].operation_type,
                    'status': status,
                    'progress': completed,
                    'total': total,
                    'started_at': min(started_times).isoformat() if started_times else None,
                    'completed_at': max(completed_times).isoformat() if completed_times and len(completed_times) == total else None,
                    'estimated_completion': None  # Could calculate based on current rate
                }
                
                batch_operations.append(operation)
            
            return jsonify({
                'success': True,
                'operations': batch_operations
            })
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@products_staging_bp.route('/sync/operations/<operation_id>/<action>', methods=['POST'])
@supabase_jwt_required
def control_batch_operation(operation_id, action):
    """Control batch operations (pause, resume, cancel)."""
    try:
        if action not in ['pause', 'resume', 'cancel']:
            return jsonify({'success': False, 'error': 'Invalid action'}), 400
        
        with db_session_scope() as session:
            # Get all items in this batch
            batch_items = []
            all_items = session.query(SyncQueue).filter(
                SyncQueue.operation_data.isnot(None)
            ).all()
            
            # Filter items by batch_id in Python to avoid JSON operator issues
            for item in all_items:
                if item.operation_data:
                    try:
                        if isinstance(item.operation_data, dict):
                            batch_data = item.operation_data
                        else:
                            batch_data = json.loads(item.operation_data)
                        
                        if batch_data.get('batch_id') == operation_id:
                            batch_items.append(item)
                    except (json.JSONDecodeError, TypeError):
                        continue
            
            if not batch_items:
                return jsonify({'success': False, 'error': 'Operation not found'}), 404
            
            # Apply action to all items
            for item in batch_items:
                if action == 'pause' and item.status == 'running':
                    item.status = 'paused'
                elif action == 'resume' and item.status == 'paused':
                    item.status = 'pending'
                elif action == 'cancel' and item.status in ['pending', 'running', 'paused']:
                    item.status = 'cancelled'
            
            session.commit()
            
            return jsonify({
                'success': True,
                'message': f'Operation {action}d successfully'
            })
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@products_staging_bp.route('/<int:product_id>/changes', methods=['GET'])
@supabase_jwt_required
def get_product_changes(product_id):
    """Get change history for a product."""
    try:
        with db_session_scope() as session:
            product = session.query(Product).get(product_id)
            if not product:
                return jsonify({'success': False, 'error': 'Product not found'}), 404
            
            # Get change log entries
            changes = session.query(ProductChangeLog).options(
                joinedload(ProductChangeLog.user)
            ).filter(
                ProductChangeLog.product_id == product_id
            ).order_by(desc(ProductChangeLog.created_at)).limit(50).all()
            
            # Group changes into versions
            versions = []
            current_version = None
            
            for change in changes:
                # Create new version if timestamp gap > 5 minutes or different user
                if (not current_version or 
                    (current_version and current_version['created_at'] - change.created_at).seconds > 300 or
                    current_version['created_by'] != (change.user.email if change.user else 'System')):
                    
                    current_version = {
                        'id': str(uuid.uuid4()),
                        'product_id': product_id,
                        'changes': {},
                        'created_at': change.created_at.isoformat(),
                        'created_by': change.user.email if change.user else 'System',
                        'change_type': change.change_type,
                        'is_applied': True  # All logged changes are applied
                    }
                    versions.append(current_version)
                
                # Add field change to current version
                if change.field_name:
                    current_version['changes'][change.field_name] = {
                        'old_value': change.old_value,
                        'new_value': change.new_value
                    }
            
            return jsonify({
                'success': True,
                'changes': versions
            })
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@products_staging_bp.route('/changes/<version_id>/revert', methods=['POST'])
@supabase_jwt_required
def revert_product_version(version_id):
    """Revert a product to a previous version."""
    try:
        user_id = get_current_user_id()
        
        # This is a placeholder - in a real implementation, you'd need to:
        # 1. Store version snapshots with complete product state
        # 2. Apply the reversion changes
        # 3. Log the revert action
        # 4. Queue for sync if needed
        
        return jsonify({
            'success': True,
            'message': 'Version revert functionality is not yet implemented'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500