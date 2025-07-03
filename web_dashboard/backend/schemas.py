"""Schema definitions for request/response validation."""
from marshmallow import Schema, fields, validate, ValidationError
from datetime import datetime

class LoginSchema(Schema):
    """Schema for login requests."""
    email = fields.Email(required=True)
    password = fields.String(required=True, validate=validate.Length(min=6))

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