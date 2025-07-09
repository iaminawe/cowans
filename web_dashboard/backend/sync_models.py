"""
Sync Models - Additional database models for sync operations

This module contains additional SQLAlchemy models specifically for 
sync operations, conflict tracking, and performance monitoring.
"""

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Float, JSON, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum

from models import Base


class SyncConflictStatus(enum.Enum):
    """Status of sync conflicts."""
    PENDING = "pending"
    RESOLVED = "resolved"
    IGNORED = "ignored"


# SyncQueueStatus is defined in models.py to avoid duplicate definitions


class ChangeTrackingAction(enum.Enum):
    """Types of change tracking actions."""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    RESTORE = "restore"


class SyncConflict(Base):
    """Model for tracking sync conflicts between local and Shopify data."""
    __tablename__ = 'sync_conflicts'
    
    id = Column(Integer, primary_key=True)
    
    # Conflict identification
    conflict_id = Column(String(100), unique=True, nullable=False, index=True)
    entity_type = Column(String(50), nullable=False)  # product, category, image
    entity_id = Column(Integer, nullable=False)
    field_name = Column(String(100), nullable=False)
    
    # Conflict data
    local_value = Column(Text)
    shopify_value = Column(Text)
    local_checksum = Column(String(64))  # MD5 hash of local data
    shopify_checksum = Column(String(64))  # MD5 hash of Shopify data
    
    # Resolution
    status = Column(String(20), default=SyncConflictStatus.PENDING.value, nullable=False)
    resolution_strategy = Column(String(50))  # etilize_priority, shopify_priority, manual, etc.
    resolved_value = Column(Text)
    resolved_by = Column(Integer, ForeignKey('users.id'))
    resolved_at = Column(DateTime)
    
    # Metadata
    detection_method = Column(String(50))  # auto, manual, webhook
    conflict_severity = Column(String(20), default='medium')  # low, medium, high, critical
    auto_resolvable = Column(Boolean, default=True)
    
    # Audit
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Additional context
    context_data = Column(JSON)  # Additional data about the conflict
    notes = Column(Text)
    
    # Relationships
    resolved_by_user = relationship("User")
    
    # Indexes
    __table_args__ = (
        Index('idx_conflict_entity', 'entity_type', 'entity_id'),
        Index('idx_conflict_status', 'status'),
        Index('idx_conflict_field', 'field_name'),
        Index('idx_conflict_created', 'created_at'),
    )
    
    def __repr__(self):
        return f"<SyncConflict(id={self.conflict_id}, entity={self.entity_type}:{self.entity_id}, field={self.field_name})>"


# SyncQueue is defined in models.py to avoid duplicate table definition


class ChangeTracking(Base):
    """Model for tracking changes to entities for incremental sync."""
    __tablename__ = 'change_tracking'
    
    id = Column(Integer, primary_key=True)
    
    # Entity identification
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(Integer, nullable=False)
    action = Column(String(20), nullable=False)  # create, update, delete, restore
    
    # Change details
    changed_fields = Column(JSON)  # Array of field names that changed
    old_values = Column(JSON)  # Previous values (for update/delete)
    new_values = Column(JSON)  # New values (for create/update)
    change_checksum = Column(String(64))  # Hash of the change
    
    # Change context
    change_source = Column(String(50))  # manual, import, api, webhook
    user_id = Column(Integer, ForeignKey('users.id'))
    session_id = Column(String(100))
    request_id = Column(String(100))
    
    # Sync status
    sync_required = Column(Boolean, default=True, nullable=False)
    sync_priority = Column(Integer, default=3)
    synced_at = Column(DateTime)
    sync_job_id = Column(Integer, ForeignKey('jobs.id'))
    
    # Metadata
    change_description = Column(Text)
    business_impact = Column(String(20))  # low, medium, high, critical
    automated_change = Column(Boolean, default=False)
    
    # Audit
    created_at = Column(DateTime, default=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User")
    sync_job = relationship("Job")
    
    # Indexes
    __table_args__ = (
        Index('idx_change_entity', 'entity_type', 'entity_id'),
        Index('idx_change_sync_required', 'sync_required'),
        Index('idx_change_created', 'created_at'),
        Index('idx_change_user', 'user_id'),
        Index('idx_change_source', 'change_source'),
        Index('idx_change_priority', 'sync_priority'),
    )
    
    def __repr__(self):
        return f"<ChangeTracking(entity={self.entity_type}:{self.entity_id}, action={self.action}, created={self.created_at})>"


class SyncPerformanceMetrics(Base):
    """Model for tracking sync performance metrics and analytics."""
    __tablename__ = 'sync_performance_metrics'
    
    id = Column(Integer, primary_key=True)
    
    # Metric identification
    metric_name = Column(String(100), nullable=False)
    metric_type = Column(String(50), nullable=False)  # counter, gauge, histogram, timer
    
    # Metric data
    value = Column(Float, nullable=False)
    unit = Column(String(20))  # seconds, count, percentage, bytes
    
    # Context
    operation = Column(String(50))  # sync_product, sync_category, sync_image
    entity_type = Column(String(50))
    batch_size = Column(Integer)
    
    # Performance dimensions
    duration = Column(Float)  # Operation duration in seconds
    api_calls = Column(Integer)  # Number of API calls made
    data_size = Column(Integer)  # Size of data processed in bytes
    success_rate = Column(Float)  # Success rate percentage
    
    # Error tracking
    error_count = Column(Integer, default=0)
    error_types = Column(JSON)  # Array of error types encountered
    rate_limit_hits = Column(Integer, default=0)
    
    # System context
    concurrent_operations = Column(Integer)
    queue_depth = Column(Integer)
    system_load = Column(Float)
    
    # Time dimensions
    time_bucket = Column(String(20))  # minute, hour, day
    recorded_at = Column(DateTime, default=func.now(), nullable=False)
    
    # Additional metadata
    tags = Column(JSON)  # Key-value tags for filtering and grouping
    
    # Indexes
    __table_args__ = (
        Index('idx_metric_name_time', 'metric_name', 'recorded_at'),
        Index('idx_metric_operation', 'operation'),
        Index('idx_metric_entity', 'entity_type'),
        Index('idx_metric_bucket', 'time_bucket', 'recorded_at'),
    )
    
    def __repr__(self):
        return f"<SyncPerformanceMetrics(metric={self.metric_name}, value={self.value}, recorded={self.recorded_at})>"


class SyncDependency(Base):
    """Model for tracking dependencies between sync operations."""
    __tablename__ = 'sync_dependencies'
    
    id = Column(Integer, primary_key=True)
    
    # Dependency relationship
    parent_entity_type = Column(String(50), nullable=False)
    parent_entity_id = Column(Integer, nullable=False)
    child_entity_type = Column(String(50), nullable=False)
    child_entity_id = Column(Integer, nullable=False)
    
    # Dependency type
    dependency_type = Column(String(50), nullable=False)  # required, optional, blocking, non_blocking
    dependency_reason = Column(Text)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    resolved_at = Column(DateTime)
    
    # Metadata
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Indexes
    __table_args__ = (
        Index('idx_dependency_parent', 'parent_entity_type', 'parent_entity_id'),
        Index('idx_dependency_child', 'child_entity_type', 'child_entity_id'),
        Index('idx_dependency_type', 'dependency_type'),
    )
    
    def __repr__(self):
        return f"<SyncDependency(parent={self.parent_entity_type}:{self.parent_entity_id}, child={self.child_entity_type}:{self.child_entity_id})>"


class SyncHealthCheck(Base):
    """Model for tracking sync system health and status."""
    __tablename__ = 'sync_health_checks'
    
    id = Column(Integer, primary_key=True)
    
    # Health check details
    check_name = Column(String(100), nullable=False)
    check_type = Column(String(50), nullable=False)  # shopify_api, database, queue, performance
    status = Column(String(20), nullable=False)  # healthy, warning, critical, unknown
    
    # Check results
    response_time = Column(Float)  # Response time in seconds
    success_rate = Column(Float)  # Success rate percentage
    error_count = Column(Integer, default=0)
    warning_count = Column(Integer, default=0)
    
    # Details
    message = Column(Text)
    error_details = Column(JSON)
    metrics = Column(JSON)  # Additional metrics from the health check
    
    # Timing
    check_started_at = Column(DateTime, nullable=False)
    check_completed_at = Column(DateTime, nullable=False)
    next_check_at = Column(DateTime)
    
    # Metadata
    check_version = Column(String(20))
    environment = Column(String(50))
    
    # Indexes
    __table_args__ = (
        Index('idx_health_check_name', 'check_name'),
        Index('idx_health_check_status', 'status'),
        Index('idx_health_check_completed', 'check_completed_at'),
        Index('idx_health_check_next', 'next_check_at'),
    )
    
    def __repr__(self):
        return f"<SyncHealthCheck(check={self.check_name}, status={self.status}, completed={self.check_completed_at})>"


class ApiRateLimit(Base):
    """Model for tracking API rate limit usage and patterns."""
    __tablename__ = 'api_rate_limits'
    
    id = Column(Integer, primary_key=True)
    
    # API details
    api_endpoint = Column(String(200), nullable=False)
    operation_type = Column(String(50), nullable=False)  # query, mutation
    
    # Rate limit data
    requests_made = Column(Integer, nullable=False)
    rate_limit_reached = Column(Boolean, default=False)
    bucket_size = Column(Integer)
    bucket_remaining = Column(Integer)
    refill_rate = Column(Float)
    
    # Timing
    window_start = Column(DateTime, nullable=False)
    window_end = Column(DateTime, nullable=False)
    recorded_at = Column(DateTime, default=func.now(), nullable=False)
    
    # Context
    concurrent_requests = Column(Integer)
    batch_size = Column(Integer)
    operation_context = Column(String(100))
    
    # Performance impact
    throttle_delay = Column(Float)  # Delay applied due to rate limiting
    retry_count = Column(Integer, default=0)
    
    # Indexes
    __table_args__ = (
        Index('idx_rate_limit_endpoint', 'api_endpoint'),
        Index('idx_rate_limit_window', 'window_start', 'window_end'),
        Index('idx_rate_limit_recorded', 'recorded_at'),
    )
    
    def __repr__(self):
        return f"<ApiRateLimit(endpoint={self.api_endpoint}, requests={self.requests_made}, window={self.window_start})>"


# Create additional indexes for performance
def create_sync_performance_indexes(engine):
    """Create additional performance indexes for sync operations."""
    from sqlalchemy import text
    
    indexes = [
        # Sync conflicts - common query patterns
        "CREATE INDEX IF NOT EXISTS idx_conflicts_pending_by_entity ON sync_conflicts(entity_type, entity_id) WHERE status = 'pending'",
        "CREATE INDEX IF NOT EXISTS idx_conflicts_severity_status ON sync_conflicts(conflict_severity, status)",
        
        # Sync queue - queue processing optimization
        "CREATE INDEX IF NOT EXISTS idx_queue_processing_order ON sync_queue(priority ASC, scheduled_at ASC) WHERE status = 'pending'",
        "CREATE INDEX IF NOT EXISTS idx_queue_retry_ready ON sync_queue(next_retry_at) WHERE status = 'failed' AND retry_count < max_retries",
        
        # Change tracking - incremental sync optimization
        "CREATE INDEX IF NOT EXISTS idx_changes_unsynced ON change_tracking(created_at DESC) WHERE sync_required = true",
        "CREATE INDEX IF NOT EXISTS idx_changes_by_priority ON change_tracking(sync_priority ASC, created_at ASC) WHERE sync_required = true",
        
        # Performance metrics - analytics optimization
        "CREATE INDEX IF NOT EXISTS idx_metrics_time_series ON sync_performance_metrics(metric_name, time_bucket, recorded_at)",
        "CREATE INDEX IF NOT EXISTS idx_metrics_operation_performance ON sync_performance_metrics(operation, recorded_at)",
        
        # Health checks - monitoring optimization
        "CREATE INDEX IF NOT EXISTS idx_health_latest ON sync_health_checks(check_name, check_completed_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_health_alerts ON sync_health_checks(status, check_completed_at) WHERE status IN ('warning', 'critical')",
    ]
    
    with engine.connect() as conn:
        for index_sql in indexes:
            try:
                conn.execute(text(index_sql))
            except Exception as e:
                # Index might already exist
                pass
        conn.commit()