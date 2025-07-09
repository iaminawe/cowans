# Deployment and Usage Guide

## 🎯 Current Status: Fully Functional Dashboard
All major issues have been resolved. The system now features:
- ✅ Modern React TypeScript frontend with 8 functional tabs
- ✅ Flask API backend with Supabase PostgreSQL integration  
- ✅ Fixed API routing issues (no more double prefixes or 308 redirects)
- ✅ Enhanced admin features with user management
- ✅ AI-powered icon generation with collection assignment
- ✅ Real-time monitoring and WebSocket integration

## Table of Contents
1. [Quick Start](#quick-start)
2. [System Requirements](#system-requirements)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [Running the Application](#running-the-application)
6. [Dashboard Features](#dashboard-features)
7. [API Documentation](#api-documentation)
8. [Troubleshooting](#troubleshooting)
9. [Production Deployment](#production-deployment)

## Quick Start

### 🚀 Fastest Way to Get Started
```bash
# 1. Start the unified dashboard
./start_dashboard_unified.sh

# 2. Access the dashboard
# Frontend: http://localhost:3055
# Backend API: http://localhost:3560

# 3. Login with admin user
# Email: gregg@iaminawe.com
# Password: [Your Supabase password]
```

## System Requirements

### Minimum Requirements
- **Python 3.8+** (Backend Flask API)
- **Node.js 14+** (Frontend React TypeScript)
- **Supabase Account** (PostgreSQL database + authentication)
- **4GB RAM minimum**
- **10GB disk space**

### Required Services
- **Supabase** (PostgreSQL database and auth)
- **OpenAI API** (optional, for AI icon generation)
- **Shopify Store** (for product synchronization)
- **Redis** (optional, for background job processing)

### Software Dependencies
- **Git** (version control)
- **pip** (Python package manager)
- **npm** (Node package manager)
- **curl** (for API testing)

## Installation

### 1. Clone the Repository
```bash
git clone <repository-url>
cd cowans
```

### 2. Set Up Python Environment
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt
pip install -r web_dashboard/backend/requirements.txt
```

### 3. Set Up Frontend
```bash
cd frontend
npm install
cd ..
```

### 4. Install Redis (if not already installed)
```bash
# macOS:
brew install redis

# Ubuntu/Debian:
sudo apt-get install redis-server

# Start Redis
redis-server
```

## Configuration

### 1. Create Environment File
Create a `.env` file in the project root:

```bash
# FTP Configuration
FTP_HOST=your_ftp_host
FTP_USERNAME=your_ftp_username
FTP_PASSWORD=your_ftp_password

# Shopify Configuration
SHOPIFY_SHOP_URL=your-shop.myshopify.com
SHOPIFY_ACCESS_TOKEN=your_shopify_access_token

# Security
JWT_SECRET_KEY=your_secret_key_here

# Redis (optional, defaults to localhost)
REDIS_URL=redis://localhost:6379/0
```

### 2. Configure Data Paths
Ensure these directories exist:
```bash
mkdir -p data
mkdir -p web_dashboard/backend/logs
```

## Running the Application

### Development Mode

#### 1. Start Backend Server
```bash
cd web_dashboard/backend
python app.py
```
The backend will run on http://localhost:5000

#### 2. Start Frontend Development Server
In a new terminal:
```bash
cd frontend
npm start
```
The frontend will run on http://localhost:3000

#### 3. Start Redis (if not running)
```bash
redis-server
```

### Quick Start Script
Create a `start-dev.sh` script:
```bash
#!/bin/bash
# Start Redis
redis-server --daemonize yes

# Start Backend
cd web_dashboard/backend
python app.py &
BACKEND_PID=$!

# Start Frontend
cd ../../frontend
npm start &
FRONTEND_PID=$!

echo "Backend PID: $BACKEND_PID"
echo "Frontend PID: $FRONTEND_PID"
echo "Press Ctrl+C to stop all services"

# Wait for interrupt
trap "kill $BACKEND_PID $FRONTEND_PID; redis-cli shutdown" INT
wait
```

## Using the Dashboard

### 1. Login
- Navigate to http://localhost:3000
- Use default credentials:
  - Email: test@example.com
  - Password: test123

### 2. Dashboard Features

#### Sync Control
- **Manual Sync**: Click "Sync Now" to trigger immediate synchronization
- **View History**: See past sync operations in the log viewer
- **Filter Logs**: Use status filters (All, Success, Error, Running)
- **Search Logs**: Search through log messages

#### Script Execution
Available scripts from the dashboard:
- **Full Import**: Complete workflow from FTP download to Shopify upload
- **FTP Download**: Download latest files from Etilize
- **Filter Products**: Filter products against reference data
- **Create Metafields**: Generate Shopify metafields
- **Upload to Shopify**: Upload processed data to Shopify
- **Cleanup Duplicates**: Remove duplicate images/products

### 3. Real-time Updates
- Progress bars show current operation status
- Live log streaming displays script output
- Stage indicators show current processing phase

## Script Usage

### Command Line Interface

#### Full Import Workflow
```bash
python scripts/run_import.py

# Skip specific stages
python scripts/run_import.py --skip-download --skip-filter

# Debug mode
python scripts/run_import.py --debug

# No sound notifications
python scripts/run_import.py --no-sound
```

#### Individual Scripts

##### FTP Download
```bash
python scripts/utilities/ftp_downloader.py
```

##### Filter Products
```bash
python scripts/data_processing/filter_products.py input.csv reference.csv --output filtered.csv
```

##### Create Metafields
```bash
python scripts/data_processing/create_metafields.py input.csv --output output.csv
```

##### Upload to Shopify
```bash
python scripts/shopify/shopify_uploader_new.py data.csv \
    --shop-url your-shop.myshopify.com \
    --access-token your_token

# Fast upload (skip images)
python scripts/shopify/shopify_uploader_new.py data.csv \
    --shop-url your-shop.myshopify.com \
    --access-token your_token \
    --skip-images
```

##### Cleanup Operations
```bash
# Remove duplicate images
python scripts/cleanup/cleanup_duplicate_images.py \
    --shop-url your-shop.myshopify.com \
    --access-token your_token

# Remove size-based duplicates
python scripts/cleanup/cleanup_size_duplicates.py \
    --shop-url your-shop.myshopify.com \
    --access-token your_token
```

## Troubleshooting

### Common Issues

#### 1. Backend Won't Start
- Check if port 5000 is already in use: `lsof -i :5000`
- Verify Redis is running: `redis-cli ping`
- Check Python dependencies: `pip list`

#### 2. Frontend Build Errors
- Clear npm cache: `npm cache clean --force`
- Delete node_modules and reinstall: `rm -rf node_modules && npm install`
- Check Node version: `node --version` (should be 14+)

#### 3. Authentication Issues
- Verify JWT_SECRET_KEY is set in .env
- Check token expiration settings
- Clear browser localStorage

#### 4. Script Execution Failures
- Check file permissions
- Verify CSV file formats
- Check environment variables
- Review logs in `web_dashboard/backend/logs/`

#### 5. FTP Connection Issues
- Verify FTP credentials in .env
- Check network connectivity
- Test with FTP client: `ftp your_ftp_host`

### Debug Mode
Enable debug logging:
```bash
# For scripts
python scripts/run_import.py --debug

# For Flask
export FLASK_ENV=development
python app.py
```

## Production Deployment

### 1. Build Frontend
```bash
cd frontend
npm run build
```

### 2. Set Up Production Server

#### Using Gunicorn (recommended)
```bash
pip install gunicorn
cd web_dashboard/backend
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

#### Using systemd Service
Create `/etc/systemd/system/cowans-backend.service`:
```ini
[Unit]
Description=Cowans Backend Service
After=network.target redis.service

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/cowans/web_dashboard/backend
Environment="PATH=/path/to/cowans/venv/bin"
ExecStart=/path/to/cowans/venv/bin/gunicorn -w 4 -b 0.0.0.0:5000 app:app
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable cowans-backend
sudo systemctl start cowans-backend
```

### 3. Nginx Configuration
```nginx
server {
    listen 80;
    server_name your-domain.com;

    # Frontend
    location / {
        root /path/to/cowans/frontend/dist;
        try_files $uri /index.html;
    }

    # Backend API
    location /api {
        proxy_pass http://localhost:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # WebSocket support
    location /socket.io {
        proxy_pass http://localhost:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### 4. Environment Variables
For production, use a secure method to manage environment variables:
- Use a secrets management service
- Or create a secure .env file with restricted permissions:
```bash
chmod 600 .env
```

### 5. Monitoring
Set up monitoring for:
- Application logs: `/var/log/cowans/`
- System resources: CPU, memory, disk
- Redis status
- API response times
- Error rates

### 6. Backup Strategy
- Database backups (if using)
- Configuration backups
- Data file backups
- Log rotation

## Security Best Practices

1. **Use HTTPS in production**
2. **Secure environment variables**
3. **Implement rate limiting**
4. **Regular security updates**
5. **Monitor for suspicious activity**
6. **Use strong JWT secrets**
7. **Implement proper CORS policies**

## Maintenance

### Regular Tasks
1. Clear old job logs: `find web_dashboard/backend/logs -mtime +7 -delete`
2. Update dependencies: `pip install --upgrade -r requirements.txt`
3. Monitor disk space
4. Check Redis memory usage
5. Review error logs

### Updating the Application
```bash
# Pull latest changes
git pull origin main

# Update dependencies
pip install -r requirements.txt
cd frontend && npm install && cd ..

# Rebuild frontend
cd frontend && npm run build && cd ..

# Restart services
sudo systemctl restart cowans-backend
```

## Support

For issues or questions:
1. Check the logs first
2. Review this documentation
3. Check the GitHub issues
4. Contact the development team

---
Last Updated: January 2025