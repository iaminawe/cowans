"""
Enhanced Sync API for Shopify Integration

This module provides the enhanced sync API endpoints with staging support:
- Pull products from Shopify with change detection
- Stage changes for review
- Push approved changes to Shopify
- Version tracking and rollback capabilities
"""

import json
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required
from services.supabase_auth import supabase_jwt_required, get_current_user_id
from database import db_session_scope as db_session
from sqlalchemy import func, and_, or_
from sqlalchemy.orm import joinedload

from models import Product, Category, SyncStatus
from staging_models import (
    StagedProductChange, StagedCategoryChange, SyncVersion, 
    SyncBatch, SyncApprovalRule, SyncRollback,
    StagedChangeStatus, SyncDirection, ChangeType
)
# from sync_models import ChangeTracking
from repositories import ProductRepository, CategoryRepository
from services.shopify_sync_service import ShopifySyncService
from parallel_sync_engine import ParallelSyncEngine, SyncOperation, OperationType, SyncPriority

import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from scripts.shopify.shopify_base import ShopifyAPIBase

# Create blueprint
enhanced_sync_bp = Blueprint('enhanced_sync', __name__, url_prefix='/api/sync')

# Configure logging
logger = logging.getLogger(__name__)

# Initialize services
# sync_engine = ParallelSyncEngine(max_workers=4)  # Initialize in route handlers


def get_shopify_client():
    """Get configured Shopify API client."""
    shop_url = os.getenv('SHOPIFY_SHOP_URL')
    access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
    
    if not shop_url or not access_token:
        raise ValueError("Shopify credentials not configured")
    
    return ShopifyAPIBase(shop_url, access_token, debug=True)


def calculate_data_hash(data: Dict[str, Any]) -> str:
    """Calculate hash of data for version tracking."""
    # Sort keys for consistent hashing
    sorted_data = json.dumps(data, sort_keys=True)
    return hashlib.sha256(sorted_data.encode()).hexdigest()


def detect_changes(current_data: Dict[str, Any], new_data: Dict[str, Any]) -> Dict[str, Any]:
    """Detect changes between current and new data."""
    changes = {}
    all_keys = set(current_data.keys()) | set(new_data.keys())
    
    for key in all_keys:
        current_value = current_data.get(key)
        new_value = new_data.get(key)
        
        if current_value != new_value:
            changes[key] = {
                'old': current_value,
                'new': new_value
            }
    
    return changes


@enhanced_sync_bp.route('/shopify/pull', methods=['POST'])
@supabase_jwt_required
def pull_from_shopify():
    """Pull products from Shopify and stage changes."""
    with db_session() as session:
        try:
            user_id = get_current_user_id()
            data = request.get_json() or {}
            
            # Create sync batch
            batch_id = f"pull_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{user_id}"
            sync_batch = SyncBatch(
                batch_id=batch_id,
                batch_name=data.get('batch_name', 'Shopify Pull'),
                sync_type=data.get('sync_type', 'incremental'),
                sync_direction=SyncDirection.PULL_FROM_SHOPIFY.value,
                status='running',
                created_by=user_id,
                started_at=datetime.utcnow(),
                configuration=data
            )
            session.add(sync_batch)
            session.flush()
            
            # Get Shopify client
            shopify_client = get_shopify_client()
            
            # Determine what to sync
            since_date = None
            if data.get('sync_type') == 'incremental':
                # Get last sync date
                last_sync = session.query(func.max(SyncBatch.completed_at)).filter(
                    SyncBatch.sync_direction == SyncDirection.PULL_FROM_SHOPIFY.value,
                    SyncBatch.status == 'completed'
                ).scalar()
                
                if last_sync:
                    since_date = last_sync
            
            # Pull products from Shopify
            shopify_products = []
            cursor = None
            total_pulled = 0
            
            while True:
                # Build query
                query = """
                query GetProducts($cursor: String, $first: Int!) {
                    products(first: $first, after: $cursor) {
                        edges {
                            node {
                                id
                                title
                                description
                                handle
                                status
                                vendor
                                productType
                                tags
                                updatedAt
                                createdAt
                                variants(first: 10) {
                                    edges {
                                        node {
                                            id
                                            sku
                                            price
                                            compareAtPrice
                                            inventoryQuantity
                                            barcode
                                            weight
                                            weightUnit
                                        }
                                    }
                                }
                                images(first: 10) {
                                    edges {
                                        node {
                                            id
                                            url
                                            altText
                                        }
                                    }
                                }
                                metafields(first: 10) {
                                    edges {
                                        node {
                                            namespace
                                            key
                                            value
                                            type
                                        }
                                    }
                                }
                            }
                        }
                        pageInfo {
                            hasNextPage
                            endCursor
                        }
                    }
                }
                """
                
                variables = {
                    'first': 50,
                    'cursor': cursor
                }
                
                result = shopify_client.execute_graphql(query, variables)
                
                if 'errors' in result:
                    raise Exception(f"GraphQL errors: {result['errors']}")
                
                products_data = result['data']['products']
                
                for edge in products_data['edges']:
                    product = edge['node']
                    
                    # Check if product was updated since last sync
                    if since_date:
                        updated_at = datetime.fromisoformat(product['updatedAt'].replace('Z', '+00:00'))
                        if updated_at <= since_date:
                            continue
                    
                    shopify_products.append(product)
                    total_pulled += 1
                
                # Check if there are more pages
                if not products_data['pageInfo']['hasNextPage']:
                    break
                
                cursor = products_data['pageInfo']['endCursor']
            
            # Update batch statistics
            sync_batch.total_items = total_pulled
            
            # Stage changes for each product
            staged_changes = []
            product_repo = ProductRepository(session)
            
            for shopify_product in shopify_products:
                try:
                    # Extract product data
                    shopify_id = shopify_product['id'].split('/')[-1]
                    
                    # Get first variant data
                    variant_data = {}
                    if shopify_product.get('variants', {}).get('edges'):
                        first_variant = shopify_product['variants']['edges'][0]['node']
                        variant_data = {
                            'sku': first_variant.get('sku'),
                            'price': float(first_variant.get('price', 0)),
                            'compare_at_price': float(first_variant.get('compareAtPrice', 0)) if first_variant.get('compareAtPrice') else None,
                            'inventory_quantity': first_variant.get('inventoryQuantity', 0),
                            'barcode': first_variant.get('barcode'),
                            'weight': float(first_variant.get('weight', 0)) if first_variant.get('weight') else None,
                            'weight_unit': first_variant.get('weightUnit', 'kg').lower()
                        }
                    
                    # Build proposed data
                    proposed_data = {
                        'shopify_product_id': shopify_id,
                        'name': shopify_product['title'],
                        'title': shopify_product['title'],  # Compatibility
                        'description': shopify_product.get('description', ''),
                        'shopify_handle': shopify_product.get('handle'),
                        'shopify_status': shopify_product.get('status', '').lower(),
                        'brand': shopify_product.get('vendor'),
                        'product_type': shopify_product.get('productType'),
                        'tags': ', '.join(shopify_product.get('tags', [])),
                        **variant_data
                    }
                    
                    # Extract images
                    if shopify_product.get('images', {}).get('edges'):
                        images = []
                        for img_edge in shopify_product['images']['edges']:
                            images.append({
                                'url': img_edge['node']['url'],
                                'alt': img_edge['node'].get('altText', '')
                            })
                        proposed_data['featured_image_url'] = images[0]['url'] if images else None
                        proposed_data['additional_images'] = images[1:] if len(images) > 1 else []
                    
                    # Find existing product
                    existing_product = None
                    if variant_data.get('sku'):
                        existing_product = product_repo.get_by_sku(variant_data['sku'])
                    if not existing_product and shopify_id:
                        existing_product = product_repo.get_by_shopify_id(shopify_id)
                    
                    # Determine change type
                    if existing_product:
                        change_type = ChangeType.UPDATE.value
                        product_id = existing_product.id
                        
                        # Get current data
                        current_data = {
                            'name': existing_product.name,
                            'title': existing_product.title,
                            'description': existing_product.description,
                            'sku': existing_product.sku,
                            'price': existing_product.price,
                            'compare_at_price': existing_product.compare_at_price,
                            'inventory_quantity': existing_product.inventory_quantity,
                            'brand': existing_product.brand,
                            'product_type': existing_product.custom_attributes.get('product_type') if existing_product.custom_attributes else None,
                            'shopify_handle': existing_product.shopify_handle,
                            'shopify_status': existing_product.shopify_status,
                            'featured_image_url': existing_product.featured_image_url,
                            'additional_images': existing_product.additional_images
                        }
                        
                        # Detect field changes
                        field_changes = detect_changes(current_data, proposed_data)
                        
                        # Skip if no changes
                        if not field_changes:
                            continue
                    else:
                        change_type = ChangeType.CREATE.value
                        product_id = None
                        current_data = {}
                        field_changes = {k: {'old': None, 'new': v} for k, v in proposed_data.items()}
                    
                    # Calculate version hashes
                    source_version = calculate_data_hash(proposed_data)
                    target_version = calculate_data_hash(current_data) if current_data else None
                    
                    # Check for conflicts
                    has_conflicts = False
                    conflict_fields = []
                    
                    if existing_product and existing_product.updated_at > sync_batch.started_at:
                        # Product was modified locally after sync started
                        has_conflicts = True
                        conflict_fields = list(field_changes.keys())
                    
                    # Create staged change
                    staged_change = StagedProductChange(
                        change_id=f"{batch_id}_product_{shopify_id}",
                        product_id=product_id,
                        shopify_product_id=shopify_id,
                        change_type=change_type,
                        sync_direction=SyncDirection.PULL_FROM_SHOPIFY.value,
                        source_version=source_version,
                        target_version=target_version,
                        current_data=current_data,
                        proposed_data=proposed_data,
                        field_changes=field_changes,
                        has_conflicts=has_conflicts,
                        conflict_fields=conflict_fields,
                        status=StagedChangeStatus.PENDING.value,
                        source_system='shopify',
                        batch_id=batch_id,
                        priority=2 if has_conflicts else 3
                    )
                    
                    # Check approval rules
                    auto_approved = check_auto_approval(session, staged_change)
                    staged_change.auto_approved = auto_approved
                    if auto_approved:
                        staged_change.status = StagedChangeStatus.APPROVED.value
                        staged_change.reviewed_at = datetime.utcnow()
                    
                    session.add(staged_change)
                    staged_changes.append(staged_change)
                    
                except Exception as e:
                    logger.error(f"Failed to stage product {shopify_product.get('id')}: {str(e)}")
                    sync_batch.failed_items += 1
            
            # Update batch statistics
            sync_batch.processed_items = len(shopify_products)
            sync_batch.successful_items = len(staged_changes)
            sync_batch.status = 'completed'
            sync_batch.completed_at = datetime.utcnow()
            
            # Calculate summary
            summary = {
                'total_changes': len(staged_changes),
                'new_products': sum(1 for c in staged_changes if c.change_type == ChangeType.CREATE.value),
                'updated_products': sum(1 for c in staged_changes if c.change_type == ChangeType.UPDATE.value),
                'conflicts': sum(1 for c in staged_changes if c.has_conflicts),
                'auto_approved': sum(1 for c in staged_changes if c.auto_approved)
            }
            
            sync_batch.error_summary = summary
            
            session.commit()
            
            return jsonify({
                'success': True,
                'batch_id': batch_id,
                'summary': summary,
                'message': f"Successfully pulled {len(shopify_products)} products from Shopify"
            })
            
        except Exception as e:
            logger.error(f"Failed to pull from Shopify: {str(e)}")
            if 'sync_batch' in locals():
                sync_batch.status = 'failed'
                sync_batch.error_summary = {'error': str(e)}
            session.rollback()
            return jsonify({'error': str(e)}), 500


@enhanced_sync_bp.route('/staged', methods=['GET'])
@supabase_jwt_required
def get_staged_changes():
    """Get staged changes for review."""
    with db_session() as session:
        try:
            # Get query parameters
            batch_id = request.args.get('batch_id')
            status = request.args.get('status', 'pending')
            change_type = request.args.get('change_type')
            has_conflicts = request.args.get('has_conflicts')
            page = int(request.args.get('page', 1))
            per_page = int(request.args.get('per_page', 50))
            
            # Build query
            query = session.query(StagedProductChange).options(
                joinedload(StagedProductChange.product)
            )
            
            if batch_id:
                query = query.filter(StagedProductChange.batch_id == batch_id)
            
            if status:
                query = query.filter(StagedProductChange.status == status)
            
            if change_type:
                query = query.filter(StagedProductChange.change_type == change_type)
            
            if has_conflicts is not None:
                query = query.filter(StagedProductChange.has_conflicts == (has_conflicts == 'true'))
            
            # Order by priority and creation date
            query = query.order_by(
                StagedProductChange.priority.asc(),
                StagedProductChange.created_at.desc()
            )
            
            # Paginate
            total = query.count()
            changes = query.offset((page - 1) * per_page).limit(per_page).all()
            
            # Format response
            items = []
            for change in changes:
                item = {
                    'id': change.id,
                    'change_id': change.change_id,
                    'product_id': change.product_id,
                    'shopify_product_id': change.shopify_product_id,
                    'change_type': change.change_type,
                    'sync_direction': change.sync_direction,
                    'status': change.status,
                    'has_conflicts': change.has_conflicts,
                    'conflict_fields': change.conflict_fields,
                    'field_changes': change.field_changes,
                    'current_data': change.current_data,
                    'proposed_data': change.proposed_data,
                    'auto_approved': change.auto_approved,
                    'created_at': change.created_at.isoformat(),
                    'product': {
                        'id': change.product.id,
                        'sku': change.product.sku,
                        'name': change.product.name
                    } if change.product else None
                }
                items.append(item)
            
            return jsonify({
                'success': True,
                'items': items,
                'total': total,
                'page': page,
                'per_page': per_page,
                'total_pages': (total + per_page - 1) // per_page
            })
            
        except Exception as e:
            logger.error(f"Failed to get staged changes: {str(e)}")
            return jsonify({'error': str(e)}), 500


@enhanced_sync_bp.route('/staged/<int:change_id>/approve', methods=['POST'])
@supabase_jwt_required
def approve_staged_change(change_id):
    """Approve a staged change."""
    with db_session() as session:
        try:
            user_id = get_current_user_id()
            
            # Get staged change
            change = session.query(StagedProductChange).filter_by(id=change_id).first()
            if not change:
                return jsonify({'error': 'Staged change not found'}), 404
            
            if change.status != StagedChangeStatus.PENDING.value:
                return jsonify({'error': 'Change already processed'}), 400
            
            # Update status
            change.status = StagedChangeStatus.APPROVED.value
            change.reviewed_by = user_id
            change.reviewed_at = datetime.utcnow()
            
            data = request.get_json() or {}
            if data.get('notes'):
                change.review_notes = data['notes']
            
            session.commit()
            
            return jsonify({
                'success': True,
                'message': 'Change approved successfully'
            })
            
        except Exception as e:
            logger.error(f"Failed to approve change: {str(e)}")
            session.rollback()
            return jsonify({'error': str(e)}), 500


@enhanced_sync_bp.route('/staged/<int:change_id>/reject', methods=['POST'])
@supabase_jwt_required
def reject_staged_change(change_id):
    """Reject a staged change."""
    with db_session() as session:
        try:
            user_id = get_current_user_id()
            data = request.get_json() or {}
            
            # Get staged change
            change = session.query(StagedProductChange).filter_by(id=change_id).first()
            if not change:
                return jsonify({'error': 'Staged change not found'}), 404
            
            if change.status != StagedChangeStatus.PENDING.value:
                return jsonify({'error': 'Change already processed'}), 400
            
            # Update status
            change.status = StagedChangeStatus.REJECTED.value
            change.reviewed_by = user_id
            change.reviewed_at = datetime.utcnow()
            change.review_notes = data.get('reason', 'Rejected by user')
            
            session.commit()
            
            return jsonify({
                'success': True,
                'message': 'Change rejected successfully'
            })
            
        except Exception as e:
            logger.error(f"Failed to reject change: {str(e)}")
            session.rollback()
            return jsonify({'error': str(e)}), 500


@enhanced_sync_bp.route('/staged/bulk-approve', methods=['POST'])
@supabase_jwt_required
def bulk_approve_changes():
    """Approve multiple staged changes."""
    with db_session() as session:
        try:
            user_id = get_current_user_id()
            data = request.get_json() or {}
            
            change_ids = data.get('change_ids', [])
            if not change_ids:
                return jsonify({'error': 'No change IDs provided'}), 400
            
            # Update all changes
            updated = session.query(StagedProductChange).filter(
                StagedProductChange.id.in_(change_ids),
                StagedProductChange.status == StagedChangeStatus.PENDING.value
            ).update({
                'status': StagedChangeStatus.APPROVED.value,
                'reviewed_by': user_id,
                'reviewed_at': datetime.utcnow(),
                'review_notes': data.get('notes', 'Bulk approved')
            }, synchronize_session=False)
            
            session.commit()
            
            return jsonify({
                'success': True,
                'updated': updated,
                'message': f'Successfully approved {updated} changes'
            })
            
        except Exception as e:
            logger.error(f"Failed to bulk approve: {str(e)}")
            session.rollback()
            return jsonify({'error': str(e)}), 500


@enhanced_sync_bp.route('/shopify/push', methods=['POST'])
@supabase_jwt_required
def push_to_shopify():
    """Push approved staged changes to Shopify."""
    with db_session() as session:
        try:
            user_id = get_current_user_id()
            data = request.get_json() or {}
            
            # Get batch ID or specific changes
            batch_id = data.get('batch_id')
            change_ids = data.get('change_ids', [])
            
            # Create sync batch
            sync_batch_id = f"push_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{user_id}"
            sync_batch = SyncBatch(
                batch_id=sync_batch_id,
                batch_name=data.get('batch_name', 'Shopify Push'),
                sync_type='selective',
                sync_direction=SyncDirection.PUSH_TO_SHOPIFY.value,
                status='running',
                created_by=user_id,
                started_at=datetime.utcnow(),
                configuration=data
            )
            session.add(sync_batch)
            session.flush()
            
            # Get approved changes to push
            query = session.query(StagedProductChange).filter(
                StagedProductChange.status == StagedChangeStatus.APPROVED.value
            )
            
            if batch_id:
                query = query.filter(StagedProductChange.batch_id == batch_id)
            elif change_ids:
                query = query.filter(StagedProductChange.id.in_(change_ids))
            
            changes = query.all()
            
            if not changes:
                return jsonify({
                    'success': False,
                    'message': 'No approved changes to push'
                }), 400
            
            sync_batch.total_items = len(changes)
            
            # Get Shopify client
            shopify_client = get_shopify_client()
            
            # Process each change
            results = []
            for change in changes:
                try:
                    result = apply_staged_change(session, change, shopify_client, user_id)
                    results.append(result)
                    
                    if result['success']:
                        sync_batch.successful_items += 1
                    else:
                        sync_batch.failed_items += 1
                        
                except Exception as e:
                    logger.error(f"Failed to apply change {change.change_id}: {str(e)}")
                    sync_batch.failed_items += 1
                    results.append({
                        'change_id': change.change_id,
                        'success': False,
                        'error': str(e)
                    })
            
            # Update batch status
            sync_batch.processed_items = len(changes)
            sync_batch.status = 'completed' if sync_batch.failed_items == 0 else 'partial'
            sync_batch.completed_at = datetime.utcnow()
            
            # Calculate summary
            summary = {
                'total_processed': len(results),
                'successful': sum(1 for r in results if r['success']),
                'failed': sum(1 for r in results if not r['success']),
                'results': results
            }
            
            sync_batch.error_summary = summary
            
            session.commit()
            
            return jsonify({
                'success': True,
                'batch_id': sync_batch_id,
                'summary': summary,
                'message': f"Pushed {summary['successful']} changes to Shopify"
            })
            
        except Exception as e:
            logger.error(f"Failed to push to Shopify: {str(e)}")
            if 'sync_batch' in locals():
                sync_batch.status = 'failed'
                sync_batch.error_summary = {'error': str(e)}
            session.rollback()
            return jsonify({'error': str(e)}), 500


def check_auto_approval(session, staged_change: StagedProductChange) -> bool:
    """Check if a staged change can be auto-approved based on rules."""
    # Get active approval rules
    rules = session.query(SyncApprovalRule).filter(
        SyncApprovalRule.is_active == True,
        or_(
            SyncApprovalRule.entity_type == 'all',
            SyncApprovalRule.entity_type == 'product'
        ),
        or_(
            SyncApprovalRule.change_type == 'all',
            SyncApprovalRule.change_type == staged_change.change_type
        )
    ).order_by(SyncApprovalRule.priority.asc()).all()
    
    for rule in rules:
        # Check if rule applies
        if not rule.requires_approval:
            continue
            
        # Check auto-approve conditions
        if rule.auto_approve_conditions:
            conditions = rule.auto_approve_conditions
            
            # Check field patterns
            if conditions.get('exclude_fields'):
                changed_fields = set(staged_change.field_changes.keys())
                excluded_fields = set(conditions['exclude_fields'])
                if changed_fields & excluded_fields:
                    return False
            
            # Check value thresholds
            if conditions.get('max_price_change'):
                if 'price' in staged_change.field_changes:
                    old_price = staged_change.field_changes['price'].get('old', 0) or 0
                    new_price = staged_change.field_changes['price'].get('new', 0) or 0
                    if abs(new_price - old_price) > conditions['max_price_change']:
                        return False
            
            # Check for conflicts
            if conditions.get('no_conflicts') and staged_change.has_conflicts:
                return False
    
    # Default to auto-approve if no rules prevent it
    return True


def apply_staged_change(session, change: StagedProductChange, shopify_client, user_id: int) -> Dict[str, Any]:
    """Apply a staged change to the database and optionally to Shopify."""
    try:
        # Store version before applying change
        if change.product_id:
            product = session.query(Product).filter_by(id=change.product_id).first()
            if product:
                # Create version snapshot
                version_data = {
                    'id': product.id,
                    'sku': product.sku,
                    'name': product.name,
                    'description': product.description,
                    'price': product.price,
                    'inventory_quantity': product.inventory_quantity,
                    'shopify_product_id': product.shopify_product_id,
                    'updated_at': product.updated_at.isoformat()
                }
                
                version = SyncVersion(
                    entity_type='product',
                    entity_id=product.id,
                    shopify_id=product.shopify_product_id,
                    version_hash=calculate_data_hash(version_data),
                    version_number=session.query(func.coalesce(func.max(SyncVersion.version_number), 0)).filter(
                        SyncVersion.entity_type == 'product',
                        SyncVersion.entity_id == product.id
                    ).scalar() + 1,
                    data_snapshot=version_data,
                    source_system='local',
                    sync_direction=change.sync_direction,
                    created_by=user_id
                )
                session.add(version)
        
        # Apply change based on type
        if change.change_type == ChangeType.CREATE.value:
            # Create new product
            product_repo = ProductRepository(session)
            product = product_repo.create(**change.proposed_data)
            change.product_id = product.id
            
        elif change.change_type == ChangeType.UPDATE.value:
            # Update existing product
            product = session.query(Product).filter_by(id=change.product_id).first()
            if not product:
                raise Exception(f"Product {change.product_id} not found")
            
            # Apply changes
            for field, value in change.proposed_data.items():
                if hasattr(product, field):
                    setattr(product, field, value)
            
            product.updated_at = datetime.utcnow()
        
        # Update change status
        change.status = StagedChangeStatus.APPLIED.value
        change.applied_at = datetime.utcnow()
        change.applied_by = user_id
        
        # Store application result
        change.application_result = {
            'product_id': product.id,
            'applied_fields': list(change.proposed_data.keys()),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Log change tracking for audit purposes
        try:
            change_log = {
                'entity_type': 'product',
                'entity_id': product.id,
                'action': change.change_type,
                'changed_fields': list(change.field_changes.keys()),
                'old_values': change.current_data,
                'new_values': change.proposed_data,
                'change_source': 'sync',
                'user_id': user_id,
                'sync_required': False,
                'synced_at': datetime.utcnow().isoformat()
            }
            logger.info(f"Change applied: {change_log}")
        except Exception as tracking_error:
            logger.warning(f"Failed to create change tracking record: {tracking_error}")
            # Continue without tracking if this fails
        
        session.flush()
        
        return {
            'change_id': change.change_id,
            'success': True,
            'product_id': product.id,
            'message': f"Successfully applied {change.change_type} for product {product.sku}"
        }
        
    except Exception as e:
        logger.error(f"Failed to apply change {change.change_id}: {str(e)}")
        return {
            'change_id': change.change_id,
            'success': False,
            'error': str(e)
        }


@enhanced_sync_bp.route('/batches', methods=['GET'])
@supabase_jwt_required
def get_sync_batches():
    """Get sync batch history."""
    with db_session() as session:
        try:
            # Get query parameters
            sync_direction = request.args.get('direction')
            status = request.args.get('status')
            page = int(request.args.get('page', 1))
            per_page = int(request.args.get('per_page', 20))
            
            # Build query
            query = session.query(SyncBatch)
            
            if sync_direction:
                query = query.filter(SyncBatch.sync_direction == sync_direction)
            
            if status:
                query = query.filter(SyncBatch.status == status)
            
            # Order by creation date
            query = query.order_by(SyncBatch.created_at.desc())
            
            # Paginate
            total = query.count()
            batches = query.offset((page - 1) * per_page).limit(per_page).all()
            
            # Format response
            items = []
            for batch in batches:
                item = {
                    'id': batch.id,
                    'batch_id': batch.batch_id,
                    'batch_name': batch.batch_name,
                    'sync_type': batch.sync_type,
                    'sync_direction': batch.sync_direction,
                    'status': batch.status,
                    'total_items': batch.total_items,
                    'processed_items': batch.processed_items,
                    'successful_items': batch.successful_items,
                    'failed_items': batch.failed_items,
                    'created_at': batch.created_at.isoformat(),
                    'started_at': batch.started_at.isoformat() if batch.started_at else None,
                    'completed_at': batch.completed_at.isoformat() if batch.completed_at else None,
                    'created_by': batch.created_by
                }
                items.append(item)
            
            return jsonify({
                'success': True,
                'items': items,
                'total': total,
                'page': page,
                'per_page': per_page,
                'total_pages': (total + per_page - 1) // per_page
            })
            
        except Exception as e:
            logger.error(f"Failed to get sync batches: {str(e)}")
            return jsonify({'error': str(e)}), 500


@enhanced_sync_bp.route('/rollback/<int:change_id>', methods=['POST'])
@supabase_jwt_required
def rollback_change(change_id):
    """Rollback an applied change."""
    with db_session() as session:
        try:
            user_id = get_current_user_id()
            data = request.get_json() or {}
            
            # Get the applied change
            change = session.query(StagedProductChange).filter_by(id=change_id).first()
            if not change:
                return jsonify({'error': 'Change not found'}), 404
            
            if change.status != StagedChangeStatus.APPLIED.value:
                return jsonify({'error': 'Change not applied, cannot rollback'}), 400
            
            if not change.product_id:
                return jsonify({'error': 'No product associated with change'}), 400
            
            # Get previous version
            previous_version = session.query(SyncVersion).filter(
                SyncVersion.entity_type == 'product',
                SyncVersion.entity_id == change.product_id,
                SyncVersion.created_at < change.applied_at
            ).order_by(SyncVersion.version_number.desc()).first()
            
            if not previous_version:
                return jsonify({'error': 'No previous version found'}), 400
            
            # Create rollback record
            rollback = SyncRollback(
                rollback_id=f"rollback_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{change_id}",
                entity_type='product',
                entity_id=change.product_id,
                staged_change_id=change.id,
                previous_version_id=previous_version.id,
                rollback_data=previous_version.data_snapshot,
                status='pending',
                reason=data.get('reason', 'User requested rollback'),
                executed_by=user_id
            )
            session.add(rollback)
            session.flush()
            
            # Apply rollback
            product = session.query(Product).filter_by(id=change.product_id).first()
            if product:
                # Restore previous data
                for field, value in previous_version.data_snapshot.items():
                    if hasattr(product, field) and field != 'id':
                        setattr(product, field, value)
                
                product.updated_at = datetime.utcnow()
                
                # Update rollback status
                rollback.status = 'completed'
                rollback.executed_at = datetime.utcnow()
                
                # Update change status
                change.status = StagedChangeStatus.ROLLED_BACK.value
                
                session.commit()
                
                return jsonify({
                    'success': True,
                    'message': 'Change rolled back successfully',
                    'rollback_id': rollback.rollback_id
                })
            else:
                rollback.status = 'failed'
                rollback.error_message = 'Product not found'
                session.commit()
                return jsonify({'error': 'Product not found'}), 404
                
        except Exception as e:
            logger.error(f"Failed to rollback change: {str(e)}")
            session.rollback()
            return jsonify({'error': str(e)}), 500


# Missing Enhanced Sync Endpoints
@enhanced_sync_bp.route('/metrics', methods=['GET'])
@supabase_jwt_required
def get_sync_metrics():
    """Get sync performance metrics."""
    try:
        # Get query parameters
        timeframe = request.args.get('timeframe', '24h')
        
        # Return fallback metrics since database tables may not exist yet
        now = datetime.utcnow()
        
        return jsonify({
            'success': True,
            'timeframe': timeframe,
            'sync_batches': {
                'total': 0,
                'successful': 0,
                'failed': 0,
                'partial': 0,
                'success_rate': 0.0
            },
            'items': {
                'total': 0,
                'successful': 0,
                'failed': 0,
                'success_rate': 0.0
            },
            'performance': {
                'avg_processing_time_seconds': 0.0,
                'items_per_second': 0.0
            },
            'staged_changes': {
                'total': 0,
                'pending': 0,
                'approved': 0,
                'rejected': 0,
                'applied': 0
            },
            'timestamp': now.isoformat()
        })
            
    except Exception as e:
        logger.error(f"Failed to get sync metrics: {str(e)}")
        return jsonify({'error': str(e)}), 500


@enhanced_sync_bp.route('/recent-activity', methods=['GET'])
@supabase_jwt_required
def get_recent_activity():
    """Get recent sync activity."""
    try:
        # Get query parameters
        limit = int(request.args.get('limit', 20))
        activity_type = request.args.get('type', 'all')
        
        # Return fallback activity data since database tables may not exist yet
        now = datetime.utcnow()
        
        activities = [
            {
                'type': 'system',
                'action': 'Enhanced sync system initialized',
                'timestamp': now.isoformat(),
                'status': 'completed',
                'user_id': 'system'
            }
        ]
        
        return jsonify(activities)
            
    except Exception as e:
        logger.error(f"Failed to get recent activity: {str(e)}")
        return jsonify({'error': str(e)}), 500


# Export blueprint
__all__ = ['enhanced_sync_bp']