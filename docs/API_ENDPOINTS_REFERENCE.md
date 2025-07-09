# API Endpoints Reference

## 🌐 Base URL
- **Development**: `http://localhost:3560/api`
- **Authentication**: Supabase JWT tokens required for all endpoints

## 🔐 Authentication

### Login
```http
POST /api/auth/login
Content-Type: application/json

{
  "email": "gregg@iaminawe.com",
  "password": "your-password"
}
```

**Response**:
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh_token": "...",
  "user": {
    "id": 1,
    "email": "gregg@iaminawe.com",
    "first_name": "Gregg",
    "last_name": "Admin",
    "is_admin": true
  }
}
```

### Get Current User
```http
GET /api/auth/me
Authorization: Bearer {access_token}
```

## 👥 Admin API (Admin Only)

### Get Admin Dashboard Data
```http
GET /api/admin/dashboard
Authorization: Bearer {access_token}
```

**Response**:
```json
{
  "users": {
    "total": 5,
    "active": 4,
    "admins": 1,
    "recent_signups": 2
  },
  "system": {
    "database_size": "45.2 MB",
    "cache_hit_rate": 94.5,
    "avg_response_time": 125,
    "uptime_percentage": 99.8
  },
  "jobs": {
    "total": 150,
    "running": 2,
    "completed": 145,
    "failed": 3
  }
}
```

### Get Users List
```http
GET /api/admin/users
Authorization: Bearer {access_token}
```

### Update User
```http
PUT /api/admin/users/{user_id}
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "is_admin": true,
  "is_active": true
}
```

## 📚 Collections API

### Get Collections
```http
GET /api/collections
Authorization: Bearer {access_token}
```

**Query Parameters**:
- `status` (optional): Filter by status
- `include_archived` (optional): Include archived collections

**Response**:
```json
{
  "collections": [
    {
      "id": 1,
      "name": "Art Supplies",
      "handle": "art-supplies",
      "description": "Professional art supplies and materials",
      "products_count": 45,
      "status": "active",
      "shopify_collection_id": "gid://shopify/Collection/123456789"
    }
  ],
  "total": 1
}
```

### Create Collection
```http
POST /api/collections/create
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "name": "New Collection",
  "handle": "new-collection",
  "description": "Collection description",
  "status": "active"
}
```

## 🎨 Icons API (Admin Only)

### Generate Single Icon
```http
POST /api/icons/generate
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "category": "office supplies",
  "style": "modern",
  "color_scheme": "brand_colors",
  "custom_elements": ["professional", "clean"]
}
```

**Response**:
```json
{
  "success": true,
  "image_url": "http://localhost:3560/api/images/office_supplies_20250708_123456_abc123.png",
  "local_path": "data/generated_icons/office_supplies/office_supplies_20250708_123456_abc123.png",
  "generation_time": 3.2,
  "metadata": {
    "style": "modern",
    "color_scheme": "brand_colors",
    "model": "dall-e-3"
  }
}
```

### Start Batch Icon Generation
```http
POST /api/icons/generate/batch
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "categories": ["office supplies", "art supplies", "electronics"],
  "style": "modern",
  "color_scheme": "brand_colors",
  "variations_per_category": 1
}
```

**Response**:
```json
{
  "message": "Batch generation started",
  "batch_id": "batch_20250708_123456_xyz789"
}
```

### Get Batch Status
```http
GET /api/icons/batch/{batch_id}/status
Authorization: Bearer {access_token}
```

**Response**:
```json
{
  "batch_id": "batch_20250708_123456_xyz789",
  "status": "running",
  "progress": 66.7,
  "current_category": "electronics",
  "total_categories": 3,
  "completed_categories": 2,
  "estimated_completion": "2025-07-08T12:45:00Z",
  "created_at": "2025-07-08T12:30:00Z",
  "started_at": "2025-07-08T12:30:15Z"
}
```

### List User's Batch Jobs
```http
GET /api/icons/batches
Authorization: Bearer {access_token}
```

**Response**:
```json
[
  {
    "batch_id": "batch_20250708_123456_xyz789",
    "status": "completed",
    "progress": 100,
    "total_categories": 3,
    "completed_categories": 3,
    "created_at": "2025-07-08T12:30:00Z",
    "completed_at": "2025-07-08T12:35:00Z"
  }
]
```

### Get Cached Icons
```http
GET /api/icons/cached
Authorization: Bearer {access_token}
```

**Query Parameters**:
- `category` (optional): Filter by category

## 📦 Products API

### Get Syncable Products
```http
GET /api/shopify/products/syncable
Authorization: Bearer {access_token}
```

**Query Parameters**:
- `import_batch_id` (optional): Filter by import batch
- `category` (optional): Filter by category
- `status` (optional): Filter by status
- `limit` (optional): Limit results (default: 50)
- `offset` (optional): Offset for pagination

## 📝 Sync History API

### Get Sync History
```http
GET /api/sync/history
Authorization: Bearer {access_token}
```

**Response**:
```json
[
  {
    "id": "sync_123",
    "timestamp": "2025-07-08T12:00:00Z",
    "status": "success",
    "message": "Products synchronized successfully",
    "details": "150 products updated, 5 new products added"
  }
]
```

## 🔧 Health Check

### Check API Health
```http
GET /api/health
```

**Response**:
```json
{
  "status": "healthy",
  "timestamp": "2025-07-08T12:00:00Z",
  "database": "connected",
  "version": "1.0.0"
}
```

## ❌ Error Responses

### Common Error Codes
- **400**: Bad Request - Invalid request data
- **401**: Unauthorized - Missing or invalid authentication
- **403**: Forbidden - Insufficient permissions
- **404**: Not Found - Resource doesn't exist
- **500**: Internal Server Error - Server-side error

### Error Response Format
```json
{
  "error": "Invalid or expired token",
  "message": "Authentication required",
  "timestamp": "2025-07-08T12:00:00Z"
}
```

## 🔐 Authentication Headers

All protected endpoints require the Authorization header:
```http
Authorization: Bearer {your_jwt_token}
```

The JWT token is obtained from the `/api/auth/login` endpoint and should be included in all subsequent requests.

## 🚀 Recent Fixes Applied

1. **Fixed Double API Prefix**: All endpoints now correctly respond to single `/api/` prefix
2. **Resolved 308 Redirects**: Collections API supports both `/api/collections` and `/api/collections/`
3. **Updated Authentication**: All endpoints now use Supabase JWT authentication
4. **Enhanced Error Handling**: Consistent error response format across all endpoints
5. **Improved Validation**: Better request validation and error messages

---

**Note**: All endpoints are fully functional and tested. The API is ready for production use with proper authentication and error handling.