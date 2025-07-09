"""
Enhanced Staging Models for Sync System

This module extends the sync models with additional staging capabilities:
- Version tracking for changes
- Staging tables for review before sync
- Enhanced conflict resolution
- Sync history with rollback support
"""

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Float, JSON, Index, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum

from models import Base


class StagedChangeStatus(enum.Enum):
    """Status of staged changes."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLIED = "applied"
    ROLLED_BACK = "rolled_back"


class SyncDirection(enum.Enum):
    """Direction of sync operation."""
    PULL_FROM_SHOPIFY = "pull_from_shopify"
    PUSH_TO_SHOPIFY = "push_to_shopify"
    BIDIRECTIONAL = "bidirectional"


class ChangeType(enum.Enum):
    """Type of change detected."""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    RESTORE = "restore"
    MERGE = "merge"


class StagedProductChange(Base):
    """Model for staging product changes before applying them."""
    __tablename__ = 'staged_product_changes'
    
    id = Column(Integer, primary_key=True)
    
    # Change identification
    change_id = Column(String(100), unique=True, nullable=False, index=True)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=True)  # Null for new products
    shopify_product_id = Column(String(50), index=True)
    
    # Change details
    change_type = Column(String(20), nullable=False)
    sync_direction = Column(String(30), nullable=False)
    
    # Version tracking
    source_version = Column(String(64))  # Version hash from source
    target_version = Column(String(64))  # Current version in target
    
    # Change data
    current_data = Column(JSON)  # Current state (before change)
    proposed_data = Column(JSON)  # Proposed state (after change)
    field_changes = Column(JSON)  # Specific fields that changed
    
    # Conflict detection
    has_conflicts = Column(Boolean, default=False)
    conflict_fields = Column(JSON)  # Fields with conflicts
    conflict_resolution = Column(JSON)  # How conflicts were resolved
    
    # Review and approval
    status = Column(String(20), default=StagedChangeStatus.PENDING.value, nullable=False)
    reviewed_by = Column(Integer, ForeignKey('users.id'))
    reviewed_at = Column(DateTime)
    review_notes = Column(Text)
    auto_approved = Column(Boolean, default=False)
    
    # Application tracking
    applied_at = Column(DateTime)
    applied_by = Column(Integer, ForeignKey('users.id'))
    application_result = Column(JSON)
    rollback_data = Column(JSON)  # Data needed for rollback
    
    # Metadata
    source_system = Column(String(50))  # shopify, manual, import, etc.
    batch_id = Column(String(100), index=True)
    priority = Column(Integer, default=3)
    
    # Audit
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    product = relationship("Product")
    reviewed_by_user = relationship("User", foreign_keys=[reviewed_by])
    applied_by_user = relationship("User", foreign_keys=[applied_by])
    
    # Indexes
    __table_args__ = (
        Index('idx_staged_product_status', 'status'),
        Index('idx_staged_product_type', 'change_type'),
        Index('idx_staged_product_batch', 'batch_id'),
        Index('idx_staged_product_created', 'created_at'),
        Index('idx_staged_product_priority', 'priority', 'created_at'),
    )
    
    def __repr__(self):
        return f"<StagedProductChange(id={self.change_id}, type={self.change_type}, status={self.status})>"


class StagedCategoryChange(Base):
    """Model for staging category/collection changes."""
    __tablename__ = 'staged_category_changes'
    
    id = Column(Integer, primary_key=True)
    
    # Change identification
    change_id = Column(String(100), unique=True, nullable=False, index=True)
    category_id = Column(Integer, ForeignKey('categories.id'), nullable=True)
    shopify_collection_id = Column(String(50), index=True)
    
    # Change details
    change_type = Column(String(20), nullable=False)
    sync_direction = Column(String(30), nullable=False)
    
    # Change data
    current_data = Column(JSON)
    proposed_data = Column(JSON)
    field_changes = Column(JSON)
    
    # Products affected
    affected_products = Column(JSON)  # List of product IDs affected
    product_count = Column(Integer, default=0)
    
    # Status and review
    status = Column(String(20), default=StagedChangeStatus.PENDING.value, nullable=False)
    reviewed_by = Column(Integer, ForeignKey('users.id'))
    reviewed_at = Column(DateTime)
    
    # Application
    applied_at = Column(DateTime)
    applied_by = Column(Integer, ForeignKey('users.id'))
    
    # Metadata
    batch_id = Column(String(100), index=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    category = relationship("Category")
    reviewed_by_user = relationship("User", foreign_keys=[reviewed_by])
    applied_by_user = relationship("User", foreign_keys=[applied_by])
    
    # Indexes
    __table_args__ = (
        Index('idx_staged_category_status', 'status'),
        Index('idx_staged_category_batch', 'batch_id'),
    )


class SyncVersion(Base):
    """Model for tracking version history of synced entities."""
    __tablename__ = 'sync_versions'
    
    id = Column(Integer, primary_key=True)
    
    # Entity identification
    entity_type = Column(String(50), nullable=False)  # product, category, etc.
    entity_id = Column(Integer, nullable=False)
    shopify_id = Column(String(50))
    
    # Version data
    version_hash = Column(String(64), nullable=False)  # SHA256 of data
    version_number = Column(Integer, nullable=False)
    
    # Data snapshot
    data_snapshot = Column(JSON, nullable=False)
    
    # Source tracking
    source_system = Column(String(50), nullable=False)
    sync_direction = Column(String(30))
    
    # Metadata
    created_at = Column(DateTime, default=func.now(), nullable=False)
    created_by = Column(Integer, ForeignKey('users.id'))
    
    # Relationships
    created_by_user = relationship("User")
    
    # Indexes
    __table_args__ = (
        Index('idx_version_entity', 'entity_type', 'entity_id'),
        Index('idx_version_hash', 'version_hash'),
        Index('idx_version_created', 'created_at'),
        UniqueConstraint('entity_type', 'entity_id', 'version_number', name='uq_entity_version'),
    )


class SyncBatch(Base):
    """Model for tracking sync batches."""
    __tablename__ = 'sync_batches'
    
    id = Column(Integer, primary_key=True)
    
    # Batch identification
    batch_id = Column(String(100), unique=True, nullable=False, index=True)
    batch_name = Column(String(255))
    
    # Batch details
    sync_type = Column(String(50), nullable=False)  # full, incremental, selective
    sync_direction = Column(String(30), nullable=False)
    
    # Statistics
    total_items = Column(Integer, default=0)
    processed_items = Column(Integer, default=0)
    successful_items = Column(Integer, default=0)
    failed_items = Column(Integer, default=0)
    skipped_items = Column(Integer, default=0)
    
    # Status
    status = Column(String(20), nullable=False)  # pending, running, completed, failed, cancelled
    
    # Timing
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    estimated_completion = Column(DateTime)
    
    # Performance
    processing_rate = Column(Float)  # Items per second
    api_calls_made = Column(Integer, default=0)
    api_quota_used = Column(Integer, default=0)
    
    # Error tracking
    error_summary = Column(JSON)
    warnings = Column(JSON)
    
    # User context
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    cancelled_by = Column(Integer, ForeignKey('users.id'))
    
    # Metadata
    configuration = Column(JSON)  # Batch configuration
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    created_by_user = relationship("User", foreign_keys=[created_by])
    cancelled_by_user = relationship("User", foreign_keys=[cancelled_by])
    # Note: staged_products relationship is handled via query due to string-based batch_id
    
    # Indexes
    __table_args__ = (
        Index('idx_batch_status', 'status'),
        Index('idx_batch_created', 'created_at'),
        Index('idx_batch_user', 'created_by'),
    )


class SyncApprovalRule(Base):
    """Model for defining approval rules for sync operations."""
    __tablename__ = 'sync_approval_rules'
    
    id = Column(Integer, primary_key=True)
    
    # Rule definition
    rule_name = Column(String(255), nullable=False)
    rule_description = Column(Text)
    
    # Conditions
    entity_type = Column(String(50))  # product, category, all
    change_type = Column(String(20))  # create, update, delete, all
    field_patterns = Column(JSON)  # Fields that trigger this rule
    value_thresholds = Column(JSON)  # Value changes that trigger approval
    
    # Approval requirements
    requires_approval = Column(Boolean, default=True)
    auto_approve_conditions = Column(JSON)  # Conditions for auto-approval
    approval_level = Column(Integer, default=1)  # Number of approvals needed
    
    # Status
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=3)
    
    # Metadata
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    created_by = Column(Integer, ForeignKey('users.id'))
    
    # Relationships
    created_by_user = relationship("User")
    
    # Indexes
    __table_args__ = (
        Index('idx_approval_rule_active', 'is_active'),
        Index('idx_approval_rule_entity', 'entity_type'),
        Index('idx_approval_rule_priority', 'priority'),
    )


class SyncRollback(Base):
    """Model for tracking rollback operations."""
    __tablename__ = 'sync_rollbacks'
    
    id = Column(Integer, primary_key=True)
    
    # Rollback identification
    rollback_id = Column(String(100), unique=True, nullable=False, index=True)
    
    # Target of rollback
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(Integer, nullable=False)
    staged_change_id = Column(Integer, ForeignKey('staged_product_changes.id'))
    
    # Rollback data
    previous_version_id = Column(Integer, ForeignKey('sync_versions.id'))
    rollback_data = Column(JSON, nullable=False)
    
    # Status
    status = Column(String(20), nullable=False)  # pending, completed, failed
    error_message = Column(Text)
    
    # Execution
    executed_at = Column(DateTime)
    executed_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # Metadata
    reason = Column(Text)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    
    # Relationships
    staged_change = relationship("StagedProductChange")
    previous_version = relationship("SyncVersion")
    executed_by_user = relationship("User")
    
    # Indexes
    __table_args__ = (
        Index('idx_rollback_entity', 'entity_type', 'entity_id'),
        Index('idx_rollback_status', 'status'),
        Index('idx_rollback_created', 'created_at'),
    )


# Create performance indexes
def create_staging_performance_indexes(engine):
    """Create additional performance indexes for staging operations."""
    from sqlalchemy import text
    
    indexes = [
        # Staged changes - common query patterns
        "CREATE INDEX IF NOT EXISTS idx_staged_pending_priority ON staged_product_changes(priority ASC, created_at ASC) WHERE status = 'pending'",
        "CREATE INDEX IF NOT EXISTS idx_staged_conflicts ON staged_product_changes(created_at DESC) WHERE has_conflicts = true",
        "CREATE INDEX IF NOT EXISTS idx_staged_auto_approve ON staged_product_changes(created_at ASC) WHERE status = 'pending' AND auto_approved = false",
        
        # Version tracking - history queries
        "CREATE INDEX IF NOT EXISTS idx_version_latest ON sync_versions(entity_type, entity_id, version_number DESC)",
        
        # Batch processing - monitoring queries
        "CREATE INDEX IF NOT EXISTS idx_batch_active ON sync_batches(created_at DESC) WHERE status IN ('pending', 'running')",
        
        # Approval rules - evaluation queries
        "CREATE INDEX IF NOT EXISTS idx_approval_evaluation ON sync_approval_rules(entity_type, change_type, priority DESC) WHERE is_active = true",
    ]
    
    with engine.connect() as conn:
        for index_sql in indexes:
            try:
                conn.execute(text(index_sql))
            except Exception as e:
                # Index might already exist
                pass
        conn.commit()