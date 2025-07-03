# Backend API Documentation

This backend provides a comprehensive API for managing product synchronization scripts with real-time logging, job management, and security features.

## Features

- **Script Execution API**: Execute various data processing scripts with parameter validation
- **Real-time Logging**: WebSocket-based real-time log streaming
- **Job Queue System**: Asynchronous job execution with status tracking
- **Security**: Parameter validation, sanitization, and sandboxed execution
- **Comprehensive Logging**: Structured logging with multiple handlers

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Start Redis server:
```bash
redis-server
```

3. Start Celery worker (optional, for background tasks):
```bash
celery -A celery_app worker --loglevel=info
```

4. Start the Flask application:
```bash
python app.py
```

## API Endpoints

### Authentication

#### POST /api/auth/login
Login with email and password.

Request:
```json
{
  "email": "test@example.com",
  "password": "test123"
}
```

Response:
```json
{
  "access_token": "jwt_token",
  "user": {"email": "test@example.com"}
}
```

### Scripts

#### GET /api/scripts
Get all available scripts organized by category.

Response:
```json
{
  "data_import": [...],
  "data_processing": [...],
  "shopify": [...],
  "maintenance": [...]
}
```

#### GET /api/scripts/{script_name}
Get details for a specific script.

#### POST /api/scripts/execute
Execute a script with parameters.

Request:
```json
{
  "script_name": "filter_products",
  "parameters": [
    {
      "name": "input_file",
      "value": "/path/to/file.csv",
      "type": "file"
    }
  ]
}
```

Response:
```json
{
  "job_id": "uuid",
  "message": "Job created successfully"
}
```

### Jobs

#### GET /api/jobs
Get all jobs for the current user.

#### GET /api/jobs/{job_id}
Get status of a specific job.

#### POST /api/jobs/{job_id}/cancel
Cancel a running job.

#### GET /api/jobs/{job_id}/logs
Download log file for a job.

### WebSocket Events

Connect to the WebSocket endpoint to receive real-time updates.

#### Client Events

- `subscribe_job`: Subscribe to job updates
  ```json
  {"job_id": "uuid"}
  ```

- `unsubscribe_job`: Unsubscribe from job updates
  ```json
  {"job_id": "uuid"}
  ```

#### Server Events

- `job_output`: Real-time log output
  ```json
  {
    "job_id": "uuid",
    "line": "Processing product 1 of 100..."
  }
  ```

- `job_progress`: Progress updates
  ```json
  {
    "job_id": "uuid",
    "progress": 50
  }
  ```

- `job_completed`: Job completion notification
- `job_failed`: Job failure notification

## Security Features

1. **Parameter Validation**: All script parameters are validated for type and constraints
2. **Path Traversal Protection**: File paths are sanitized to prevent directory traversal
3. **SQL Injection Prevention**: String parameters are checked for SQL patterns
4. **Resource Limits**: Scripts run with CPU and memory limits
5. **Sandboxed Environment**: Scripts execute with limited environment variables

## Logging

Logs are stored in multiple formats:
- `logs/app.log`: Application logs (rotated)
- `logs/app.json.log`: Structured JSON logs
- `logs/errors.log`: Error logs only
- `logs/jobs/{job_id}.log`: Individual job logs

## Available Scripts

### Data Import
- `ftp_download`: Download data from FTP server

### Data Processing
- `filter_products`: Filter products against reference data
- `create_metafields`: Generate Shopify metafields
- `categorize_products`: Auto-categorize products

### Shopify Operations
- `shopify_upload`: Upload products to Shopify

### Maintenance
- `cleanup_duplicates`: Remove duplicate images

### Workflows
- `full_import`: Complete import workflow

## Development

### Running Tests
```bash
pytest tests/
```

### Adding New Scripts

1. Add script definition to `script_registry.py`
2. Define parameter validation rules
3. Update script mapping in `job_manager.py`

### Monitoring

Monitor job execution:
```bash
celery -A celery_app flower
```

Access Flower dashboard at http://localhost:5555