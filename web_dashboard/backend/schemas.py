"""Schema definitions for request/response validation."""
from marshmallow import Schema, fields, validate, ValidationError
from datetime import datetime

class LoginSchema(Schema):
    """Schema for login requests."""
    email = fields.Email(required=True)
    password = fields.String(required=True, validate=validate.Length(min=6))

class RegisterSchema(Schema):
    """Schema for user registration requests."""
    email = fields.Email(required=True)
    password = fields.String(required=True, validate=validate.Length(min=8, max=128))
    first_name = fields.String(required=True, validate=validate.Length(min=1, max=100))
    last_name = fields.String(required=True, validate=validate.Length(min=1, max=100))

class ScriptParameterSchema(Schema):
    """Schema for script parameters."""
    name = fields.String(required=True)
    value = fields.Raw(required=True)
    type = fields.String(validate=validate.OneOf(['string', 'number', 'boolean', 'file']))

class ScriptExecutionSchema(Schema):
    """Schema for script execution requests."""
    script_name = fields.String(required=True, validate=validate.OneOf([
        'ftp_download',
        'filter_products',
        'create_metafields',
        'shopify_upload',
        'cleanup_duplicates',
        'categorize_products',
        'full_import',
        'icon_generation_batch'
    ]))
    parameters = fields.List(fields.Nested(ScriptParameterSchema), load_default=[])
    options = fields.Dict(load_default={})
    
class JobStatusSchema(Schema):
    """Schema for job status responses."""
    job_id = fields.String(required=True)
    status = fields.String(required=True, validate=validate.OneOf([
        'pending', 'running', 'completed', 'failed', 'cancelled'
    ]))
    script_name = fields.String(required=True)
    created_at = fields.DateTime(required=True)
    started_at = fields.DateTime(allow_none=True)
    completed_at = fields.DateTime(allow_none=True)
    progress = fields.Integer(load_default=0, validate=validate.Range(min=0, max=100))
    current_stage = fields.String(allow_none=True)
    output = fields.List(fields.String(), load_default=[])
    error = fields.String(allow_none=True)
    result = fields.Dict(allow_none=True)

class SyncHistorySchema(Schema):
    """Schema for sync history responses."""
    id = fields.Integer(required=True)
    timestamp = fields.DateTime(required=True)
    status = fields.String(required=True)
    message = fields.String(required=True)
    duration = fields.Integer(allow_none=True)
    products_synced = fields.Integer(allow_none=True)
    errors = fields.List(fields.String(), load_default=[])

class ScriptDefinitionSchema(Schema):
    """Schema for script definitions."""
    name = fields.String(required=True)
    display_name = fields.String(required=True)
    description = fields.String(required=True)
    category = fields.String(required=True)
    parameters = fields.List(fields.Dict(), load_default=[])
    estimated_duration = fields.Integer(allow_none=True)
    requires_auth = fields.Boolean(load_default=True)

class CategoryIconSchema(Schema):
    """Schema for category icon responses."""
    id = fields.Integer(required=True)
    category_id = fields.Integer(required=True)
    category_name = fields.String(required=True)
    file_path = fields.String(required=True)
    url = fields.String(required=True)
    created_at = fields.DateTime(required=True)
    updated_at = fields.DateTime(required=True)
    metadata = fields.Dict(load_default={})
    status = fields.String(validate=validate.OneOf(['active', 'inactive', 'generating']))

class IconGenerationSchema(Schema):
    """Schema for icon generation requests."""
    category_id = fields.Integer(required=True)
    category_name = fields.String(required=True, validate=validate.Length(min=1, max=100))
    style = fields.String(validate=validate.OneOf(['modern', 'flat', 'outlined', 'minimal']), load_default='modern')
    color = fields.String(validate=validate.Regexp(r'^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$'), load_default='#3B82F6')
    size = fields.Integer(validate=validate.Range(min=32, max=512), load_default=128)
    background = fields.String(validate=validate.OneOf(['transparent', 'white', 'colored']), load_default='transparent')
    model = fields.String(validate=validate.OneOf(['gpt-image-1', 'dall-e-3']), load_default='gpt-image-1')

class ParallelSyncConfigSchema(Schema):
    """Schema for parallel sync configuration."""
    sync_mode = fields.String(validate=validate.OneOf([
        'full_sync', 'new_only', 'update_only', 'ultra_fast', 'image_sync'
    ]), required=True)
    batch_size = fields.Integer(validate=validate.Range(min=1, max=250), load_default=50)
    min_workers = fields.Integer(validate=validate.Range(min=1, max=20), load_default=2)
    max_workers = fields.Integer(validate=validate.Range(min=1, max=50), load_default=10)
    priority = fields.String(validate=validate.OneOf(['critical', 'high', 'normal', 'low', 'batch']), load_default='normal')
    enable_bulk_operations = fields.Boolean(load_default=True)
    memory_limit_mb = fields.Integer(validate=validate.Range(min=256, max=4096), load_default=512)
    enable_monitoring = fields.Boolean(load_default=True)
    
class SyncOperationSchema(Schema):
    """Schema for sync operation requests."""
    operation_type = fields.String(validate=validate.OneOf([
        'create', 'update', 'delete', 'update_inventory', 'update_status', 'update_images'
    ]), required=True)
    product_ids = fields.List(fields.Integer(), required=True, validate=validate.Length(min=1))
    priority = fields.String(validate=validate.OneOf(['critical', 'high', 'normal', 'low', 'batch']), load_default='normal')
    data = fields.Dict(load_default={})

class SyncMetricsSchema(Schema):
    """Schema for sync metrics responses."""
    total_operations = fields.Integer(required=True)
    completed_operations = fields.Integer(required=True)
    failed_operations = fields.Integer(required=True)
    retry_operations = fields.Integer(required=True)
    success_rate = fields.Float(required=True)
    operations_per_second = fields.Float(required=True)
    average_operation_time = fields.Float(required=True)
    queue_depth = fields.Integer(required=True)
    active_workers = fields.Integer(required=True)
    total_workers = fields.Integer(required=True)
    memory_usage_mb = fields.Float(required=True)
    eta_seconds = fields.Float(allow_none=True)
    last_updated = fields.DateTime(required=True)

class PerformanceReportSchema(Schema):
    """Schema for performance report responses."""
    period_start = fields.DateTime(required=True)
    period_end = fields.DateTime(required=True)
    total_operations = fields.Integer(required=True)
    successful_operations = fields.Integer(required=True)
    failed_operations = fields.Integer(required=True)
    average_operation_time = fields.Float(required=True)
    p95_operation_time = fields.Float(required=True)
    p99_operation_time = fields.Float(required=True)
    operations_per_second = fields.Float(required=True)
    average_queue_depth = fields.Float(required=True)
    peak_queue_depth = fields.Integer(required=True)
    average_memory_usage = fields.Float(required=True)
    peak_memory_usage = fields.Float(required=True)
    average_cpu_usage = fields.Float(required=True)
    api_calls = fields.Integer(required=True)
    api_errors = fields.Integer(required=True)
    cache_hits = fields.Integer(required=True)
    cache_misses = fields.Integer(required=True)