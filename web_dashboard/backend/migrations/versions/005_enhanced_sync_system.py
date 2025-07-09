"""Enhanced sync system with staging, versioning, and Xorosoft integration

Revision ID: 005_enhanced_sync
Revises: 004_add_supabase_auth
Create Date: 2025-01-08 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '005_enhanced_sync'
down_revision = '004_add_supabase_auth'
branch_labels = None
depends_on = None


def upgrade():
    """Create enhanced sync system tables."""
    
    # Create products_staging table
    op.create_table('products_staging',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source_product_id', sa.Integer(), nullable=True),
        sa.Column('shopify_product_id', sa.String(50), nullable=True),
        sa.Column('sku', sa.String(100), nullable=True),
        sa.Column('name', sa.String(500), nullable=True),
        sa.Column('title', sa.String(500), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('short_description', sa.Text(), nullable=True),
        sa.Column('price', sa.Float(), nullable=True),
        sa.Column('compare_at_price', sa.Float(), nullable=True),
        sa.Column('cost_price', sa.Float(), nullable=True),
        sa.Column('brand', sa.String(200), nullable=True),
        sa.Column('manufacturer', sa.String(200), nullable=True),
        sa.Column('manufacturer_part_number', sa.String(200), nullable=True),
        sa.Column('upc', sa.String(20), nullable=True),
        sa.Column('weight', sa.Float(), nullable=True),
        sa.Column('weight_unit', sa.String(10), nullable=True),
        sa.Column('length', sa.Float(), nullable=True),
        sa.Column('width', sa.Float(), nullable=True),
        sa.Column('height', sa.Float(), nullable=True),
        sa.Column('dimension_unit', sa.String(10), nullable=True),
        sa.Column('inventory_quantity', sa.Integer(), nullable=True),
        sa.Column('track_inventory', sa.Boolean(), default=True),
        sa.Column('continue_selling_when_out_of_stock', sa.Boolean(), default=False),
        sa.Column('seo_title', sa.String(255), nullable=True),
        sa.Column('seo_description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(20), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('category_id', sa.Integer(), nullable=True),
        sa.Column('featured_image_url', sa.String(1000), nullable=True),
        sa.Column('additional_images', sa.JSON(), nullable=True),
        sa.Column('metafields', sa.JSON(), nullable=True),
        sa.Column('custom_attributes', sa.JSON(), nullable=True),
        sa.Column('change_type', sa.String(20), nullable=False),
        sa.Column('change_data', sa.JSON(), nullable=True),
        sa.Column('change_source', sa.String(50), nullable=True),
        sa.Column('staged_by', sa.Integer(), nullable=True),
        sa.Column('staged_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('sync_operation_id', sa.Integer(), nullable=True),
        sa.Column('has_conflicts', sa.Boolean(), default=False),
        sa.Column('conflict_fields', sa.JSON(), nullable=True),
        sa.Column('version', sa.Integer(), default=1),
        sa.Column('parent_version', sa.Integer(), nullable=True),
        sa.Column('processing_status', sa.String(20), default='pending'),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['source_product_id'], ['products.id']),
        sa.ForeignKeyConstraint(['category_id'], ['categories.id']),
        sa.ForeignKeyConstraint(['staged_by'], ['users.id']),
        sa.ForeignKeyConstraint(['sync_operation_id'], ['sync_operations.id'])
    )
    op.create_index('idx_staging_source_product', 'products_staging', ['source_product_id'])
    op.create_index('idx_staging_shopify_id', 'products_staging', ['shopify_product_id'])
    op.create_index('idx_staging_sku', 'products_staging', ['sku'])
    op.create_index('idx_staging_sync_op', 'products_staging', ['sync_operation_id'])
    op.create_index('idx_staging_status', 'products_staging', ['processing_status'])
    op.create_index('idx_staging_change_type', 'products_staging', ['change_type'])
    op.create_index('idx_staging_conflicts', 'products_staging', ['has_conflicts'])
    op.create_index('idx_staging_staged_at', 'products_staging', ['staged_at'])
    
    # Create sync_operations table
    op.create_table('sync_operations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('operation_uuid', sa.String(36), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('operation_type', sa.String(50), nullable=False),
        sa.Column('sync_direction', sa.String(20), nullable=False),
        sa.Column('sync_config', sa.JSON(), nullable=True),
        sa.Column('filters', sa.JSON(), nullable=True),
        sa.Column('options', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(20), default='pending', nullable=False),
        sa.Column('stage', sa.String(100), nullable=True),
        sa.Column('progress', sa.Integer(), default=0),
        sa.Column('scheduled_at', sa.DateTime(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('duration', sa.Integer(), nullable=True),
        sa.Column('total_items', sa.Integer(), default=0),
        sa.Column('items_processed', sa.Integer(), default=0),
        sa.Column('items_succeeded', sa.Integer(), default=0),
        sa.Column('items_failed', sa.Integer(), default=0),
        sa.Column('items_skipped', sa.Integer(), default=0),
        sa.Column('items_with_conflicts', sa.Integer(), default=0),
        sa.Column('products_created', sa.Integer(), default=0),
        sa.Column('products_updated', sa.Integer(), default=0),
        sa.Column('products_deleted', sa.Integer(), default=0),
        sa.Column('images_synced', sa.Integer(), default=0),
        sa.Column('error_count', sa.Integer(), default=0),
        sa.Column('warning_count', sa.Integer(), default=0),
        sa.Column('errors', sa.JSON(), nullable=True),
        sa.Column('warnings', sa.JSON(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('executed_by', sa.Integer(), nullable=True),
        sa.Column('system_triggered', sa.Boolean(), default=False),
        sa.Column('parent_operation_id', sa.Integer(), nullable=True),
        sa.Column('is_rollbackable', sa.Boolean(), default=True),
        sa.Column('rollback_operation_id', sa.Integer(), nullable=True),
        sa.Column('meta_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('operation_uuid'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.ForeignKeyConstraint(['executed_by'], ['users.id']),
        sa.ForeignKeyConstraint(['parent_operation_id'], ['sync_operations.id']),
        sa.ForeignKeyConstraint(['rollback_operation_id'], ['sync_operations.id'])
    )
    op.create_index('idx_sync_op_uuid', 'sync_operations', ['operation_uuid'])
    op.create_index('idx_sync_op_status', 'sync_operations', ['status'])
    op.create_index('idx_sync_op_type', 'sync_operations', ['operation_type'])
    op.create_index('idx_sync_op_direction', 'sync_operations', ['sync_direction'])
    op.create_index('idx_sync_op_created_by', 'sync_operations', ['created_by'])
    op.create_index('idx_sync_op_scheduled', 'sync_operations', ['scheduled_at'])
    op.create_index('idx_sync_op_created', 'sync_operations', ['created_at'])
    op.create_index('idx_sync_op_parent', 'sync_operations', ['parent_operation_id'])
    
    # Create sync_conflicts table
    op.create_table('sync_conflicts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('conflict_uuid', sa.String(36), nullable=False),
        sa.Column('sync_operation_id', sa.Integer(), nullable=False),
        sa.Column('staging_product_id', sa.Integer(), nullable=True),
        sa.Column('product_id', sa.Integer(), nullable=True),
        sa.Column('conflict_type', sa.String(50), nullable=False),
        sa.Column('field_name', sa.String(100), nullable=True),
        sa.Column('local_value', sa.Text(), nullable=True),
        sa.Column('remote_value', sa.Text(), nullable=True),
        sa.Column('suggested_value', sa.Text(), nullable=True),
        sa.Column('local_version', sa.Integer(), nullable=True),
        sa.Column('remote_version', sa.Integer(), nullable=True),
        sa.Column('local_updated_at', sa.DateTime(), nullable=True),
        sa.Column('remote_updated_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(20), default='unresolved', nullable=False),
        sa.Column('resolution_strategy', sa.String(50), nullable=True),
        sa.Column('resolved_value', sa.Text(), nullable=True),
        sa.Column('resolved_by', sa.Integer(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('auto_resolvable', sa.Boolean(), default=False),
        sa.Column('auto_resolution_confidence', sa.Float(), nullable=True),
        sa.Column('auto_resolution_reason', sa.String(255), nullable=True),
        sa.Column('severity', sa.String(20), default='medium'),
        sa.Column('affected_systems', sa.JSON(), nullable=True),
        sa.Column('meta_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('conflict_uuid'),
        sa.ForeignKeyConstraint(['sync_operation_id'], ['sync_operations.id']),
        sa.ForeignKeyConstraint(['staging_product_id'], ['products_staging.id']),
        sa.ForeignKeyConstraint(['product_id'], ['products.id']),
        sa.ForeignKeyConstraint(['resolved_by'], ['users.id'])
    )
    op.create_index('idx_conflict_uuid', 'sync_conflicts', ['conflict_uuid'])
    op.create_index('idx_conflict_sync_op', 'sync_conflicts', ['sync_operation_id'])
    op.create_index('idx_conflict_product', 'sync_conflicts', ['product_id'])
    op.create_index('idx_conflict_status', 'sync_conflicts', ['status'])
    op.create_index('idx_conflict_type', 'sync_conflicts', ['conflict_type'])
    op.create_index('idx_conflict_severity', 'sync_conflicts', ['severity'])
    op.create_index('idx_conflict_field', 'sync_conflicts', ['field_name'])
    op.create_index('idx_conflict_created', 'sync_conflicts', ['created_at'])
    
    # Create product_versions table
    op.create_table('product_versions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('product_data', sa.JSON(), nullable=False),
        sa.Column('change_type', sa.String(20), nullable=False),
        sa.Column('changed_fields', sa.JSON(), nullable=True),
        sa.Column('change_summary', sa.Text(), nullable=True),
        sa.Column('change_source', sa.String(50), nullable=True),
        sa.Column('source_reference', sa.String(255), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('system_generated', sa.Boolean(), default=False),
        sa.Column('sync_operation_id', sa.Integer(), nullable=True),
        sa.Column('shopify_version_id', sa.String(50), nullable=True),
        sa.Column('meta_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('product_id', 'version_number', name='uq_product_version'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.ForeignKeyConstraint(['sync_operation_id'], ['sync_operations.id'])
    )
    op.create_index('idx_version_product', 'product_versions', ['product_id'])
    op.create_index('idx_version_number', 'product_versions', ['version_number'])
    op.create_index('idx_version_change_type', 'product_versions', ['change_type'])
    op.create_index('idx_version_source', 'product_versions', ['change_source'])
    op.create_index('idx_version_created', 'product_versions', ['created_at'])
    op.create_index('idx_version_sync_op', 'product_versions', ['sync_operation_id'])
    
    # Create category_versions table
    op.create_table('category_versions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('category_id', sa.Integer(), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('category_data', sa.JSON(), nullable=False),
        sa.Column('change_type', sa.String(20), nullable=False),
        sa.Column('changed_fields', sa.JSON(), nullable=True),
        sa.Column('change_summary', sa.Text(), nullable=True),
        sa.Column('change_source', sa.String(50), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('category_id', 'version_number', name='uq_category_version'),
        sa.ForeignKeyConstraint(['category_id'], ['categories.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'])
    )
    op.create_index('idx_cat_version_category', 'category_versions', ['category_id'])
    op.create_index('idx_cat_version_number', 'category_versions', ['version_number'])
    op.create_index('idx_cat_version_created', 'category_versions', ['created_at'])
    
    # Create xorosoft_products table
    op.create_table('xorosoft_products',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('xorosoft_id', sa.String(100), nullable=False),
        sa.Column('xorosoft_sku', sa.String(100), nullable=True),
        sa.Column('product_id', sa.Integer(), nullable=True),
        sa.Column('sku_mapping', sa.String(100), nullable=True),
        sa.Column('stock_on_hand', sa.Integer(), default=0),
        sa.Column('stock_available', sa.Integer(), default=0),
        sa.Column('stock_allocated', sa.Integer(), default=0),
        sa.Column('stock_on_order', sa.Integer(), default=0),
        sa.Column('warehouse_code', sa.String(50), nullable=True),
        sa.Column('bin_location', sa.String(100), nullable=True),
        sa.Column('cost_price', sa.Float(), nullable=True),
        sa.Column('wholesale_price', sa.Float(), nullable=True),
        sa.Column('retail_price', sa.Float(), nullable=True),
        sa.Column('product_name', sa.String(500), nullable=True),
        sa.Column('product_description', sa.Text(), nullable=True),
        sa.Column('barcode', sa.String(50), nullable=True),
        sa.Column('supplier_code', sa.String(50), nullable=True),
        sa.Column('supplier_name', sa.String(200), nullable=True),
        sa.Column('supplier_sku', sa.String(100), nullable=True),
        sa.Column('last_synced', sa.DateTime(), nullable=True),
        sa.Column('sync_status', sa.String(20), default='pending'),
        sa.Column('sync_errors', sa.JSON(), nullable=True),
        sa.Column('stock_updated_at', sa.DateTime(), nullable=True),
        sa.Column('price_updated_at', sa.DateTime(), nullable=True),
        sa.Column('data_hash', sa.String(64), nullable=True),
        sa.Column('raw_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('xorosoft_id'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'])
    )
    op.create_index('idx_xoro_product', 'xorosoft_products', ['product_id'])
    op.create_index('idx_xoro_sku', 'xorosoft_products', ['xorosoft_sku'])
    op.create_index('idx_xoro_sku_mapping', 'xorosoft_products', ['sku_mapping'])
    op.create_index('idx_xoro_sync_status', 'xorosoft_products', ['sync_status'])
    op.create_index('idx_xoro_warehouse', 'xorosoft_products', ['warehouse_code'])
    op.create_index('idx_xoro_supplier', 'xorosoft_products', ['supplier_code'])
    op.create_index('idx_xoro_updated', 'xorosoft_products', ['updated_at'])
    
    # Create xorosoft_sync_logs table
    op.create_table('xorosoft_sync_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('sync_type', sa.String(50), nullable=False),
        sa.Column('sync_direction', sa.String(20), default='down'),
        sa.Column('started_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('duration', sa.Integer(), nullable=True),
        sa.Column('total_records', sa.Integer(), default=0),
        sa.Column('records_processed', sa.Integer(), default=0),
        sa.Column('records_updated', sa.Integer(), default=0),
        sa.Column('records_failed', sa.Integer(), default=0),
        sa.Column('stock_updates', sa.Integer(), default=0),
        sa.Column('price_updates', sa.Integer(), default=0),
        sa.Column('new_products', sa.Integer(), default=0),
        sa.Column('status', sa.String(20), default='pending'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('errors', sa.JSON(), nullable=True),
        sa.Column('import_file', sa.String(1000), nullable=True),
        sa.Column('export_file', sa.String(1000), nullable=True),
        sa.Column('triggered_by', sa.Integer(), nullable=True),
        sa.Column('meta_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['triggered_by'], ['users.id'])
    )
    op.create_index('idx_xoro_log_type', 'xorosoft_sync_logs', ['sync_type'])
    op.create_index('idx_xoro_log_status', 'xorosoft_sync_logs', ['status'])
    op.create_index('idx_xoro_log_started', 'xorosoft_sync_logs', ['started_at'])
    op.create_index('idx_xoro_log_user', 'xorosoft_sync_logs', ['triggered_by'])
    
    # Create sync_rollbacks table
    op.create_table('sync_rollbacks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('rollback_uuid', sa.String(36), nullable=False),
        sa.Column('original_operation_id', sa.Integer(), nullable=False),
        sa.Column('rollback_operation_id', sa.Integer(), nullable=True),
        sa.Column('rollback_type', sa.String(50), nullable=False),
        sa.Column('rollback_scope', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(20), default='pending', nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('total_items', sa.Integer(), default=0),
        sa.Column('items_rolled_back', sa.Integer(), default=0),
        sa.Column('items_failed', sa.Integer(), default=0),
        sa.Column('backup_data', sa.JSON(), nullable=True),
        sa.Column('initiated_by', sa.Integer(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('rollback_uuid'),
        sa.ForeignKeyConstraint(['original_operation_id'], ['sync_operations.id']),
        sa.ForeignKeyConstraint(['rollback_operation_id'], ['sync_operations.id']),
        sa.ForeignKeyConstraint(['initiated_by'], ['users.id'])
    )
    op.create_index('idx_rollback_uuid', 'sync_rollbacks', ['rollback_uuid'])
    op.create_index('idx_rollback_original', 'sync_rollbacks', ['original_operation_id'])
    op.create_index('idx_rollback_status', 'sync_rollbacks', ['status'])
    op.create_index('idx_rollback_user', 'sync_rollbacks', ['initiated_by'])
    op.create_index('idx_rollback_created', 'sync_rollbacks', ['created_at'])
    
    # Create sync_performance_logs table
    op.create_table('sync_performance_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('sync_operation_id', sa.Integer(), nullable=False),
        sa.Column('total_duration', sa.Integer(), nullable=True),
        sa.Column('api_calls_count', sa.Integer(), default=0),
        sa.Column('api_calls_duration', sa.Integer(), nullable=True),
        sa.Column('db_queries_count', sa.Integer(), default=0),
        sa.Column('db_queries_duration', sa.Integer(), nullable=True),
        sa.Column('db_writes_count', sa.Integer(), default=0),
        sa.Column('peak_memory_mb', sa.Float(), nullable=True),
        sa.Column('avg_cpu_percent', sa.Float(), nullable=True),
        sa.Column('items_per_second', sa.Float(), nullable=True),
        sa.Column('api_calls_per_minute', sa.Float(), nullable=True),
        sa.Column('shopify_rate_limit_hits', sa.Integer(), default=0),
        sa.Column('shopify_throttle_duration', sa.Integer(), nullable=True),
        sa.Column('bottleneck_stage', sa.String(100), nullable=True),
        sa.Column('bottleneck_duration', sa.Integer(), nullable=True),
        sa.Column('performance_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['sync_operation_id'], ['sync_operations.id'])
    )
    op.create_index('idx_perf_sync_op', 'sync_performance_logs', ['sync_operation_id'])
    op.create_index('idx_perf_duration', 'sync_performance_logs', ['total_duration'])
    op.create_index('idx_perf_throughput', 'sync_performance_logs', ['items_per_second'])
    op.create_index('idx_perf_created', 'sync_performance_logs', ['created_at'])
    
    # Add version fields to existing products table
    op.add_column('products', sa.Column('version', sa.Integer(), default=1))
    op.add_column('products', sa.Column('last_sync_version', sa.Integer(), nullable=True))
    op.add_column('products', sa.Column('sync_locked', sa.Boolean(), default=False))
    op.add_column('products', sa.Column('sync_locked_by', sa.Integer(), nullable=True))
    op.add_column('products', sa.Column('sync_locked_at', sa.DateTime(), nullable=True))
    
    # Add Xorosoft reference to products
    op.add_column('products', sa.Column('xorosoft_id', sa.String(100), nullable=True))
    op.add_column('products', sa.Column('xorosoft_sku', sa.String(100), nullable=True))
    op.add_column('products', sa.Column('stock_synced_at', sa.DateTime(), nullable=True))
    
    # Create indexes for new columns
    op.create_index('idx_product_version', 'products', ['version'])
    op.create_index('idx_product_sync_locked', 'products', ['sync_locked'])
    op.create_index('idx_product_xorosoft_id', 'products', ['xorosoft_id'])
    op.create_index('idx_product_xorosoft_sku', 'products', ['xorosoft_sku'])


def downgrade():
    """Drop enhanced sync system tables."""
    
    # Drop indexes on products table
    op.drop_index('idx_product_xorosoft_sku', 'products')
    op.drop_index('idx_product_xorosoft_id', 'products')
    op.drop_index('idx_product_sync_locked', 'products')
    op.drop_index('idx_product_version', 'products')
    
    # Remove columns from products table
    op.drop_column('products', 'stock_synced_at')
    op.drop_column('products', 'xorosoft_sku')
    op.drop_column('products', 'xorosoft_id')
    op.drop_column('products', 'sync_locked_at')
    op.drop_column('products', 'sync_locked_by')
    op.drop_column('products', 'sync_locked')
    op.drop_column('products', 'last_sync_version')
    op.drop_column('products', 'version')
    
    # Drop all new tables
    op.drop_table('sync_performance_logs')
    op.drop_table('sync_rollbacks')
    op.drop_table('xorosoft_sync_logs')
    op.drop_table('xorosoft_products')
    op.drop_table('category_versions')
    op.drop_table('product_versions')
    op.drop_table('sync_conflicts')
    op.drop_table('sync_operations')
    op.drop_table('products_staging')