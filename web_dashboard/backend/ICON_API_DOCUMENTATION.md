# Icon Generation API Documentation

## Overview

The Icon Generation API provides endpoints for generating, managing, and serving category icons. It supports both single icon generation and batch processing with real-time progress tracking.

## Authentication

All endpoints require JWT authentication. Include the token in the Authorization header:

```
Authorization: Bearer <your_jwt_token>
```

## Base URL

```
http://localhost:3560/api/icons
```

## Endpoints

### 1. Get Categories

Get all categories with their icon status.

**Endpoint:** `GET /api/icons/categories`

**Response:**
```json
[
  {
    "id": 1,
    "category_id": 1,
    "category_name": "Office Supplies",
    "file_path": "/path/to/icon.png",
    "url": "/api/icons/categories/1/icon",
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z",
    "metadata": {
      "style": "modern",
      "color": "#3B82F6",
      "size": 128
    },
    "status": "active",
    "has_icon": true
  }
]
```

### 2. Get Category Details

Get details for a specific category.

**Endpoint:** `GET /api/icons/categories/{category_id}`

**Response:**
```json
{
  "id": 1,
  "category_id": 1,
  "category_name": "Office Supplies",
  "file_path": "/path/to/icon.png",
  "url": "/api/icons/categories/1/icon",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z",
  "metadata": {
    "style": "modern",
    "color": "#3B82F6",
    "size": 128
  },
  "status": "active",
  "has_icon": true
}
```

### 3. Serve Category Icon

Serve the icon file for a category.

**Endpoint:** `GET /api/icons/categories/{category_id}/icon`

**Response:** PNG image file

### 4. Generate Single Icon

Generate an icon for a single category.

**Endpoint:** `POST /api/icons/generate`

**Request Body:**
```json
{
  "category_id": 1,
  "category_name": "Office Supplies",
  "style": "modern",
  "color": "#3B82F6",
  "size": 128,
  "background": "transparent"
}
```

**Parameters:**
- `category_id` (required): Integer - Category ID
- `category_name` (required): String - Category name
- `style` (optional): String - Icon style (`modern`, `flat`, `outlined`, `minimal`)
- `color` (optional): String - Hex color code (e.g., `#3B82F6`)
- `size` (optional): Integer - Icon size in pixels (32-512)
- `background` (optional): String - Background type (`transparent`, `white`, `colored`)

**Response:**
```json
{
  "message": "Icon generated successfully",
  "icon": {
    "id": 1,
    "category_id": 1,
    "category_name": "Office Supplies",
    "file_path": "/path/to/icon.png",
    "url": "/api/icons/categories/1/icon",
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z",
    "metadata": {
      "style": "modern",
      "color": "#3B82F6",
      "size": 128,
      "generated_by": "user@example.com"
    },
    "status": "active",
    "has_icon": true
  }
}
```

### 5. Generate Batch Icons

Generate icons for multiple categories using background job processing.

**Endpoint:** `POST /api/icons/generate/batch`

**Request Body:**
```json
{
  "categories": [
    {"id": 1, "name": "Office Supplies"},
    {"id": 2, "name": "Computer Hardware"},
    {"id": 3, "name": "Office Furniture"}
  ],
  "options": {
    "style": "modern",
    "color": "#3B82F6",
    "size": 128,
    "background": "transparent"
  }
}
```

**Response:**
```json
{
  "job_id": "uuid-string",
  "message": "Batch icon generation started for 3 categories"
}
```

**Job Status Tracking:**
Use the job management endpoints to track batch processing progress:
- `GET /api/jobs/{job_id}` - Get job status
- WebSocket events for real-time updates

### 6. Regenerate Icon

Regenerate an icon for an existing category.

**Endpoint:** `POST /api/icons/categories/{category_id}/regenerate`

**Request Body:**
```json
{
  "style": "outlined",
  "color": "#EF4444"
}
```

**Response:**
```json
{
  "message": "Icon regenerated successfully",
  "icon": {
    "id": 1,
    "category_id": 1,
    "category_name": "Office Supplies",
    "file_path": "/path/to/icon.png",
    "url": "/api/icons/categories/1/icon",
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z",
    "metadata": {
      "style": "outlined",
      "color": "#EF4444",
      "regenerated": true
    },
    "status": "active",
    "has_icon": true
  }
}
```

### 7. Delete Icon

Delete an icon and its associated files.

**Endpoint:** `DELETE /api/icons/categories/{category_id}`

**Response:**
```json
{
  "message": "Icon deleted successfully"
}
```

### 8. Get Statistics

Get icon generation statistics.

**Endpoint:** `GET /api/icons/stats`

**Response:**
```json
{
  "total_icons": 25,
  "total_jobs": 10,
  "recent_icons": 5,
  "job_stats": {
    "pending": 2,
    "completed": 8,
    "failed": 0
  },
  "storage_path": "/path/to/icons"
}
```

## Icon Styles

### Available Styles

1. **Modern** (`modern`)
   - Features: Background gradients, shadows, rounded corners
   - Best for: Professional applications

2. **Flat** (`flat`)
   - Features: Clean flat design, solid colors
   - Best for: Minimalist interfaces

3. **Outlined** (`outlined`)
   - Features: Borders, minimal fills
   - Best for: Clean, lightweight designs

4. **Minimal** (`minimal`)
   - Features: Transparent backgrounds, simple shapes
   - Best for: Text-focused interfaces

## Category Symbol Mapping

The system automatically maps category names to appropriate symbols/emojis:

- **Office Supplies**: pens (✏️), paper (📄), notebooks (📓), etc.
- **Technology**: computers (💻), keyboards (⌨️), monitors (🖥️), etc.
- **Furniture**: desks (🪑), chairs (🪑), tables (🪑), etc.
- **General**: tools (🔧), supplies (📦), equipment (⚙️), etc.

## Error Handling

### Common Error Responses

**400 Bad Request:**
```json
{
  "message": "Invalid request data",
  "errors": "Category ID is required"
}
```

**401 Unauthorized:**
```json
{
  "message": "Missing or invalid JWT token"
}
```

**404 Not Found:**
```json
{
  "message": "Category not found"
}
```

**500 Internal Server Error:**
```json
{
  "message": "Failed to generate icon",
  "error": "PIL image creation failed"
}
```

## WebSocket Events

For real-time updates during batch processing:

### Connection
```javascript
const socket = io('http://localhost:3560');
```

### Events

**Job Progress:**
```javascript
socket.on('job_progress', (data) => {
  console.log(`Job ${data.job_id}: ${data.progress}%`);
});
```

**Job Output:**
```javascript
socket.on('job_output', (data) => {
  console.log(`Job ${data.job_id}: ${data.line}`);
});
```

**Job Completed:**
```javascript
socket.on('job_completed', (data) => {
  console.log(`Job ${data.job_id} completed: ${data.summary}`);
});
```

**Job Failed:**
```javascript
socket.on('job_failed', (data) => {
  console.log(`Job ${data.job_id} failed: ${data.error}`);
});
```

## Database Schema

### category_icons Table

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| category_id | INTEGER | Unique category identifier |
| category_name | TEXT | Category name |
| file_path | TEXT | Path to icon file |
| url | TEXT | API URL for icon |
| created_at | TIMESTAMP | Creation timestamp |
| updated_at | TIMESTAMP | Last update timestamp |
| metadata | TEXT | JSON metadata |
| status | TEXT | Icon status (active/inactive) |

### icon_generation_jobs Table

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| job_id | TEXT | Job identifier |
| category_id | INTEGER | Category ID |
| status | TEXT | Job status |
| created_at | TIMESTAMP | Creation timestamp |
| completed_at | TIMESTAMP | Completion timestamp |
| error_message | TEXT | Error details |

## Background Jobs

### Job Types

1. **Single Icon Generation**: Immediate processing
2. **Batch Icon Generation**: Background processing with progress tracking
3. **Cleanup Jobs**: Scheduled maintenance tasks

### Job Management

Monitor jobs using the existing job management system:
- `GET /api/jobs/{job_id}` - Get job status
- `POST /api/jobs/{job_id}/cancel` - Cancel job
- `GET /api/jobs/{job_id}/logs` - Get job logs

## File Storage

### Directory Structure
```
data/
├── category_icons/
│   ├── category_1.png
│   ├── category_2.png
│   └── ...
└── icons.db
```

### File Naming Convention
- Icons: `category_{category_id}.png`
- Database: `icons.db`

## Testing

Run the API test suite:

```bash
cd web_dashboard/backend
python test_icon_api.py
```

### Test Coverage
- Authentication
- Single icon generation
- Batch icon generation
- Icon serving
- Icon regeneration
- Statistics
- Error handling

## Configuration

### Environment Variables
- `DATA_PATH`: Base path for data storage
- `ICON_MAX_SIZE`: Maximum icon size (default: 512)
- `ICON_DEFAULT_SIZE`: Default icon size (default: 128)
- `ICON_BATCH_MAX_SIZE`: Maximum batch size (default: 100)

### Dependencies
- `Pillow`: Image processing
- `SQLite`: Database storage
- `Flask`: Web framework
- `Celery`: Background job processing
- `Redis`: Job queue backend

## Performance Considerations

1. **Icon Generation**: ~100ms per icon
2. **Batch Processing**: Parallel processing for large batches
3. **File Caching**: Generated icons are cached on disk
4. **Database Indexing**: Optimized queries for category lookups
5. **Memory Usage**: Efficient PIL operations

## Security

1. **Authentication**: JWT tokens required for all endpoints
2. **Input Validation**: Strict parameter validation
3. **File Security**: Sandboxed file storage
4. **Rate Limiting**: Celery throttling for batch jobs
5. **Error Handling**: Sanitized error messages

## Monitoring

- Health check endpoint: `/api/health`
- Statistics endpoint: `/api/icons/stats`
- Job monitoring: WebSocket events
- Log files: Application and job logs