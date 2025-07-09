"""Admin API endpoints for user management and system administration."""

from flask import Blueprint, jsonify, request
# from flask_jwt_extended import jwt_required, get_jwt_identity  # Replaced with Supabase auth
from services.supabase_auth import (
    supabase_jwt_required, get_current_user_id, require_role, 
    get_current_user_email, auth_service
)
from marshmallow import Schema, fields, validate, ValidationError
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import logging
import json
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func, desc

from database import db_session_scope
from repositories import (
    UserRepository, ProductRepository, CategoryRepository,
    JobRepository, SyncHistoryRepository
)
from models import User, Product, Category, Job, SyncHistory, JobStatus
from error_tracking import error_tracker

# Configure logging
logger = logging.getLogger(__name__)

# Create Blueprint
admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')

# Schemas
class UserCreateSchema(Schema):
    """Schema for creating users."""
    email = fields.Email(required=True)
    first_name = fields.String(required=True, validate=validate.Length(min=1, max=100))
    last_name = fields.String(required=True, validate=validate.Length(min=1, max=100))
    password = fields.String(required=True, validate=validate.Length(min=8, max=128))
    is_admin = fields.Boolean(default=False)
    is_active = fields.Boolean(default=True)

class UserUpdateSchema(Schema):
    """Schema for updating users."""
    first_name = fields.String(validate=validate.Length(min=1, max=100))
    last_name = fields.String(validate=validate.Length(min=1, max=100))
    is_admin = fields.Boolean()
    is_active = fields.Boolean()

class UserResponseSchema(Schema):
    """Schema for user responses."""
    id = fields.Integer()
    email = fields.String()
    first_name = fields.String()
    last_name = fields.String()
    is_admin = fields.Boolean()
    is_active = fields.Boolean()
    supabase_id = fields.String()
    last_login = fields.DateTime(allow_none=True)
    created_at = fields.DateTime()
    updated_at = fields.DateTime()
    job_count = fields.Integer()
    recent_activity = fields.List(fields.Dict())

class SystemStatsSchema(Schema):
    """Schema for system statistics."""
    users = fields.Dict()
    products = fields.Dict()
    categories = fields.Dict()
    jobs = fields.Dict()
    sync_history = fields.Dict()
    system = fields.Dict()

class JobManagementSchema(Schema):
    """Schema for job management actions."""
    action = fields.String(required=True, validate=validate.OneOf(['cancel', 'retry', 'delete']))
    job_ids = fields.List(fields.Integer(), required=True)

# Initialize schemas
user_create_schema = UserCreateSchema()
user_update_schema = UserUpdateSchema()
user_response_schema = UserResponseSchema()
users_response_schema = UserResponseSchema(many=True)
system_stats_schema = SystemStatsSchema()
job_management_schema = JobManagementSchema()

@admin_bp.route('/dashboard', methods=['GET'])
@supabase_jwt_required
@require_role('admin')
def get_admin_dashboard():
    """Get admin dashboard overview."""
    try:
        with db_session_scope() as session:
            user_repo = UserRepository(session)
            product_repo = ProductRepository(session)
            category_repo = CategoryRepository(session)
            job_repo = JobRepository(session)
            sync_repo = SyncHistoryRepository(session)
            
            # Calculate date ranges
            now = datetime.utcnow()
            week_ago = now - timedelta(days=7)
            month_ago = now - timedelta(days=30)
            
            # User statistics
            user_stats = {
                'total': user_repo.count(),
                'active': user_repo.count_active(),
                'admins': user_repo.count_admins(),
                'new_this_week': user_repo.count_created_since(week_ago),
                'new_this_month': user_repo.count_created_since(month_ago)
            }
            
            # Product statistics
            product_stats = {
                'total': product_repo.count(),
                'active': product_repo.count_active(),
                'with_shopify_sync': product_repo.count_synced_to_shopify(),
                'pending_sync': product_repo.count_pending_sync(),
                'new_this_week': product_repo.count_created_since(week_ago),
                'new_this_month': product_repo.count_created_since(month_ago)
            }
            
            # Category statistics  
            category_stats = {
                'total': category_repo.count(),
                'active': category_repo.count_active(),
                'with_products': category_repo.count_with_products(),
                'empty': category_repo.count_empty(),
                'max_depth': category_repo.get_max_depth()
            }
            
            # Job statistics
            job_stats = {
                'total': job_repo.count(),
                'running': job_repo.count_by_status(JobStatus.RUNNING),
                'pending': job_repo.count_by_status(JobStatus.PENDING),
                'completed': job_repo.count_by_status(JobStatus.COMPLETED),
                'failed': job_repo.count_by_status(JobStatus.FAILED),
                'today': job_repo.count_created_today()
            }
            
            # Sync history statistics
            sync_stats = {
                'total_syncs': sync_repo.count(),
                'successful_syncs': sync_repo.count_successful(),
                'failed_syncs': sync_repo.count_failed(),
                'this_week': sync_repo.count_since(week_ago),
                'avg_products_per_sync': sync_repo.get_avg_products_per_sync()
            }
            
            # System health
            system_stats = {
                'error_rate': error_tracker.get_error_rate(),
                'avg_response_time': error_tracker.get_avg_response_time(),
                'uptime_percentage': 99.9,  # This would come from monitoring
                'database_size': product_repo.get_database_size_mb(),
                'last_backup': None  # This would come from backup system
            }
            
            # Recent activity
            recent_jobs = job_repo.get_recent(limit=10)
            recent_activity = []
            for job in recent_jobs:
                recent_activity.append({
                    'id': job.id,
                    'script_name': job.script_name,
                    'status': job.status,
                    'created_at': job.created_at.isoformat(),
                    'user_email': job.user.email if job.user else 'System'
                })
            
            # Performance metrics
            performance = {
                'avg_job_duration': job_repo.get_avg_duration(),
                'jobs_per_hour': job_repo.get_jobs_per_hour(),
                'success_rate': job_repo.get_success_rate()
            }
        
        dashboard_data = {
            'users': user_stats,
            'products': product_stats,
            'categories': category_stats,
            'jobs': job_stats,
            'sync_history': sync_stats,
            'system': system_stats,
            'recent_activity': recent_activity,
            'performance': performance,
            'generated_at': now.isoformat()
        }
        
        return jsonify(dashboard_data), 200
    
    except Exception as e:
        logger.error(f"Error fetching admin dashboard: {str(e)}")
        return jsonify({'error': 'Failed to fetch dashboard data'}), 500

@admin_bp.route('/users', methods=['GET'])
@supabase_jwt_required
@require_role('admin')
def get_users():
    """Get all users with filtering and pagination."""
    try:
        # Query parameters
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 50, type=int)
        search = request.args.get('search', '').strip()
        is_active = request.args.get('is_active')
        is_admin = request.args.get('is_admin')
        sort_by = request.args.get('sort_by', 'created_at')
        sort_order = request.args.get('sort_order', 'desc')
        
        with db_session_scope() as session:
            user_repo = UserRepository(session)
            job_repo = JobRepository(session)
            
            # Build filters
            filters = {}
            if is_active is not None:
                filters['is_active'] = is_active.lower() == 'true'
            if is_admin is not None:
                filters['is_admin'] = is_admin.lower() == 'true'
            
            # Get users with pagination
            users, total = user_repo.get_paginated(
                page=page,
                limit=limit,
                search=search,
                filters=filters,
                sort_by=sort_by,
                sort_order=sort_order
            )
            
            # Add additional data for each user
            users_data = []
            for user in users:
                user_data = {
                    'id': user.id,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'is_admin': user.is_admin,
                    'is_active': user.is_active,
                    'supabase_id': user.supabase_id,
                    'last_login': user.last_login.isoformat() if user.last_login else None,
                    'created_at': user.created_at.isoformat(),
                    'updated_at': user.updated_at.isoformat(),
                    'job_count': job_repo.count_by_user(user.id)
                }
                
                # Add recent activity
                recent_jobs = job_repo.get_by_user(user.id, limit=5)
                user_data['recent_activity'] = [
                    {
                        'script_name': job.script_name,
                        'status': job.status,
                        'created_at': job.created_at.isoformat()
                    } for job in recent_jobs
                ]
                
                users_data.append(user_data)
        
        return jsonify({
            'users': users_data,
            'pagination': {
                'page': page,
                'limit': limit,
                'total': total,
                'pages': (total + limit - 1) // limit
            }
        }), 200
    
    except Exception as e:
        logger.error(f"Error fetching users: {str(e)}")
        return jsonify({'error': 'Failed to fetch users'}), 500

@admin_bp.route('/users/<int:user_id>', methods=['GET'])
@supabase_jwt_required
@require_role('admin')
def get_user(user_id: int):
    """Get detailed information about a specific user."""
    try:
        with db_session_scope() as session:
            user_repo = UserRepository(session)
            job_repo = JobRepository(session)
            
            user = user_repo.get(user_id)
            if not user:
                return jsonify({'error': 'User not found'}), 404
            
            # Get user's job history
            jobs = job_repo.get_by_user(user_id, limit=50)
            job_history = []
            for job in jobs:
                job_history.append({
                    'id': job.id,
                    'script_name': job.script_name,
                    'status': job.status,
                    'progress': job.progress,
                    'created_at': job.created_at.isoformat(),
                    'started_at': job.started_at.isoformat() if job.started_at else None,
                    'completed_at': job.completed_at.isoformat() if job.completed_at else None,
                    'duration': job.actual_duration,
                    'error_message': job.error_message
                })
            
            # Get user statistics
            job_stats = {
                'total': job_repo.count_by_user(user_id),
                'completed': job_repo.count_by_user_and_status(user_id, JobStatus.COMPLETED),
                'failed': job_repo.count_by_user_and_status(user_id, JobStatus.FAILED),
                'avg_duration': job_repo.get_avg_duration_by_user(user_id)
            }
            
            user_data = {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'is_admin': user.is_admin,
                'is_active': user.is_active,
                'supabase_id': user.supabase_id,
                'last_login': user.last_login.isoformat() if user.last_login else None,
                'created_at': user.created_at.isoformat(),
                'updated_at': user.updated_at.isoformat(),
                'job_statistics': job_stats,
                'job_history': job_history
            }
        
        return jsonify(user_data), 200
    
    except Exception as e:
        logger.error(f"Error fetching user {user_id}: {str(e)}")
        return jsonify({'error': 'Failed to fetch user'}), 500

@admin_bp.route('/users', methods=['POST'])
@supabase_jwt_required
@require_role('admin')
def create_user():
    """Create a new user (admin only)."""
    try:
        # Validate input
        data = user_create_schema.load(request.get_json())
        
        # Create user in Supabase first
        supabase_result = auth_service.admin_create_user(
            email=data['email'],
            password=data['password'],
            user_metadata={
                'first_name': data['first_name'],
                'last_name': data['last_name'],
                'is_admin': data.get('is_admin', False)
            }
        )
        
        # Create local user record
        with db_session_scope() as session:
            user_repo = UserRepository(session)
            
            user_data = {
                'email': data['email'],
                'first_name': data['first_name'],
                'last_name': data['last_name'],
                'is_admin': data.get('is_admin', False),
                'is_active': data.get('is_active', True),
                'supabase_id': supabase_result['user']['id'],
                'password_hash': ''  # Not stored locally
            }
            
            user = user_repo.create(**user_data)
            session.commit()
            
            user_response = {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'is_admin': user.is_admin,
                'is_active': user.is_active,
                'created_at': user.created_at.isoformat()
            }
        
        logger.info(f"Created user: {user.email} (ID: {user.id})")
        return jsonify(user_response), 201
    
    except ValidationError as e:
        return jsonify({'error': 'Validation failed', 'details': e.messages}), 400
    except IntegrityError as e:
        return jsonify({'error': 'User with this email already exists'}), 409
    except Exception as e:
        logger.error(f"Error creating user: {str(e)}")
        return jsonify({'error': 'Failed to create user'}), 500

@admin_bp.route('/users/<int:user_id>', methods=['PUT'])
@supabase_jwt_required
@require_role('admin')
def update_user(user_id: int):
    """Update an existing user (admin only)."""
    try:
        # Validate input
        data = user_update_schema.load(request.get_json())
        
        with db_session_scope() as session:
            user_repo = UserRepository(session)
            user = user_repo.get(user_id)
            
            if not user:
                return jsonify({'error': 'User not found'}), 404
            
            # Update user
            updated_user = user_repo.update(user_id, **data)
            session.commit()
            
            # Update Supabase user metadata if needed
            if user.supabase_id and any(k in data for k in ['first_name', 'last_name', 'is_admin']):
                metadata_update = {}
                if 'first_name' in data:
                    metadata_update['first_name'] = data['first_name']
                if 'last_name' in data:
                    metadata_update['last_name'] = data['last_name']
                if 'is_admin' in data:
                    metadata_update['is_admin'] = data['is_admin']
                
                try:
                    auth_service.admin_update_user_metadata(user.supabase_id, metadata_update)
                except Exception as e:
                    logger.warning(f"Failed to update Supabase metadata for user {user_id}: {e}")
            
            user_response = {
                'id': updated_user.id,
                'email': updated_user.email,
                'first_name': updated_user.first_name,
                'last_name': updated_user.last_name,
                'is_admin': updated_user.is_admin,
                'is_active': updated_user.is_active,
                'updated_at': updated_user.updated_at.isoformat()
            }
        
        logger.info(f"Updated user: {updated_user.email} (ID: {user_id})")
        return jsonify(user_response), 200
    
    except ValidationError as e:
        return jsonify({'error': 'Validation failed', 'details': e.messages}), 400
    except Exception as e:
        logger.error(f"Error updating user {user_id}: {str(e)}")
        return jsonify({'error': 'Failed to update user'}), 500

@admin_bp.route('/users/<int:user_id>', methods=['DELETE'])
@supabase_jwt_required
@require_role('admin')
def delete_user(user_id: int):
    """Delete a user (admin only)."""
    try:
        current_user_id = get_current_user_id()
        
        # Prevent self-deletion
        if user_id == current_user_id:
            return jsonify({'error': 'Cannot delete your own account'}), 400
        
        with db_session_scope() as session:
            user_repo = UserRepository(session)
            job_repo = JobRepository(session)
            
            user = user_repo.get(user_id)
            if not user:
                return jsonify({'error': 'User not found'}), 404
            
            # Check if user has running jobs
            running_jobs = job_repo.count_by_user_and_status(user_id, JobStatus.RUNNING)
            if running_jobs > 0:
                return jsonify({
                    'error': 'Cannot delete user with running jobs',
                    'running_jobs': running_jobs
                }), 400
            
            # Delete from Supabase if exists
            if user.supabase_id:
                try:
                    auth_service.admin_delete_user(user.supabase_id)
                except Exception as e:
                    logger.warning(f"Failed to delete Supabase user {user.supabase_id}: {e}")
            
            # Delete local user
            user_repo.delete(user_id)
            session.commit()
        
        logger.info(f"Deleted user: {user.email} (ID: {user_id})")
        return jsonify({'message': 'User deleted successfully'}), 200
    
    except Exception as e:
        logger.error(f"Error deleting user {user_id}: {str(e)}")
        return jsonify({'error': 'Failed to delete user'}), 500

@admin_bp.route('/jobs', methods=['GET'])
@supabase_jwt_required
@require_role('admin')
def get_all_jobs():
    """Get all jobs with filtering and pagination."""
    try:
        # Query parameters
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 50, type=int)
        status = request.args.get('status')
        script_name = request.args.get('script_name')
        user_id = request.args.get('user_id', type=int)
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        
        with db_session_scope() as session:
            job_repo = JobRepository(session)
            
            # Build filters
            filters = {}
            if status:
                filters['status'] = status
            if script_name:
                filters['script_name'] = script_name
            if user_id:
                filters['user_id'] = user_id
            
            # Date range filters
            date_filters = {}
            if date_from:
                date_filters['date_from'] = datetime.fromisoformat(date_from)
            if date_to:
                date_filters['date_to'] = datetime.fromisoformat(date_to)
            
            # Get jobs with pagination
            jobs, total = job_repo.get_paginated_with_users(
                page=page,
                limit=limit,
                filters=filters,
                date_filters=date_filters
            )
            
            # Format response
            jobs_data = []
            for job in jobs:
                jobs_data.append({
                    'id': job.id,
                    'script_name': job.script_name,
                    'status': job.status,
                    'progress': job.progress,
                    'current_stage': job.current_stage,
                    'created_at': job.created_at.isoformat(),
                    'started_at': job.started_at.isoformat() if job.started_at else None,
                    'completed_at': job.completed_at.isoformat() if job.completed_at else None,
                    'duration': job.actual_duration,
                    'user': {
                        'id': job.user.id,
                        'email': job.user.email,
                        'name': f"{job.user.first_name} {job.user.last_name}"
                    } if job.user else None,
                    'error_message': job.error_message,
                    'parameters': job.parameters
                })
        
        return jsonify({
            'jobs': jobs_data,
            'pagination': {
                'page': page,
                'limit': limit,
                'total': total,
                'pages': (total + limit - 1) // limit
            }
        }), 200
    
    except Exception as e:
        logger.error(f"Error fetching jobs: {str(e)}")
        return jsonify({'error': 'Failed to fetch jobs'}), 500

@admin_bp.route('/jobs/manage', methods=['POST'])
@supabase_jwt_required
@require_role('admin')
def manage_jobs():
    """Perform bulk actions on jobs."""
    try:
        # Validate input
        data = job_management_schema.load(request.get_json())
        action = data['action']
        job_ids = data['job_ids']
        
        results = []
        errors = []
        
        with db_session_scope() as session:
            job_repo = JobRepository(session)
            
            for job_id in job_ids:
                try:
                    job = job_repo.get(job_id)
                    if not job:
                        errors.append(f"Job {job_id} not found")
                        continue
                    
                    if action == 'cancel':
                        if job.status in [JobStatus.RUNNING.value, JobStatus.PENDING.value]:
                            job_repo.update(job_id, status=JobStatus.CANCELLED.value)
                            results.append(f"Cancelled job {job_id}")
                        else:
                            errors.append(f"Job {job_id} cannot be cancelled (status: {job.status})")
                    
                    elif action == 'retry':
                        if job.status in [JobStatus.FAILED.value, JobStatus.CANCELLED.value]:
                            job_repo.update(job_id, 
                                status=JobStatus.PENDING.value,
                                progress=0,
                                error_message=None,
                                started_at=None,
                                completed_at=None
                            )
                            results.append(f"Reset job {job_id} for retry")
                        else:
                            errors.append(f"Job {job_id} cannot be retried (status: {job.status})")
                    
                    elif action == 'delete':
                        if job.status not in [JobStatus.RUNNING.value]:
                            job_repo.delete(job_id)
                            results.append(f"Deleted job {job_id}")
                        else:
                            errors.append(f"Cannot delete running job {job_id}")
                
                except Exception as e:
                    errors.append(f"Error with job {job_id}: {str(e)}")
            
            session.commit()
        
        return jsonify({
            'success': len(results),
            'errors': len(errors),
            'results': results,
            'error_details': errors
        }), 200
    
    except ValidationError as e:
        return jsonify({'error': 'Validation failed', 'details': e.messages}), 400
    except Exception as e:
        logger.error(f"Error in job management: {str(e)}")
        return jsonify({'error': 'Job management failed'}), 500

@admin_bp.route('/system/health', methods=['GET'])
@supabase_jwt_required
@require_role('admin')
def get_system_health():
    """Get system health status."""
    try:
        with db_session_scope() as session:
            # Database connectivity check
            session.execute('SELECT 1')
            db_status = 'healthy'
        
        # Additional health checks would go here
        health_data = {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'components': {
                'database': {
                    'status': db_status,
                    'response_time_ms': 5  # This would be measured
                },
                'auth_service': {
                    'status': 'healthy',  # This would check Supabase
                    'response_time_ms': 10
                },
                'file_storage': {
                    'status': 'healthy',  # This would check file system
                    'disk_usage_percent': 45
                },
                'external_apis': {
                    'shopify': 'healthy',  # This would check Shopify API
                    'openai': 'healthy'    # This would check OpenAI API
                }
            },
            'metrics': {
                'error_rate': error_tracker.get_error_rate(),
                'avg_response_time': error_tracker.get_avg_response_time(),
                'requests_per_minute': error_tracker.get_requests_per_minute(),
                'memory_usage_mb': 150,  # This would be measured
                'cpu_usage_percent': 25  # This would be measured
            }
        }
        
        return jsonify(health_data), 200
    
    except Exception as e:
        logger.error(f"Error checking system health: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@admin_bp.route('/system/logs', methods=['GET'])
@supabase_jwt_required
@require_role('admin')
def get_system_logs():
    """Get system logs."""
    try:
        level = request.args.get('level', 'INFO').upper()
        limit = request.args.get('limit', 100, type=int)
        since = request.args.get('since')  # ISO datetime string
        
        # This is a simplified implementation
        # In production, you'd read from actual log files or logging service
        
        logs = [
            {
                'timestamp': datetime.utcnow().isoformat(),
                'level': 'INFO',
                'logger': 'admin_api',
                'message': 'System logs accessed',
                'user': get_current_user_email()
            }
        ]
        
        return jsonify({
            'logs': logs,
            'total': len(logs),
            'level_filter': level,
            'limit': limit
        }), 200
    
    except Exception as e:
        logger.error(f"Error fetching system logs: {str(e)}")
        return jsonify({'error': 'Failed to fetch logs'}), 500

@admin_bp.route('/system/settings', methods=['GET'])
@supabase_jwt_required
@require_role('admin')
def get_system_settings():
    """Get system configuration settings."""
    try:
        import os
        
        # Return safe, non-sensitive settings
        settings = {
            'flask_env': os.getenv('FLASK_ENV', 'development'),
            'debug_mode': os.getenv('DEBUG', 'false').lower() == 'true',
            'cors_origins': ['http://localhost:3055', 'http://localhost:3056'],
            'file_upload_max_size_mb': 100,
            'job_timeout_minutes': 30,
            'api_rate_limit': '100/hour',
            'features': {
                'icon_generation': True,
                'shopify_sync': True,
                'batch_processing': True,
                'webhooks': False  # Currently disabled
            }
        }
        
        return jsonify(settings), 200
    
    except Exception as e:
        logger.error(f"Error fetching system settings: {str(e)}")
        return jsonify({'error': 'Failed to fetch settings'}), 500

@admin_bp.route('/analytics/performance', methods=['GET'])
@supabase_jwt_required
@require_role('admin')
def get_performance_analytics():
    """Get performance analytics and metrics."""
    try:
        days = request.args.get('days', 7, type=int)
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        with db_session_scope() as session:
            job_repo = JobRepository(session)
            
            # Performance metrics over time
            daily_metrics = job_repo.get_daily_metrics(start_date, end_date)
            
            # Script performance
            script_performance = job_repo.get_script_performance_stats()
            
            # Error analysis
            error_analysis = job_repo.get_error_analysis(start_date, end_date)
            
            analytics = {
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'days': days
                },
                'daily_metrics': daily_metrics,
                'script_performance': script_performance,
                'error_analysis': error_analysis,
                'overall_stats': {
                    'total_jobs': job_repo.count_in_period(start_date, end_date),
                    'avg_job_duration': job_repo.get_avg_duration_in_period(start_date, end_date),
                    'success_rate': job_repo.get_success_rate_in_period(start_date, end_date),
                    'peak_concurrent_jobs': job_repo.get_peak_concurrent_jobs(start_date, end_date)
                }
            }
        
        return jsonify(analytics), 200
    
    except Exception as e:
        logger.error(f"Error fetching performance analytics: {str(e)}")
        return jsonify({'error': 'Failed to fetch analytics'}), 500