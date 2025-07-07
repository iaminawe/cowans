"""
Import Error Handler

Provides comprehensive error handling and recovery mechanisms for import operations
with detailed logging, categorization, and recovery strategies.
"""

import logging
import traceback
import sys
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json
import hashlib


class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for classification."""
    VALIDATION = "validation"
    DATA_QUALITY = "data_quality"
    BUSINESS_RULE = "business_rule"
    SYSTEM = "system"
    NETWORK = "network"
    DATABASE = "database"
    EXTERNAL_API = "external_api"
    FILE_IO = "file_io"
    PARSING = "parsing"
    TRANSFORMATION = "transformation"
    UNKNOWN = "unknown"


class RecoveryStrategy(Enum):
    """Error recovery strategies."""
    RETRY = "retry"
    SKIP = "skip"
    ABORT = "abort"
    FALLBACK = "fallback"
    MANUAL = "manual"


@dataclass
class ErrorContext:
    """Context information for an error."""
    import_id: str
    stage: str
    record_number: Optional[int] = None
    batch_number: Optional[int] = None
    operation: Optional[str] = None
    data_snapshot: Optional[Dict[str, Any]] = None
    system_state: Optional[Dict[str, Any]] = None


@dataclass
class ImportError:
    """Detailed import error information."""
    error_id: str
    timestamp: datetime
    severity: ErrorSeverity
    category: ErrorCategory
    message: str
    exception_type: str
    exception_message: str
    traceback: Optional[str] = None
    context: Optional[ErrorContext] = None
    recovery_strategy: Optional[RecoveryStrategy] = None
    recovery_attempted: bool = False
    recovery_successful: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary."""
        return {
            'error_id': self.error_id,
            'timestamp': self.timestamp.isoformat(),
            'severity': self.severity.value,
            'category': self.category.value,
            'message': self.message,
            'exception_type': self.exception_type,
            'exception_message': self.exception_message,
            'traceback': self.traceback,
            'context': {
                'import_id': self.context.import_id,
                'stage': self.context.stage,
                'record_number': self.context.record_number,
                'batch_number': self.context.batch_number,
                'operation': self.context.operation
            } if self.context else None,
            'recovery_strategy': self.recovery_strategy.value if self.recovery_strategy else None,
            'recovery_attempted': self.recovery_attempted,
            'recovery_successful': self.recovery_successful,
            'metadata': self.metadata
        }


@dataclass
class ErrorSummary:
    """Summary of errors for an import operation."""
    import_id: str
    total_errors: int = 0
    error_by_severity: Dict[str, int] = field(default_factory=dict)
    error_by_category: Dict[str, int] = field(default_factory=dict)
    critical_errors: List[ImportError] = field(default_factory=list)
    recovery_success_rate: float = 0.0
    most_common_errors: List[Tuple[str, int]] = field(default_factory=list)


class ImportErrorHandler:
    """
    Comprehensive error handling service for import operations.
    
    Features:
    - Error classification and categorization
    - Recovery strategy determination
    - Automatic retry mechanisms
    - Error aggregation and reporting
    - Context-aware error handling
    - Logging integration
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize the error handler."""
        self.logger = logger or logging.getLogger(__name__)
        
        # Error storage
        self._errors: Dict[str, List[ImportError]] = {}  # import_id -> errors
        self._error_patterns: Dict[str, int] = {}  # error pattern -> count
        
        # Recovery configuration
        self.max_retries = 3
        self.retry_delays = [1, 5, 15]  # seconds
        
        # Error classification rules
        self._classification_rules = self._load_classification_rules()
        self._recovery_strategies = self._load_recovery_strategies()
    
    def handle_error(
        self,
        error: Exception,
        context: ErrorContext,
        custom_message: Optional[str] = None,
        severity: Optional[ErrorSeverity] = None
    ) -> ImportError:
        """
        Handle an error with classification and recovery strategy.
        
        Args:
            error: The exception that occurred
            context: Context information about the error
            custom_message: Custom error message (optional)
            severity: Override severity level (optional)
            
        Returns:
            ImportError object with classification and recovery info
        """
        # Generate unique error ID
        error_id = self._generate_error_id(error, context)
        
        # Classify error
        category = self._classify_error(error)
        severity = severity or self._assess_severity(error, category)
        
        # Create error object
        import_error = ImportError(
            error_id=error_id,
            timestamp=datetime.now(),
            severity=severity,
            category=category,
            message=custom_message or str(error),
            exception_type=type(error).__name__,
            exception_message=str(error),
            traceback=traceback.format_exc(),
            context=context,
            recovery_strategy=self._determine_recovery_strategy(error, category, severity)
        )
        
        # Store error
        if context.import_id not in self._errors:
            self._errors[context.import_id] = []
        self._errors[context.import_id].append(import_error)
        
        # Update error patterns
        self._update_error_patterns(import_error)
        
        # Log error
        self._log_error(import_error)
        
        # Attempt recovery if appropriate
        if import_error.recovery_strategy in [RecoveryStrategy.RETRY, RecoveryStrategy.FALLBACK]:
            self._attempt_recovery(import_error)
        
        return import_error
    
    def attempt_recovery(
        self,
        import_error: ImportError,
        recovery_function: Optional[callable] = None,
        recovery_args: Optional[Tuple] = None,
        recovery_kwargs: Optional[Dict] = None
    ) -> bool:
        """
        Attempt error recovery using the specified strategy.
        
        Args:
            import_error: The error to recover from
            recovery_function: Function to call for recovery (optional)
            recovery_args: Arguments for recovery function (optional)
            recovery_kwargs: Keyword arguments for recovery function (optional)
            
        Returns:
            True if recovery was successful, False otherwise
        """
        if import_error.recovery_attempted:
            return import_error.recovery_successful
        
        import_error.recovery_attempted = True
        strategy = import_error.recovery_strategy
        
        try:
            if strategy == RecoveryStrategy.RETRY:
                success = self._retry_operation(import_error, recovery_function, recovery_args, recovery_kwargs)
            elif strategy == RecoveryStrategy.FALLBACK:
                success = self._fallback_operation(import_error, recovery_function, recovery_args, recovery_kwargs)
            elif strategy == RecoveryStrategy.SKIP:
                success = True  # Skipping is always "successful"
            else:
                success = False
            
            import_error.recovery_successful = success
            
            if success:
                self.logger.info(f"Successfully recovered from error {import_error.error_id} using {strategy.value}")
            else:
                self.logger.warning(f"Failed to recover from error {import_error.error_id} using {strategy.value}")
            
            return success
            
        except Exception as recovery_error:
            self.logger.error(f"Recovery attempt failed for error {import_error.error_id}: {str(recovery_error)}")
            import_error.metadata['recovery_error'] = str(recovery_error)
            return False
    
    def get_error_summary(self, import_id: str) -> Optional[ErrorSummary]:
        """Get error summary for an import operation."""
        errors = self._errors.get(import_id, [])
        if not errors:
            return None
        
        # Count errors by severity and category
        severity_counts = {}
        category_counts = {}
        critical_errors = []
        successful_recoveries = 0
        
        for error in errors:
            # Count by severity
            severity_counts[error.severity.value] = severity_counts.get(error.severity.value, 0) + 1
            
            # Count by category
            category_counts[error.category.value] = category_counts.get(error.category.value, 0) + 1
            
            # Track critical errors
            if error.severity == ErrorSeverity.CRITICAL:
                critical_errors.append(error)
            
            # Count successful recoveries
            if error.recovery_attempted and error.recovery_successful:
                successful_recoveries += 1
        
        # Calculate recovery success rate
        attempted_recoveries = sum(1 for e in errors if e.recovery_attempted)
        recovery_rate = (successful_recoveries / attempted_recoveries * 100) if attempted_recoveries > 0 else 0.0
        
        # Find most common error patterns
        error_messages = [e.message for e in errors]
        message_counts = {}
        for message in error_messages:
            message_counts[message] = message_counts.get(message, 0) + 1
        
        most_common = sorted(message_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return ErrorSummary(
            import_id=import_id,
            total_errors=len(errors),
            error_by_severity=severity_counts,
            error_by_category=category_counts,
            critical_errors=critical_errors,
            recovery_success_rate=recovery_rate,
            most_common_errors=most_common
        )
    
    def get_errors(
        self,
        import_id: str,
        severity: Optional[ErrorSeverity] = None,
        category: Optional[ErrorCategory] = None,
        limit: Optional[int] = None
    ) -> List[ImportError]:
        """Get errors for an import with optional filtering."""
        errors = self._errors.get(import_id, [])
        
        # Apply filters
        if severity:
            errors = [e for e in errors if e.severity == severity]
        
        if category:
            errors = [e for e in errors if e.category == category]
        
        # Apply limit
        if limit:
            errors = errors[-limit:]  # Get most recent
        
        return errors
    
    def clear_errors(self, import_id: str) -> int:
        """Clear errors for an import operation."""
        if import_id in self._errors:
            count = len(self._errors[import_id])
            del self._errors[import_id]
            return count
        return 0
    
    def get_global_error_patterns(self) -> Dict[str, Any]:
        """Get global error patterns across all imports."""
        total_errors = sum(len(errors) for errors in self._errors.values())
        
        # Most common error patterns
        sorted_patterns = sorted(self._error_patterns.items(), key=lambda x: x[1], reverse=True)
        
        # Category distribution
        category_counts = {}
        severity_counts = {}
        
        for errors in self._errors.values():
            for error in errors:
                category_counts[error.category.value] = category_counts.get(error.category.value, 0) + 1
                severity_counts[error.severity.value] = severity_counts.get(error.severity.value, 0) + 1
        
        return {
            'total_errors': total_errors,
            'total_imports': len(self._errors),
            'most_common_patterns': sorted_patterns[:10],
            'category_distribution': category_counts,
            'severity_distribution': severity_counts,
            'pattern_count': len(self._error_patterns)
        }
    
    def _generate_error_id(self, error: Exception, context: ErrorContext) -> str:
        """Generate unique error ID."""
        # Create hash from error type, message, and context
        error_info = f"{type(error).__name__}:{str(error)}:{context.stage}:{context.operation}"
        return hashlib.md5(error_info.encode()).hexdigest()[:12]
    
    def _classify_error(self, error: Exception) -> ErrorCategory:
        """Classify error into appropriate category."""
        error_type = type(error).__name__
        error_message = str(error).lower()
        
        # Check classification rules
        for rule in self._classification_rules:
            if self._matches_rule(error_type, error_message, rule):
                return ErrorCategory(rule['category'])
        
        # Default classification based on exception type
        if 'ValidationError' in error_type or 'ValueError' in error_type:
            return ErrorCategory.VALIDATION
        elif 'IntegrityError' in error_type or 'DatabaseError' in error_type:
            return ErrorCategory.DATABASE
        elif 'ConnectionError' in error_type or 'TimeoutError' in error_type:
            return ErrorCategory.NETWORK
        elif 'FileNotFoundError' in error_type or 'PermissionError' in error_type:
            return ErrorCategory.FILE_IO
        elif 'JSONDecodeError' in error_type or 'ParseError' in error_type:
            return ErrorCategory.PARSING
        else:
            return ErrorCategory.UNKNOWN
    
    def _assess_severity(self, error: Exception, category: ErrorCategory) -> ErrorSeverity:
        """Assess error severity based on type and category."""
        error_type = type(error).__name__
        error_message = str(error).lower()
        
        # Critical errors
        if (category == ErrorCategory.DATABASE and 'connection' in error_message) or \
           'memory' in error_message or \
           'system' in error_message:
            return ErrorSeverity.CRITICAL
        
        # High severity errors
        if category in [ErrorCategory.DATABASE, ErrorCategory.SYSTEM] or \
           'integrity' in error_message or \
           'constraint' in error_message:
            return ErrorSeverity.HIGH
        
        # Medium severity errors
        if category in [ErrorCategory.VALIDATION, ErrorCategory.BUSINESS_RULE] or \
           'required' in error_message:
            return ErrorSeverity.MEDIUM
        
        # Default to low severity
        return ErrorSeverity.LOW
    
    def _determine_recovery_strategy(
        self,
        error: Exception,
        category: ErrorCategory,
        severity: ErrorSeverity
    ) -> RecoveryStrategy:
        """Determine appropriate recovery strategy."""
        # Check predefined strategies
        for strategy_rule in self._recovery_strategies:
            if (strategy_rule['category'] == category.value and
                strategy_rule['severity'] == severity.value):
                return RecoveryStrategy(strategy_rule['strategy'])
        
        # Default strategies based on category
        if category == ErrorCategory.NETWORK:
            return RecoveryStrategy.RETRY
        elif category == ErrorCategory.VALIDATION:
            return RecoveryStrategy.SKIP
        elif category == ErrorCategory.DATA_QUALITY:
            return RecoveryStrategy.FALLBACK
        elif severity == ErrorSeverity.CRITICAL:
            return RecoveryStrategy.ABORT
        else:
            return RecoveryStrategy.SKIP
    
    def _attempt_recovery(self, import_error: ImportError) -> None:
        """Attempt automatic recovery for an error."""
        # This is a placeholder for automatic recovery
        # In practice, you would implement specific recovery logic
        pass
    
    def _retry_operation(
        self,
        import_error: ImportError,
        operation_func: Optional[callable],
        args: Optional[Tuple],
        kwargs: Optional[Dict]
    ) -> bool:
        """Retry an operation with exponential backoff."""
        if not operation_func:
            return False
        
        args = args or ()
        kwargs = kwargs or {}
        
        for attempt in range(self.max_retries):
            try:
                # Wait before retry (except first attempt)
                if attempt > 0:
                    delay = self.retry_delays[min(attempt - 1, len(self.retry_delays) - 1)]
                    time.sleep(delay)
                
                # Attempt operation
                result = operation_func(*args, **kwargs)
                
                # Operation succeeded
                import_error.metadata['retry_attempts'] = attempt + 1
                return True
                
            except Exception as retry_error:
                self.logger.warning(f"Retry attempt {attempt + 1} failed for error {import_error.error_id}: {str(retry_error)}")
                
                if attempt == self.max_retries - 1:
                    # All retries exhausted
                    import_error.metadata['retry_attempts'] = self.max_retries
                    import_error.metadata['final_retry_error'] = str(retry_error)
        
        return False
    
    def _fallback_operation(
        self,
        import_error: ImportError,
        fallback_func: Optional[callable],
        args: Optional[Tuple],
        kwargs: Optional[Dict]
    ) -> bool:
        """Execute fallback operation."""
        if not fallback_func:
            return False
        
        try:
            args = args or ()
            kwargs = kwargs or {}
            result = fallback_func(*args, **kwargs)
            return True
        except Exception as fallback_error:
            import_error.metadata['fallback_error'] = str(fallback_error)
            return False
    
    def _matches_rule(self, error_type: str, error_message: str, rule: Dict[str, Any]) -> bool:
        """Check if error matches classification rule."""
        if 'error_types' in rule and error_type not in rule['error_types']:
            return False
        
        if 'message_patterns' in rule:
            for pattern in rule['message_patterns']:
                if pattern.lower() in error_message:
                    return True
            return False
        
        return True
    
    def _update_error_patterns(self, import_error: ImportError) -> None:
        """Update error pattern tracking."""
        pattern = f"{import_error.exception_type}:{import_error.category.value}"
        self._error_patterns[pattern] = self._error_patterns.get(pattern, 0) + 1
    
    def _log_error(self, import_error: ImportError) -> None:
        """Log error with appropriate level."""
        log_message = (f"Import error [{import_error.error_id}]: {import_error.message} "
                      f"(Category: {import_error.category.value}, "
                      f"Severity: {import_error.severity.value})")
        
        if import_error.context:
            log_message += (f" [Import: {import_error.context.import_id}, "
                           f"Stage: {import_error.context.stage}")
            if import_error.context.record_number:
                log_message += f", Record: {import_error.context.record_number}"
            log_message += "]"
        
        if import_error.severity == ErrorSeverity.CRITICAL:
            self.logger.critical(log_message)
        elif import_error.severity == ErrorSeverity.HIGH:
            self.logger.error(log_message)
        elif import_error.severity == ErrorSeverity.MEDIUM:
            self.logger.warning(log_message)
        else:
            self.logger.info(log_message)
    
    def _load_classification_rules(self) -> List[Dict[str, Any]]:
        """Load error classification rules."""
        return [
            {
                'category': 'validation',
                'error_types': ['ValidationError', 'ValueError'],
                'message_patterns': ['required', 'invalid', 'missing']
            },
            {
                'category': 'database',
                'error_types': ['IntegrityError', 'DatabaseError', 'OperationalError'],
                'message_patterns': ['constraint', 'foreign key', 'unique']
            },
            {
                'category': 'network',
                'error_types': ['ConnectionError', 'TimeoutError', 'HTTPError'],
                'message_patterns': ['connection', 'timeout', 'network']
            },
            {
                'category': 'file_io',
                'error_types': ['FileNotFoundError', 'PermissionError', 'IOError'],
                'message_patterns': ['file not found', 'permission denied', 'no such file']
            },
            {
                'category': 'parsing',
                'error_types': ['JSONDecodeError', 'ParseError', 'UnicodeDecodeError'],
                'message_patterns': ['parse', 'decode', 'invalid json', 'malformed']
            }
        ]
    
    def _load_recovery_strategies(self) -> List[Dict[str, Any]]:
        """Load recovery strategy configurations."""
        return [
            {'category': 'network', 'severity': 'medium', 'strategy': 'retry'},
            {'category': 'network', 'severity': 'high', 'strategy': 'retry'},
            {'category': 'validation', 'severity': 'low', 'strategy': 'skip'},
            {'category': 'validation', 'severity': 'medium', 'strategy': 'skip'},
            {'category': 'data_quality', 'severity': 'low', 'strategy': 'fallback'},
            {'category': 'data_quality', 'severity': 'medium', 'strategy': 'fallback'},
            {'category': 'database', 'severity': 'critical', 'strategy': 'abort'},
            {'category': 'system', 'severity': 'critical', 'strategy': 'abort'}
        ]