# ChatGPT Integration - Implementation Guide

## Quick Integration Steps

### 1. Install Dependencies
```bash
cd web_dashboard/backend
pip install openai==1.12.0 Pillow==10.2.0 requests==2.31.0 aiohttp==3.9.3 asyncio-throttle==1.0.2
```

### 2. Add Environment Variables
Add to your `.env` file:
```bash
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=dall-e-3
OPENAI_IMAGE_SIZE=1024x1024
OPENAI_RATE_LIMIT_RPM=50
OPENAI_RATE_LIMIT_TPM=40000
```

### 3. Update Configuration
Add the configuration variables from `config_additions.py` to your main `config.py` file.

### 4. Copy Core Files
Copy these files to your backend directory:
- `openai_client.py` - OpenAI API client with rate limiting
- `prompt_templates.py` - Prompt template system
- `icon_generation_service.py` - Main service layer
- `app_with_icons.py` - Complete Flask app with icon endpoints

### 5. Integration Options

#### Option A: Replace Existing App
Replace your current `app.py` with `app_with_icons.py` for complete integration.

#### Option B: Add Endpoints Only
Add the icon generation endpoints from `app_with_icons.py` to your existing `app.py`:

```python
# Add these imports
from icon_generation_service import IconGenerationService, BatchGenerationRequest
from prompt_templates import IconStyle, IconColor
from openai_client import ImageGenerationRequest

# Add the helper function
def run_async(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

# Copy all the @app.route("/api/icons/...") endpoints
```

### 6. Test the Integration

#### Test Single Icon Generation
```bash
curl -X POST http://localhost:3560/api/icons/generate \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "category": "office supplies",
    "style": "modern",
    "color_scheme": "brand_colors"
  }'
```

#### Test Batch Generation
```bash
curl -X POST http://localhost:3560/api/icons/generate/batch \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "categories": ["electronics", "tools", "automotive"],
    "style": "flat",
    "variations_per_category": 1
  }'
```

### 7. WebSocket Integration

For real-time progress updates, ensure your frontend connects to WebSocket and listens for:
- `batch_progress` - Batch generation progress
- `job_output` - Individual job output
- `job_completed` - Job completion notifications

## API Endpoints Reference

### Core Generation
- `POST /api/icons/generate` - Generate single icon
- `POST /api/icons/generate/batch` - Start batch generation

### Batch Management
- `GET /api/icons/batch/{id}/status` - Get batch status
- `GET /api/icons/batch/{id}/result` - Get batch results
- `POST /api/icons/batch/{id}/cancel` - Cancel batch
- `GET /api/icons/batches` - List user batches

### Icon Management
- `GET /api/icons/cached` - List cached icons
- `POST /api/icons/cache/clear` - Clear cache
- `GET /api/icons/stats` - Generation statistics
- `GET /api/icons/categories/suggestions` - Category suggestions

### Image Serving
- `GET /api/images/{filename}` - Serve generated images

## Request/Response Examples

### Single Icon Generation Request
```json
{
  "category": "office supplies",
  "style": "modern",
  "color_scheme": "brand_colors",
  "custom_elements": ["pen", "stapler", "calculator"]
}
```

### Single Icon Generation Response
```json
{
  "success": true,
  "image_url": "https://...",
  "local_path": "/path/to/image.png",
  "generation_time": 12.5,
  "metadata": {
    "style": "modern",
    "color_scheme": "brand_colors",
    "category": "office supplies"
  }
}
```

### Batch Generation Request
```json
{
  "categories": ["electronics", "tools", "automotive"],
  "style": "flat",
  "color_scheme": "blue_tones",
  "variations_per_category": 2,
  "custom_elements": {
    "electronics": ["circuit", "device"],
    "tools": ["hammer", "wrench"]
  }
}
```

### Batch Status Response
```json
{
  "batch_id": "uuid-here",
  "status": "running",
  "progress": 60,
  "current_category": "tools",
  "total_categories": 3,
  "completed_categories": 1,
  "estimated_completion": "2024-01-01T12:30:00Z"
}
```

## Error Handling

All endpoints return structured error responses:

```json
{
  "message": "Error description",
  "error": "Detailed error information",
  "metadata": {
    "category": "electronics",
    "attempts": 3
  }
}
```

## Performance Considerations

### Rate Limiting
- Default: 50 requests/minute, 40,000 tokens/minute
- Automatic throttling and backoff
- Configurable via environment variables

### Batch Processing
- Default batch size: 5 concurrent generations
- Configurable concurrent limits
- Progress tracking and cancellation support

### Caching
- Request-based caching prevents duplicates
- Local image storage with organized directories
- Configurable cache retention policies

## Security Notes

1. **API Key Protection**: Store OpenAI API key in environment variables
2. **Authentication**: All endpoints require JWT authentication
3. **Input Validation**: All inputs are validated and sanitized
4. **Rate Limiting**: Built-in protection against abuse
5. **File Security**: Generated images stored in controlled directories

## Troubleshooting

### Common Issues

1. **OpenAI API Key**: Ensure valid API key with DALL-E access
2. **Rate Limits**: Monitor rate limit errors and adjust configuration
3. **Memory Usage**: Large batches may require memory optimization
4. **Directory Permissions**: Ensure write access to image storage directory

### Logging

All operations are logged with appropriate levels:
- INFO: Normal operations and progress
- WARNING: Rate limits and recoverable errors
- ERROR: Failed generations and system errors

### Monitoring

Check generation statistics via `/api/icons/stats`:
- Total generations and success rates
- Average generation times
- Active batch jobs
- Cache utilization

This integration provides a complete, production-ready solution for AI-powered icon generation with comprehensive error handling, batch processing, and real-time progress tracking.