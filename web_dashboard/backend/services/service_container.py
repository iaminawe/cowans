"""
Service Container and Dependency Injection

Provides dependency injection container for managing import services
with transaction management and service configuration.
"""

import logging
from typing import Dict, Any, Optional, Type, TypeVar, Callable, Union
from dataclasses import dataclass, field
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from .import_service import EtilizeImportService, ImportConfiguration
from .mapping_service import ProductMappingService
from .validation_service import DataValidationService
from .transformation_service import DataTransformationService
from .staging_service import StagingDataService
from .progress_tracker import ImportProgressTracker
from .error_handler import ImportErrorHandler


T = TypeVar('T')


@dataclass
class ServiceConfiguration:
    """Configuration for import services."""
    # Database settings
    session_factory: Optional[Callable[[], Session]] = None
    
    # Import settings
    default_batch_size: int = 100
    max_retries: int = 3
    timeout_seconds: int = 300
    
    # Validation settings
    enable_reference_validation: bool = True
    enable_business_rules: bool = True
    quality_threshold: float = 70.0
    
    # Error handling settings
    max_errors_per_batch: int = 10
    continue_on_errors: bool = True
    
    # Progress tracking settings
    enable_progress_tracking: bool = True
    progress_update_interval: int = 10  # records
    
    # Logging settings
    log_level: int = logging.INFO
    log_format: str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Performance settings
    memory_limit_mb: int = 512
    cleanup_interval_hours: int = 24


class ServiceContainer:
    """
    Dependency injection container for import services.
    
    Features:
    - Service registration and resolution
    - Lifecycle management
    - Configuration injection
    - Transaction management
    - Logging coordination
    """
    
    def __init__(self, config: Optional[ServiceConfiguration] = None):
        """Initialize the service container."""
        self.config = config or ServiceConfiguration()
        
        # Service registry
        self._services: Dict[str, Any] = {}
        self._singletons: Dict[str, Any] = {}
        self._factories: Dict[str, Callable] = {}
        
        # Session management
        self._session: Optional[Session] = None
        self._session_factory = config.session_factory if config else None
        
        # Initialize logger
        self.logger = self._setup_logger()
        
        # Register default services
        self._register_default_services()
    
    def register_service(
        self,
        service_type: Type[T],
        implementation: Union[T, Callable[[], T]],
        singleton: bool = True,
        name: Optional[str] = None
    ) -> None:
        """
        Register a service in the container.
        
        Args:
            service_type: The service type/interface
            implementation: Service instance or factory function
            singleton: Whether to use singleton pattern
            name: Optional service name (defaults to type name)
        """
        service_name = name or service_type.__name__
        
        if singleton:
            if callable(implementation) and not hasattr(implementation, '__call__'):
                # It's a class, not an instance
                self._factories[service_name] = implementation
            else:
                # It's an instance or callable
                self._singletons[service_name] = implementation
        else:
            if callable(implementation):
                self._factories[service_name] = implementation
            else:
                raise ValueError("Non-singleton services must be registered with a factory function")
    
    def get_service(self, service_type: Type[T], name: Optional[str] = None) -> T:
        """
        Get a service instance from the container.
        
        Args:
            service_type: The service type to retrieve
            name: Optional service name
            
        Returns:
            Service instance
        """
        service_name = name or service_type.__name__
        
        # Check singletons first
        if service_name in self._singletons:
            return self._singletons[service_name]
        
        # Check services
        if service_name in self._services:
            return self._services[service_name]
        
        # Check factories
        if service_name in self._factories:
            factory = self._factories[service_name]
            instance = factory()
            
            # Cache as singleton if it was registered as one
            if service_name not in self._factories or service_name in self._singletons:
                self._singletons[service_name] = instance
            
            return instance
        
        raise ValueError(f"Service {service_name} not registered")
    
    def create_import_service(
        self,
        session: Optional[Session] = None,
        config: Optional[ImportConfiguration] = None
    ) -> EtilizeImportService:
        """
        Create a fully configured import service with all dependencies.
        
        Args:
            session: Database session (optional)
            config: Import configuration (optional)
            
        Returns:
            Configured EtilizeImportService instance
        """
        # Get or create session
        if session is None:
            session = self.get_session()
        
        # Get dependencies
        mapping_service = self.get_service(ProductMappingService)
        validation_service = self.get_service(DataValidationService)
        transformation_service = self.get_service(DataTransformationService)
        staging_service = StagingDataService(session, self.logger)
        progress_tracker = self.get_service(ImportProgressTracker)
        error_handler = self.get_service(ImportErrorHandler)
        
        # Create import service
        import_service = EtilizeImportService(
            session=session,
            logger=self.logger,
            config=config
        )
        
        # Inject dependencies manually (in a real DI framework, this would be automatic)
        import_service.mapping_service = mapping_service
        import_service.validation_service = validation_service
        import_service.transformation_service = transformation_service
        import_service.staging_service = staging_service
        import_service.progress_tracker = progress_tracker
        import_service.error_handler = error_handler
        
        return import_service
    
    def get_session(self) -> Session:
        """Get database session."""
        if self._session is None:
            if self._session_factory is None:
                raise ValueError("No session factory configured")
            self._session = self._session_factory()
        
        return self._session
    
    def begin_transaction(self) -> 'TransactionContext':
        """Begin a new transaction context."""
        return TransactionContext(self)
    
    def cleanup(self) -> None:
        """Clean up container resources."""
        # Clean up session
        if self._session:
            try:
                self._session.close()
            except Exception as e:
                self.logger.warning(f"Error closing session: {str(e)}")
            finally:
                self._session = None
        
        # Clean up progress tracker
        try:
            progress_tracker = self.get_service(ImportProgressTracker)
            progress_tracker.cleanup_old_sessions(self.config.cleanup_interval_hours)
        except Exception as e:
            self.logger.warning(f"Error cleaning up progress tracker: {str(e)}")
        
        self.logger.info("Service container cleaned up")
    
    def _register_default_services(self) -> None:
        """Register default service implementations."""
        # Register mapping service
        self.register_service(
            ProductMappingService,
            lambda: ProductMappingService(self.logger),
            singleton=True
        )
        
        # Register validation service
        self.register_service(
            DataValidationService,
            lambda: DataValidationService(self.logger),
            singleton=True
        )
        
        # Register transformation service
        self.register_service(
            DataTransformationService,
            lambda: DataTransformationService(self.logger),
            singleton=True
        )
        
        # Register progress tracker
        self.register_service(
            ImportProgressTracker,
            lambda: ImportProgressTracker(self.logger),
            singleton=True
        )
        
        # Register error handler
        self.register_service(
            ImportErrorHandler,
            lambda: ImportErrorHandler(self.logger),
            singleton=True
        )
    
    def _setup_logger(self) -> logging.Logger:
        """Setup logger with configuration."""
        logger = logging.getLogger('import_services')
        logger.setLevel(self.config.log_level)
        
        # Create handler if not exists
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(self.config.log_format)
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger


class TransactionContext:
    """
    Context manager for handling transactions across import services.
    
    Features:
    - Automatic transaction management
    - Rollback on errors
    - Service cleanup
    - Error propagation
    """
    
    def __init__(self, container: ServiceContainer):
        """Initialize transaction context."""
        self.container = container
        self.session = None
        self.savepoint = None
        self.logger = container.logger
    
    def __enter__(self) -> Session:
        """Enter transaction context."""
        try:
            self.session = self.container.get_session()
            
            # Begin transaction
            if not self.session.in_transaction():
                self.session.begin()
            
            # Create savepoint for nested transactions
            self.savepoint = self.session.begin_nested()
            
            self.logger.debug("Transaction context started")
            return self.session
            
        except Exception as e:
            self.logger.error(f"Failed to start transaction context: {str(e)}")
            raise
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit transaction context."""
        try:
            if exc_type is None:
                # No exception, commit
                if self.savepoint:
                    self.savepoint.commit()
                if self.session and self.session.in_transaction():
                    self.session.commit()
                self.logger.debug("Transaction committed successfully")
            else:
                # Exception occurred, rollback
                if self.savepoint:
                    self.savepoint.rollback()
                if self.session and self.session.in_transaction():
                    self.session.rollback()
                self.logger.warning(f"Transaction rolled back due to: {exc_type.__name__}: {exc_val}")
                
        except SQLAlchemyError as db_error:
            self.logger.error(f"Database error during transaction cleanup: {str(db_error)}")
            # Re-raise the original exception, not the cleanup error
            
        except Exception as cleanup_error:
            self.logger.error(f"Error during transaction cleanup: {str(cleanup_error)}")
        
        # Return False to propagate any original exception
        return False


def create_default_container(
    session_factory: Optional[Callable[[], Session]] = None,
    **config_kwargs
) -> ServiceContainer:
    """
    Create a service container with default configuration.
    
    Args:
        session_factory: Factory function for creating database sessions
        **config_kwargs: Additional configuration parameters
        
    Returns:
        Configured ServiceContainer instance
    """
    config = ServiceConfiguration(
        session_factory=session_factory,
        **config_kwargs
    )
    
    container = ServiceContainer(config)
    
    # Log container creation
    container.logger.info("Import services container created with default configuration")
    
    return container


# Example usage and integration functions
def example_import_workflow(
    csv_file_path: str,
    reference_file_path: Optional[str] = None,
    session_factory: Optional[Callable[[], Session]] = None
) -> Dict[str, Any]:
    """
    Example of complete import workflow using the service container.
    
    Args:
        csv_file_path: Path to CSV file to import
        reference_file_path: Path to reference file (optional)
        session_factory: Database session factory
        
    Returns:
        Import results
    """
    # Create service container
    container = create_default_container(session_factory=session_factory)
    
    try:
        # Begin transaction
        with container.begin_transaction() as session:
            # Create import service
            import_service = container.create_import_service(session)
            
            # Configure import
            import_config = ImportConfiguration(
                batch_size=50,
                max_errors=20,
                validate_references=reference_file_path is not None,
                create_missing_categories=True
            )
            
            # Execute import
            result = import_service.import_from_csv(
                csv_file_path,
                reference_file_path,
                import_config
            )
            
            # Return results
            return {
                'success': result.status.value == 'completed',
                'total_rows': result.total_rows,
                'processed_rows': result.processed_rows,
                'successful_imports': result.successful_imports,
                'failed_imports': result.failed_imports,
                'errors': [error for error in result.import_errors],
                'warnings': [warning for warning in result.warnings],
                'execution_time': result.execution_time,
                'created_products': result.created_products,
                'updated_products': result.updated_products
            }
            
    except Exception as e:
        container.logger.error(f"Import workflow failed: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'total_rows': 0,
            'processed_rows': 0,
            'successful_imports': 0,
            'failed_imports': 0
        }
    finally:
        # Clean up container
        container.cleanup()


# Integration with Flask application
def create_flask_integration(app, session_factory: Callable[[], Session]) -> ServiceContainer:
    """
    Create service container integrated with Flask application.
    
    Args:
        app: Flask application instance
        session_factory: Database session factory
        
    Returns:
        ServiceContainer instance
    """
    # Create container with Flask logger
    config = ServiceConfiguration(
        session_factory=session_factory,
        log_level=app.logger.level
    )
    
    container = ServiceContainer(config)
    
    # Store container in Flask app
    app.import_service_container = container
    
    # Add cleanup on app teardown
    @app.teardown_appcontext
    def cleanup_import_services(error):
        if hasattr(app, 'import_service_container'):
            try:
                app.import_service_container.cleanup()
            except Exception as e:
                app.logger.warning(f"Error cleaning up import services: {str(e)}")
    
    app.logger.info("Import services integrated with Flask application")
    return container