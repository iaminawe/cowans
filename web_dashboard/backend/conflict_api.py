"""API endpoints for data conflict detection and resolution."""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from conflict_detector import conflict_detector, ConflictSeverity
from database import db_session_scope
from repositories.user_repository import UserRepository


def get_user_id():
    """Helper function to get numeric user ID, handling dev mode."""
    jwt_identity = get_jwt_identity()
    if jwt_identity == "dev-user":
        return 1  # Development mode fallback
    try:
        return int(jwt_identity)
    except (ValueError, TypeError):
        return 1  # Fallback for invalid ID

logger = logging.getLogger(__name__)

conflict_bp = Blueprint('conflict', __name__, url_prefix='/api/conflicts')


@conflict_bp.route('/detect', methods=['POST'])
@jwt_required()
def detect_conflicts():
    """Detect conflicts between source and target records."""
    try:
        data = request.get_json()
        source_record = data.get('source_record', {})
        target_record = data.get('target_record', {})
        key_field = data.get('key_field', 'id')
        ignore_fields = set(data.get('ignore_fields', []))
        
        if not source_record or not target_record:
            return jsonify({'message': 'Both source_record and target_record are required'}), 400
        
        conflict = conflict_detector.detect_conflicts(
            source_record=source_record,
            target_record=target_record,
            key_field=key_field,
            ignore_fields=ignore_fields
        )
        
        if conflict:
            return jsonify({
                'conflict_detected': True,
                'conflict': {
                    'id': conflict.id,
                    'severity': conflict.severity.value,
                    'status': conflict.status,
                    'detected_at': conflict.detected_at.isoformat(),
                    'is_auto_resolvable': conflict.is_auto_resolvable,
                    'conflicts': [
                        {
                            'field_name': c.field_name,
                            'conflict_type': c.conflict_type.value,
                            'severity': c.severity.value,
                            'source_value': c.source_value,
                            'target_value': c.target_value,
                            'description': c.description,
                            'auto_resolvable': c.auto_resolvable,
                            'resolution_strategy': c.resolution_strategy,
                            'confidence_score': c.confidence_score
                        }
                        for c in conflict.conflicts
                    ]
                }
            })
        else:
            return jsonify({
                'conflict_detected': False,
                'message': 'No conflicts detected between records'
            })
            
    except Exception as e:
        logger.error(f"Error detecting conflicts: {str(e)}")
        return jsonify({'message': f'Failed to detect conflicts: {str(e)}'}), 500


@conflict_bp.route('/batch-detect', methods=['POST'])
@jwt_required()
def batch_detect_conflicts():
    """Detect conflicts for multiple record pairs."""
    try:
        data = request.get_json()
        record_pairs = data.get('record_pairs', [])
        key_field = data.get('key_field', 'id')
        ignore_fields = set(data.get('ignore_fields', []))
        
        if not record_pairs:
            return jsonify({'message': 'record_pairs is required'}), 400
        
        results = []
        conflict_count = 0
        
        for i, pair in enumerate(record_pairs):
            source_record = pair.get('source_record', {})
            target_record = pair.get('target_record', {})
            
            if not source_record or not target_record:
                results.append({
                    'index': i,
                    'error': 'Both source_record and target_record are required'
                })
                continue
            
            conflict = conflict_detector.detect_conflicts(
                source_record=source_record,
                target_record=target_record,
                key_field=key_field,
                ignore_fields=ignore_fields
            )
            
            if conflict:
                conflict_count += 1
                results.append({
                    'index': i,
                    'conflict_detected': True,
                    'conflict_id': conflict.id,
                    'severity': conflict.severity.value,
                    'conflict_count': len(conflict.conflicts),
                    'is_auto_resolvable': conflict.is_auto_resolvable
                })
            else:
                results.append({
                    'index': i,
                    'conflict_detected': False
                })
        
        return jsonify({
            'total_pairs': len(record_pairs),
            'conflicts_detected': conflict_count,
            'results': results
        })
        
    except Exception as e:
        logger.error(f"Error in batch conflict detection: {str(e)}")
        return jsonify({'message': f'Failed to detect conflicts: {str(e)}'}), 500


@conflict_bp.route('/', methods=['GET'])
@jwt_required()
def list_conflicts():
    """List conflicts with optional filtering."""
    try:
        status_filter = request.args.get('status')
        severity_filter = request.args.get('severity')
        limit = min(int(request.args.get('limit', 50)), 200)
        
        # Convert severity filter
        severity_enum = None
        if severity_filter:
            try:
                severity_enum = ConflictSeverity(severity_filter)
            except ValueError:
                return jsonify({'message': f'Invalid severity: {severity_filter}'}), 400
        
        conflicts = conflict_detector.get_conflicts(
            status_filter=status_filter,
            severity_filter=severity_enum
        )
        
        # Paginate results
        conflicts = conflicts[:limit]
        
        return jsonify({
            'conflicts': [
                {
                    'id': conflict.id,
                    'severity': conflict.severity.value,
                    'status': conflict.status,
                    'detected_at': conflict.detected_at.isoformat(),
                    'resolved_at': conflict.resolved_at.isoformat() if conflict.resolved_at else None,
                    'resolution_method': conflict.resolution_method,
                    'resolved_by': conflict.resolved_by,
                    'is_auto_resolvable': conflict.is_auto_resolvable,
                    'conflict_count': len(conflict.conflicts),
                    'source_record_preview': {
                        k: v for k, v in list(conflict.source_record.items())[:3]
                    },
                    'target_record_preview': {
                        k: v for k, v in list(conflict.target_record.items())[:3]
                    }
                }
                for conflict in conflicts
            ],
            'total_count': len(conflicts),
            'limit': limit
        })
        
    except Exception as e:
        logger.error(f"Error listing conflicts: {str(e)}")
        return jsonify({'message': f'Failed to list conflicts: {str(e)}'}), 500


@conflict_bp.route('/<conflict_id>', methods=['GET'])
@jwt_required()
def get_conflict_details(conflict_id: str):
    """Get detailed information about a specific conflict."""
    try:
        conflicts = conflict_detector.get_conflicts()
        conflict = next((c for c in conflicts if c.id == conflict_id), None)
        
        if not conflict:
            return jsonify({'message': 'Conflict not found'}), 404
        
        return jsonify({
            'id': conflict.id,
            'severity': conflict.severity.value,
            'status': conflict.status,
            'detected_at': conflict.detected_at.isoformat(),
            'resolved_at': conflict.resolved_at.isoformat() if conflict.resolved_at else None,
            'resolution_method': conflict.resolution_method,
            'resolved_by': conflict.resolved_by,
            'is_auto_resolvable': conflict.is_auto_resolvable,
            'source_record': conflict.source_record,
            'target_record': conflict.target_record,
            'conflicts': [
                {
                    'field_name': c.field_name,
                    'conflict_type': c.conflict_type.value,
                    'severity': c.severity.value,
                    'source_value': c.source_value,
                    'target_value': c.target_value,
                    'description': c.description,
                    'auto_resolvable': c.auto_resolvable,
                    'resolution_strategy': c.resolution_strategy,
                    'confidence_score': c.confidence_score
                }
                for c in conflict.conflicts
            ]
        })
        
    except Exception as e:
        logger.error(f"Error getting conflict details: {str(e)}")
        return jsonify({'message': f'Failed to get conflict details: {str(e)}'}), 500


@conflict_bp.route('/<conflict_id>/resolve', methods=['POST'])
@jwt_required()
def resolve_conflict(conflict_id: str):
    """Manually resolve a conflict."""
    try:
        data = request.get_json()
        resolution = data.get('resolution', {})
        
        if not resolution:
            return jsonify({'message': 'Resolution data is required'}), 400
        
        user_id = get_user_id()
        
        # Get user info for logging
        try:
            with db_session_scope() as session:
                user_repo = UserRepository(session)
                # Try to get user by ID (if method exists)
                user = getattr(user_repo, 'get_by_id', lambda x: None)(user_id)
                if user:
                    resolved_by = f"{user.first_name} {user.last_name}"
                else:
                    resolved_by = f"User {user_id}"
        except:
            # If database is not available or method doesn't exist, use fallback
            resolved_by = f"User {user_id}"
        
        success = conflict_detector.resolve_conflict(
            conflict_id=conflict_id,
            resolution=resolution,
            resolved_by=resolved_by
        )
        
        if success:
            return jsonify({
                'message': 'Conflict resolved successfully',
                'resolved_by': resolved_by,
                'resolved_at': datetime.utcnow().isoformat()
            })
        else:
            return jsonify({'message': 'Conflict not found or already resolved'}), 404
            
    except Exception as e:
        logger.error(f"Error resolving conflict: {str(e)}")
        return jsonify({'message': f'Failed to resolve conflict: {str(e)}'}), 500


@conflict_bp.route('/stats', methods=['GET'])
@jwt_required()
def get_conflict_stats():
    """Get conflict statistics."""
    try:
        stats = conflict_detector.get_conflict_stats()
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Error getting conflict stats: {str(e)}")
        return jsonify({'message': f'Failed to get stats: {str(e)}'}), 500


@conflict_bp.route('/auto-resolve', methods=['POST'])
@jwt_required()
def auto_resolve_conflicts():
    """Auto-resolve all auto-resolvable conflicts."""
    try:
        data = request.get_json() or {}
        severity_limit = data.get('severity_limit', 'medium')  # Only auto-resolve up to this severity
        
        # Convert severity limit
        try:
            max_severity = ConflictSeverity(severity_limit)
        except ValueError:
            return jsonify({'message': f'Invalid severity limit: {severity_limit}'}), 400
        
        conflicts = conflict_detector.get_conflicts(status_filter='pending')
        auto_resolved_count = 0
        
        for conflict in conflicts:
            # Check if conflict can be auto-resolved and is within severity limit
            if (conflict.is_auto_resolvable and 
                conflict.severity.value <= max_severity.value):
                
                conflict_detector._attempt_auto_resolution(conflict)
                auto_resolved_count += 1
        
        return jsonify({
            'message': f'Auto-resolved {auto_resolved_count} conflicts',
            'auto_resolved_count': auto_resolved_count,
            'total_pending_conflicts': len(conflicts)
        })
        
    except Exception as e:
        logger.error(f"Error auto-resolving conflicts: {str(e)}")
        return jsonify({'message': f'Failed to auto-resolve conflicts: {str(e)}'}), 500


@conflict_bp.route('/rules', methods=['GET'])
@jwt_required()
def get_resolution_rules():
    """Get current conflict resolution rules."""
    try:
        return jsonify({
            'resolution_rules': conflict_detector.resolution_rules,
            'business_rules': [
                {
                    'name': rule['name'],
                    'description': rule['description'],
                    'field': rule['field']
                }
                for rule in conflict_detector.business_rules
            ]
        })
        
    except Exception as e:
        logger.error(f"Error getting resolution rules: {str(e)}")
        return jsonify({'message': f'Failed to get rules: {str(e)}'}), 500


@conflict_bp.route('/cleanup', methods=['POST'])
@jwt_required()
def cleanup_old_conflicts():
    """Clean up old resolved conflicts (admin only)."""
    user_id = get_user_id()
    
    # Check if user is admin
    with db_session_scope() as session:
        user_repo = UserRepository(session)
        user = user_repo.get_by_id(user_id)
        
        if not user or not user.is_admin:
            return jsonify({"message": "Admin access required"}), 403
    
    try:
        max_age_days = int(request.args.get('max_age_days', 30))
        cutoff_date = datetime.utcnow() - timedelta(days=max_age_days)
        
        cleaned_count = 0
        conflicts_to_remove = []
        
        for conflict_id, conflict in conflict_detector.detected_conflicts.items():
            if (conflict.status in ['auto_resolved', 'manually_resolved'] and 
                conflict.resolved_at and conflict.resolved_at < cutoff_date):
                conflicts_to_remove.append(conflict_id)
        
        for conflict_id in conflicts_to_remove:
            del conflict_detector.detected_conflicts[conflict_id]
            cleaned_count += 1
        
        logger.info(f"Cleaned up {cleaned_count} old conflicts (older than {max_age_days} days) by user {user_id}")
        
        return jsonify({
            'message': f'Cleaned up {cleaned_count} old conflicts',
            'max_age_days': max_age_days
        })
        
    except Exception as e:
        logger.error(f"Error cleaning up conflicts: {str(e)}")
        return jsonify({'message': f'Failed to cleanup conflicts: {str(e)}'}), 500