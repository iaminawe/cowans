# Coolify Deployment Troubleshooting Guide

## Issues Identified and Solutions

### 1. Server Not Found & SSL Certificate Errors

The issues you're experiencing are likely due to:

1. **Missing Coolify Labels**: The frontend service needs proper Coolify routing labels
2. **Port Configuration**: Changed from `ports` to `expose` as Coolify handles external routing
3. **SSL Configuration**: Added labels for HTTPS support

### Changes Made:

#### docker-compose.coolify.yml
- Changed frontend service from `ports: - "80"` to `expose: - "80"`
- Added Coolify-specific labels:
  - `coolify.port=80` - Tells Coolify which internal port to route to
  - `coolify.domain=${COOLIFY_URL:-cowans.apps.iaminawe.net}` - Sets the domain
  - `coolify.https=true` - Enables HTTPS

### Deployment Steps in Coolify:

1. **Environment Variables**: Set these in Coolify's environment settings:
   ```
   COOLIFY_URL=cowans.apps.iaminawe.net
   JWT_SECRET_KEY=your-secret-key
   SHOPIFY_SHOP_URL=your-shop.myshopify.com
   SHOPIFY_ACCESS_TOKEN=your-token
   OPENAI_API_KEY=your-api-key
   FTP_HOST=ftp.etilize.com
   FTP_USERNAME=your-username
   FTP_PASSWORD=your-password
   ```

2. **Docker Compose File**: Use `docker-compose.coolify.yml` as your compose file

3. **Build Configuration**:
   - Build Pack: Docker Compose
   - Base Directory: `/` (root of repository)
   - Docker Compose Location: `docker-compose.coolify.yml`

4. **Domain & SSL**:
   - Domain: `cowans.apps.iaminawe.net`
   - Enable "Force HTTPS"
   - Enable "Auto-generate SSL"

5. **Health Checks**: The services include health checks that Coolify will use

### Verification Steps:

1. Check Coolify logs for deployment errors
2. Verify DNS points to your Coolify server
3. Check if SSL certificates are generated (Coolify > Application > SSL)
4. Test health endpoints:
   - Frontend: `https://cowans.apps.iaminawe.net/health`
   - Backend: `https://cowans.apps.iaminawe.net/api/health`

### Common Issues:

1. **Build Context**: Ensure Coolify has access to the full repository
2. **Volumes**: Make sure Coolify has permissions to create volumes
3. **Network**: Backend service must be accessible by name from frontend

### Additional Debugging:

If issues persist, check:
- Coolify application logs
- Container logs for each service
- Nginx error logs in the frontend container
- SSL certificate status in Coolify UI