"""Initial schema baseline

Revision ID: 001
Revises: 
Create Date: 2025-01-03

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Mark the current schema as the baseline.
    This migration assumes all tables are already created.
    """
    # Create alembic_version table if it doesn't exist
    conn = op.get_bind()
    
    # Check if tables exist
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()
    
    expected_tables = [
        'users', 'categories', 'products', 'icons', 'jobs', 
        'sync_history', 'product_images', 'system_logs', 'configurations'
    ]
    
    # If tables don't exist, create them
    if not all(table in existing_tables for table in expected_tables):
        # Create all tables
        create_tables()
    else:
        # Tables already exist, just mark as baseline
        print("Tables already exist. Marking as baseline migration.")


def downgrade() -> None:
    """
    This is the initial migration, so downgrade would drop all tables.
    """
    # Drop all tables in reverse order to respect foreign keys
    op.drop_table('system_logs')
    op.drop_table('product_images')
    op.drop_table('sync_history')
    op.drop_table('jobs')
    op.drop_table('icons')
    op.drop_table('products')
    op.drop_table('categories')
    op.drop_table('configurations')
    op.drop_table('users')


def create_tables():
    """Create all tables if they don't exist."""
    # Users table
    op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('first_name', sa.String(length=100), nullable=True),
        sa.Column('last_name', sa.String(length=100), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('is_admin', sa.Boolean(), nullable=False, default=False),
        sa.Column('last_login', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # Categories table
    op.create_table('categories',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.Column('level', sa.Integer(), nullable=False, default=0),
        sa.Column('path', sa.String(length=500), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=True, default=0),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('shopify_collection_id', sa.String(length=50), nullable=True),
        sa.Column('shopify_handle', sa.String(length=255), nullable=True),
        sa.Column('shopify_synced_at', sa.DateTime(), nullable=True),
        sa.Column('meta_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['parent_id'], ['categories.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug')
    )
    op.create_index('idx_category_parent_level', 'categories', ['parent_id', 'level'], unique=False)
    op.create_index('idx_category_path', 'categories', ['path'], unique=False)
    op.create_index('idx_category_shopify', 'categories', ['shopify_collection_id'], unique=False)
    op.create_index(op.f('ix_categories_parent_id'), 'categories', ['parent_id'], unique=False)
    op.create_index(op.f('ix_categories_shopify_collection_id'), 'categories', ['shopify_collection_id'], unique=False)
    op.create_index(op.f('ix_categories_slug'), 'categories', ['slug'], unique=True)

    # Products table
    op.create_table('products',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('sku', sa.String(length=100), nullable=False),
        sa.Column('name', sa.String(length=500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('short_description', sa.Text(), nullable=True),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('compare_at_price', sa.Float(), nullable=True),
        sa.Column('cost_price', sa.Float(), nullable=True),
        sa.Column('brand', sa.String(length=200), nullable=True),
        sa.Column('manufacturer', sa.String(length=200), nullable=True),
        sa.Column('manufacturer_part_number', sa.String(length=200), nullable=True),
        sa.Column('upc', sa.String(length=20), nullable=True),
        sa.Column('weight', sa.Float(), nullable=True),
        sa.Column('weight_unit', sa.String(length=10), nullable=True, default='kg'),
        sa.Column('length', sa.Float(), nullable=True),
        sa.Column('width', sa.Float(), nullable=True),
        sa.Column('height', sa.Float(), nullable=True),
        sa.Column('dimension_unit', sa.String(length=10), nullable=True, default='cm'),
        sa.Column('inventory_quantity', sa.Integer(), nullable=True, default=0),
        sa.Column('track_inventory', sa.Boolean(), nullable=True, default=True),
        sa.Column('continue_selling_when_out_of_stock', sa.Boolean(), nullable=True, default=False),
        sa.Column('seo_title', sa.String(length=255), nullable=True),
        sa.Column('seo_description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, default='draft'),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('category_id', sa.Integer(), nullable=False),
        sa.Column('shopify_product_id', sa.String(length=50), nullable=True),
        sa.Column('shopify_variant_id', sa.String(length=50), nullable=True),
        sa.Column('shopify_handle', sa.String(length=255), nullable=True),
        sa.Column('shopify_synced_at', sa.DateTime(), nullable=True),
        sa.Column('shopify_sync_status', sa.String(length=20), nullable=True, default='pending'),
        sa.Column('featured_image_url', sa.String(length=1000), nullable=True),
        sa.Column('additional_images', sa.JSON(), nullable=True),
        sa.Column('metafields', sa.JSON(), nullable=True),
        sa.Column('custom_attributes', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('sku')
    )
    op.create_index('idx_product_brand', 'products', ['brand'], unique=False)
    op.create_index('idx_product_category', 'products', ['category_id'], unique=False)
    op.create_index('idx_product_mpn', 'products', ['manufacturer_part_number'], unique=False)
    op.create_index('idx_product_shopify', 'products', ['shopify_product_id'], unique=False)
    op.create_index('idx_product_sku', 'products', ['sku'], unique=False)
    op.create_index('idx_product_status', 'products', ['status'], unique=False)
    op.create_index(op.f('ix_products_category_id'), 'products', ['category_id'], unique=False)
    op.create_index(op.f('ix_products_manufacturer_part_number'), 'products', ['manufacturer_part_number'], unique=False)
    op.create_index(op.f('ix_products_shopify_product_id'), 'products', ['shopify_product_id'], unique=False)
    op.create_index(op.f('ix_products_sku'), 'products', ['sku'], unique=True)

    # Icons table
    op.create_table('icons',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('category_id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('file_path', sa.String(length=1000), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('file_hash', sa.String(length=64), nullable=True),
        sa.Column('width', sa.Integer(), nullable=True),
        sa.Column('height', sa.Integer(), nullable=True),
        sa.Column('format', sa.String(length=10), nullable=True),
        sa.Column('prompt', sa.Text(), nullable=True),
        sa.Column('style', sa.String(length=50), nullable=True),
        sa.Column('color', sa.String(length=20), nullable=True),
        sa.Column('background', sa.String(length=20), nullable=True),
        sa.Column('model', sa.String(length=50), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, default='generating'),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('shopify_image_id', sa.String(length=50), nullable=True),
        sa.Column('shopify_image_url', sa.String(length=1000), nullable=True),
        sa.Column('shopify_synced_at', sa.DateTime(), nullable=True),
        sa.Column('shopify_sync_status', sa.String(length=20), nullable=True, default='pending'),
        sa.Column('generation_time', sa.Float(), nullable=True),
        sa.Column('generation_cost', sa.Float(), nullable=True),
        sa.Column('generation_batch_id', sa.String(length=50), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('meta_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_icon_batch', 'icons', ['generation_batch_id'], unique=False)
    op.create_index('idx_icon_category', 'icons', ['category_id'], unique=False)
    op.create_index('idx_icon_hash', 'icons', ['file_hash'], unique=False)
    op.create_index('idx_icon_shopify', 'icons', ['shopify_image_id'], unique=False)
    op.create_index('idx_icon_status', 'icons', ['status'], unique=False)
    op.create_index(op.f('ix_icons_category_id'), 'icons', ['category_id'], unique=False)
    op.create_index(op.f('ix_icons_created_by'), 'icons', ['created_by'], unique=False)

    # Jobs table
    op.create_table('jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('job_uuid', sa.String(length=36), nullable=False),
        sa.Column('script_name', sa.String(length=200), nullable=False),
        sa.Column('display_name', sa.String(length=255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, default='pending'),
        sa.Column('progress', sa.Integer(), nullable=True, default=0),
        sa.Column('current_stage', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('estimated_duration', sa.Integer(), nullable=True),
        sa.Column('actual_duration', sa.Integer(), nullable=True),
        sa.Column('parameters', sa.JSON(), nullable=True),
        sa.Column('options', sa.JSON(), nullable=True),
        sa.Column('result', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('output_log', sa.Text(), nullable=True),
        sa.Column('log_file_path', sa.String(length=1000), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=True, default=0),
        sa.Column('retry_count', sa.Integer(), nullable=True, default=0),
        sa.Column('max_retries', sa.Integer(), nullable=True, default=3),
        sa.Column('meta_data', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('job_uuid')
    )
    op.create_index('idx_job_created', 'jobs', ['created_at'], unique=False)
    op.create_index('idx_job_script', 'jobs', ['script_name'], unique=False)
    op.create_index('idx_job_status', 'jobs', ['status'], unique=False)
    op.create_index('idx_job_user', 'jobs', ['user_id'], unique=False)
    op.create_index('idx_job_uuid', 'jobs', ['job_uuid'], unique=False)
    op.create_index(op.f('ix_jobs_job_uuid'), 'jobs', ['job_uuid'], unique=True)
    op.create_index(op.f('ix_jobs_user_id'), 'jobs', ['user_id'], unique=False)

    # Sync History table
    op.create_table('sync_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('sync_type', sa.String(length=50), nullable=False),
        sa.Column('sync_source', sa.String(length=50), nullable=True),
        sa.Column('sync_target', sa.String(length=50), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, default='pending'),
        sa.Column('started_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('duration', sa.Integer(), nullable=True),
        sa.Column('total_items', sa.Integer(), nullable=True, default=0),
        sa.Column('items_processed', sa.Integer(), nullable=True, default=0),
        sa.Column('items_successful', sa.Integer(), nullable=True, default=0),
        sa.Column('items_failed', sa.Integer(), nullable=True, default=0),
        sa.Column('items_skipped', sa.Integer(), nullable=True, default=0),
        sa.Column('products_synced', sa.Integer(), nullable=True, default=0),
        sa.Column('categories_synced', sa.Integer(), nullable=True, default=0),
        sa.Column('icons_synced', sa.Integer(), nullable=True, default=0),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('warnings', sa.JSON(), nullable=True),
        sa.Column('errors', sa.JSON(), nullable=True),
        sa.Column('input_files', sa.JSON(), nullable=True),
        sa.Column('output_files', sa.JSON(), nullable=True),
        sa.Column('log_file_path', sa.String(length=1000), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('job_id', sa.Integer(), nullable=True),
        sa.Column('meta_data', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_sync_job', 'sync_history', ['job_id'], unique=False)
    op.create_index('idx_sync_started', 'sync_history', ['started_at'], unique=False)
    op.create_index('idx_sync_status', 'sync_history', ['status'], unique=False)
    op.create_index('idx_sync_type', 'sync_history', ['sync_type'], unique=False)
    op.create_index('idx_sync_user', 'sync_history', ['user_id'], unique=False)
    op.create_index(op.f('ix_sync_history_job_id'), 'sync_history', ['job_id'], unique=False)
    op.create_index(op.f('ix_sync_history_user_id'), 'sync_history', ['user_id'], unique=False)

    # Product Images table
    op.create_table('product_images',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('file_path', sa.String(length=1000), nullable=False),
        sa.Column('url', sa.String(length=1000), nullable=True),
        sa.Column('alt_text', sa.String(length=255), nullable=True),
        sa.Column('width', sa.Integer(), nullable=True),
        sa.Column('height', sa.Integer(), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('format', sa.String(length=10), nullable=True),
        sa.Column('file_hash', sa.String(length=64), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=True, default=0),
        sa.Column('is_featured', sa.Boolean(), nullable=True, default=False),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('shopify_image_id', sa.String(length=50), nullable=True),
        sa.Column('shopify_image_url', sa.String(length=1000), nullable=True),
        sa.Column('shopify_synced_at', sa.DateTime(), nullable=True),
        sa.Column('meta_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('product_id', 'file_hash', name='uq_product_image_hash')
    )
    op.create_index('idx_product_image_hash', 'product_images', ['file_hash'], unique=False)
    op.create_index('idx_product_image_product', 'product_images', ['product_id'], unique=False)
    op.create_index('idx_product_image_shopify', 'product_images', ['shopify_image_id'], unique=False)
    op.create_index(op.f('ix_product_images_product_id'), 'product_images', ['product_id'], unique=False)

    # System Logs table
    op.create_table('system_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('level', sa.String(length=20), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('logger_name', sa.String(length=200), nullable=True),
        sa.Column('module', sa.String(length=200), nullable=True),
        sa.Column('function', sa.String(length=200), nullable=True),
        sa.Column('line_number', sa.Integer(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('job_id', sa.Integer(), nullable=True),
        sa.Column('session_id', sa.String(length=100), nullable=True),
        sa.Column('request_id', sa.String(length=100), nullable=True),
        sa.Column('extra_data', sa.JSON(), nullable=True),
        sa.Column('stack_trace', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_log_created', 'system_logs', ['created_at'], unique=False)
    op.create_index('idx_log_job', 'system_logs', ['job_id'], unique=False)
    op.create_index('idx_log_level', 'system_logs', ['level'], unique=False)
    op.create_index('idx_log_module', 'system_logs', ['module'], unique=False)
    op.create_index('idx_log_user', 'system_logs', ['user_id'], unique=False)
    op.create_index(op.f('ix_system_logs_job_id'), 'system_logs', ['job_id'], unique=False)
    op.create_index(op.f('ix_system_logs_user_id'), 'system_logs', ['user_id'], unique=False)

    # Configurations table
    op.create_table('configurations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=200), nullable=False),
        sa.Column('value', sa.Text(), nullable=True),
        sa.Column('data_type', sa.String(length=20), nullable=True, default='string'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('is_required', sa.Boolean(), nullable=True, default=False),
        sa.Column('is_encrypted', sa.Boolean(), nullable=True, default=False),
        sa.Column('validation_regex', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key')
    )
    op.create_index('idx_config_category', 'configurations', ['category'], unique=False)
    op.create_index('idx_config_key', 'configurations', ['key'], unique=False)
    op.create_index(op.f('ix_configurations_category'), 'configurations', ['category'], unique=False)
    op.create_index(op.f('ix_configurations_key'), 'configurations', ['key'], unique=True)

    # Create performance indexes
    conn = op.get_bind()
    with conn.begin():
        # Products by category and status
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_products_category_status ON products(category_id, status)"))
        
        # Products by brand and category
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_products_brand_category ON products(brand, category_id)"))
        
        # Jobs by user and status
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_jobs_user_status ON jobs(user_id, status)"))
        
        # Sync history by type and status
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_sync_type_status ON sync_history(sync_type, status)"))
        
        # Icons by category and status
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_icons_category_status ON icons(category_id, status)"))
        
        # System logs by level and date
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_logs_level_date ON system_logs(level, created_at)"))