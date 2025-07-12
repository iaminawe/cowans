# Cowan's Product Management System

A comprehensive Shopify integration system with modern web dashboard for product management, synchronization, and automation. Features React TypeScript frontend, Flask API backend, Supabase authentication, and AI-powered icon generation.

## 🚀 Quick Start

### Prerequisites
- **Supabase Account**: This application requires Supabase for authentication and database
- **Docker & Docker Compose**: For containerized deployment
- **Environment Variables**: Copy `.env.example` to `.env` and configure

### Start the Application

```bash
# 1. Configure your Supabase credentials
cp .env.example .env
# Edit .env with your Supabase URL and keys

# 2. Start with Docker Compose
docker-compose up -d

# Or use the unified script (for local development)
./start_dashboard_unified.sh
```

The dashboard will be available at:
- **Frontend**: http://localhost:3055
- **Backend API**: http://localhost:3560

## 🔑 Default Login
- **Email**: gregg@iaminawe.com
- **Password**: [Your Supabase password]

## 📁 Project Structure

```
cowans/
├── web_dashboard/              # Main web application
│   └── backend/               # Flask API backend (Supabase PostgreSQL)
├── frontend/                  # React TypeScript frontend
├── start_dashboard_unified.sh # ← START HERE! (Unified launcher)
├── scripts/                   # Data processing scripts
│   ├── shopify/              # Shopify integration
│   ├── data_processing/      # Data transformation
│   └── utilities/            # Helper utilities
├── data/                     # Data files (CSV, etc.)
├── collection_images/        # AI-generated collection icons
├── docs/                     # Comprehensive documentation
├── .env.example              # Environment template
└── archived_*/               # Archived old files
```

## 🔑 Key Features

### 🎯 **Modern Web Dashboard**
- **Frontend**: React 18 + TypeScript + Tailwind CSS + shadcn/ui
- **Backend**: Flask API + SQLAlchemy + Supabase PostgreSQL
- **Authentication**: Supabase Auth with JWT tokens
- **Real-time**: WebSocket integration for live monitoring

### 🛍️ **Shopify Integration**
- Full product catalog synchronization
- Collection management and organization
- Batch processing for large catalogs
- Real-time sync status monitoring

### 🤖 **AI-Powered Features**
- **Icon Generation**: OpenAI DALL-E integration for category icons
- **Collection Assignment**: Assign generated icons to collections
- **Batch Generation**: Generate multiple icons simultaneously

### 👥 **Admin Features**
- User management and role-based access
- System statistics and monitoring
- Job queue management
- Performance analytics

## 📋 Prerequisites

- **Python 3.8+** (for backend)
- **Node.js 14+** (for frontend)
- **Supabase Account** (for PostgreSQL database and auth)
- **OpenAI API Key** (optional, for AI icon generation)
- **Redis** (optional, for background tasks)
- **Shopify Store** (for product sync)

## 🎛️ Dashboard Features (8 Navigation Tabs)

### 📊 **Dashboard** - Overview & Controls
- System status and sync triggers
- Real-time sync history monitoring
- Quick access to all functions

### 🔧 **Scripts** - Automation & Execution  
- Execute data processing scripts
- Monitor script progress and logs
- Batch operations management

### 📋 **Logs** - Real-time Monitoring
- Live system activity monitoring
- WebSocket-powered real-time updates
- Error tracking and debugging

### 📦 **Products** - Product Management
- Searchable product listings with filters
- Product creation and editing
- Shopify sync status tracking
- Bulk operations support

### 📚 **Collections** - Collection Management
- Collection hierarchy organization
- Product-to-collection assignments
- Automated collection creation
- SEO and metadata management

### 🏷️ **Categories** - Category Management *(Admin Only)*
- Category hierarchy management
- Icon assignments to categories
- Bulk category operations

### 🎨 **Icons** - AI Icon Generation *(Admin Only)*
- OpenAI DALL-E powered icon generation
- Single and batch icon creation
- Icon library management
- Assign icons to collections
- Real-time generation progress

### 👥 **Admin** - System Administration *(Admin Only)*
- User management and permissions
- System statistics and metrics
- Job queue monitoring
- Performance analytics

## 🛠️ Configuration

### 1. Environment Setup
```bash
# Copy environment template
cp .env.example .env
```

### 2. Update .env with your credentials:
```bash
# Supabase Configuration
SUPABASE_URL=your-supabase-url
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-key
SUPABASE_DB_PASSWORD=your-db-password

# Shopify Configuration  
SHOPIFY_STORE_URL=your-store.myshopify.com
SHOPIFY_ACCESS_TOKEN=your-access-token

# OpenAI Configuration (for AI icon generation)
OPENAI_API_KEY=your-openai-key

# Optional: Redis (for background tasks)
REDIS_URL=redis://localhost:6379
```

## 🔧 Recent Fixes & Improvements

### ✅ **API Issues Resolved**
- **Fixed double API prefix bug** (`/api/api/...` → `/api/...`)
- **Resolved Collections 308 redirect** (now supports both `/api/collections` and `/api/collections/`)
- **Updated to Supabase authentication** (replaced insecure JWT bypass)

### ✅ **Frontend Enhancements**
- **Enhanced Products view** with ProductsTableView for actual product listings
- **Added icon-to-collection assignment** in AI icon generator
- **Fixed admin dashboard data loading** (users, jobs, statistics)
- **All 8 navigation tabs now fully functional**

### ✅ **Authentication & Security**
- **Supabase JWT authentication** fully implemented
- **Admin user created**: `gregg@iaminawe.com`
- **Role-based access control** for admin features

## 📚 Documentation

- **Deployment Guide**: `docs/DEPLOYMENT_GUIDE.md`
- **API Documentation**: Available at http://localhost:3560/api/docs
- **Supabase Auth Guide**: `SUPABASE_AUTH_COMPLETE_GUIDE.md`
- **Shopify API Integration**: `docs/SHOPIFY_API_FUTURE_IDEAS.md`
- **Script Usage**: `scripts/README.md`

## 🧪 Testing

```bash
# Backend tests
cd web_dashboard/backend
pytest

# Frontend tests
cd frontend
npm test
```

## 🔍 Troubleshooting

### Dashboard Won't Load
1. Check if both services are running: `./start_dashboard_unified.sh`
2. Verify ports 3055 (frontend) and 3560 (backend) are free
3. Check logs: `logs/frontend.log` and `logs/backend.log`

### Authentication Issues
1. Verify Supabase credentials in `.env`
2. Check if user exists: `gregg@iaminawe.com`
3. Ensure proper Supabase schema is applied

### Database Connection Issues (IPv6/Network Unreachable)
If you see errors like "Network is unreachable" or IPv6 connection failures:

1. **Use Connection Pooler** (Recommended):
   - The app defaults to using Supabase's connection pooler
   - This avoids IPv6 issues in Docker containers
   
2. **Set Custom Database URL**:
   - Go to Supabase Dashboard > Settings > Database
   - Copy the "Connection pooling" connection string
   - Add to `.env`: `SUPABASE_DB_URL=your-pooler-connection-string`
   
3. **Force IPv4 Connection**:
   - Ensure `SUPABASE_USE_POOLER=true` in `.env` (default)
   - This uses the pooler which only uses IPv4

4. **Alternative Solutions**:
   - Add `--add-host=host.docker.internal:host-gateway` to docker run
   - Use Docker network in host mode (not recommended for production)

### API Errors
- **404 errors**: Check for double `/api/` prefixes in frontend calls
- **308 redirects**: Fixed in collections API (both routes supported)
- **401 errors**: Authentication required (login with valid user)

## 🤝 Development

### Backend Development
```bash
cd web_dashboard/backend
source venv/bin/activate
python app.py
```

### Frontend Development  
```bash
cd frontend
npm start
```

### Full Stack Development
```bash
./start_dashboard_unified.sh
```

## 🚀 Production Deployment

See `docs/DEPLOYMENT_GUIDE.md` for comprehensive deployment instructions including:
- Docker deployment
- Supabase configuration
- Environment setup
- Security considerations

---

**🎯 System Status: All major issues resolved. Dashboard fully functional with 8 working tabs, Supabase authentication, and enhanced features.**