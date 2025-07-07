"""
Database Models for Product Feed Integration System

This module contains SQLAlchemy models for all entities in the system.
"""

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Float, JSON, Index, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, validates
from sqlalchemy.sql import func
from datetime import datetime
import enum

Base = declarative_base()

# Enums for type safety
class JobStatus(enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class SyncStatus(enum.Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"

class IconStatus(enum.Enum):
    GENERATING = "generating"
    ACTIVE = "active"
    INACTIVE = "inactive"
    FAILED = "failed"

class ProductStatus(enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"
    SYNCED = "synced"

class User(Base):
    """User model for authentication and audit trails."""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    first_name = Column(String(100))
    last_name = Column(String(100))
    is_active = Column(Boolean, default=True, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    supabase_id = Column(String(255), unique=True, index=True)  # Supabase user ID
    last_login = Column(DateTime)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    jobs = relationship("Job", back_populates="user")
    icons = relationship("Icon", back_populates="created_by_user")
    sync_history = relationship("SyncHistory", back_populates="user")
    
    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}')>"

class Category(Base):
    """Category model with hierarchy support."""
    __tablename__ = 'categories'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text)
    parent_id = Column(Integer, ForeignKey('categories.id'), index=True)
    level = Column(Integer, default=0, nullable=False)
    path = Column(String(500))  # Materialized path for efficient queries
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Shopify integration
    shopify_collection_id = Column(String(50), index=True)
    shopify_handle = Column(String(255))
    shopify_synced_at = Column(DateTime)
    
    # Metadata
    meta_data = Column(JSON)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    parent = relationship("Category", remote_side=[id], backref="children")
    products = relationship("Product", back_populates="category")
    icons = relationship("Icon", back_populates="category")
    
    # Indexes
    __table_args__ = (
        Index('idx_category_parent_level', 'parent_id', 'level'),
        Index('idx_category_path', 'path'),
        Index('idx_category_shopify', 'shopify_collection_id'),
    )
    
    @validates('name')
    def validate_name(self, key, name):
        if not name or len(name.strip()) == 0:
            raise ValueError("Category name cannot be empty")
        return name.strip()
    
    def __repr__(self):
        return f"<Category(id={self.id}, name='{self.name}', level={self.level})>"

class Product(Base):
    """Product model with full product information."""
    __tablename__ = 'products'
    
    id = Column(Integer, primary_key=True)
    
    # Basic product information
    sku = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(500), nullable=False)
    description = Column(Text)
    short_description = Column(Text)
    
    # Pricing
    price = Column(Float, nullable=False)
    compare_at_price = Column(Float)
    cost_price = Column(Float)
    
    # Product attributes
    brand = Column(String(200))
    manufacturer = Column(String(200))
    manufacturer_part_number = Column(String(200), index=True)
    upc = Column(String(20))
    weight = Column(Float)
    weight_unit = Column(String(10), default='kg')
    
    # Dimensions
    length = Column(Float)
    width = Column(Float)
    height = Column(Float)
    dimension_unit = Column(String(10), default='cm')
    
    # Inventory
    inventory_quantity = Column(Integer, default=0)
    track_inventory = Column(Boolean, default=True)
    continue_selling_when_out_of_stock = Column(Boolean, default=False)
    
    # SEO
    seo_title = Column(String(255))
    seo_description = Column(Text)
    
    # Status
    status = Column(String(20), default=ProductStatus.DRAFT.value, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Category relationship
    category_id = Column(Integer, ForeignKey('categories.id'), nullable=False, index=True)
    
    # Shopify integration
    shopify_product_id = Column(String(50), index=True)
    shopify_variant_id = Column(String(50))
    shopify_handle = Column(String(255))
    shopify_synced_at = Column(DateTime)
    shopify_sync_status = Column(String(20), default=SyncStatus.PENDING.value)
    shopify_id = Column(String(50), index=True)  # Alternative field name for compatibility
    shopify_status = Column(String(20), default='pending')
    last_synced = Column(DateTime)
    title = Column(String(500))  # Alternative field name for name
    
    # Images
    featured_image_url = Column(String(1000))
    additional_images = Column(JSON)  # Array of image URLs
    
    # Metafields and custom data
    metafields = Column(JSON)
    custom_attributes = Column(JSON)
    
    # Etilize integration fields
    etilize_id = Column(String(100), index=True)
    primary_source = Column(String(50), default='manual')
    source_priority = Column(Integer, default=100)
    data_sources = Column(JSON)  # Track all contributing sources
    import_batch_id = Column(Integer, ForeignKey('etilize_import_batches.id'))
    last_imported = Column(DateTime)
    import_errors = Column(JSON)
    has_conflicts = Column(Boolean, default=False)
    conflict_resolution = Column(JSON)
    manual_overrides = Column(JSON)
    etilize_data = Column(JSON)
    computed_fields = Column(JSON)
    data_quality_score = Column(Float, default=0.0)
    completeness_score = Column(Float, default=0.0)
    
    # Audit fields
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    category = relationship("Category", back_populates="products")
    sources = relationship("ProductSource", back_populates="product")
    import_batch = relationship("EtilizeImportBatch")
    
    # Indexes
    __table_args__ = (
        Index('idx_product_sku', 'sku'),
        Index('idx_product_mpn', 'manufacturer_part_number'),
        Index('idx_product_shopify', 'shopify_product_id'),
        Index('idx_product_category', 'category_id'),
        Index('idx_product_status', 'status'),
        Index('idx_product_brand', 'brand'),
        Index('idx_product_etilize', 'etilize_id'),
        Index('idx_product_source', 'primary_source'),
        Index('idx_product_import_batch', 'import_batch_id'),
        Index('idx_product_conflicts', 'has_conflicts'),
        Index('idx_product_quality', 'data_quality_score'),
    )
    
    @validates('sku')
    def validate_sku(self, key, sku):
        if not sku or len(sku.strip()) == 0:
            raise ValueError("SKU cannot be empty")
        return sku.strip().upper()
    
    @validates('price')
    def validate_price(self, key, price):
        if price is not None and price < 0:
            raise ValueError("Price cannot be negative")
        return price
    
    def __repr__(self):
        return f"<Product(id={self.id}, sku='{self.sku}', name='{self.name}')>"

class Icon(Base):
    """Icon model for category icons and their metadata."""
    __tablename__ = 'icons'
    
    id = Column(Integer, primary_key=True)
    
    # Basic information
    category_id = Column(Integer, ForeignKey('categories.id'), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(1000), nullable=False)
    file_size = Column(Integer)  # Size in bytes
    file_hash = Column(String(64))  # SHA256 hash for deduplication
    
    # Image properties
    width = Column(Integer)
    height = Column(Integer)
    format = Column(String(10))  # PNG, JPEG, SVG, etc.
    
    # Generation information
    prompt = Column(Text)
    style = Column(String(50))  # modern, flat, outlined, minimal
    color = Column(String(20))  # Hex color code
    background = Column(String(20))  # transparent, white, colored
    model = Column(String(50))  # AI model used for generation
    
    # Status and sync
    status = Column(String(20), default=IconStatus.GENERATING.value, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Shopify integration
    shopify_image_id = Column(String(50))
    shopify_image_url = Column(String(1000))
    shopify_synced_at = Column(DateTime)
    shopify_sync_status = Column(String(20), default=SyncStatus.PENDING.value)
    
    # Generation metadata
    generation_time = Column(Float)  # Time taken to generate in seconds
    generation_cost = Column(Float)  # Cost in USD
    generation_batch_id = Column(String(50))  # For batch operations
    
    # User who created the icon
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    
    # Metadata
    meta_data = Column(JSON)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    category = relationship("Category", back_populates="icons")
    created_by_user = relationship("User", back_populates="icons")
    
    # Indexes
    __table_args__ = (
        Index('idx_icon_category', 'category_id'),
        Index('idx_icon_hash', 'file_hash'),
        Index('idx_icon_status', 'status'),
        Index('idx_icon_shopify', 'shopify_image_id'),
        Index('idx_icon_batch', 'generation_batch_id'),
    )
    
    def __repr__(self):
        return f"<Icon(id={self.id}, category_id={self.category_id}, filename='{self.filename}')>"

class Job(Base):
    """Job model for background task tracking."""
    __tablename__ = 'jobs'
    
    id = Column(Integer, primary_key=True)
    job_uuid = Column(String(36), unique=True, nullable=False, index=True)  # UUID for external reference
    
    # Job information
    script_name = Column(String(200), nullable=False)
    display_name = Column(String(255))
    description = Column(Text)
    
    # Status and progress
    status = Column(String(20), default=JobStatus.PENDING.value, nullable=False)
    progress = Column(Integer, default=0)  # 0-100
    current_stage = Column(String(255))
    
    # Timing
    created_at = Column(DateTime, default=func.now(), nullable=False)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    estimated_duration = Column(Integer)  # Seconds
    actual_duration = Column(Integer)  # Seconds
    
    # Parameters and results
    parameters = Column(JSON)
    options = Column(JSON)
    result = Column(JSON)
    error_message = Column(Text)
    
    # Output and logging
    output_log = Column(Text)
    log_file_path = Column(String(1000))
    
    # User who created the job
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    
    # Priority and retry
    priority = Column(Integer, default=0)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    
    # Metadata
    meta_data = Column(JSON)
    
    # Relationships
    user = relationship("User", back_populates="jobs")
    
    # Indexes
    __table_args__ = (
        Index('idx_job_uuid', 'job_uuid'),
        Index('idx_job_status', 'status'),
        Index('idx_job_user', 'user_id'),
        Index('idx_job_script', 'script_name'),
        Index('idx_job_created', 'created_at'),
    )
    
    def __repr__(self):
        return f"<Job(id={self.id}, uuid='{self.job_uuid}', script='{self.script_name}', status='{self.status}')>"

class SyncHistory(Base):
    """Sync history model for tracking data synchronization events."""
    __tablename__ = 'sync_history'
    
    id = Column(Integer, primary_key=True)
    
    # Sync information
    sync_type = Column(String(50), nullable=False)  # full_import, product_sync, icon_sync, etc.
    sync_source = Column(String(50))  # etilize, manual, scheduled
    sync_target = Column(String(50))  # shopify, local
    
    # Status
    status = Column(String(20), default=SyncStatus.PENDING.value, nullable=False)
    
    # Timing
    started_at = Column(DateTime, default=func.now(), nullable=False)
    completed_at = Column(DateTime)
    duration = Column(Integer)  # Duration in seconds
    
    # Statistics
    total_items = Column(Integer, default=0)
    items_processed = Column(Integer, default=0)
    items_successful = Column(Integer, default=0)
    items_failed = Column(Integer, default=0)
    items_skipped = Column(Integer, default=0)
    
    # Related records
    products_synced = Column(Integer, default=0)
    categories_synced = Column(Integer, default=0)
    icons_synced = Column(Integer, default=0)
    
    # Messages and errors
    message = Column(Text)
    error_message = Column(Text)
    warnings = Column(JSON)  # Array of warning messages
    errors = Column(JSON)  # Array of error messages
    
    # Files involved
    input_files = Column(JSON)  # Array of input file paths
    output_files = Column(JSON)  # Array of output file paths
    log_file_path = Column(String(1000))
    
    # User who triggered the sync
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    
    # Related job
    job_id = Column(Integer, ForeignKey('jobs.id'), index=True)
    
    # Metadata
    meta_data = Column(JSON)
    
    # Relationships
    user = relationship("User", back_populates="sync_history")
    job = relationship("Job")
    
    # Indexes
    __table_args__ = (
        Index('idx_sync_type', 'sync_type'),
        Index('idx_sync_status', 'status'),
        Index('idx_sync_started', 'started_at'),
        Index('idx_sync_user', 'user_id'),
        Index('idx_sync_job', 'job_id'),
    )
    
    def __repr__(self):
        return f"<SyncHistory(id={self.id}, type='{self.sync_type}', status='{self.status}')>"

class ProductImage(Base):
    """Product image model for managing product images."""
    __tablename__ = 'product_images'
    
    id = Column(Integer, primary_key=True)
    
    # Product relationship
    product_id = Column(Integer, ForeignKey('products.id'), nullable=False, index=True)
    
    # Image information
    filename = Column(String(255), nullable=False)
    file_path = Column(String(1000), nullable=False)
    url = Column(String(1000))
    alt_text = Column(String(255))
    
    # Image properties
    width = Column(Integer)
    height = Column(Integer)
    file_size = Column(Integer)
    format = Column(String(10))
    file_hash = Column(String(64))
    
    # Order and status
    sort_order = Column(Integer, default=0)
    is_featured = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    
    # Shopify integration
    shopify_image_id = Column(String(50))
    shopify_image_url = Column(String(1000))
    shopify_synced_at = Column(DateTime)
    
    # Metadata
    meta_data = Column(JSON)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    product = relationship("Product")
    
    # Indexes
    __table_args__ = (
        Index('idx_product_image_product', 'product_id'),
        Index('idx_product_image_hash', 'file_hash'),
        Index('idx_product_image_shopify', 'shopify_image_id'),
        UniqueConstraint('product_id', 'file_hash', name='uq_product_image_hash'),
    )
    
    def __repr__(self):
        return f"<ProductImage(id={self.id}, product_id={self.product_id}, filename='{self.filename}')>"

class ProductMetafield(Base):
    """Product metafield model for custom product attributes."""
    __tablename__ = 'product_metafields'
    
    id = Column(Integer, primary_key=True)
    
    # Product relationship
    product_id = Column(Integer, ForeignKey('products.id'), nullable=False, index=True)
    
    # Metafield information
    namespace = Column(String(255), nullable=False)
    key = Column(String(255), nullable=False)
    value = Column(Text, nullable=False)
    value_type = Column(String(50), default='string')  # string, integer, float, boolean, json, date
    
    # Shopify integration
    shopify_metafield_id = Column(String(50), index=True)
    shopify_owner_id = Column(String(50))  # Product ID in Shopify
    shopify_owner_resource = Column(String(50), default='product')
    
    # Metadata
    description = Column(Text)
    is_visible = Column(Boolean, default=True)
    display_order = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    product = relationship("Product", backref="product_metafields")
    
    # Indexes and constraints
    __table_args__ = (
        Index('idx_metafield_product', 'product_id'),
        Index('idx_metafield_namespace_key', 'namespace', 'key'),
        Index('idx_metafield_shopify', 'shopify_metafield_id'),
        UniqueConstraint('product_id', 'namespace', 'key', name='uq_product_metafield'),
    )
    
    @validates('value_type')
    def validate_value_type(self, key, value_type):
        valid_types = ['string', 'integer', 'float', 'boolean', 'json', 'date']
        if value_type not in valid_types:
            raise ValueError(f"Invalid value_type. Must be one of: {', '.join(valid_types)}")
        return value_type
    
    def get_typed_value(self):
        """Return the value converted to its appropriate type."""
        if self.value_type == 'integer':
            return int(self.value)
        elif self.value_type == 'float':
            return float(self.value)
        elif self.value_type == 'boolean':
            return self.value.lower() in ('true', '1', 'yes')
        elif self.value_type == 'json':
            import json
            return json.loads(self.value)
        elif self.value_type == 'date':
            from datetime import datetime
            return datetime.fromisoformat(self.value)
        else:
            return self.value
    
    def __repr__(self):
        return f"<ProductMetafield(id={self.id}, product_id={self.product_id}, namespace='{self.namespace}', key='{self.key}')>"

class SystemLog(Base):
    """System log model for application-level logging."""
    __tablename__ = 'system_logs'
    
    id = Column(Integer, primary_key=True)
    
    # Log information
    level = Column(String(20), nullable=False)  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    message = Column(Text, nullable=False)
    logger_name = Column(String(200))
    module = Column(String(200))
    function = Column(String(200))
    line_number = Column(Integer)
    
    # Context
    user_id = Column(Integer, ForeignKey('users.id'), index=True)
    job_id = Column(Integer, ForeignKey('jobs.id'), index=True)
    session_id = Column(String(100))
    request_id = Column(String(100))
    
    # Metadata
    extra_data = Column(JSON)
    stack_trace = Column(Text)
    
    # Timestamp
    created_at = Column(DateTime, default=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User")
    job = relationship("Job")
    
    # Indexes
    __table_args__ = (
        Index('idx_log_level', 'level'),
        Index('idx_log_created', 'created_at'),
        Index('idx_log_user', 'user_id'),
        Index('idx_log_job', 'job_id'),
        Index('idx_log_module', 'module'),
    )
    
    def __repr__(self):
        return f"<SystemLog(id={self.id}, level='{self.level}', message='{self.message[:50]}...')>"

class Configuration(Base):
    """Configuration model for system settings."""
    __tablename__ = 'configurations'
    
    id = Column(Integer, primary_key=True)
    
    # Configuration key-value
    key = Column(String(200), unique=True, nullable=False, index=True)
    value = Column(Text)
    data_type = Column(String(20), default='string')  # string, integer, float, boolean, json
    description = Column(Text)
    
    # Grouping
    category = Column(String(100), index=True)
    
    # Validation
    is_required = Column(Boolean, default=False)
    is_encrypted = Column(Boolean, default=False)
    validation_regex = Column(String(500))
    
    # Metadata
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Indexes
    __table_args__ = (
        Index('idx_config_key', 'key'),
        Index('idx_config_category', 'category'),
    )
    
    def __repr__(self):
        return f"<Configuration(key='{self.key}', category='{self.category}')>"

# Enhanced Models for Etilize Import System

class ImportBatchStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    VALIDATING = "validating"
    IMPORTING = "importing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class ProcessingStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    VALIDATED = "validated"
    MAPPED = "mapped"
    IMPORTED = "imported"
    FAILED = "failed"
    SKIPPED = "skipped"

class ConflictResolution(enum.Enum):
    ETILIZE_PRIORITY = "etilize_priority"
    MANUAL_PRIORITY = "manual_priority"
    SHOPIFY_PRIORITY = "shopify_priority"
    MERGE_FIELDS = "merge_fields"
    TIMESTAMP_BASED = "timestamp_based"

class EtilizeImportBatch(Base):
    """Track Etilize import batches with comprehensive metadata."""
    __tablename__ = 'etilize_import_batches'
    
    id = Column(Integer, primary_key=True)
    batch_uuid = Column(String(36), unique=True, nullable=False, index=True)
    
    # Import details
    import_type = Column(String(50), nullable=False)  # full, incremental, manual
    source_file_path = Column(String(1000), nullable=False)
    source_file_hash = Column(String(64), nullable=False)
    source_file_size = Column(Integer, nullable=False)
    source_file_modified = Column(DateTime, nullable=False)
    
    # Processing status
    status = Column(String(20), default='pending', nullable=False)
    stage = Column(String(50), default='initialization')
    progress = Column(Integer, default=0)
    
    # Timing
    started_at = Column(DateTime, nullable=False, default=func.now())
    completed_at = Column(DateTime)
    duration = Column(Integer)  # seconds
    
    # Statistics
    total_records = Column(Integer, default=0)
    records_processed = Column(Integer, default=0)
    records_imported = Column(Integer, default=0)
    records_updated = Column(Integer, default=0)
    records_failed = Column(Integer, default=0)
    records_skipped = Column(Integer, default=0)
    
    # Error handling
    error_count = Column(Integer, default=0)
    warning_count = Column(Integer, default=0)
    error_details = Column(JSON)
    
    # User and job tracking
    triggered_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    job_id = Column(Integer, ForeignKey('jobs.id'))
    
    # Metadata
    import_config = Column(JSON)
    meta_data = Column(JSON)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User")
    job = relationship("Job")
    staging_products = relationship("EtilizeStagingProduct", back_populates="batch")
    
    __table_args__ = (
        Index('idx_batch_status', 'status'),
        Index('idx_batch_type', 'import_type'),
        Index('idx_batch_started', 'started_at'),
        Index('idx_batch_user', 'triggered_by'),
    )
    
    def __repr__(self):
        return f"<EtilizeImportBatch(id={self.id}, batch_uuid='{self.batch_uuid}', status='{self.status}')>"

class EtilizeStagingProduct(Base):
    """Staging table for Etilize products before processing."""
    __tablename__ = 'etilize_staging_products'
    
    id = Column(Integer, primary_key=True)
    batch_id = Column(Integer, ForeignKey('etilize_import_batches.id'), nullable=False)
    
    # Raw Etilize data
    etilize_id = Column(String(100), index=True)
    raw_data = Column(JSON, nullable=False)
    
    # Extracted key fields
    title = Column(String(1000))
    sku = Column(String(200), index=True)
    manufacturer_part_number = Column(String(200), index=True)
    brand = Column(String(200))
    manufacturer = Column(String(200))
    description = Column(Text)
    price = Column(Float)
    
    # Processing status
    processing_status = Column(String(20), default='pending')
    validation_status = Column(String(20), default='pending')
    mapping_status = Column(String(20), default='pending')
    
    # Validation results
    validation_errors = Column(JSON)
    validation_warnings = Column(JSON)
    
    # Mapping results
    mapped_product_id = Column(Integer, ForeignKey('products.id'))
    mapping_confidence = Column(Float, default=0.0)
    mapping_method = Column(String(50))
    mapping_details = Column(JSON)
    
    # Processing metadata
    processed_at = Column(DateTime)
    error_message = Column(Text)
    
    # Audit
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    batch = relationship("EtilizeImportBatch", back_populates="staging_products")
    mapped_product = relationship("Product")
    
    __table_args__ = (
        Index('idx_staging_batch', 'batch_id'),
        Index('idx_staging_sku', 'sku'),
        Index('idx_staging_mpn', 'manufacturer_part_number'),
        Index('idx_staging_processing', 'processing_status'),
        Index('idx_staging_validation', 'validation_status'),
        Index('idx_staging_mapping', 'mapping_status'),
    )
    
    def __repr__(self):
        return f"<EtilizeStagingProduct(id={self.id}, sku='{self.sku}', status='{self.processing_status}')>"

class ProductSource(Base):
    """Track product data sources and their priority."""
    __tablename__ = 'product_sources'
    
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=False)
    
    # Source information
    source_type = Column(String(50), nullable=False)  # etilize, manual, shopify
    source_priority = Column(Integer, default=100)  # Lower = higher priority
    source_identifier = Column(String(200))
    source_url = Column(String(1000))
    
    # Source metadata
    source_data = Column(JSON)
    last_updated = Column(DateTime, nullable=False)
    
    # Synchronization
    sync_status = Column(String(20), default='pending')
    last_synced = Column(DateTime)
    sync_errors = Column(JSON)
    
    # Audit
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    product = relationship("Product", back_populates="sources")
    
    __table_args__ = (
        Index('idx_source_product', 'product_id'),
        Index('idx_source_type', 'source_type'),
        Index('idx_source_priority', 'source_priority'),
        Index('idx_source_updated', 'last_updated'),
        UniqueConstraint('product_id', 'source_type', 'source_identifier', name='uq_product_source'),
    )
    
    def __repr__(self):
        return f"<ProductSource(id={self.id}, product_id={self.product_id}, source_type='{self.source_type}')>"

class ProductChangeLog(Base):
    """Comprehensive change tracking for products."""
    __tablename__ = 'product_change_logs'
    
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=False)
    
    # Change details
    change_type = Column(String(50), nullable=False)  # create, update, delete, sync
    field_name = Column(String(100))
    old_value = Column(Text)
    new_value = Column(Text)
    value_type = Column(String(20), default='string')
    
    # Change source
    source_type = Column(String(50), nullable=False)
    source_id = Column(String(100))
    triggered_by = Column(Integer, ForeignKey('users.id'))
    
    # Batch tracking
    batch_id = Column(Integer, ForeignKey('etilize_import_batches.id'))
    job_id = Column(Integer, ForeignKey('jobs.id'))
    
    # Metadata
    change_reason = Column(String(200))
    confidence_score = Column(Float)
    meta_data = Column(JSON)
    
    # Audit
    created_at = Column(DateTime, default=func.now(), nullable=False)
    
    # Relationships
    product = relationship("Product")
    user = relationship("User")
    batch = relationship("EtilizeImportBatch")
    job = relationship("Job")
    
    __table_args__ = (
        Index('idx_change_product', 'product_id'),
        Index('idx_change_type', 'change_type'),
        Index('idx_change_field', 'field_name'),
        Index('idx_change_source', 'source_type'),
        Index('idx_change_created', 'created_at'),
        Index('idx_change_batch', 'batch_id'),
    )
    
    def __repr__(self):
        return f"<ProductChangeLog(id={self.id}, product_id={self.product_id}, change_type='{self.change_type}')>"

class SyncQueue(Base):
    """Queue for managing synchronization tasks."""
    __tablename__ = 'sync_queue'
    
    id = Column(Integer, primary_key=True)
    queue_uuid = Column(String(36), unique=True, nullable=False, index=True)
    
    # Queue item details
    item_type = Column(String(50), nullable=False)  # product, category, image
    item_id = Column(Integer, nullable=False)
    target_system = Column(String(50), nullable=False)  # shopify, etilize
    
    # Sync operation
    operation_type = Column(String(50), nullable=False)  # create, update, delete
    operation_data = Column(JSON)
    
    # Priority and scheduling
    priority = Column(Integer, default=100)
    scheduled_at = Column(DateTime, default=func.now())
    
    # Status tracking
    status = Column(String(20), default='pending')
    attempts = Column(Integer, default=0)
    max_attempts = Column(Integer, default=3)
    
    # Processing
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    duration = Column(Integer)
    
    # Error handling
    last_error = Column(Text)
    error_details = Column(JSON)
    
    # Dependencies
    depends_on = Column(JSON)  # List of queue item IDs
    blocks = Column(JSON)  # List of queue item IDs that depend on this
    
    # Metadata
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_queue_status', 'status'),
        Index('idx_queue_type', 'item_type'),
        Index('idx_queue_target', 'target_system'),
        Index('idx_queue_priority', 'priority'),
        Index('idx_queue_scheduled', 'scheduled_at'),
        Index('idx_queue_item', 'item_type', 'item_id'),
    )
    
    def __repr__(self):
        return f"<SyncQueue(id={self.id}, item_type='{self.item_type}', status='{self.status}')>"

class ImportRule(Base):
    """Rules for import processing and validation."""
    __tablename__ = 'import_rules'
    
    id = Column(Integer, primary_key=True)
    
    # Rule identification
    rule_name = Column(String(200), nullable=False)
    rule_type = Column(String(50), nullable=False)  # validation, mapping, transformation
    rule_category = Column(String(100))
    
    # Rule definition
    conditions = Column(JSON, nullable=False)
    actions = Column(JSON, nullable=False)
    
    # Rule metadata
    description = Column(Text)
    priority = Column(Integer, default=100)
    is_active = Column(Boolean, default=True)
    
    # Execution tracking
    execution_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    last_executed = Column(DateTime)
    
    # Audit
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    created_by_user = relationship("User")
    
    __table_args__ = (
        Index('idx_rule_type', 'rule_type'),
        Index('idx_rule_category', 'rule_category'),
        Index('idx_rule_active', 'is_active'),
        Index('idx_rule_priority', 'priority'),
    )
    
    def __repr__(self):
        return f"<ImportRule(id={self.id}, name='{self.rule_name}', type='{self.rule_type}')>"

class ShopifySync(Base):
    """Track Shopify synchronization operations."""
    __tablename__ = 'shopify_syncs'
    
    id = Column(Integer, primary_key=True)
    sync_uuid = Column(String(36), unique=True, nullable=False, index=True)
    
    # Sync configuration
    mode = Column(String(50), nullable=False)  # full_sync, new_only, update_only, ultra_fast, image_sync
    configuration = Column(JSON, nullable=False)
    filters = Column(JSON)
    
    # Related import batch
    import_batch_id = Column(Integer, ForeignKey('etilize_import_batches.id'))
    
    # Status tracking
    status = Column(String(20), default='queued', nullable=False)  # queued, running, completed, failed, cancelled
    stage = Column(String(50), default='initialization')
    progress = Column(Integer, default=0)
    
    # Timing
    created_at = Column(DateTime, default=func.now(), nullable=False)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    duration = Column(Integer)  # seconds
    
    # Statistics
    total_products = Column(Integer, default=0)
    successful_uploads = Column(Integer, default=0)
    failed_uploads = Column(Integer, default=0)
    skipped_uploads = Column(Integer, default=0)
    duplicates_cleaned = Column(Integer, default=0)
    retry_count = Column(Integer, default=0)
    
    # Error handling
    errors = Column(JSON)
    warnings = Column(JSON)
    
    # User tracking
    triggered_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # Relationships
    user = relationship("User")
    import_batch = relationship("EtilizeImportBatch")
    
    __table_args__ = (
        Index('idx_shopify_sync_status', 'status'),
        Index('idx_shopify_sync_mode', 'mode'),
        Index('idx_shopify_sync_created', 'created_at'),
        Index('idx_shopify_sync_batch', 'import_batch_id'),
        Index('idx_shopify_sync_user', 'triggered_by'),
    )
    
    def __repr__(self):
        return f"<ShopifySync(id={self.id}, mode='{self.mode}', status='{self.status}')>"

# Create indexes for performance
def create_performance_indexes(engine):
    """Create additional performance indexes."""
    from sqlalchemy import text
    
    # Create composite indexes for common queries
    indexes = [
        # Products by category and status
        "CREATE INDEX IF NOT EXISTS idx_products_category_status ON products(category_id, status)",
        
        # Products by brand and category
        "CREATE INDEX IF NOT EXISTS idx_products_brand_category ON products(brand, category_id)",
        
        # Jobs by user and status
        "CREATE INDEX IF NOT EXISTS idx_jobs_user_status ON jobs(user_id, status)",
        
        # Sync history by type and status
        "CREATE INDEX IF NOT EXISTS idx_sync_type_status ON sync_history(sync_type, status)",
        
        # Icons by category and status
        "CREATE INDEX IF NOT EXISTS idx_icons_category_status ON icons(category_id, status)",
        
        # System logs by level and date
        "CREATE INDEX IF NOT EXISTS idx_logs_level_date ON system_logs(level, created_at)",
        
        # Product metafields by namespace
        "CREATE INDEX IF NOT EXISTS idx_metafields_namespace ON product_metafields(namespace)",
        
        # Product metafields by product and namespace
        "CREATE INDEX IF NOT EXISTS idx_metafields_product_namespace ON product_metafields(product_id, namespace)",
    ]
    
    with engine.connect() as conn:
        for index_sql in indexes:
            conn.execute(text(index_sql))
        conn.commit()