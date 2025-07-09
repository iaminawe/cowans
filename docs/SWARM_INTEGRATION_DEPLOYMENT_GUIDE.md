# SWARM Integration Deployment Guide

## Table of Contents
1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [Prerequisites](#prerequisites)
4. [Installation and Setup](#installation-and-setup)
5. [Configuration](#configuration)
6. [Testing and Validation](#testing-and-validation)
7. [Monitoring and Alerting](#monitoring-and-alerting)
8. [Deployment Procedures](#deployment-procedures)
9. [Troubleshooting](#troubleshooting)
10. [Maintenance and Updates](#maintenance-and-updates)

## Overview

This guide provides comprehensive instructions for deploying the SWARM (Systematic Parallel Agent Resource Coordination) integration system for the Cowan's Product Feed Integration dashboard. The system coordinates multiple agents for complex task execution with real-time monitoring and centralized memory management.

### Key Components
- **SPARC Orchestrator**: Coordinates parallel agent execution
- **Memory Coordinator**: Manages distributed session state and shared context
- **Integration Test Suite**: Comprehensive testing framework
- **Performance Monitor**: Real-time system monitoring
- **Error Handler**: Robust error detection and recovery

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Frontend Dashboard (React)                    │
├─────────────────────────────────────────────────────────────────┤
│                     WebSocket Layer                              │
├─────────────────────────────────────────────────────────────────┤
│                 Backend API (Flask)                              │
├─────────────────────────────────────────────────────────────────┤
│     SPARC Orchestrator    │    Memory Coordinator               │
├─────────────────────────────────────────────────────────────────┤
│                        Redis Cache                               │
├─────────────────────────────────────────────────────────────────┤
│              Product Processing Scripts                          │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow
1. UI triggers operations via REST API
2. Backend creates SPARC sessions with tasks
3. SPARC Orchestrator assigns tasks to agents
4. Memory Coordinator manages shared state
5. Progress updates flow back via WebSocket
6. Results are logged and stored

## Prerequisites

### System Requirements
- **Operating System**: Linux (Ubuntu 20.04+), macOS (10.15+), or Windows 10+
- **Python**: 3.8 or higher
- **Node.js**: 16.0 or higher
- **Redis**: 6.0 or higher
- **Memory**: Minimum 4GB RAM (8GB recommended for production)
- **Storage**: 10GB free space
- **Network**: Outbound internet access for API calls

### Dependencies
- Docker (optional but recommended)
- Git
- Chrome/Chromium (for end-to-end testing)

### Account Requirements
- Shopify API access tokens
- FTP credentials for product data
- Supabase account (for production authentication)

## Installation and Setup

### 1. Repository Setup

```bash
# Clone the repository
git clone <repository-url>
cd cowans

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt
pip install -r web_dashboard/backend/requirements.txt
```

### 2. Frontend Setup

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Build for production (optional)
npm run build
```

### 3. Redis Setup

#### Option A: Docker (Recommended)
```bash
# Start Redis container
docker run -d --name redis-cowans -p 6379:6379 redis:6-alpine

# Verify Redis is running
docker ps | grep redis
```

#### Option B: Native Installation
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install redis-server

# macOS
brew install redis
brew services start redis

# Verify installation
redis-cli ping
```

### 4. Environment Configuration

Create `.env` file in the project root:

```env
# Flask Configuration
FLASK_ENV=production
SECRET_KEY=your-super-secret-key-here
JWT_SECRET_KEY=jwt-secret-key-here

# Redis Configuration
REDIS_URL=redis://localhost:6379/0

# Shopify Configuration
SHOPIFY_SHOP_URL=your-shop.myshopify.com
SHOPIFY_ACCESS_TOKEN=your-access-token

# FTP Configuration
FTP_HOST=ftp.etilize.com
FTP_USERNAME=your-username
FTP_PASSWORD=your-password

# Database Configuration (if using external database)
DATABASE_URL=postgresql://user:password@localhost/cowans

# SPARC Configuration
SPARC_MAX_AGENTS=10
SPARC_SESSION_TIMEOUT=3600
SPARC_TASK_TIMEOUT=600

# Monitoring Configuration
ENABLE_MONITORING=true
MONITORING_INTERVAL=30
LOG_LEVEL=INFO
```

### 5. Database Setup (Optional)

```bash
# If using PostgreSQL for persistent storage
sudo apt install postgresql postgresql-contrib
sudo -u postgres createdb cowans
sudo -u postgres createuser cowans_user

# Run database migrations (if applicable)
python manage.py migrate
```

## Configuration

### SPARC Orchestrator Configuration

Edit `scripts/orchestration/sparc_orchestrator.py` configuration:

```python
# Default configuration in _load_default_config()
{
    "max_workers": 10,              # Maximum parallel workers
    "max_sessions": 100,            # Maximum concurrent sessions
    "session_timeout": 3600,        # Session timeout in seconds
    "task_timeout": 600,            # Task timeout in seconds
    "heartbeat_interval": 30,       # Agent heartbeat interval
    "cleanup_interval": 300,        # Cleanup interval
    "websocket_port": 8765,         # WebSocket port
    "enable_performance_monitoring": True,
    "retry_policy": "exponential",
    "max_retries": 3
}
```

### Memory Coordinator Configuration

Edit `scripts/orchestration/sparc_memory.py` configuration:

```python
# Initialize with custom settings
memory_coordinator = SPARCMemoryCoordinator(
    redis_client=redis_client,
    namespace="production_sparc",
    event_ttl=3600,        # Event time-to-live
    session_ttl=7200       # Session time-to-live
)
```

### Backend API Configuration

Edit `web_dashboard/backend/config.py`:

```python
class ProductionConfig:
    SECRET_KEY = os.environ.get('SECRET_KEY')
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY')
    REDIS_URL = os.environ.get('REDIS_URL')
    
    # Security settings
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    CORS_ORIGINS = ["https://yourdomain.com"]
    
    # Performance settings
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max upload
    
    # Logging
    LOG_PATH = '/var/log/cowans'
    LOG_LEVEL = 'INFO'
```

### Frontend Configuration

Edit `frontend/src/lib/api.ts`:

```typescript
const config = {
  apiBaseUrl: process.env.REACT_APP_API_BASE_URL || 'http://localhost:3560',
  websocketUrl: process.env.REACT_APP_WS_URL || 'ws://localhost:3560',
  enableDebugLogs: process.env.NODE_ENV === 'development',
  requestTimeout: 30000,
  retryAttempts: 3
};
```

## Testing and Validation

### 1. Integration Test Suite

Run comprehensive integration tests:

```bash
# Navigate to test directory
cd tests/integration

# Run all integration tests
python swarm_test_runner.py --parallel --max-workers 4

# Run specific test suites
python swarm_test_runner.py --suites orchestration memory api

# Generate detailed reports
python swarm_test_runner.py --output-dir ./reports --verbose
```

### 2. API Integration Validation

```bash
# Test API integrations
python api_integration_validator.py --base-url http://localhost:3560

# Test with custom endpoints
python api_integration_validator.py --base-url https://your-domain.com --verbose
```

### 3. End-to-End Workflow Testing

```bash
# Test complete workflows
python e2e_workflow_tester.py --headless

# Test specific workflow
python e2e_workflow_tester.py --workflow full_sync_workflow

# Test with visible browser (for debugging)
python e2e_workflow_tester.py --headless=false
```

### 4. Error Handling Validation

```bash
# Test error handling and recovery
python error_handling_validator.py

# Test specific error types
python error_handling_validator.py --test-type system_failure
```

### 5. Performance and Reliability Testing

```bash
# Run performance tests
python performance_reliability_tester.py --test-type all

# Load testing only
python performance_reliability_tester.py --test-type load

# Reliability testing only
python performance_reliability_tester.py --test-type reliability
```

### Test Reports

All tests generate detailed reports:
- HTML reports for visual inspection
- JSON reports for CI/CD integration
- JUnit XML for Jenkins/other CI systems

Example test execution:

```bash
# Generate comprehensive test reports
python swarm_test_runner.py --output-dir ./test_reports --parallel

# View HTML report
open test_reports/test_report_*.html
```

## Monitoring and Alerting

### 1. System Monitoring Setup

Create monitoring configuration file `monitoring/config.yaml`:

```yaml
monitoring:
  enabled: true
  interval: 30
  metrics:
    - cpu_usage
    - memory_usage
    - disk_usage
    - network_io
    - redis_metrics
    - application_metrics

alerts:
  cpu_threshold: 80
  memory_threshold: 85
  disk_threshold: 90
  error_rate_threshold: 5
  response_time_threshold: 5000

notifications:
  email:
    enabled: true
    smtp_server: smtp.gmail.com
    recipients: ["admin@yourcompany.com"]
  slack:
    enabled: false
    webhook_url: ""
```

### 2. Application Monitoring

Create monitoring script `monitoring/system_monitor.py`:

```python
#!/usr/bin/env python3
"""
System monitoring for SWARM integration
"""

import time
import psutil
import requests
import logging
from datetime import datetime

class SystemMonitor:
    def __init__(self, config_file="config.yaml"):
        self.config = self.load_config(config_file)
        self.logger = self.setup_logging()
        
    def monitor_system(self):
        """Monitor system metrics"""
        while True:
            try:
                metrics = self.collect_metrics()
                self.check_alerts(metrics)
                self.log_metrics(metrics)
                
                time.sleep(self.config['monitoring']['interval'])
                
            except Exception as e:
                self.logger.error(f"Monitoring error: {e}")
                time.sleep(60)
    
    def collect_metrics(self):
        """Collect system metrics"""
        return {
            'timestamp': datetime.now().isoformat(),
            'cpu_percent': psutil.cpu_percent(),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_percent': psutil.disk_usage('/').percent,
            'redis_status': self.check_redis_health(),
            'api_status': self.check_api_health(),
            'sparc_status': self.check_sparc_health()
        }
    
    def check_redis_health(self):
        """Check Redis health"""
        try:
            import redis
            r = redis.from_url(os.environ.get('REDIS_URL', 'redis://localhost:6379/0'))
            r.ping()
            return 'healthy'
        except:
            return 'unhealthy'
    
    def check_api_health(self):
        """Check API health"""
        try:
            response = requests.get('http://localhost:3560/api/health', timeout=5)
            return 'healthy' if response.status_code == 200 else 'unhealthy'
        except:
            return 'unhealthy'
    
    def check_sparc_health(self):
        """Check SPARC orchestrator health"""
        # Implementation depends on your SPARC monitoring endpoints
        return 'healthy'  # Placeholder

if __name__ == "__main__":
    monitor = SystemMonitor()
    monitor.monitor_system()
```

### 3. Log Management

Configure log rotation in `/etc/logrotate.d/cowans`:

```
/var/log/cowans/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    sharedscripts
    postrotate
        systemctl reload cowans-backend
    endscript
}
```

### 4. Health Check Endpoints

The system provides health check endpoints:

- `GET /api/health` - Overall system health
- `GET /api/health/redis` - Redis connectivity
- `GET /api/health/sparc` - SPARC orchestrator status
- `GET /api/health/detailed` - Detailed component status

### 5. Metrics Collection

System exposes metrics at:
- `GET /api/metrics` - Prometheus-compatible metrics
- `GET /api/metrics/performance` - Performance metrics
- `GET /api/metrics/errors` - Error rates and patterns

## Deployment Procedures

### 1. Production Deployment with Docker

Create `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  redis:
    image: redis:6-alpine
    restart: unless-stopped
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    command: redis-server --appendonly yes

  backend:
    build:
      context: .
      dockerfile: Dockerfile.backend
    restart: unless-stopped
    depends_on:
      - redis
    environment:
      - FLASK_ENV=production
      - REDIS_URL=redis://redis:6379/0
    env_file:
      - .env.production
    ports:
      - "3560:3560"
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    restart: unless-stopped
    ports:
      - "3055:80"
    environment:
      - REACT_APP_API_BASE_URL=http://localhost:3560

  nginx:
    image: nginx:alpine
    restart: unless-stopped
    depends_on:
      - backend
      - frontend
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl

volumes:
  redis_data:
```

### 2. Deployment Script

Create `deploy.sh`:

```bash
#!/bin/bash
set -e

echo "Starting deployment..."

# Pull latest code
git pull origin main

# Backup current deployment
echo "Creating backup..."
docker-compose -f docker-compose.prod.yml down
tar -czf backup_$(date +%Y%m%d_%H%M%S).tar.gz data/ logs/

# Build and deploy
echo "Building containers..."
docker-compose -f docker-compose.prod.yml build

echo "Starting services..."
docker-compose -f docker-compose.prod.yml up -d

# Wait for services to be ready
echo "Waiting for services..."
sleep 30

# Run health checks
echo "Running health checks..."
python tests/integration/api_integration_validator.py --base-url http://localhost

# Run smoke tests
echo "Running smoke tests..."
python tests/integration/swarm_test_runner.py --suites api --parallel

echo "Deployment complete!"
```

### 3. Systemd Service (Alternative to Docker)

Create `/etc/systemd/system/cowans-backend.service`:

```ini
[Unit]
Description=Cowans SWARM Backend
After=network.target redis.service

[Service]
Type=simple
User=cowans
WorkingDirectory=/opt/cowans
Environment=FLASK_ENV=production
ExecStart=/opt/cowans/venv/bin/python web_dashboard/backend/app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable cowans-backend
sudo systemctl start cowans-backend
sudo systemctl status cowans-backend
```

### 4. Nginx Configuration

Create `/etc/nginx/sites-available/cowans`:

```nginx
upstream backend {
    server 127.0.0.1:3560;
}

upstream frontend {
    server 127.0.0.1:3055;
}

server {
    listen 80;
    server_name your-domain.com;
    
    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    ssl_certificate /etc/ssl/certs/your-domain.crt;
    ssl_certificate_key /etc/ssl/private/your-domain.key;
    
    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    
    # Frontend
    location / {
        proxy_pass http://frontend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    # Backend API
    location /api/ {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # WebSocket
    location /socket.io/ {
        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

## Troubleshooting

### Common Issues and Solutions

#### 1. Redis Connection Issues

**Problem**: `ConnectionError: Error connecting to Redis`

**Solutions**:
```bash
# Check Redis status
redis-cli ping

# Check Redis logs
docker logs redis-cowans

# Restart Redis
docker restart redis-cowans

# Check network connectivity
telnet localhost 6379
```

#### 2. SPARC Session Failures

**Problem**: Tasks stuck in "queued" status

**Solutions**:
```bash
# Check SPARC orchestrator status
python -c "
from scripts.orchestration.sparc_orchestrator import SPARCOrchestrator
orch = SPARCOrchestrator()
print(f'Active sessions: {len(orch.active_sessions)}')
"

# Clear stuck sessions
redis-cli FLUSHDB

# Restart backend service
sudo systemctl restart cowans-backend
```

#### 3. High Memory Usage

**Problem**: System consuming excessive memory

**Solutions**:
```bash
# Check memory usage by component
ps aux | grep python | sort -k4 -nr

# Monitor memory leaks
python tests/integration/performance_reliability_tester.py --test-type reliability

# Restart services to free memory
docker-compose restart
```

#### 4. WebSocket Connection Issues

**Problem**: Real-time updates not working

**Solutions**:
```bash
# Test WebSocket connectivity
wscat -c ws://localhost:3560

# Check firewall settings
sudo ufw status

# Verify nginx proxy configuration
sudo nginx -t
sudo systemctl reload nginx
```

#### 5. API Authentication Failures

**Problem**: 401 Unauthorized errors

**Solutions**:
```bash
# Check JWT configuration
python -c "
import os
print(f'JWT_SECRET_KEY: {bool(os.environ.get(\"JWT_SECRET_KEY\"))}')
"

# Test authentication endpoint
curl -X POST http://localhost:3560/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test123"}'

# Regenerate JWT secret
openssl rand -base64 32
```

### Debug Mode

Enable debug mode for troubleshooting:

```bash
# Set environment variables
export FLASK_ENV=development
export DEBUG=true
export LOG_LEVEL=DEBUG

# Run with debug logging
python web_dashboard/backend/app.py
```

### Log Analysis

Common log locations:
- Application logs: `/var/log/cowans/app.log`
- Error logs: `/var/log/cowans/error.log`
- Access logs: `/var/log/nginx/access.log`
- System logs: `journalctl -u cowans-backend`

Useful log analysis commands:

```bash
# Monitor real-time logs
tail -f /var/log/cowans/app.log

# Search for errors
grep -i error /var/log/cowans/*.log

# Check performance issues
grep -i "slow" /var/log/cowans/app.log

# Monitor Redis operations
redis-cli monitor
```

## Maintenance and Updates

### 1. Regular Maintenance Tasks

**Daily**:
- Check system health dashboards
- Review error logs for new issues
- Monitor disk space and memory usage

**Weekly**:
- Run comprehensive test suite
- Review performance metrics
- Update dependencies (security patches)
- Clean up old log files

**Monthly**:
- Full system backup
- Performance optimization review
- Security audit
- Capacity planning review

### 2. Update Procedures

**Code Updates**:
```bash
# Create maintenance window
echo "Starting maintenance..." | tee /tmp/maintenance.log

# Backup current state
./scripts/backup.sh

# Pull updates
git pull origin main

# Test in staging environment
python tests/integration/swarm_test_runner.py --output-dir ./staging_test_reports

# Deploy to production
./deploy.sh

# Verify deployment
python tests/integration/api_integration_validator.py

echo "Maintenance complete." | tee -a /tmp/maintenance.log
```

**Dependency Updates**:
```bash
# Update Python dependencies
pip install --upgrade -r requirements.txt

# Update Node.js dependencies
cd frontend && npm update

# Update Docker images
docker-compose pull
docker-compose up -d
```

### 3. Backup and Recovery

**Backup Script** (`scripts/backup.sh`):
```bash
#!/bin/bash
BACKUP_DIR="/backup/cowans/$(date +%Y%m%d_%H%M%S)"
mkdir -p $BACKUP_DIR

# Backup Redis data
redis-cli BGSAVE
cp /var/lib/redis/dump.rdb $BACKUP_DIR/

# Backup application data
tar -czf $BACKUP_DIR/app_data.tar.gz data/

# Backup configuration
cp -r config/ $BACKUP_DIR/

# Backup logs
tar -czf $BACKUP_DIR/logs.tar.gz logs/

echo "Backup completed: $BACKUP_DIR"
```

**Recovery Procedures**:
```bash
# Stop services
docker-compose down

# Restore Redis data
cp backup/20240101_120000/dump.rdb /var/lib/redis/

# Restore application data
cd data/ && tar -xzf backup/20240101_120000/app_data.tar.gz

# Restart services
docker-compose up -d

# Verify recovery
python tests/integration/api_integration_validator.py
```

### 4. Performance Optimization

**Regular Performance Checks**:
```bash
# Run performance tests monthly
python tests/integration/performance_reliability_tester.py --output monthly_perf_report.json

# Analyze Redis performance
redis-cli --latency-history

# Check database performance (if applicable)
pg_stat_statements  # PostgreSQL
```

**Optimization Tasks**:
- Review and optimize slow API endpoints
- Analyze and optimize Redis memory usage
- Update system configurations based on usage patterns
- Scale infrastructure based on load trends

### 5. Security Updates

**Security Checklist**:
- [ ] Update all dependencies to latest secure versions
- [ ] Review and rotate API keys and secrets
- [ ] Audit user access and permissions
- [ ] Check SSL certificate expiration
- [ ] Review firewall rules and access controls
- [ ] Scan for vulnerabilities using security tools

**Security Monitoring**:
```bash
# Check for failed login attempts
grep "Failed login" /var/log/cowans/app.log

# Monitor for suspicious API usage
grep -E "(40[1-4]|50[0-5])" /var/log/nginx/access.log

# Check SSL certificate validity
openssl x509 -in /etc/ssl/certs/your-domain.crt -text -noout | grep "Not After"
```

---

## Conclusion

This deployment guide provides comprehensive instructions for deploying, monitoring, and maintaining the SWARM integration system. Regular testing, monitoring, and maintenance are essential for reliable operation in production environments.

For additional support or questions, refer to the project documentation or contact the development team.

**Key Success Metrics**:
- System uptime > 99.5%
- API response time < 2 seconds (95th percentile)
- Error rate < 1%
- Successful daily sync completion rate > 98%

**Emergency Contacts**:
- Development Team: dev-team@yourcompany.com
- Infrastructure Team: infra@yourcompany.com
- On-call Engineer: +1-555-ONCALL