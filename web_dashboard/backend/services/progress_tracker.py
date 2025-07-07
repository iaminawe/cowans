"""
Import Progress Tracker

Provides progress tracking and user feedback for import operations
with real-time updates and detailed statistics.
"""

import logging
import threading
import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json


class ProgressStatus(Enum):
    """Progress status enumeration."""
    NOT_STARTED = "not_started"
    INITIALIZING = "initializing"
    PARSING = "parsing"
    VALIDATING = "validating"
    MAPPING = "mapping"
    TRANSFORMING = "transforming"
    STAGING = "staging"
    IMPORTING = "importing"
    COMPLETING = "completing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ProgressMetrics:
    """Progress metrics for an import operation."""
    total_records: int = 0
    processed_records: int = 0
    successful_records: int = 0
    failed_records: int = 0
    skipped_records: int = 0
    current_batch: int = 0
    total_batches: int = 0
    records_per_second: float = 0.0
    estimated_time_remaining: Optional[timedelta] = None
    
    @property
    def completion_percentage(self) -> float:
        """Calculate completion percentage."""
        if self.total_records == 0:
            return 0.0
        return (self.processed_records / self.total_records) * 100.0
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.processed_records == 0:
            return 0.0
        return (self.successful_records / self.processed_records) * 100.0


@dataclass
class ProgressUpdate:
    """A progress update event."""
    import_id: str
    timestamp: datetime
    status: ProgressStatus
    stage: str
    message: str
    metrics: ProgressMetrics
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ImportSession:
    """An import session with progress tracking."""
    import_id: str
    started_at: datetime
    status: ProgressStatus = ProgressStatus.NOT_STARTED
    current_stage: str = ""
    metrics: ProgressMetrics = field(default_factory=ProgressMetrics)
    updates: List[ProgressUpdate] = field(default_factory=list)
    callbacks: List[Callable[[ProgressUpdate], None]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_update(self, status: ProgressStatus, stage: str, message: str, **kwargs) -> None:
        """Add a progress update."""
        update = ProgressUpdate(
            import_id=self.import_id,
            timestamp=datetime.now(),
            status=status,
            stage=stage,
            message=message,
            metrics=self.metrics,
            metadata=kwargs
        )
        
        self.updates.append(update)
        self.status = status
        self.current_stage = stage
        
        # Notify callbacks
        for callback in self.callbacks:
            try:
                callback(update)
            except Exception as e:
                # Log callback errors but don't fail the import
                logging.getLogger(__name__).warning(f"Progress callback failed: {str(e)}")


class ImportProgressTracker:
    """
    Service for tracking import progress with real-time updates.
    
    Features:
    - Real-time progress tracking
    - Performance metrics calculation
    - Time estimation
    - Callback notifications
    - Progress history
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize the progress tracker."""
        self.logger = logger or logging.getLogger(__name__)
        
        # Active import sessions
        self._sessions: Dict[str, ImportSession] = {}
        self._lock = threading.RLock()
        
        # Performance tracking
        self._performance_samples: Dict[str, List[Tuple[datetime, int]]] = {}
        self._sample_window = timedelta(minutes=5)  # 5-minute window for rate calculation
    
    def start_import(
        self,
        import_id: str,
        total_records: int = 0,
        total_batches: int = 0,
        callbacks: Optional[List[Callable[[ProgressUpdate], None]]] = None
    ) -> ImportSession:
        """
        Start tracking a new import operation.
        
        Args:
            import_id: Unique identifier for the import
            total_records: Total number of records to process
            total_batches: Total number of batches
            callbacks: Optional list of progress callbacks
            
        Returns:
            ImportSession object for tracking
        """
        with self._lock:
            session = ImportSession(
                import_id=import_id,
                started_at=datetime.now(),
                callbacks=callbacks or []
            )
            
            session.metrics.total_records = total_records
            session.metrics.total_batches = total_batches
            
            self._sessions[import_id] = session
            self._performance_samples[import_id] = []
            
            session.add_update(
                ProgressStatus.INITIALIZING,
                "initialization",
                f"Starting import of {total_records} records in {total_batches} batches"
            )
            
            self.logger.info(f"Started tracking import {import_id}")
            return session
    
    def update_status(
        self,
        import_id: str,
        status: ProgressStatus,
        stage: Optional[str] = None,
        message: Optional[str] = None
    ) -> None:
        """Update import status."""
        with self._lock:
            session = self._sessions.get(import_id)
            if not session:
                self.logger.warning(f"Import session {import_id} not found")
                return
            
            stage = stage or status.value
            message = message or f"Status changed to {status.value}"
            
            session.add_update(status, stage, message)
            
            self.logger.debug(f"Import {import_id} status: {status.value} - {message}")
    
    def update_progress(
        self,
        import_id: str,
        processed: int,
        successful: Optional[int] = None,
        failed: Optional[int] = None,
        skipped: Optional[int] = None,
        current_batch: Optional[int] = None,
        message: Optional[str] = None
    ) -> None:
        """
        Update import progress metrics.
        
        Args:
            import_id: Import identifier
            processed: Number of records processed
            successful: Number of successful records
            failed: Number of failed records
            skipped: Number of skipped records
            current_batch: Current batch number
            message: Optional progress message
        """
        with self._lock:
            session = self._sessions.get(import_id)
            if not session:
                self.logger.warning(f"Import session {import_id} not found")
                return
            
            # Update metrics
            session.metrics.processed_records = processed
            if successful is not None:
                session.metrics.successful_records = successful
            if failed is not None:
                session.metrics.failed_records = failed
            if skipped is not None:
                session.metrics.skipped_records = skipped
            if current_batch is not None:
                session.metrics.current_batch = current_batch
            
            # Update performance metrics
            self._update_performance_metrics(import_id, processed)
            
            # Calculate time estimates
            self._calculate_time_estimates(session)
            
            # Create progress message
            if not message:
                message = self._create_progress_message(session.metrics)
            
            session.add_update(
                session.status,
                session.current_stage,
                message,
                progress_update=True
            )
    
    def add_callback(self, import_id: str, callback: Callable[[ProgressUpdate], None]) -> bool:
        """Add a progress callback for an import."""
        with self._lock:
            session = self._sessions.get(import_id)
            if session:
                session.callbacks.append(callback)
                return True
            return False
    
    def remove_callback(self, import_id: str, callback: Callable[[ProgressUpdate], None]) -> bool:
        """Remove a progress callback."""
        with self._lock:
            session = self._sessions.get(import_id)
            if session and callback in session.callbacks:
                session.callbacks.remove(callback)
                return True
            return False
    
    def get_progress(self, import_id: str) -> Optional[Dict[str, Any]]:
        """Get current progress for an import."""
        with self._lock:
            session = self._sessions.get(import_id)
            if not session:
                return None
            
            return {
                'import_id': import_id,
                'status': session.status.value,
                'stage': session.current_stage,
                'started_at': session.started_at.isoformat(),
                'duration': (datetime.now() - session.started_at).total_seconds(),
                'metrics': {
                    'total_records': session.metrics.total_records,
                    'processed_records': session.metrics.processed_records,
                    'successful_records': session.metrics.successful_records,
                    'failed_records': session.metrics.failed_records,
                    'skipped_records': session.metrics.skipped_records,
                    'current_batch': session.metrics.current_batch,
                    'total_batches': session.metrics.total_batches,
                    'completion_percentage': session.metrics.completion_percentage,
                    'success_rate': session.metrics.success_rate,
                    'records_per_second': session.metrics.records_per_second,
                    'estimated_time_remaining': (
                        session.metrics.estimated_time_remaining.total_seconds()
                        if session.metrics.estimated_time_remaining else None
                    )
                },
                'last_update': session.updates[-1].timestamp.isoformat() if session.updates else None
            }
    
    def get_progress_history(self, import_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get progress history for an import."""
        with self._lock:
            session = self._sessions.get(import_id)
            if not session:
                return []
            
            updates = session.updates
            if limit:
                updates = updates[-limit:]
            
            return [
                {
                    'timestamp': update.timestamp.isoformat(),
                    'status': update.status.value,
                    'stage': update.stage,
                    'message': update.message,
                    'completion_percentage': update.metrics.completion_percentage,
                    'records_per_second': update.metrics.records_per_second,
                    'metadata': update.metadata
                }
                for update in updates
            ]
    
    def get_active_imports(self) -> List[str]:
        """Get list of active import IDs."""
        with self._lock:
            active_statuses = [
                ProgressStatus.INITIALIZING,
                ProgressStatus.PARSING,
                ProgressStatus.VALIDATING,
                ProgressStatus.MAPPING,
                ProgressStatus.TRANSFORMING,
                ProgressStatus.STAGING,
                ProgressStatus.IMPORTING
            ]
            
            return [
                import_id for import_id, session in self._sessions.items()
                if session.status in active_statuses
            ]
    
    def end_import(
        self,
        import_id: str,
        status: ProgressStatus = ProgressStatus.COMPLETED,
        message: Optional[str] = None
    ) -> None:
        """End import tracking."""
        with self._lock:
            session = self._sessions.get(import_id)
            if not session:
                self.logger.warning(f"Import session {import_id} not found")
                return
            
            # Calculate final statistics
            duration = datetime.now() - session.started_at
            
            final_message = message or self._create_completion_message(session, duration)
            
            session.add_update(status, "completed", final_message)
            
            # Clean up performance samples
            if import_id in self._performance_samples:
                del self._performance_samples[import_id]
            
            self.logger.info(f"Import {import_id} completed with status {status.value}")
    
    def cancel_import(self, import_id: str, message: Optional[str] = None) -> bool:
        """Cancel an import operation."""
        with self._lock:
            session = self._sessions.get(import_id)
            if not session:
                return False
            
            cancel_message = message or "Import cancelled by user"
            self.end_import(import_id, ProgressStatus.CANCELLED, cancel_message)
            return True
    
    def cleanup_old_sessions(self, max_age_hours: int = 24) -> int:
        """Clean up old import sessions."""
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        cleaned_count = 0
        
        with self._lock:
            completed_statuses = [
                ProgressStatus.COMPLETED,
                ProgressStatus.FAILED,
                ProgressStatus.CANCELLED
            ]
            
            to_remove = []
            for import_id, session in self._sessions.items():
                if (session.status in completed_statuses and
                    session.started_at < cutoff_time):
                    to_remove.append(import_id)
            
            for import_id in to_remove:
                del self._sessions[import_id]
                if import_id in self._performance_samples:
                    del self._performance_samples[import_id]
                cleaned_count += 1
        
        if cleaned_count > 0:
            self.logger.info(f"Cleaned up {cleaned_count} old import sessions")
        
        return cleaned_count
    
    def get_current_status(self) -> Optional[ProgressStatus]:
        """Get current status if there's an active import."""
        active_imports = self.get_active_imports()
        if active_imports:
            # Return status of most recent active import
            most_recent = max(active_imports, key=lambda x: self._sessions[x].started_at)
            return self._sessions[most_recent].status
        return None
    
    def _update_performance_metrics(self, import_id: str, processed: int) -> None:
        """Update performance metrics for calculating throughput."""
        now = datetime.now()
        samples = self._performance_samples.get(import_id, [])
        
        # Add new sample
        samples.append((now, processed))
        
        # Remove old samples outside the window
        cutoff_time = now - self._sample_window
        samples = [(timestamp, count) for timestamp, count in samples if timestamp > cutoff_time]
        
        self._performance_samples[import_id] = samples
        
        # Calculate records per second
        if len(samples) >= 2:
            first_sample = samples[0]
            last_sample = samples[-1]
            
            time_diff = (last_sample[0] - first_sample[0]).total_seconds()
            record_diff = last_sample[1] - first_sample[1]
            
            if time_diff > 0:
                session = self._sessions[import_id]
                session.metrics.records_per_second = record_diff / time_diff
    
    def _calculate_time_estimates(self, session: ImportSession) -> None:
        """Calculate estimated time remaining."""
        metrics = session.metrics
        
        if (metrics.records_per_second > 0 and 
            metrics.processed_records < metrics.total_records):
            
            remaining_records = metrics.total_records - metrics.processed_records
            estimated_seconds = remaining_records / metrics.records_per_second
            metrics.estimated_time_remaining = timedelta(seconds=estimated_seconds)
        else:
            metrics.estimated_time_remaining = None
    
    def _create_progress_message(self, metrics: ProgressMetrics) -> str:
        """Create a progress message from metrics."""
        return (f"Processed {metrics.processed_records}/{metrics.total_records} records "
                f"({metrics.completion_percentage:.1f}%) - "
                f"Success: {metrics.successful_records}, "
                f"Failed: {metrics.failed_records}, "
                f"Skipped: {metrics.skipped_records}")
    
    def _create_completion_message(self, session: ImportSession, duration: timedelta) -> str:
        """Create completion message with final statistics."""
        metrics = session.metrics
        avg_rate = metrics.processed_records / duration.total_seconds() if duration.total_seconds() > 0 else 0
        
        return (f"Import completed in {duration.total_seconds():.1f} seconds. "
                f"Processed {metrics.processed_records} records "
                f"(Success: {metrics.successful_records}, "
                f"Failed: {metrics.failed_records}, "
                f"Skipped: {metrics.skipped_records}). "
                f"Average rate: {avg_rate:.1f} records/second")
    
    def get_session_statistics(self) -> Dict[str, Any]:
        """Get overall session statistics."""
        with self._lock:
            total_sessions = len(self._sessions)
            active_sessions = len(self.get_active_imports())
            
            status_counts = {}
            for session in self._sessions.values():
                status = session.status.value
                status_counts[status] = status_counts.get(status, 0) + 1
            
            return {
                'total_sessions': total_sessions,
                'active_sessions': active_sessions,
                'status_breakdown': status_counts,
                'memory_usage': {
                    'sessions': len(self._sessions),
                    'performance_samples': sum(len(samples) for samples in self._performance_samples.values())
                }
            }