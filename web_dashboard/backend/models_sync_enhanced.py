"""
Enhanced Database Models for Sync System

This module contains additional SQLAlchemy models for the enhanced sync system
with staging, versioning, and Xorosoft integration.
"""

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Float, JSON, Index, UniqueConstraint, CheckConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum

# Import base from main models
from models import Base

# Enums for sync system
class SyncDirection(enum.Enum):
    UP = "up"  # Local to Shopify
    DOWN = "down"  # Shopify to Local
    BIDIRECTIONAL = "bidirectional"

class SyncOperationStatus(enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"

class ConflictStatus(enum.Enum):
    UNRESOLVED = "unresolved"
    RESOLVED = "resolved"
    IGNORED = "ignored"
    AUTO_RESOLVED = "auto_resolved"

class ConflictResolutionStrategy(enum.Enum):
    LOCAL_WINS = "local_wins"
    REMOTE_WINS = "remote_wins"
    MERGE = "merge"
    MANUAL = "manual"
    NEWER_WINS = "newer_wins"

class ChangeType(enum.Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    RESTORE = "restore"

# Enhanced Staging Tables

class ProductsStaging(Base):
    """Staging area for product changes before sync operations."""
    __tablename__ = 'products_staging'
    
    id = Column(Integer, primary_key=True)
    
    # Reference to source product
    source_product_id = Column(Integer, ForeignKey('products.id'), index=True)
    shopify_product_id = Column(String(50), index=True)
    
    # Product data (mirrors main product table structure)
    sku = Column(String(100), index=True)
    name = Column(String(500))
    title = Column(String(500))
    description = Column(Text)
    short_description = Column(Text)
    
    # Pricing
    price = Column(Float)
    compare_at_price = Column(Float)
    cost_price = Column(Float)
    
    # Product attributes
    brand = Column(String(200))
    manufacturer = Column(String(200))
    manufacturer_part_number = Column(String(200))
    upc = Column(String(20))
    weight = Column(Float)
    weight_unit = Column(String(10))
    
    # Dimensions
    length = Column(Float)
    width = Column(Float)
    height = Column(Float)
    dimension_unit = Column(String(10))
    
    # Inventory
    inventory_quantity = Column(Integer)
    track_inventory = Column(Boolean, default=True)
    continue_selling_when_out_of_stock = Column(Boolean, default=False)
    
    # SEO
    seo_title = Column(String(255))
    seo_description = Column(Text)
    
    # Status
    status = Column(String(20))
    is_active = Column(Boolean, default=True)
    
    # Category
    category_id = Column(Integer, ForeignKey('categories.id'))
    
    # Images
    featured_image_url = Column(String(1000))
    additional_images = Column(JSON)
    
    # Metafields and custom data
    metafields = Column(JSON)
    custom_attributes = Column(JSON)
    
    # Staging metadata
    change_type = Column(String(20), nullable=False)  # create, update, delete
    change_data = Column(JSON)  # Specific fields that changed
    change_source = Column(String(50))  # manual, api, sync, import
    staged_by = Column(Integer, ForeignKey('users.id'))
    staged_at = Column(DateTime, default=func.now())
    
    # Sync operation reference
    sync_operation_id = Column(Integer, ForeignKey('sync_operations.id'))
    
    # Conflict detection
    has_conflicts = Column(Boolean, default=False)
    conflict_fields = Column(JSON)  # List of fields with conflicts
    
    # Version tracking
    version = Column(Integer, default=1)
    parent_version = Column(Integer)
    
    # Processing status
    processing_status = Column(String(20), default='pending')
    processed_at = Column(DateTime)
    error_message = Column(Text)
    
    # Relationships
    source_product = relationship("Product")
    staged_by_user = relationship("User")
    sync_operation = relationship("SyncOperation", back_populates="staging_products")
    
    # Indexes
    __table_args__ = (
        Index('idx_staging_source_product', 'source_product_id'),
        Index('idx_staging_shopify_id', 'shopify_product_id'),
        Index('idx_staging_sku', 'sku'),
        Index('idx_staging_sync_op', 'sync_operation_id'),
        Index('idx_staging_status', 'processing_status'),
        Index('idx_staging_change_type', 'change_type'),
        Index('idx_staging_conflicts', 'has_conflicts'),
        Index('idx_staging_staged_at', 'staged_at'),
    )
    
    def __repr__(self):
        return f"<ProductsStaging(id={self.id}, sku='{self.sku}', change_type='{self.change_type}')>"


class SyncOperation(Base):
    """Track sync operations and their lifecycle."""
    __tablename__ = 'sync_operations'
    
    id = Column(Integer, primary_key=True)
    operation_uuid = Column(String(36), unique=True, nullable=False, index=True)
    
    # Operation details
    name = Column(String(255), nullable=False)
    description = Column(Text)
    operation_type = Column(String(50), nullable=False)  # full_sync, partial_sync, selective_sync
    sync_direction = Column(String(20), nullable=False)  # up, down, bidirectional
    
    # Configuration
    sync_config = Column(JSON)  # Sync configuration and filters
    filters = Column(JSON)  # Product filters
    options = Column(JSON)  # Additional options
    
    # Status tracking
    status = Column(String(20), default='pending', nullable=False)
    stage = Column(String(100))  # Current stage of operation
    progress = Column(Integer, default=0)  # 0-100
    
    # Timing
    scheduled_at = Column(DateTime)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    duration = Column(Integer)  # seconds
    
    # Statistics
    total_items = Column(Integer, default=0)
    items_processed = Column(Integer, default=0)
    items_succeeded = Column(Integer, default=0)
    items_failed = Column(Integer, default=0)
    items_skipped = Column(Integer, default=0)
    items_with_conflicts = Column(Integer, default=0)
    
    # Shopify specific stats
    products_created = Column(Integer, default=0)
    products_updated = Column(Integer, default=0)
    products_deleted = Column(Integer, default=0)
    images_synced = Column(Integer, default=0)
    
    # Error tracking
    error_count = Column(Integer, default=0)
    warning_count = Column(Integer, default=0)
    errors = Column(JSON)  # Detailed error log
    warnings = Column(JSON)  # Warning messages
    
    # User and system tracking
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    executed_by = Column(Integer, ForeignKey('users.id'))
    system_triggered = Column(Boolean, default=False)
    
    # Parent operation for chained syncs
    parent_operation_id = Column(Integer, ForeignKey('sync_operations.id'))
    
    # Rollback support
    is_rollbackable = Column(Boolean, default=True)
    rollback_operation_id = Column(Integer, ForeignKey('sync_operations.id'))
    
    # Metadata
    meta_data = Column(JSON)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    created_by_user = relationship("User", foreign_keys=[created_by])
    executed_by_user = relationship("User", foreign_keys=[executed_by])
    parent_operation = relationship("SyncOperation", remote_side=[id], foreign_keys=[parent_operation_id])
    rollback_operation = relationship("SyncOperation", remote_side=[id], foreign_keys=[rollback_operation_id])
    staging_products = relationship("ProductsStaging", back_populates="sync_operation")
    conflicts = relationship("SyncConflict", back_populates="sync_operation")
    
    # Indexes
    __table_args__ = (
        Index('idx_sync_op_uuid', 'operation_uuid'),
        Index('idx_sync_op_status', 'status'),
        Index('idx_sync_op_type', 'operation_type'),
        Index('idx_sync_op_direction', 'sync_direction'),
        Index('idx_sync_op_created_by', 'created_by'),
        Index('idx_sync_op_scheduled', 'scheduled_at'),
        Index('idx_sync_op_created', 'created_at'),
        Index('idx_sync_op_parent', 'parent_operation_id'),
    )
    
    def __repr__(self):
        return f"<SyncOperation(id={self.id}, name='{self.name}', status='{self.status}')>"


class SyncConflict(Base):
    """Manage sync conflicts and their resolution."""
    __tablename__ = 'sync_conflicts'
    
    id = Column(Integer, primary_key=True)
    conflict_uuid = Column(String(36), unique=True, nullable=False, index=True)
    
    # Conflict context
    sync_operation_id = Column(Integer, ForeignKey('sync_operations.id'), nullable=False)
    staging_product_id = Column(Integer, ForeignKey('products_staging.id'))
    product_id = Column(Integer, ForeignKey('products.id'))
    
    # Conflict details
    conflict_type = Column(String(50), nullable=False)  # field_mismatch, version_conflict, delete_conflict
    field_name = Column(String(100))  # Specific field in conflict
    
    # Values in conflict
    local_value = Column(Text)
    remote_value = Column(Text)
    suggested_value = Column(Text)
    
    # Version information
    local_version = Column(Integer)
    remote_version = Column(Integer)
    
    # Timestamps
    local_updated_at = Column(DateTime)
    remote_updated_at = Column(DateTime)
    
    # Resolution
    status = Column(String(20), default='unresolved', nullable=False)
    resolution_strategy = Column(String(50))  # local_wins, remote_wins, merge, manual
    resolved_value = Column(Text)
    resolved_by = Column(Integer, ForeignKey('users.id'))
    resolved_at = Column(DateTime)
    resolution_notes = Column(Text)
    
    # Auto-resolution
    auto_resolvable = Column(Boolean, default=False)
    auto_resolution_confidence = Column(Float)  # 0.0 to 1.0
    auto_resolution_reason = Column(String(255))
    
    # Impact assessment
    severity = Column(String(20), default='medium')  # low, medium, high, critical
    affected_systems = Column(JSON)  # List of systems affected
    
    # Metadata
    meta_data = Column(JSON)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    sync_operation = relationship("SyncOperation", back_populates="conflicts")
    staging_product = relationship("ProductsStaging")
    product = relationship("Product")
    resolved_by_user = relationship("User")
    
    # Indexes
    __table_args__ = (
        Index('idx_conflict_uuid', 'conflict_uuid'),
        Index('idx_conflict_sync_op', 'sync_operation_id'),
        Index('idx_conflict_product', 'product_id'),
        Index('idx_conflict_status', 'status'),
        Index('idx_conflict_type', 'conflict_type'),
        Index('idx_conflict_severity', 'severity'),
        Index('idx_conflict_field', 'field_name'),
        Index('idx_conflict_created', 'created_at'),
    )
    
    def __repr__(self):
        return f"<SyncConflict(id={self.id}, type='{self.conflict_type}', status='{self.status}')>"


# Versioning Support

class ProductVersion(Base):
    """Version history for products."""
    __tablename__ = 'product_versions'
    
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=False)
    version_number = Column(Integer, nullable=False)
    
    # Snapshot of product data at this version
    product_data = Column(JSON, nullable=False)  # Complete product state
    
    # Change information
    change_type = Column(String(20), nullable=False)
    changed_fields = Column(JSON)  # List of fields that changed
    change_summary = Column(Text)
    
    # Source of change
    change_source = Column(String(50))  # manual, sync, import, api
    source_reference = Column(String(255))  # Reference ID from source
    
    # User and system tracking
    created_by = Column(Integer, ForeignKey('users.id'))
    system_generated = Column(Boolean, default=False)
    
    # Sync tracking
    sync_operation_id = Column(Integer, ForeignKey('sync_operations.id'))
    shopify_version_id = Column(String(50))  # Shopify's version identifier
    
    # Metadata
    meta_data = Column(JSON)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    
    # Relationships
    product = relationship("Product")
    created_by_user = relationship("User")
    sync_operation = relationship("SyncOperation")
    
    # Indexes
    __table_args__ = (
        UniqueConstraint('product_id', 'version_number', name='uq_product_version'),
        Index('idx_version_product', 'product_id'),
        Index('idx_version_number', 'version_number'),
        Index('idx_version_change_type', 'change_type'),
        Index('idx_version_source', 'change_source'),
        Index('idx_version_created', 'created_at'),
        Index('idx_version_sync_op', 'sync_operation_id'),
    )
    
    def __repr__(self):
        return f"<ProductVersion(id={self.id}, product_id={self.product_id}, version={self.version_number})>"


class CategoryVersion(Base):
    """Version history for categories."""
    __tablename__ = 'category_versions'
    
    id = Column(Integer, primary_key=True)
    category_id = Column(Integer, ForeignKey('categories.id'), nullable=False)
    version_number = Column(Integer, nullable=False)
    
    # Snapshot of category data
    category_data = Column(JSON, nullable=False)
    
    # Change information
    change_type = Column(String(20), nullable=False)
    changed_fields = Column(JSON)
    change_summary = Column(Text)
    
    # Source tracking
    change_source = Column(String(50))
    created_by = Column(Integer, ForeignKey('users.id'))
    
    # Metadata
    created_at = Column(DateTime, default=func.now(), nullable=False)
    
    # Relationships
    category = relationship("Category")
    created_by_user = relationship("User")
    
    # Indexes
    __table_args__ = (
        UniqueConstraint('category_id', 'version_number', name='uq_category_version'),
        Index('idx_cat_version_category', 'category_id'),
        Index('idx_cat_version_number', 'version_number'),
        Index('idx_cat_version_created', 'created_at'),
    )
    
    def __repr__(self):
        return f"<CategoryVersion(id={self.id}, category_id={self.category_id}, version={self.version_number})>"


# Xorosoft Integration

class XorosoftProduct(Base):
    """Xorosoft product data for stock and inventory integration."""
    __tablename__ = 'xorosoft_products'
    
    id = Column(Integer, primary_key=True)
    
    # Xorosoft identifiers
    xorosoft_id = Column(String(100), unique=True, nullable=False, index=True)
    xorosoft_sku = Column(String(100), index=True)
    
    # Product mapping
    product_id = Column(Integer, ForeignKey('products.id'), index=True)
    sku_mapping = Column(String(100))  # Our SKU that maps to Xorosoft
    
    # Stock information
    stock_on_hand = Column(Integer, default=0)
    stock_available = Column(Integer, default=0)
    stock_allocated = Column(Integer, default=0)
    stock_on_order = Column(Integer, default=0)
    
    # Location information
    warehouse_code = Column(String(50))
    bin_location = Column(String(100))
    
    # Pricing from Xorosoft
    cost_price = Column(Float)
    wholesale_price = Column(Float)
    retail_price = Column(Float)
    
    # Product information
    product_name = Column(String(500))
    product_description = Column(Text)
    barcode = Column(String(50))
    
    # Supplier information
    supplier_code = Column(String(50))
    supplier_name = Column(String(200))
    supplier_sku = Column(String(100))
    
    # Sync information
    last_synced = Column(DateTime)
    sync_status = Column(String(20), default='pending')
    sync_errors = Column(JSON)
    
    # Change tracking
    stock_updated_at = Column(DateTime)
    price_updated_at = Column(DateTime)
    data_hash = Column(String(64))  # Hash of data for change detection
    
    # Metadata
    raw_data = Column(JSON)  # Complete Xorosoft record
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    product = relationship("Product")
    
    # Indexes
    __table_args__ = (
        Index('idx_xoro_product', 'product_id'),
        Index('idx_xoro_sku', 'xorosoft_sku'),
        Index('idx_xoro_sku_mapping', 'sku_mapping'),
        Index('idx_xoro_sync_status', 'sync_status'),
        Index('idx_xoro_warehouse', 'warehouse_code'),
        Index('idx_xoro_supplier', 'supplier_code'),
        Index('idx_xoro_updated', 'updated_at'),
    )
    
    def __repr__(self):
        return f"<XorosoftProduct(id={self.id}, xorosoft_id='{self.xorosoft_id}', sku='{self.xorosoft_sku}')>"


class XorosoftSyncLog(Base):
    """Log Xorosoft sync operations."""
    __tablename__ = 'xorosoft_sync_logs'
    
    id = Column(Integer, primary_key=True)
    
    # Sync details
    sync_type = Column(String(50), nullable=False)  # stock_update, price_update, full_sync
    sync_direction = Column(String(20), default='down')  # down (from Xorosoft), up (to Xorosoft)
    
    # Timing
    started_at = Column(DateTime, default=func.now(), nullable=False)
    completed_at = Column(DateTime)
    duration = Column(Integer)  # seconds
    
    # Statistics
    total_records = Column(Integer, default=0)
    records_processed = Column(Integer, default=0)
    records_updated = Column(Integer, default=0)
    records_failed = Column(Integer, default=0)
    
    # Specific counts
    stock_updates = Column(Integer, default=0)
    price_updates = Column(Integer, default=0)
    new_products = Column(Integer, default=0)
    
    # Status and errors
    status = Column(String(20), default='pending')
    error_message = Column(Text)
    errors = Column(JSON)
    
    # File information (if applicable)
    import_file = Column(String(1000))
    export_file = Column(String(1000))
    
    # User tracking
    triggered_by = Column(Integer, ForeignKey('users.id'))
    
    # Metadata
    meta_data = Column(JSON)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    
    # Relationships
    triggered_by_user = relationship("User")
    
    # Indexes
    __table_args__ = (
        Index('idx_xoro_log_type', 'sync_type'),
        Index('idx_xoro_log_status', 'status'),
        Index('idx_xoro_log_started', 'started_at'),
        Index('idx_xoro_log_user', 'triggered_by'),
    )
    
    def __repr__(self):
        return f"<XorosoftSyncLog(id={self.id}, type='{self.sync_type}', status='{self.status}')>"


# Rollback Support

class SyncRollback(Base):
    """Track rollback operations for sync operations."""
    __tablename__ = 'sync_rollbacks'
    
    id = Column(Integer, primary_key=True)
    rollback_uuid = Column(String(36), unique=True, nullable=False, index=True)
    
    # Original operation
    original_operation_id = Column(Integer, ForeignKey('sync_operations.id'), nullable=False)
    rollback_operation_id = Column(Integer, ForeignKey('sync_operations.id'))
    
    # Rollback details
    rollback_type = Column(String(50), nullable=False)  # full, partial, selective
    rollback_scope = Column(JSON)  # Specific items to rollback
    
    # Status
    status = Column(String(20), default='pending', nullable=False)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    
    # Statistics
    total_items = Column(Integer, default=0)
    items_rolled_back = Column(Integer, default=0)
    items_failed = Column(Integer, default=0)
    
    # Backup data
    backup_data = Column(JSON)  # Snapshot of data before original operation
    
    # User tracking
    initiated_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    reason = Column(Text)
    
    # Metadata
    created_at = Column(DateTime, default=func.now(), nullable=False)
    
    # Relationships
    original_operation = relationship("SyncOperation", foreign_keys=[original_operation_id])
    rollback_operation = relationship("SyncOperation", foreign_keys=[rollback_operation_id])
    initiated_by_user = relationship("User")
    
    # Indexes
    __table_args__ = (
        Index('idx_rollback_uuid', 'rollback_uuid'),
        Index('idx_rollback_original', 'original_operation_id'),
        Index('idx_rollback_status', 'status'),
        Index('idx_rollback_user', 'initiated_by'),
        Index('idx_rollback_created', 'created_at'),
    )
    
    def __repr__(self):
        return f"<SyncRollback(id={self.id}, original_op={self.original_operation_id}, status='{self.status}')>"


# Audit and Performance

class SyncPerformanceLog(Base):
    """Track performance metrics for sync operations."""
    __tablename__ = 'sync_performance_logs'
    
    id = Column(Integer, primary_key=True)
    
    # Operation reference
    sync_operation_id = Column(Integer, ForeignKey('sync_operations.id'), nullable=False)
    
    # Performance metrics
    total_duration = Column(Integer)  # Total time in seconds
    api_calls_count = Column(Integer, default=0)
    api_calls_duration = Column(Integer)  # Time spent on API calls
    
    # Database metrics
    db_queries_count = Column(Integer, default=0)
    db_queries_duration = Column(Integer)
    db_writes_count = Column(Integer, default=0)
    
    # Resource usage
    peak_memory_mb = Column(Float)
    avg_cpu_percent = Column(Float)
    
    # Throughput
    items_per_second = Column(Float)
    api_calls_per_minute = Column(Float)
    
    # Shopify specific
    shopify_rate_limit_hits = Column(Integer, default=0)
    shopify_throttle_duration = Column(Integer)  # Time spent waiting for rate limits
    
    # Bottlenecks
    bottleneck_stage = Column(String(100))
    bottleneck_duration = Column(Integer)
    
    # Metadata
    performance_data = Column(JSON)  # Detailed performance breakdown
    created_at = Column(DateTime, default=func.now(), nullable=False)
    
    # Relationships
    sync_operation = relationship("SyncOperation")
    
    # Indexes
    __table_args__ = (
        Index('idx_perf_sync_op', 'sync_operation_id'),
        Index('idx_perf_duration', 'total_duration'),
        Index('idx_perf_throughput', 'items_per_second'),
        Index('idx_perf_created', 'created_at'),
    )
    
    def __repr__(self):
        return f"<SyncPerformanceLog(id={self.id}, sync_op={self.sync_operation_id}, duration={self.total_duration}s)>"