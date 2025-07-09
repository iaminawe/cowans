"""
Database models for icon batch processing.
"""

from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, JSON, ForeignKey, Text, Boolean, Index
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid

from models import db

class IconBatch(db.Model):
    """Batch job for generating multiple icons."""
    __tablename__ = 'icon_batches'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=False)
    status = Column(String(50), nullable=False, default='pending')  # pending, processing, completed, completed_with_errors, failed, cancelled
    total_items = Column(Integer, nullable=False)
    completed_items = Column(Integer, default=0)
    failed_items = Column(Integer, default=0)
    config = Column(JSON)  # Batch configuration (style, colors, etc.)
    error = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    
    # Relationships
    items = relationship('IconBatchItem', back_populates='batch', cascade='all, delete-orphan')
    
    # Indexes
    __table_args__ = (
        Index('idx_icon_batches_user_status', 'user_id', 'status'),
        Index('idx_icon_batches_created', 'created_at'),
    )

class IconBatchItem(db.Model):
    """Individual item in an icon batch."""
    __tablename__ = 'icon_batch_items'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    batch_id = Column(String(36), ForeignKey('icon_batches.id'), nullable=False)
    category_id = Column(String(100))
    category_name = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, default='pending')  # pending, processing, completed, failed
    position = Column(Integer, nullable=False)  # Order in batch
    result = Column(JSON)  # Result data (file_path, url, etc.)
    error = Column(Text)
    metadata = Column(JSON)  # Additional metadata
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    
    # Relationships
    batch = relationship('IconBatch', back_populates='items')
    
    # Indexes
    __table_args__ = (
        Index('idx_batch_items_batch_status', 'batch_id', 'status'),
        Index('idx_batch_items_position', 'batch_id', 'position'),
    )

class IconGeneration(db.Model):
    """Record of individual icon generations."""
    __tablename__ = 'icon_generations'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    batch_item_id = Column(String(36), ForeignKey('icon_batch_items.id'))
    user_id = Column(String(36), nullable=False)
    category_id = Column(String(100))
    category_name = Column(String(255), nullable=False)
    file_path = Column(String(500))
    thumbnail_path = Column(String(500))
    image_url = Column(String(500))
    thumbnail_url = Column(String(500))
    style = Column(String(50))
    size = Column(Integer)
    format = Column(String(10))
    color_scheme = Column(String(50))
    generation_time = Column(Integer)  # Time in milliseconds
    model = Column(String(50))  # AI model used
    prompt = Column(Text)  # Prompt used for generation
    metadata = Column(JSON)
    is_synced_to_shopify = Column(Boolean, default=False)
    shopify_image_id = Column(String(100))
    shopify_collection_id = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    batch_item = relationship('IconBatchItem')
    
    # Indexes
    __table_args__ = (
        Index('idx_icon_generations_user', 'user_id'),
        Index('idx_icon_generations_category', 'category_id'),
        Index('idx_icon_generations_synced', 'is_synced_to_shopify'),
        Index('idx_icon_generations_created', 'created_at'),
    )