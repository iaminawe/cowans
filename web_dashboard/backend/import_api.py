"""
Import API Endpoints

This module provides REST API endpoints for the Etilize import functionality.
It integrates with the EtilizeImportService to handle file uploads and processing.
"""

import os
import json
import uuid
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage

from services.import_service import (
    EtilizeImportService, ImportConfiguration, 
    ImportProgress, ImportResult
)
from database import db_session_scope
from models import User

logger = logging.getLogger(__name__)

# Create blueprint for import endpoints
import_bp = Blueprint('import', __name__, url_prefix='/api/import')

ALLOWED_EXTENSIONS = {'csv', 'txt'}
UPLOAD_FOLDER = 'uploads/imports'

def allowed_file(filename):
    """Check if file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_user_id():
    """Helper function to get numeric user ID."""
    jwt_identity = get_jwt_identity()
    if jwt_identity == "dev-user":
        return 1  # Default dev user ID
    else:
        try:
            return int(jwt_identity)
        except (ValueError, TypeError):
            return 1  # Fallback to default

def save_uploaded_file(file: FileStorage) -> str:
    """Save uploaded file and return the file path."""
    if not file or file.filename == '':
        raise ValueError("No file provided")
    
    if not allowed_file(file.filename):
        raise ValueError("File type not allowed. Please upload CSV files only.")
    
    # Create upload directory if it doesn't exist
    upload_dir = Path(UPLOAD_FOLDER)
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate unique filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_id = str(uuid.uuid4())[:8]
    filename = secure_filename(file.filename)
    name, ext = os.path.splitext(filename)
    
    unique_filename = f"{timestamp}_{file_id}_{name}{ext}"
    file_path = upload_dir / unique_filename
    
    # Save file
    file.save(str(file_path))
    
    logger.info(f"Uploaded file saved to: {file_path}")
    return str(file_path)

@import_bp.route('/upload', methods=['POST'])
@jwt_required()
def upload_file():
    """Upload a CSV file for import.
    
    Returns:
        JSON response with file_path for use in import operations
    """
    try:
        user_id = get_user_id()
        
        # Check if file is in request
        if 'file' not in request.files:
            return jsonify({"error": "No file part in request"}), 400
        
        file = request.files['file']
        
        # Save the uploaded file
        file_path = save_uploaded_file(file)
        
        return jsonify({
            "success": True,
            "message": "File uploaded successfully",
            "file_path": file_path,
            "filename": file.filename
        })
        
    except ValueError as e:
        logger.warning(f"File upload validation error: {str(e)}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"File upload error: {str(e)}")
        return jsonify({"error": "File upload failed"}), 500

@import_bp.route('/validate', methods=['POST'])
@jwt_required()
def validate_import():
    """Validate CSV file without importing.
    
    Request body:
    {
        "file_path": "path/to/uploaded/file.csv",
        "config": {
            "encoding": "utf-8-sig",
            "delimiter": ",",
            "batch_size": 100
        }
    }
    
    Returns:
        JSON response with validation results
    """
    try:
        user_id = get_user_id()
        data = request.get_json()
        
        if not data or 'file_path' not in data:
            return jsonify({"error": "file_path is required"}), 400
        
        file_path = data['file_path']
        config_data = data.get('config', {})
        
        # Validate file exists
        if not os.path.exists(file_path):
            return jsonify({"error": "File not found"}), 404
        
        # Create import configuration
        config = ImportConfiguration(**config_data)
        
        with db_session_scope() as session:
            import_service = EtilizeImportService(session, user_id)
            
            # Parse file to validate format and structure
            try:
                csv_data = import_service._parse_csv_file(file_path, config)
                
                # Basic validation
                if not csv_data:
                    return jsonify({
                        "valid": False,
                        "error": "CSV file is empty"
                    }), 400
                
                # Check for required columns
                first_row = csv_data[0] if csv_data else {}
                required_fields = ['SKU', 'Product Title']
                missing_fields = []
                
                for field in required_fields:
                    # Check various possible column names
                    if not any(field.lower() in col.lower() for col in first_row.keys()):
                        missing_fields.append(field)
                
                if missing_fields:
                    return jsonify({
                        "valid": False,
                        "error": f"Missing required columns: {', '.join(missing_fields)}",
                        "available_columns": list(first_row.keys())
                    }), 400
                
                # Sample data for preview
                sample_records = csv_data[:5]  # First 5 records
                
                return jsonify({
                    "valid": True,
                    "total_records": len(csv_data),
                    "sample_records": sample_records,
                    "available_columns": list(first_row.keys()),
                    "message": f"File is valid with {len(csv_data)} records"
                })
                
            except Exception as e:
                return jsonify({
                    "valid": False,
                    "error": f"File parsing error: {str(e)}"
                }), 400
        
    except Exception as e:
        logger.error(f"Validation error: {str(e)}")
        return jsonify({"error": "Validation failed"}), 500

@import_bp.route('/execute', methods=['POST'])
@jwt_required()
def execute_import():
    """Execute import operation.
    
    Request body:
    {
        "file_path": "path/to/uploaded/file.csv",
        "reference_file_path": "optional/path/to/reference.csv",
        "config": {
            "batch_size": 100,
            "max_errors": 50,
            "validate_references": true,
            "create_missing_categories": false,
            "skip_duplicates": true,
            "encoding": "utf-8-sig"
        }
    }
    
    Returns:
        JSON response with import_id for tracking progress
    """
    try:
        user_id = get_user_id()
        data = request.get_json()
        
        if not data or 'file_path' not in data:
            return jsonify({"error": "file_path is required"}), 400
        
        file_path = data['file_path']
        reference_file_path = data.get('reference_file_path')
        config_data = data.get('config', {})
        
        # Validate file exists
        if not os.path.exists(file_path):
            return jsonify({"error": "File not found"}), 404
        
        if reference_file_path and not os.path.exists(reference_file_path):
            return jsonify({"error": "Reference file not found"}), 404
        
        # Create import configuration
        config = ImportConfiguration(**config_data)
        
        with db_session_scope() as session:
            import_service = EtilizeImportService(session, user_id)
            
            # Start import operation
            result = import_service.import_from_csv(
                file_path, reference_file_path, config
            )
            
            if result.success:
                return jsonify({
                    "success": True,
                    "import_id": result.import_id,
                    "message": "Import started successfully",
                    "total_records": result.total_records
                })
            else:
                return jsonify({
                    "success": False,
                    "import_id": result.import_id,
                    "errors": result.errors,
                    "message": "Import failed"
                }), 400
        
    except Exception as e:
        logger.error(f"Import execution error: {str(e)}")
        return jsonify({"error": "Import execution failed"}), 500

@import_bp.route('/status/<import_id>', methods=['GET'])
@jwt_required()
def get_import_status(import_id: str):
    """Get status of an import operation.
    
    Args:
        import_id: UUID of the import operation
        
    Returns:
        JSON response with current import status and progress
    """
    try:
        user_id = get_user_id()
        
        with db_session_scope() as session:
            import_service = EtilizeImportService(session, user_id)
            
            status = import_service.get_import_status(import_id)
            
            if not status:
                return jsonify({"error": "Import not found"}), 404
            
            return jsonify({
                "import_id": status.import_id,
                "status": status.status,
                "stage": status.stage,
                "total_records": status.total_records,
                "processed_records": status.processed_records,
                "imported_records": status.imported_records,
                "failed_records": status.failed_records,
                "progress_percentage": status.progress_percentage,
                "current_operation": status.current_operation,
                "errors": status.errors
            })
        
    except Exception as e:
        logger.error(f"Status check error: {str(e)}")
        return jsonify({"error": "Failed to get import status"}), 500

@import_bp.route('/history', methods=['GET'])
@jwt_required()
def get_import_history():
    """Get import history for the current user.
    
    Query parameters:
        limit: Maximum number of records to return (default: 50)
        
    Returns:
        JSON response with list of import operations
    """
    try:
        user_id = get_user_id()
        limit = min(int(request.args.get('limit', 50)), 100)  # Max 100 records
        
        with db_session_scope() as session:
            import_service = EtilizeImportService(session, user_id)
            
            history = import_service.get_import_history(limit)
            
            results = []
            for result in history:
                results.append({
                    "import_id": result.import_id,
                    "success": result.success,
                    "total_records": result.total_records,
                    "imported_records": result.imported_records,
                    "failed_records": result.failed_records,
                    "duration_seconds": result.duration_seconds,
                    "batch_id": result.batch_id,
                    "errors": result.errors[:5] if result.errors else []  # Limit errors shown
                })
            
            return jsonify({
                "history": results,
                "count": len(results)
            })
        
    except Exception as e:
        logger.error(f"History retrieval error: {str(e)}")
        return jsonify({"error": "Failed to get import history"}), 500

@import_bp.route('/cancel/<import_id>', methods=['POST'])
@jwt_required()
def cancel_import(import_id: str):
    """Cancel a running import operation.
    
    Args:
        import_id: UUID of the import operation to cancel
        
    Returns:
        JSON response indicating success or failure
    """
    try:
        user_id = get_user_id()
        
        with db_session_scope() as session:
            import_service = EtilizeImportService(session, user_id)
            
            success = import_service.cancel_import(import_id)
            
            if success:
                return jsonify({
                    "success": True,
                    "message": "Import cancelled successfully"
                })
            else:
                return jsonify({
                    "success": False,
                    "message": "Import could not be cancelled (not found or already completed)"
                }), 400
        
    except Exception as e:
        logger.error(f"Import cancellation error: {str(e)}")
        return jsonify({"error": "Failed to cancel import"}), 500

@import_bp.route('/staging/<int:batch_id>', methods=['GET'])
@jwt_required()
def get_staging_data(batch_id: int):
    """Get staging data for a specific import batch.
    
    Args:
        batch_id: ID of the import batch
        
    Query parameters:
        limit: Maximum number of records to return (default: 100)
        offset: Number of records to skip (default: 0)
        status: Filter by processing status
        
    Returns:
        JSON response with staging records
    """
    try:
        user_id = get_user_id()
        limit = min(int(request.args.get('limit', 100)), 500)  # Max 500 records
        offset = int(request.args.get('offset', 0))
        status_filter = request.args.get('status')
        
        with db_session_scope() as session:
            from models import EtilizeStagingProduct, EtilizeImportBatch
            
            # Verify user has access to this batch
            batch = session.query(EtilizeImportBatch).filter_by(
                id=batch_id, triggered_by=user_id
            ).first()
            
            if not batch:
                return jsonify({"error": "Batch not found or access denied"}), 404
            
            # Build query
            query = session.query(EtilizeStagingProduct).filter_by(batch_id=batch_id)
            
            if status_filter:
                query = query.filter_by(processing_status=status_filter)
            
            # Get total count
            total_count = query.count()
            
            # Apply pagination
            staging_records = query.offset(offset).limit(limit).all()
            
            results = []
            for record in staging_records:
                results.append({
                    "id": record.id,
                    "sku": record.sku,
                    "title": record.title,
                    "brand": record.brand,
                    "price": record.price,
                    "processing_status": record.processing_status,
                    "validation_status": record.validation_status,
                    "mapping_status": record.mapping_status,
                    "validation_errors": record.validation_errors,
                    "mapping_confidence": record.mapping_confidence,
                    "created_at": record.created_at.isoformat() if record.created_at else None
                })
            
            return jsonify({
                "staging_records": results,
                "total_count": total_count,
                "limit": limit,
                "offset": offset,
                "batch_info": {
                    "id": batch.id,
                    "status": batch.status,
                    "total_records": batch.total_records,
                    "records_processed": batch.records_processed,
                    "records_imported": batch.records_imported,
                    "records_failed": batch.records_failed
                }
            })
        
    except Exception as e:
        logger.error(f"Staging data retrieval error: {str(e)}")
        return jsonify({"error": "Failed to get staging data"}), 500


# Missing Etilize Endpoints
@import_bp.route('/etilize/ftp/check', methods=['GET'])
@jwt_required()
def check_etilize_ftp():
    """Check Etilize FTP connection status."""
    try:
        # Get FTP configuration from environment
        ftp_host = os.getenv('ETILIZE_FTP_HOST')
        ftp_user = os.getenv('ETILIZE_FTP_USER')
        ftp_password = os.getenv('ETILIZE_FTP_PASSWORD')
        
        if not all([ftp_host, ftp_user, ftp_password]):
            return jsonify({
                'success': False,
                'connected': False,
                'error': 'FTP credentials not configured',
                'message': 'Please configure ETILIZE_FTP_HOST, ETILIZE_FTP_USER, and ETILIZE_FTP_PASSWORD'
            }), 200
        
        # Test FTP connection
        import ftplib
        try:
            ftp = ftplib.FTP(ftp_host)
            ftp.login(ftp_user, ftp_password)
            
            # Try to list directory
            files = ftp.nlst()
            ftp.quit()
            
            return jsonify({
                'success': True,
                'connected': True,
                'message': 'FTP connection successful',
                'host': ftp_host,
                'user': ftp_user,
                'files_count': len(files),
                'timestamp': datetime.utcnow().isoformat()
            }), 200
            
        except ftplib.all_errors as ftp_error:
            return jsonify({
                'success': False,
                'connected': False,
                'error': str(ftp_error),
                'message': 'Failed to connect to Etilize FTP server',
                'timestamp': datetime.utcnow().isoformat()
            }), 200
        
    except Exception as e:
        logger.error(f"Failed to check FTP connection: {str(e)}")
        return jsonify({
            'success': False,
            'connected': False,
            'error': str(e),
            'message': 'Internal server error',
            'timestamp': datetime.utcnow().isoformat()
        }), 500


@import_bp.route('/etilize/import/history', methods=['GET'])
@jwt_required()
def get_etilize_import_history():
    """Get Etilize import history."""
    try:
        user_id = get_user_id()
        
        # Get query parameters
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        status = request.args.get('status')
        
        with db_session_scope() as session:
            from models import EtilizeImportBatch
            
            # Build query
            query = session.query(EtilizeImportBatch)
            
            # Filter by user if not admin
            query = query.filter_by(triggered_by=user_id)
            
            # Filter by status if provided
            if status:
                query = query.filter_by(status=status)
            
            # Order by creation date
            query = query.order_by(EtilizeImportBatch.created_at.desc())
            
            # Paginate
            total = query.count()
            imports = query.offset((page - 1) * per_page).limit(per_page).all()
            
            # Format response
            items = []
            for import_batch in imports:
                items.append({
                    'id': import_batch.id,
                    'batch_id': import_batch.batch_id,
                    'status': import_batch.status,
                    'stage': import_batch.stage,
                    'source_file_path': import_batch.source_file_path,
                    'total_records': import_batch.total_records,
                    'processed_records': import_batch.processed_records,
                    'imported_records': import_batch.imported_records,
                    'failed_records': import_batch.failed_records,
                    'validation_errors': import_batch.validation_errors,
                    'mapping_errors': import_batch.mapping_errors,
                    'created_at': import_batch.created_at.isoformat() if import_batch.created_at else None,
                    'started_at': import_batch.started_at.isoformat() if import_batch.started_at else None,
                    'completed_at': import_batch.completed_at.isoformat() if import_batch.completed_at else None,
                    'error_summary': import_batch.error_summary
                })
            
            return jsonify({
                'success': True,
                'imports': items,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total,
                    'total_pages': (total + per_page - 1) // per_page
                },
                'timestamp': datetime.utcnow().isoformat()
            })
            
    except Exception as e:
        logger.error(f"Failed to get import history: {str(e)}")
        return jsonify({'error': 'Failed to get import history'}), 500


# Error handlers for the blueprint
@import_bp.errorhandler(413)
def file_too_large(error):
    """Handle file too large error."""
    return jsonify({"error": "File too large. Maximum size is 50MB."}), 413

@import_bp.errorhandler(404)
def not_found(error):
    """Handle not found error."""
    return jsonify({"error": "Endpoint not found"}), 404

@import_bp.errorhandler(405)
def method_not_allowed(error):
    """Handle method not allowed error."""
    return jsonify({"error": "Method not allowed"}), 405