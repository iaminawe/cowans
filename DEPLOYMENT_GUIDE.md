# Deployment Guide

This project supports multiple deployment methods with optimized configurations for each.

## Deployment Options

### 1. Coolify Deployment (Recommended for Production)

Coolify handles the proxy and SSL termination automatically.

**Files used:**
- `docker-compose.coolify.yml` - Optimized for Coolify's proxy system
- `.env.coolify.example` - Environment variables for Coolify

**Configuration:**
- No external ports exposed (Coolify handles routing)
- Uses relative API URLs (`/api`)
- Frontend container serves both static files and API proxy
- Automatic SSL and domain management via Coolify

**Setup:**
1. Copy `.env.coolify.example` to `.env`
2. Update environment variables
3. Deploy using `docker-compose.coolify.yml`

### 2. Standard Docker Compose (Development/Local)

Standard deployment with nginx proxy for local development.

**Files used:**
- `docker-compose.yml` - Full nginx proxy setup
- `.env.example` - Environment variables for local/standard deployment

**Configuration:**
- Exposes port 80/443 externally
- Includes dedicated nginx service for load balancing
- Requires manual SSL certificate management
- Full domain URLs needed for API communication

**Setup:**
1. Copy `.env.example` to `.env`
2. Update `REACT_APP_API_URL` with your domain
3. Deploy using `docker-compose.yml`

## Key Differences

| Feature | Coolify | Standard Docker |
|---------|---------|-----------------|
| Proxy | Coolify handles | Nginx container |
| SSL | Automatic | Manual setup |
| Ports | Internal only | 80/443 exposed |
| API URLs | Relative (`/api`) | Full URLs |
| Scaling | Coolify native | Manual |

## Environment Variables

### Required for All Deployments
- `JWT_SECRET_KEY` - Secure random string
- `SHOPIFY_SHOP_URL` - Your Shopify store URL
- `SHOPIFY_ACCESS_TOKEN` - Shopify API access token
- `OPENAI_API_KEY` - OpenAI API key for icon generation

### Coolify Specific
- `REACT_APP_API_URL=/api` - Relative API path
- `COOLIFY_URL=${FQDN}` - Auto-set by Coolify

### Standard Deployment Specific
- `REACT_APP_API_URL=https://your-domain.com` - Full API URL

## Health Checks

Both configurations include health checks:
- Backend: `http://localhost:3560/health`
- Frontend: `http://localhost:80/health`
- Redis: `redis-cli ping`

## Troubleshooting

### Port Conflicts
If you encounter "port already allocated" errors:
- For Coolify: Ensure you're using `docker-compose.coolify.yml`
- For Standard: Change ports in `docker-compose.yml`

### API Connection Issues
- Coolify: Verify `REACT_APP_API_URL=/api`
- Standard: Verify `REACT_APP_API_URL` matches your domain

### SSL Issues
- Coolify: Handled automatically
- Standard: Ensure SSL certificates are properly mounted in nginx container