"""Add version columns to products table

Revision ID: 006_add_product_version_columns
Revises: 005_add_staging_tables
Create Date: 2025-01-08 21:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '006_add_product_version_columns'
down_revision = '005_add_staging_tables'
branch_labels = None
depends_on = None


def upgrade():
    """Add version columns to products table."""
    
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
    
    # Update existing products with default version
    op.execute("UPDATE products SET version = 1 WHERE version IS NULL")


def downgrade():
    """Remove version columns from products table."""
    
    # Drop indexes
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