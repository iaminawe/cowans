# Coolify Deployment Guide

This guide walks you through deploying the Cowan's Product Feed Integration System to Coolify.

## Prerequisites

1. A Coolify instance (v4.0.0 or higher)
2. A domain name pointed to your Coolify server
3. Environment variables configured
4. Git repository access

## Deployment Steps

### 1. Prepare Your Repository

Ensure your repository contains:
- `docker-compose.yml` (provided)
- Backend `Dockerfile` in `web_dashboard/backend/`
- Frontend `Dockerfile` in `frontend/`
- `.env.example` file

### 2. Create New Project in Coolify

1. Log into your Coolify dashboard
2. Click "New Project"
3. Select "Docker Compose" as the build pack
4. Connect your Git repository

### 3. Configure Environment Variables

In Coolify's environment variables section, add:

```bash
# Required Variables
JWT_SECRET_KEY=generate-a-secure-key-here
SHOPIFY_SHOP_URL=your-shop.myshopify.com
SHOPIFY_ACCESS_TOKEN=your-shopify-token
OPENAI_API_KEY=your-openai-key
FTP_HOST=ftp.etilize.com
FTP_USERNAME=your-ftp-username
FTP_PASSWORD=your-ftp-password

# Domain Configuration
REACT_APP_API_URL=https://your-domain.com

# Optional
SENTRY_DSN=your-sentry-dsn
```

### 4. Configure Domains

In Coolify's domains section:

1. **Main Application**: `your-domain.com`
   - Points to the nginx service on port 80

2. **API Subdomain** (optional): `api.your-domain.com`
   - Points to the backend service on port 3560

### 5. Persistent Storage

Coolify automatically handles Docker volumes. The following will be persisted:
- `backend-data`: SQLite database and uploaded files
- `shared-icons`: Generated icon files
- `redis-data`: Redis persistence
- `nginx-certs`: SSL certificates

### 6. Deploy

1. Click "Deploy" in Coolify
2. Monitor the deployment logs
3. Wait for all health checks to pass

### 7. Post-Deployment Setup

Once deployed, SSH into your server and run:

```bash
# Initialize the database with admin user
docker exec -it cowans-backend python init_db.py

# Or with test data
docker exec -it cowans-backend python manage_db.py seed all
```

## Service URLs

After deployment, your services will be available at:

- **Frontend**: `https://your-domain.com`
- **Backend API**: `https://your-domain.com/api`
- **Health Check**: `https://your-domain.com/health`
- **Icon Assets**: `https://your-domain.com/icons/`

## Coolify-Specific Features

### Auto-SSL

Coolify automatically provisions Let's Encrypt SSL certificates. The nginx configuration is ready for HTTPS.

### Health Checks

All services include health checks that Coolify monitors:
- Backend: `/health` endpoint
- Frontend: Port 80 check
- Redis: `redis-cli ping`

### Resource Limits

You can set resource limits in Coolify's service configuration:

```yaml
# Recommended minimums
backend:
  memory: 512MB
  cpu: 0.5

frontend:
  memory: 256MB
  cpu: 0.25

celery:
  memory: 512MB
  cpu: 0.5

redis:
  memory: 256MB
  cpu: 0.25
```

### Scaling

For horizontal scaling in Coolify:

1. **Backend**: Can scale to multiple instances
2. **Celery**: Can scale workers based on load
3. **Frontend**: Static files, scales easily
4. **Redis**: Single instance (use Redis Cluster for HA)

## Monitoring

### Logs

View logs in Coolify or via Docker:

```bash
# All services
docker-compose logs -f

# Specific service
docker logs cowans-backend -f
```

### Database Backups

Set up automated backups:

```bash
# Create backup
docker exec cowans-backend python manage_db.py backup

# Download backup
docker cp cowans-backend:/app/backups/latest.zip ./backup.zip
```

### Metrics

The application exposes metrics at:
- `/api/health` - Basic health status
- `/api/metrics` - Prometheus-compatible metrics (if enabled)

## Troubleshooting

### Database Issues

```bash
# Check database health
docker exec cowans-backend python manage_db.py health

# Reset database (WARNING: deletes data)
docker exec cowans-backend python init_db.py --force
```

### Permission Issues

```bash
# Fix volume permissions
docker exec -u root cowans-backend chown -R appuser:appuser /app/data
```

### Memory Issues

If SQLite runs out of memory:
1. Increase container memory limit
2. Enable WAL mode (already configured)
3. Run VACUUM periodically

### Connection Issues

Check nginx logs:
```bash
docker logs cowans-nginx
```

## Updates and Maintenance

### Updating the Application

1. Push changes to your Git repository
2. In Coolify, click "Redeploy"
3. Database migrations run automatically

### Database Migrations

```bash
# Check current migration
docker exec cowans-backend alembic current

# Apply migrations
docker exec cowans-backend alembic upgrade head
```

### Maintenance Mode

To enable maintenance mode:

1. Scale down application services in Coolify
2. Keep nginx running with a maintenance page

## Security Considerations

1. **Secrets**: Use Coolify's secret management for sensitive data
2. **Network**: Services communicate on internal Docker network
3. **Firewall**: Only expose ports 80/443 through Coolify
4. **Updates**: Enable automatic security updates in Coolify

## Performance Optimization

### Caching

1. **nginx**: Caches static assets for 1 year
2. **Redis**: Caches API responses and sessions
3. **SQLite**: Uses WAL mode for better concurrency

### CDN Integration

For better performance, configure a CDN:
1. Point CDN to `your-domain.com`
2. Cache `/icons/*` and `/static/*`
3. Bypass cache for `/api/*`

## Backup Strategy

### Automated Backups

Create a cron job in Coolify:

```bash
0 2 * * * docker exec cowans-backend python manage_db.py backup && \
          docker cp cowans-backend:/app/backups/$(date +%Y%m%d).zip /backups/
```

### Restore Process

```bash
# Upload backup
docker cp backup.zip cowans-backend:/tmp/

# Restore
docker exec cowans-backend python manage_db.py restore /tmp/backup.zip
```

## Support

For deployment issues:
1. Check Coolify logs
2. Verify environment variables
3. Ensure Git repository is accessible
4. Check service health endpoints

For application issues:
1. Check application logs
2. Run database health check
3. Verify API connectivity
4. Check icon generation logs