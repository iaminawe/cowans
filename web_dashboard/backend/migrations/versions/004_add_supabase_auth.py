"""Add Supabase authentication support

Revision ID: 004
Revises: 003
Create Date: 2025-01-07

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '004_add_supabase_auth'
down_revision = '003_shopify_sync'
branch_labels = None
depends_on = None


def upgrade():
    """Add supabase_id column to users table."""
    # Add supabase_id column
    op.add_column('users', sa.Column('supabase_id', sa.String(255), nullable=True))
    
    # Create unique index on supabase_id
    op.create_index('ix_users_supabase_id', 'users', ['supabase_id'], unique=True)
    
    # Make password_hash nullable for Supabase users
    op.alter_column('users', 'password_hash',
                    existing_type=sa.String(255),
                    nullable=True)


def downgrade():
    """Remove Supabase authentication support."""
    # Make password_hash not nullable again
    op.alter_column('users', 'password_hash',
                    existing_type=sa.String(255),
                    nullable=False)
    
    # Drop index
    op.drop_index('ix_users_supabase_id', table_name='users')
    
    # Drop column
    op.drop_column('users', 'supabase_id')