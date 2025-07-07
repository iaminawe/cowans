"""Add collections tables migration

This migration adds the collections and product_collections tables to support
organizing products into collections with Shopify sync capabilities.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text
from datetime import datetime

def upgrade():
    """Add collections and product_collections tables."""
    
    # Create collections table
    op.create_table(
        'collections',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('handle', sa.String(255), nullable=False, unique=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('sort_order', sa.String(50), nullable=True, server_default='manual'),
        sa.Column('status', sa.String(20), nullable=True, server_default='draft'),
        sa.Column('is_visible', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('rules_type', sa.String(20), nullable=True, server_default='manual'),
        sa.Column('rules_conditions', sa.JSON(), nullable=True),
        sa.Column('disjunctive', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('image_url', sa.String(1000), nullable=True),
        sa.Column('image_alt_text', sa.String(255), nullable=True),
        sa.Column('icon_id', sa.Integer(), nullable=True),
        sa.Column('seo_title', sa.String(255), nullable=True),
        sa.Column('seo_description', sa.Text(), nullable=True),
        sa.Column('products_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('template_suffix', sa.String(100), nullable=True),
        sa.Column('published_at', sa.DateTime(), nullable=True),
        sa.Column('published_scope', sa.String(50), nullable=True, server_default='global'),
        sa.Column('meta_data', sa.JSON(), nullable=True),
        sa.Column('shopify_collection_id', sa.String(50), nullable=True, unique=True),
        sa.Column('shopify_handle', sa.String(255), nullable=True),
        sa.Column('shopify_synced_at', sa.DateTime(), nullable=True),
        sa.Column('shopify_sync_status', sa.String(20), nullable=True, server_default='pending'),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['icon_id'], ['icons.id'], ),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
    )
    
    # Create indexes
    op.create_index('idx_collection_handle', 'collections', ['handle'])
    op.create_index('idx_collection_status', 'collections', ['status'])
    op.create_index('idx_collection_shopify', 'collections', ['shopify_collection_id'])
    op.create_index('idx_collection_created_by', 'collections', ['created_by'])
    
    # Create product_collections association table
    op.create_table(
        'product_collections',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('collection_id', sa.Integer(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ),
        sa.ForeignKeyConstraint(['collection_id'], ['collections.id'], ),
        sa.UniqueConstraint('product_id', 'collection_id', name='uq_product_collection')
    )
    
    # Create indexes for product_collections
    op.create_index('idx_product_collection_product', 'product_collections', ['product_id'])
    op.create_index('idx_product_collection_collection', 'product_collections', ['collection_id'])
    op.create_index('idx_product_collection_position', 'product_collections', ['position'])
    
    # Add product_type column to products table if it doesn't exist
    with op.batch_alter_table('products') as batch_op:
        try:
            batch_op.add_column(sa.Column('product_type', sa.String(255), nullable=True))
            batch_op.create_index('idx_product_type', ['product_type'])
        except:
            # Column might already exist
            pass

def downgrade():
    """Remove collections and product_collections tables."""
    
    # Drop indexes
    op.drop_index('idx_product_collection_position', 'product_collections')
    op.drop_index('idx_product_collection_collection', 'product_collections')
    op.drop_index('idx_product_collection_product', 'product_collections')
    
    # Drop product_collections table
    op.drop_table('product_collections')
    
    # Drop indexes
    op.drop_index('idx_collection_created_by', 'collections')
    op.drop_index('idx_collection_shopify', 'collections')
    op.drop_index('idx_collection_status', 'collections')
    op.drop_index('idx_collection_handle', 'collections')
    
    # Drop collections table
    op.drop_table('collections')
    
    # Remove product_type column from products table
    with op.batch_alter_table('products') as batch_op:
        try:
            batch_op.drop_index('idx_product_type')
            batch_op.drop_column('product_type')
        except:
            # Column might not exist
            pass