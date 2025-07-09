"""Add Etilize integration support

Revision ID: 002_etilize_integration
Revises: 001_initial_schema
Create Date: 2025-07-03 15:37:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision = '002_etilize_integration'
down_revision = '001'
branch_labels = None
depends_on = None

def upgrade():
    """Upgrade database schema for Etilize integration."""
    
    # Create EtilizeImportBatch table
    op.create_table('etilize_import_batches',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('batch_uuid', sa.String(36), nullable=False),
        sa.Column('import_type', sa.String(50), nullable=False),
        sa.Column('source_file_path', sa.String(1000), nullable=False),
        sa.Column('source_file_hash', sa.String(64), nullable=False),
        sa.Column('source_file_size', sa.Integer(), nullable=False),
        sa.Column('source_file_modified', sa.DateTime(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, default='pending'),
        sa.Column('stage', sa.String(50), default='initialization'),
        sa.Column('progress', sa.Integer(), default=0),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime()),
        sa.Column('duration', sa.Integer()),
        sa.Column('total_records', sa.Integer(), default=0),
        sa.Column('records_processed', sa.Integer(), default=0),
        sa.Column('records_imported', sa.Integer(), default=0),
        sa.Column('records_updated', sa.Integer(), default=0),
        sa.Column('records_failed', sa.Integer(), default=0),
        sa.Column('records_skipped', sa.Integer(), default=0),
        sa.Column('error_count', sa.Integer(), default=0),
        sa.Column('warning_count', sa.Integer(), default=0),
        sa.Column('error_details', sa.JSON()),
        sa.Column('triggered_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('job_id', sa.Integer(), sa.ForeignKey('jobs.id')),
        sa.Column('import_config', sa.JSON()),
        sa.Column('meta_data', sa.JSON()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('batch_uuid')
    )
    
    # Create indexes for etilize_import_batches
    op.create_index('idx_etilize_batch_status', 'etilize_import_batches', ['status'])
    op.create_index('idx_etilize_batch_type', 'etilize_import_batches', ['import_type'])
    op.create_index('idx_etilize_batch_started', 'etilize_import_batches', ['started_at'])
    op.create_index('idx_etilize_batch_user', 'etilize_import_batches', ['triggered_by'])
    op.create_index('idx_etilize_batch_uuid', 'etilize_import_batches', ['batch_uuid'])
    
    # Create EtilizeStagingProduct table
    op.create_table('etilize_staging_products',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('batch_id', sa.Integer(), sa.ForeignKey('etilize_import_batches.id'), nullable=False),
        sa.Column('etilize_id', sa.String(100)),
        sa.Column('raw_data', sa.JSON(), nullable=False),
        sa.Column('title', sa.String(1000)),
        sa.Column('sku', sa.String(200)),
        sa.Column('manufacturer_part_number', sa.String(200)),
        sa.Column('brand', sa.String(200)),
        sa.Column('manufacturer', sa.String(200)),
        sa.Column('description', sa.Text()),
        sa.Column('price', sa.Float()),
        sa.Column('processing_status', sa.String(20), default='pending'),
        sa.Column('validation_status', sa.String(20), default='pending'),
        sa.Column('mapping_status', sa.String(20), default='pending'),
        sa.Column('validation_errors', sa.JSON()),
        sa.Column('validation_warnings', sa.JSON()),
        sa.Column('mapped_product_id', sa.Integer(), sa.ForeignKey('products.id')),
        sa.Column('mapping_confidence', sa.Float(), default=0.0),
        sa.Column('mapping_method', sa.String(50)),
        sa.Column('mapping_details', sa.JSON()),
        sa.Column('processed_at', sa.DateTime()),
        sa.Column('error_message', sa.Text()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for etilize_staging_products
    op.create_index('idx_staging_batch', 'etilize_staging_products', ['batch_id'])
    op.create_index('idx_staging_sku', 'etilize_staging_products', ['sku'])
    op.create_index('idx_staging_mpn', 'etilize_staging_products', ['manufacturer_part_number'])
    op.create_index('idx_staging_processing', 'etilize_staging_products', ['processing_status'])
    op.create_index('idx_staging_validation', 'etilize_staging_products', ['validation_status'])
    op.create_index('idx_staging_mapping', 'etilize_staging_products', ['mapping_status'])
    op.create_index('idx_staging_etilize_id', 'etilize_staging_products', ['etilize_id'])
    
    # Create ProductSource table
    op.create_table('product_sources',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), sa.ForeignKey('products.id'), nullable=False),
        sa.Column('source_type', sa.String(50), nullable=False),
        sa.Column('source_priority', sa.Integer(), default=100),
        sa.Column('source_identifier', sa.String(200)),
        sa.Column('source_url', sa.String(1000)),
        sa.Column('source_data', sa.JSON()),
        sa.Column('last_updated', sa.DateTime(), nullable=False),
        sa.Column('sync_status', sa.String(20), default='pending'),
        sa.Column('last_synced', sa.DateTime()),
        sa.Column('sync_errors', sa.JSON()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('product_id', 'source_type', 'source_identifier', name='uq_product_source')
    )
    
    # Create indexes for product_sources
    op.create_index('idx_source_product', 'product_sources', ['product_id'])
    op.create_index('idx_source_type', 'product_sources', ['source_type'])
    op.create_index('idx_source_priority', 'product_sources', ['source_priority'])
    op.create_index('idx_source_updated', 'product_sources', ['last_updated'])
    
    # Create ProductChangeLog table
    op.create_table('product_change_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), sa.ForeignKey('products.id'), nullable=False),
        sa.Column('change_type', sa.String(50), nullable=False),
        sa.Column('field_name', sa.String(100)),
        sa.Column('old_value', sa.Text()),
        sa.Column('new_value', sa.Text()),
        sa.Column('value_type', sa.String(20), default='string'),
        sa.Column('source_type', sa.String(50), nullable=False),
        sa.Column('source_id', sa.String(100)),
        sa.Column('triggered_by', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('batch_id', sa.Integer(), sa.ForeignKey('etilize_import_batches.id')),
        sa.Column('job_id', sa.Integer(), sa.ForeignKey('jobs.id')),
        sa.Column('change_reason', sa.String(200)),
        sa.Column('confidence_score', sa.Float()),
        sa.Column('meta_data', sa.JSON()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for product_change_logs
    op.create_index('idx_change_product', 'product_change_logs', ['product_id'])
    op.create_index('idx_change_type', 'product_change_logs', ['change_type'])
    op.create_index('idx_change_field', 'product_change_logs', ['field_name'])
    op.create_index('idx_change_source', 'product_change_logs', ['source_type'])
    op.create_index('idx_change_created', 'product_change_logs', ['created_at'])
    op.create_index('idx_change_batch', 'product_change_logs', ['batch_id'])
    
    # Create SyncQueue table
    op.create_table('sync_queue',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('queue_uuid', sa.String(36), nullable=False),
        sa.Column('item_type', sa.String(50), nullable=False),
        sa.Column('item_id', sa.Integer(), nullable=False),
        sa.Column('target_system', sa.String(50), nullable=False),
        sa.Column('operation_type', sa.String(50), nullable=False),
        sa.Column('operation_data', sa.JSON()),
        sa.Column('priority', sa.Integer(), default=100),
        sa.Column('scheduled_at', sa.DateTime(), nullable=False),
        sa.Column('status', sa.String(20), default='pending'),
        sa.Column('attempts', sa.Integer(), default=0),
        sa.Column('max_attempts', sa.Integer(), default=3),
        sa.Column('started_at', sa.DateTime()),
        sa.Column('completed_at', sa.DateTime()),
        sa.Column('duration', sa.Integer()),
        sa.Column('last_error', sa.Text()),
        sa.Column('error_details', sa.JSON()),
        sa.Column('depends_on', sa.JSON()),
        sa.Column('blocks', sa.JSON()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('queue_uuid')
    )
    
    # Create indexes for sync_queue
    op.create_index('idx_queue_status', 'sync_queue', ['status'])
    op.create_index('idx_queue_type', 'sync_queue', ['item_type'])
    op.create_index('idx_queue_target', 'sync_queue', ['target_system'])
    op.create_index('idx_queue_priority', 'sync_queue', ['priority'])
    op.create_index('idx_queue_scheduled', 'sync_queue', ['scheduled_at'])
    op.create_index('idx_queue_item', 'sync_queue', ['item_type', 'item_id'])
    op.create_index('idx_queue_uuid', 'sync_queue', ['queue_uuid'])
    
    # Create ImportRule table
    op.create_table('import_rules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('rule_name', sa.String(200), nullable=False),
        sa.Column('rule_type', sa.String(50), nullable=False),
        sa.Column('rule_category', sa.String(100)),
        sa.Column('conditions', sa.JSON(), nullable=False),
        sa.Column('actions', sa.JSON(), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('priority', sa.Integer(), default=100),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('execution_count', sa.Integer(), default=0),
        sa.Column('success_count', sa.Integer(), default=0),
        sa.Column('failure_count', sa.Integer(), default=0),
        sa.Column('last_executed', sa.DateTime()),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for import_rules
    op.create_index('idx_rule_type', 'import_rules', ['rule_type'])
    op.create_index('idx_rule_category', 'import_rules', ['rule_category'])
    op.create_index('idx_rule_active', 'import_rules', ['is_active'])
    op.create_index('idx_rule_priority', 'import_rules', ['priority'])
    
    # Add new columns to existing products table
    op.add_column('products', sa.Column('etilize_id', sa.String(100)))
    op.add_column('products', sa.Column('primary_source', sa.String(50), default='manual'))
    op.add_column('products', sa.Column('source_priority', sa.Integer(), default=100))
    op.add_column('products', sa.Column('data_sources', sa.JSON()))
    op.add_column('products', sa.Column('import_batch_id', sa.Integer(), sa.ForeignKey('etilize_import_batches.id')))
    op.add_column('products', sa.Column('last_imported', sa.DateTime()))
    op.add_column('products', sa.Column('import_errors', sa.JSON()))
    op.add_column('products', sa.Column('has_conflicts', sa.Boolean(), default=False))
    op.add_column('products', sa.Column('conflict_resolution', sa.JSON()))
    op.add_column('products', sa.Column('manual_overrides', sa.JSON()))
    op.add_column('products', sa.Column('etilize_data', sa.JSON()))
    op.add_column('products', sa.Column('computed_fields', sa.JSON()))
    op.add_column('products', sa.Column('data_quality_score', sa.Float(), default=0.0))
    op.add_column('products', sa.Column('completeness_score', sa.Float(), default=0.0))
    
    # Create additional indexes for products
    op.create_index('idx_product_etilize', 'products', ['etilize_id'])
    op.create_index('idx_product_source', 'products', ['primary_source'])
    op.create_index('idx_product_import_batch', 'products', ['import_batch_id'])
    op.create_index('idx_product_conflicts', 'products', ['has_conflicts'])
    op.create_index('idx_product_quality', 'products', ['data_quality_score'])

def downgrade():
    """Downgrade database schema - remove Etilize integration."""
    
    # Remove added columns from products table
    op.drop_column('products', 'completeness_score')
    op.drop_column('products', 'data_quality_score')
    op.drop_column('products', 'computed_fields')
    op.drop_column('products', 'etilize_data')
    op.drop_column('products', 'manual_overrides')
    op.drop_column('products', 'conflict_resolution')
    op.drop_column('products', 'has_conflicts')
    op.drop_column('products', 'import_errors')
    op.drop_column('products', 'last_imported')
    op.drop_column('products', 'import_batch_id')
    op.drop_column('products', 'data_sources')
    op.drop_column('products', 'source_priority')
    op.drop_column('products', 'primary_source')
    op.drop_column('products', 'etilize_id')
    
    # Drop tables in reverse order (to handle foreign key constraints)
    op.drop_table('import_rules')
    op.drop_table('sync_queue')
    op.drop_table('product_change_logs')
    op.drop_table('product_sources')
    op.drop_table('etilize_staging_products')
    op.drop_table('etilize_import_batches')