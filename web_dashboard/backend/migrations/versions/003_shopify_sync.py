"""Add Shopify sync tracking

Revision ID: 003_shopify_sync
Revises: 002_etilize_integration
Create Date: 2025-07-04 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '003_shopify_sync'
down_revision = '002_etilize_integration'
branch_labels = None
depends_on = None


def upgrade():
    # Create shopify_syncs table
    op.create_table('shopify_syncs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('sync_uuid', sa.String(length=36), nullable=False),
        sa.Column('mode', sa.String(length=50), nullable=False),
        sa.Column('configuration', sa.JSON(), nullable=False),
        sa.Column('filters', sa.JSON(), nullable=True),
        sa.Column('import_batch_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('stage', sa.String(length=50), nullable=True),
        sa.Column('progress', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('duration', sa.Integer(), nullable=True),
        sa.Column('total_products', sa.Integer(), nullable=True),
        sa.Column('successful_uploads', sa.Integer(), nullable=True),
        sa.Column('failed_uploads', sa.Integer(), nullable=True),
        sa.Column('skipped_uploads', sa.Integer(), nullable=True),
        sa.Column('duplicates_cleaned', sa.Integer(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=True),
        sa.Column('errors', sa.JSON(), nullable=True),
        sa.Column('warnings', sa.JSON(), nullable=True),
        sa.Column('triggered_by', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['import_batch_id'], ['etilize_import_batches.id'], ),
        sa.ForeignKeyConstraint(['triggered_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('sync_uuid')
    )
    
    # Create indexes
    op.create_index('idx_shopify_sync_status', 'shopify_syncs', ['status'])
    op.create_index('idx_shopify_sync_mode', 'shopify_syncs', ['mode'])
    op.create_index('idx_shopify_sync_created', 'shopify_syncs', ['created_at'])
    op.create_index('idx_shopify_sync_batch', 'shopify_syncs', ['import_batch_id'])
    op.create_index('idx_shopify_sync_user', 'shopify_syncs', ['triggered_by'])
    op.create_index(op.f('ix_shopify_syncs_sync_uuid'), 'shopify_syncs', ['sync_uuid'], unique=False)
    
    # Add missing fields to products table for Shopify sync compatibility
    op.add_column('products', sa.Column('shopify_id', sa.String(length=50), nullable=True))
    op.add_column('products', sa.Column('shopify_status', sa.String(length=20), nullable=True))
    op.add_column('products', sa.Column('last_synced', sa.DateTime(), nullable=True))
    op.add_column('products', sa.Column('title', sa.String(length=500), nullable=True))
    
    # Create indexes for new product fields
    op.create_index(op.f('ix_products_shopify_id'), 'products', ['shopify_id'], unique=False)
    
    # Set default values for existing products
    op.execute("UPDATE products SET shopify_status = 'pending' WHERE shopify_status IS NULL")
    op.execute("UPDATE products SET title = name WHERE title IS NULL")


def downgrade():
    # Drop indexes for product fields
    op.drop_index(op.f('ix_products_shopify_id'), table_name='products')
    
    # Remove added columns from products table
    op.drop_column('products', 'title')
    op.drop_column('products', 'last_synced')
    op.drop_column('products', 'shopify_status')
    op.drop_column('products', 'shopify_id')
    
    # Drop shopify_syncs table indexes
    op.drop_index(op.f('ix_shopify_syncs_sync_uuid'), table_name='shopify_syncs')
    op.drop_index('idx_shopify_sync_user', table_name='shopify_syncs')
    op.drop_index('idx_shopify_sync_batch', table_name='shopify_syncs')
    op.drop_index('idx_shopify_sync_created', table_name='shopify_syncs')
    op.drop_index('idx_shopify_sync_mode', table_name='shopify_syncs')
    op.drop_index('idx_shopify_sync_status', table_name='shopify_syncs')
    
    # Drop shopify_syncs table
    op.drop_table('shopify_syncs')