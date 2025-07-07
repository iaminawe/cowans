"""Error tracking service for monitoring and logging errors."""
import os
import logging
import traceback
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from collections import deque
import json

logger = logging.getLogger(__name__)


@dataclass
class ErrorEntry:
    """Represents a tracked error."""
    timestamp: datetime
    error_type: str
    message: str
    traceback: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    user_id: Optional[int] = None
    request_id: Optional[str] = None
    endpoint: Optional[str] = None
    method: Optional[str] = None
    status_code: Optional[int] = None


class ErrorTracker:
    """Service for tracking and analyzing application errors."""
    
    def __init__(self, max_errors: int = 1000):
        """Initialize error tracker.
        
        Args:
            max_errors: Maximum number of errors to keep in memory
        """
        self.max_errors = max_errors
        self.errors: deque = deque(maxlen=max_errors)
        self.error_counts: Dict[str, int] = {}
        self.error_rate_window: deque = deque(maxlen=100)  # Last 100 requests
        
    def track_error(self, 
                   error: Exception,
                   context: Optional[Dict[str, Any]] = None,
                   user_id: Optional[int] = None,
                   request_id: Optional[str] = None,
                   endpoint: Optional[str] = None,
                   method: Optional[str] = None) -> None:
        """Track an error occurrence.
        
        Args:
            error: The exception that occurred
            context: Additional context about the error
            user_id: ID of the user who encountered the error
            request_id: Unique request identifier
            endpoint: API endpoint where error occurred
            method: HTTP method
        """
        error_type = type(error).__name__
        error_message = str(error)
        error_traceback = traceback.format_exc()
        
        # Create error entry
        entry = ErrorEntry(
            timestamp=datetime.utcnow(),
            error_type=error_type,
            message=error_message,
            traceback=error_traceback,
            context=context or {},
            user_id=user_id,
            request_id=request_id,
            endpoint=endpoint,
            method=method
        )
        
        # Add to error list
        self.errors.append(entry)
        
        # Update error counts
        self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1
        
        # Track error rate
        self.error_rate_window.append(True)
        
        # Log the error
        logger.error(f"Error tracked: {error_type} - {error_message}", extra={
            'error_type': error_type,
            'user_id': user_id,
            'request_id': request_id,
            'endpoint': endpoint,
            'context': context
        })
        
        # In production, you might want to send to external service
        if os.getenv('SENTRY_DSN'):
            self._send_to_sentry(entry)
            
    def track_request(self, success: bool = True) -> None:
        """Track a request for error rate calculation.
        
        Args:
            success: Whether the request was successful
        """
        self.error_rate_window.append(not success)
        
    def get_error_rate(self) -> float:
        """Get current error rate as a percentage.
        
        Returns:
            Error rate percentage (0-100)
        """
        if not self.error_rate_window:
            return 0.0
            
        error_count = sum(1 for is_error in self.error_rate_window if is_error)
        return (error_count / len(self.error_rate_window)) * 100
        
    def get_recent_errors(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent errors.
        
        Args:
            limit: Maximum number of errors to return
            
        Returns:
            List of error dictionaries
        """
        recent_errors = list(self.errors)[-limit:]
        return [self._error_to_dict(error) for error in reversed(recent_errors)]
        
    def get_error_summary(self) -> Dict[str, Any]:
        """Get error tracking summary.
        
        Returns:
            Summary statistics about errors
        """
        total_errors = len(self.errors)
        
        # Get error counts by type
        top_errors = sorted(
            self.error_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        # Get errors by endpoint
        endpoint_errors: Dict[str, int] = {}
        for error in self.errors:
            if error.endpoint:
                endpoint_errors[error.endpoint] = endpoint_errors.get(error.endpoint, 0) + 1
                
        top_endpoints = sorted(
            endpoint_errors.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        # Get recent error rate over time
        if self.errors:
            oldest_error = self.errors[0].timestamp
            newest_error = self.errors[-1].timestamp
            time_span = (newest_error - oldest_error).total_seconds()
            
            if time_span > 0:
                errors_per_minute = (total_errors / time_span) * 60
            else:
                errors_per_minute = 0
        else:
            errors_per_minute = 0
            
        return {
            'total_errors': total_errors,
            'error_rate_percent': round(self.get_error_rate(), 2),
            'errors_per_minute': round(errors_per_minute, 2),
            'top_error_types': [
                {'type': error_type, 'count': count}
                for error_type, count in top_errors
            ],
            'top_error_endpoints': [
                {'endpoint': endpoint, 'count': count}
                for endpoint, count in top_endpoints
            ],
            'tracking_window_size': self.max_errors
        }
        
    def get_errors_by_type(self, error_type: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get errors of a specific type.
        
        Args:
            error_type: Type of error to filter by
            limit: Maximum number of errors to return
            
        Returns:
            List of error dictionaries
        """
        filtered_errors = [
            error for error in self.errors
            if error.error_type == error_type
        ][-limit:]
        
        return [self._error_to_dict(error) for error in reversed(filtered_errors)]
        
    def get_errors_by_user(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Get errors for a specific user.
        
        Args:
            user_id: User ID to filter by
            limit: Maximum number of errors to return
            
        Returns:
            List of error dictionaries
        """
        filtered_errors = [
            error for error in self.errors
            if error.user_id == user_id
        ][-limit:]
        
        return [self._error_to_dict(error) for error in reversed(filtered_errors)]
        
    def clear_old_errors(self, days: int = 7) -> int:
        """Clear errors older than specified days.
        
        Args:
            days: Number of days to keep errors
            
        Returns:
            Number of errors cleared
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        original_count = len(self.errors)
        
        # Filter out old errors
        self.errors = deque(
            (error for error in self.errors if error.timestamp > cutoff_date),
            maxlen=self.max_errors
        )
        
        return original_count - len(self.errors)
        
    def _error_to_dict(self, error: ErrorEntry) -> Dict[str, Any]:
        """Convert error entry to dictionary.
        
        Args:
            error: ErrorEntry instance
            
        Returns:
            Dictionary representation
        """
        return {
            'timestamp': error.timestamp.isoformat(),
            'error_type': error.error_type,
            'message': error.message,
            'traceback': error.traceback,
            'context': error.context,
            'user_id': error.user_id,
            'request_id': error.request_id,
            'endpoint': error.endpoint,
            'method': error.method,
            'status_code': error.status_code
        }
        
    def _send_to_sentry(self, error: ErrorEntry) -> None:
        """Send error to Sentry (if configured).
        
        Args:
            error: ErrorEntry to send
        """
        try:
            import sentry_sdk
            
            with sentry_sdk.push_scope() as scope:
                scope.set_context("error_details", {
                    'error_type': error.error_type,
                    'endpoint': error.endpoint,
                    'method': error.method,
                    'user_id': error.user_id,
                    'request_id': error.request_id
                })
                
                if error.context:
                    scope.set_context("error_context", error.context)
                    
                sentry_sdk.capture_message(
                    f"{error.error_type}: {error.message}",
                    level="error"
                )
        except Exception as e:
            logger.warning(f"Failed to send error to Sentry: {e}")


# Global error tracker instance
error_tracker = ErrorTracker()


def track_error(error: Exception, **kwargs) -> None:
    """Convenience function to track errors.
    
    Args:
        error: The exception to track
        **kwargs: Additional context
    """
    error_tracker.track_error(error, **kwargs)


def get_error_summary() -> Dict[str, Any]:
    """Get error tracking summary.
    
    Returns:
        Error summary statistics
    """
    return error_tracker.get_error_summary()