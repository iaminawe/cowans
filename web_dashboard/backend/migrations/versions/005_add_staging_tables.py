"""Add staging tables for enhanced sync

Revision ID: 005_add_staging_tables
Revises: 004_add_supabase_auth
Create Date: 2025-01-08

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '005_add_staging_tables'
down_revision = '004_add_supabase_auth'
branch_labels = None
depends_on = None


def upgrade():
    """Add staging tables for enhanced sync functionality."""
    
    # Create staged_product_changes table
    op.create_table('staged_product_changes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('change_id', sa.String(length=100), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=True),
        sa.Column('shopify_product_id', sa.String(length=50), nullable=True),
        sa.Column('change_type', sa.String(length=20), nullable=False),
        sa.Column('sync_direction', sa.String(length=30), nullable=False),
        sa.Column('source_version', sa.String(length=64), nullable=True),
        sa.Column('target_version', sa.String(length=64), nullable=True),
        sa.Column('current_data', sa.JSON(), nullable=True),
        sa.Column('proposed_data', sa.JSON(), nullable=True),
        sa.Column('field_changes', sa.JSON(), nullable=True),
        sa.Column('has_conflicts', sa.Boolean(), nullable=True),
        sa.Column('conflict_fields', sa.JSON(), nullable=True),
        sa.Column('conflict_resolution', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('reviewed_by', sa.Integer(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('review_notes', sa.Text(), nullable=True),
        sa.Column('auto_approved', sa.Boolean(), nullable=True),
        sa.Column('applied_at', sa.DateTime(), nullable=True),
        sa.Column('applied_by', sa.Integer(), nullable=True),
        sa.Column('application_result', sa.JSON(), nullable=True),
        sa.Column('rollback_data', sa.JSON(), nullable=True),
        sa.Column('source_system', sa.String(length=50), nullable=True),
        sa.Column('batch_id', sa.String(length=100), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['applied_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('change_id')
    )
    op.create_index('idx_staged_product_batch', 'staged_product_changes', ['batch_id'], unique=False)
    op.create_index('idx_staged_product_created', 'staged_product_changes', ['created_at'], unique=False)
    op.create_index('idx_staged_product_priority', 'staged_product_changes', ['priority', 'created_at'], unique=False)
    op.create_index('idx_staged_product_status', 'staged_product_changes', ['status'], unique=False)
    op.create_index('idx_staged_product_type', 'staged_product_changes', ['change_type'], unique=False)
    op.create_index(op.f('ix_staged_product_changes_change_id'), 'staged_product_changes', ['change_id'], unique=True)
    op.create_index(op.f('ix_staged_product_changes_shopify_product_id'), 'staged_product_changes', ['shopify_product_id'], unique=False)
    
    # Create staged_category_changes table
    op.create_table('staged_category_changes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('change_id', sa.String(length=100), nullable=False),
        sa.Column('category_id', sa.Integer(), nullable=True),
        sa.Column('shopify_collection_id', sa.String(length=50), nullable=True),
        sa.Column('change_type', sa.String(length=20), nullable=False),
        sa.Column('sync_direction', sa.String(length=30), nullable=False),
        sa.Column('current_data', sa.JSON(), nullable=True),
        sa.Column('proposed_data', sa.JSON(), nullable=True),
        sa.Column('field_changes', sa.JSON(), nullable=True),
        sa.Column('affected_products', sa.JSON(), nullable=True),
        sa.Column('product_count', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('reviewed_by', sa.Integer(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('applied_at', sa.DateTime(), nullable=True),
        sa.Column('applied_by', sa.Integer(), nullable=True),
        sa.Column('batch_id', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['applied_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('change_id')
    )
    op.create_index('idx_staged_category_batch', 'staged_category_changes', ['batch_id'], unique=False)
    op.create_index('idx_staged_category_status', 'staged_category_changes', ['status'], unique=False)
    op.create_index(op.f('ix_staged_category_changes_change_id'), 'staged_category_changes', ['change_id'], unique=True)
    op.create_index(op.f('ix_staged_category_changes_shopify_collection_id'), 'staged_category_changes', ['shopify_collection_id'], unique=False)
    
    # Create sync_versions table
    op.create_table('sync_versions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('shopify_id', sa.String(length=50), nullable=True),
        sa.Column('version_hash', sa.String(length=64), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('data_snapshot', sa.JSON(), nullable=False),
        sa.Column('source_system', sa.String(length=50), nullable=False),
        sa.Column('sync_direction', sa.String(length=30), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('entity_type', 'entity_id', 'version_number', name='uq_entity_version')
    )
    op.create_index('idx_version_created', 'sync_versions', ['created_at'], unique=False)
    op.create_index('idx_version_entity', 'sync_versions', ['entity_type', 'entity_id'], unique=False)
    op.create_index('idx_version_hash', 'sync_versions', ['version_hash'], unique=False)
    
    # Create sync_batches table
    op.create_table('sync_batches',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('batch_id', sa.String(length=100), nullable=False),
        sa.Column('batch_name', sa.String(length=255), nullable=True),
        sa.Column('sync_type', sa.String(length=50), nullable=False),
        sa.Column('sync_direction', sa.String(length=30), nullable=False),
        sa.Column('total_items', sa.Integer(), nullable=True),
        sa.Column('processed_items', sa.Integer(), nullable=True),
        sa.Column('successful_items', sa.Integer(), nullable=True),
        sa.Column('failed_items', sa.Integer(), nullable=True),
        sa.Column('skipped_items', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('estimated_completion', sa.DateTime(), nullable=True),
        sa.Column('processing_rate', sa.Float(), nullable=True),
        sa.Column('api_calls_made', sa.Integer(), nullable=True),
        sa.Column('api_quota_used', sa.Integer(), nullable=True),
        sa.Column('error_summary', sa.JSON(), nullable=True),
        sa.Column('warnings', sa.JSON(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('cancelled_by', sa.Integer(), nullable=True),
        sa.Column('configuration', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['cancelled_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('batch_id')
    )
    op.create_index('idx_batch_created', 'sync_batches', ['created_at'], unique=False)
    op.create_index('idx_batch_status', 'sync_batches', ['status'], unique=False)
    op.create_index('idx_sync_batch_user', 'sync_batches', ['created_by'], unique=False)
    op.create_index(op.f('ix_sync_batches_batch_id'), 'sync_batches', ['batch_id'], unique=True)
    
    # Create sync_approval_rules table
    op.create_table('sync_approval_rules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('rule_name', sa.String(length=255), nullable=False),
        sa.Column('rule_description', sa.Text(), nullable=True),
        sa.Column('entity_type', sa.String(length=50), nullable=True),
        sa.Column('change_type', sa.String(length=20), nullable=True),
        sa.Column('field_patterns', sa.JSON(), nullable=True),
        sa.Column('value_thresholds', sa.JSON(), nullable=True),
        sa.Column('requires_approval', sa.Boolean(), nullable=True),
        sa.Column('auto_approve_conditions', sa.JSON(), nullable=True),
        sa.Column('approval_level', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_approval_rule_active', 'sync_approval_rules', ['is_active'], unique=False)
    op.create_index('idx_approval_rule_entity', 'sync_approval_rules', ['entity_type'], unique=False)
    op.create_index('idx_approval_rule_priority', 'sync_approval_rules', ['priority'], unique=False)
    
    # Create sync_rollbacks table
    op.create_table('sync_rollbacks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('rollback_id', sa.String(length=100), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('staged_change_id', sa.Integer(), nullable=True),
        sa.Column('previous_version_id', sa.Integer(), nullable=True),
        sa.Column('rollback_data', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('executed_at', sa.DateTime(), nullable=True),
        sa.Column('executed_by', sa.Integer(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['executed_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['previous_version_id'], ['sync_versions.id'], ),
        sa.ForeignKeyConstraint(['staged_change_id'], ['staged_product_changes.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('rollback_id')
    )
    op.create_index('idx_rollback_created', 'sync_rollbacks', ['created_at'], unique=False)
    op.create_index('idx_rollback_entity', 'sync_rollbacks', ['entity_type', 'entity_id'], unique=False)
    op.create_index('idx_rollback_status', 'sync_rollbacks', ['status'], unique=False)
    op.create_index(op.f('ix_sync_rollbacks_rollback_id'), 'sync_rollbacks', ['rollback_id'], unique=True)
    
    # Create performance indexes using raw SQL
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_staged_pending_priority 
        ON staged_product_changes(priority ASC, created_at ASC) 
        WHERE status = 'pending'
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_staged_conflicts 
        ON staged_product_changes(created_at DESC) 
        WHERE has_conflicts = true
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_staged_auto_approve 
        ON staged_product_changes(created_at ASC) 
        WHERE status = 'pending' AND auto_approved = false
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_version_latest 
        ON sync_versions(entity_type, entity_id, version_number DESC)
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_batch_active 
        ON sync_batches(created_at DESC) 
        WHERE status IN ('pending', 'running')
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_approval_evaluation 
        ON sync_approval_rules(entity_type, change_type, priority DESC) 
        WHERE is_active = true
    """)


def downgrade():
    """Remove staging tables."""
    # Drop performance indexes
    op.execute("DROP INDEX IF EXISTS idx_staged_pending_priority")
    op.execute("DROP INDEX IF EXISTS idx_staged_conflicts")
    op.execute("DROP INDEX IF EXISTS idx_staged_auto_approve")
    op.execute("DROP INDEX IF EXISTS idx_version_latest")
    op.execute("DROP INDEX IF EXISTS idx_batch_active")
    op.execute("DROP INDEX IF EXISTS idx_approval_evaluation")
    
    # Drop tables in reverse order of dependencies
    op.drop_table('sync_rollbacks')
    op.drop_table('sync_approval_rules')
    op.drop_table('sync_batches')
    op.drop_table('sync_versions')
    op.drop_table('staged_category_changes')
    op.drop_table('staged_product_changes')