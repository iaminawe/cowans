"""
Import API Integration

Integration example showing how to use the comprehensive import services
with the existing Flask application and API endpoints.
"""

from flask import Flask, request, jsonify
import os
import logging
from typing import Dict, Any, Optional
import traceback

# Import the new services
from services import (
    EtilizeImportService,
    ImportConfiguration,
    ImportMode,
    ImportStatus
)
from services.service_container import create_default_container, TransactionContext
from database import db_session_scope

# Import existing components
from repositories import ProductRepository, CategoryRepository


def create_import_api_endpoints(app: Flask) -> None:
    """
    Add comprehensive import API endpoints to the Flask application.
    
    This function demonstrates how to integrate the new import services
    with the existing Flask application architecture.
    """
    
    @app.route("/api/import/validate", methods=["POST"])
    def validate_import_data():
        """Validate import data without importing."""
        try:
            # Get request data
            data = request.get_json()
            csv_file_path = data.get('csv_file_path')
            reference_file_path = data.get('reference_file_path')
            
            if not csv_file_path:
                return jsonify({"message": "CSV file path is required"}), 400
            
            # Check if file exists
            if not os.path.exists(csv_file_path):
                return jsonify({"message": f"CSV file not found: {csv_file_path}"}), 404
            
            # Create service container
            container = create_default_container(
                session_factory=lambda: db_session_scope().__enter__()
            )
            
            try:
                # Create import service
                import_service = container.create_import_service()
                
                # Configure for validation only
                config = ImportConfiguration(
                    mode=ImportMode.VALIDATE_ONLY,
                    batch_size=50,
                    max_errors=100,
                    validate_references=reference_file_path is not None
                )
                
                # Execute validation
                result = import_service.import_from_csv(
                    csv_file_path,
                    reference_file_path,
                    config
                )
                
                # Return validation results
                return jsonify({
                    "valid": result.status == ImportStatus.COMPLETED,
                    "total_rows": result.total_rows,
                    "validation_errors": result.validation_errors,
                    "warnings": result.warnings,
                    "quality_score": result.metadata.get('quality_score', 0),
                    "summary": {
                        "critical_errors": len([e for e in result.validation_errors if e.get('severity') == 'critical']),
                        "errors": len([e for e in result.validation_errors if e.get('severity') == 'error']),
                        "warnings": len([w for w in result.warnings]),
                        "recommendations": result.metadata.get('recommendations', [])
                    }
                })
                
            finally:
                container.cleanup()
                
        except Exception as e:
            app.logger.error(f"Validation failed: {str(e)}")
            return jsonify({
                "message": "Validation failed",
                "error": str(e),
                "traceback": traceback.format_exc()
            }), 500
    
    @app.route("/api/import/preview", methods=["POST"])
    def preview_import_data():
        """Preview import data transformation."""
        try:
            data = request.get_json()
            csv_file_path = data.get('csv_file_path')
            reference_file_path = data.get('reference_file_path')
            preview_limit = data.get('limit', 10)
            
            if not csv_file_path:
                return jsonify({"message": "CSV file path is required"}), 400
            
            # Create service container
            container = create_default_container(
                session_factory=lambda: db_session_scope().__enter__()
            )
            
            try:
                # Create import service
                import_service = container.create_import_service()
                
                # Configure for preview
                config = ImportConfiguration(
                    mode=ImportMode.PREVIEW,
                    batch_size=preview_limit,
                    validate_references=reference_file_path is not None
                )
                
                # Execute preview
                result = import_service.import_from_csv(
                    csv_file_path,
                    reference_file_path,
                    config
                )
                
                return jsonify({
                    "success": True,
                    "total_rows": result.total_rows,
                    "preview_data": result.metadata.get('preview_data', []),
                    "validation_summary": {
                        "errors": len(result.validation_errors),
                        "warnings": len(result.warnings)
                    },
                    "transformation_summary": {
                        "mapped_products": len([p for p in result.metadata.get('preview_data', []) if p.get('_staging_metadata', {}).get('existing_product_id')]),
                        "new_products": len([p for p in result.metadata.get('preview_data', []) if not p.get('_staging_metadata', {}).get('existing_product_id')]),
                        "conflicts": sum(len(p.get('_staging_metadata', {}).get('conflicts', [])) for p in result.metadata.get('preview_data', []))
                    }
                })
                
            finally:
                container.cleanup()
                
        except Exception as e:
            app.logger.error(f"Preview failed: {str(e)}")
            return jsonify({
                "message": "Preview failed",
                "error": str(e)
            }), 500
    
    @app.route("/api/import/execute", methods=["POST"])
    def execute_import():
        """Execute full import operation."""
        try:
            data = request.get_json()
            csv_file_path = data.get('csv_file_path')
            reference_file_path = data.get('reference_file_path')
            import_options = data.get('options', {})
            
            if not csv_file_path:
                return jsonify({"message": "CSV file path is required"}), 400
            
            # Parse import options
            mode = ImportMode(import_options.get('mode', 'upsert'))
            batch_size = import_options.get('batch_size', 100)
            max_errors = import_options.get('max_errors', 50)
            create_missing_categories = import_options.get('create_missing_categories', True)
            skip_duplicates = import_options.get('skip_duplicates', True)
            
            # Create service container
            container = create_default_container(
                session_factory=lambda: db_session_scope().__enter__()
            )
            
            try:
                # Begin transaction
                with container.begin_transaction() as session:
                    # Create import service
                    import_service = container.create_import_service(session)
                    
                    # Configure import
                    config = ImportConfiguration(
                        mode=mode,
                        batch_size=batch_size,
                        max_errors=max_errors,
                        validate_references=reference_file_path is not None,
                        create_missing_categories=create_missing_categories,
                        skip_duplicates=skip_duplicates
                    )
                    
                    # Execute import
                    result = import_service.import_from_csv(
                        csv_file_path,
                        reference_file_path,
                        config
                    )
                    
                    # Return results
                    return jsonify({
                        "success": result.status == ImportStatus.COMPLETED,
                        "status": result.status.value,
                        "summary": {
                            "total_rows": result.total_rows,
                            "processed_rows": result.processed_rows,
                            "successful_imports": result.successful_imports,
                            "failed_imports": result.failed_imports,
                            "skipped_rows": result.skipped_rows,
                            "execution_time": result.execution_time
                        },
                        "results": {
                            "created_products": result.created_products,
                            "updated_products": result.updated_products,
                            "created_categories": result.created_categories
                        },
                        "errors": result.import_errors[:10],  # First 10 errors
                        "warnings": result.warnings[:10],    # First 10 warnings
                        "metadata": {
                            "memory_usage": result.memory_usage,
                            "quality_metrics": result.metadata.get('quality_metrics', {})
                        }
                    })
                
            finally:
                container.cleanup()
                
        except Exception as e:
            app.logger.error(f"Import execution failed: {str(e)}")
            return jsonify({
                "success": False,
                "message": "Import execution failed",
                "error": str(e),
                "traceback": traceback.format_exc()
            }), 500
    
    @app.route("/api/import/status/<import_id>", methods=["GET"])
    def get_import_status(import_id: str):
        """Get status of a running import operation."""
        try:
            # This would typically use a job queue or cache
            # For now, return a placeholder response
            return jsonify({
                "import_id": import_id,
                "status": "running",
                "progress": {
                    "percentage": 75.0,
                    "processed": 750,
                    "total": 1000,
                    "successful": 720,
                    "failed": 30,
                    "current_stage": "importing"
                },
                "eta_seconds": 60
            })
            
        except Exception as e:
            app.logger.error(f"Failed to get import status: {str(e)}")
            return jsonify({
                "message": "Failed to get import status",
                "error": str(e)
            }), 500
    
    @app.route("/api/import/mapping/analyze", methods=["POST"])
    def analyze_product_mapping():
        """Analyze product mapping quality."""
        try:
            data = request.get_json()
            csv_file_path = data.get('csv_file_path')
            reference_file_path = data.get('reference_file_path')
            
            if not csv_file_path or not reference_file_path:
                return jsonify({"message": "Both CSV and reference file paths are required"}), 400
            
            # Create service container
            container = create_default_container()
            
            try:
                # Get mapping service
                mapping_service = container.get_service('ProductMappingService')
                
                # This would implement detailed mapping analysis
                # For now, return a placeholder response
                return jsonify({
                    "mapping_quality": {
                        "exact_matches": 850,
                        "fuzzy_matches": 120,
                        "metafield_matches": 25,
                        "no_matches": 5,
                        "total_records": 1000
                    },
                    "quality_score": 87.5,
                    "recommendations": [
                        "Review 5 unmapped products manually",
                        "Validate 25 metafield matches",
                        "Check data quality for fuzzy matches"
                    ],
                    "conflict_summary": {
                        "price_conflicts": 12,
                        "description_conflicts": 8,
                        "category_conflicts": 3
                    }
                })
                
            finally:
                container.cleanup()
                
        except Exception as e:
            app.logger.error(f"Mapping analysis failed: {str(e)}")
            return jsonify({
                "message": "Mapping analysis failed",
                "error": str(e)
            }), 500
    
    @app.route("/api/import/quality/report", methods=["POST"])
    def generate_quality_report():
        """Generate data quality report for import data."""
        try:
            data = request.get_json()
            csv_file_path = data.get('csv_file_path')
            
            if not csv_file_path:
                return jsonify({"message": "CSV file path is required"}), 400
            
            # Create service container
            container = create_default_container()
            
            try:
                # Get validation service
                validation_service = container.get_service('DataValidationService')
                
                # This would implement comprehensive quality analysis
                # For now, return a placeholder response
                return jsonify({
                    "overall_score": 82.3,
                    "grade": "B",
                    "metrics": {
                        "completeness": 89.5,
                        "accuracy": 91.2,
                        "consistency": 78.1,
                        "validity": 84.7
                    },
                    "field_analysis": {
                        "sku": {"completeness": 100.0, "validity": 95.0, "issues": 2},
                        "title": {"completeness": 98.5, "validity": 92.0, "issues": 8},
                        "price": {"completeness": 87.3, "validity": 89.0, "issues": 15},
                        "description": {"completeness": 45.2, "validity": 88.0, "issues": 120}
                    },
                    "recommendations": [
                        "Improve description completeness (45% missing)",
                        "Validate price formats (15 invalid values)",
                        "Review SKU format compliance (2 issues)",
                        "Standardize title formatting (8 issues)"
                    ],
                    "critical_issues": 0,
                    "errors": 25,
                    "warnings": 143
                })
                
            finally:
                container.cleanup()
                
        except Exception as e:
            app.logger.error(f"Quality report generation failed: {str(e)}")
            return jsonify({
                "message": "Quality report generation failed",
                "error": str(e)
            }), 500
    
    app.logger.info("Import API endpoints registered successfully")


# Example usage in main application
def setup_import_services(app: Flask) -> None:
    """
    Setup import services in the Flask application.
    
    This function demonstrates how to integrate the import services
    with the existing application architecture.
    """
    
    # Add import API endpoints
    create_import_api_endpoints(app)
    
    # Add cleanup on app teardown
    @app.teardown_appcontext
    def cleanup_import_resources(error):
        """Clean up import service resources."""
        try:
            # Clean up any active import sessions
            # This would typically be handled by a job queue
            pass
        except Exception as e:
            app.logger.warning(f"Error cleaning up import resources: {str(e)}")
    
    # Add background task for old session cleanup
    def cleanup_old_sessions():
        """Background task to clean up old import sessions."""
        try:
            container = create_default_container()
            progress_tracker = container.get_service('ImportProgressTracker')
            cleaned = progress_tracker.cleanup_old_sessions(24)  # Clean sessions older than 24 hours
            if cleaned > 0:
                app.logger.info(f"Cleaned up {cleaned} old import sessions")
            container.cleanup()
        except Exception as e:
            app.logger.error(f"Error in cleanup task: {str(e)}")
    
    # Schedule cleanup task (would typically use Celery or similar)
    # For now, just log that it would be scheduled
    app.logger.info("Import services setup completed")


# Integration example with existing job system
def create_import_job_integration(app: Flask, job_manager) -> None:
    """
    Example of integrating import services with existing job management system.
    
    This shows how the new import services can work with the existing
    job management and WebSocket notification system.
    """
    
    def execute_import_job(job_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute import as a background job."""
        try:
            csv_file_path = parameters.get('csv_file_path')
            reference_file_path = parameters.get('reference_file_path')
            import_options = parameters.get('options', {})
            
            # Create service container
            container = create_default_container()
            
            # Progress callback for WebSocket updates
            def progress_callback(update):
                # Emit progress update via WebSocket
                if hasattr(app, 'socketio'):
                    app.socketio.emit('import_progress', {
                        'job_id': job_id,
                        'status': update.status.value,
                        'stage': update.stage,
                        'message': update.message,
                        'progress': update.metrics.completion_percentage,
                        'timestamp': update.timestamp.isoformat()
                    })
            
            try:
                with container.begin_transaction():
                    # Create import service
                    import_service = container.create_import_service()
                    
                    # Add progress callback
                    progress_tracker = container.get_service('ImportProgressTracker')
                    progress_tracker.add_callback(job_id, progress_callback)
                    
                    # Configure import
                    config = ImportConfiguration(**import_options)
                    
                    # Execute import
                    result = import_service.import_from_csv(
                        csv_file_path,
                        reference_file_path,
                        config
                    )
                    
                    return {
                        'success': result.status == ImportStatus.COMPLETED,
                        'result': result.to_dict() if hasattr(result, 'to_dict') else str(result)
                    }
                    
            finally:
                container.cleanup()
                
        except Exception as e:
            app.logger.error(f"Import job {job_id} failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'traceback': traceback.format_exc()
            }
    
    # Register job handler with existing job manager
    if job_manager:
        job_manager.register_job_handler('import_products', execute_import_job)
        app.logger.info("Import job handler registered with job manager")


if __name__ == "__main__":
    # Example of how to set up a Flask app with import services
    from flask import Flask
    from database import init_database, db_session_scope
    
    app = Flask(__name__)
    
    # Initialize database
    init_database()
    
    # Setup import services
    setup_import_services(app)
    
    app.logger.info("Flask application with import services is ready")
    
    # Run the app
    app.run(debug=True, port=3560)