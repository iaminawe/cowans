# Coolify SSL Certificate Troubleshooting

## Problem: Traefik Default Certificate Instead of Let's Encrypt

You're seeing the "TRAEFIK DEFAULT CERT" instead of a proper SSL certificate for your domain.

## Solution Applied:

Added explicit Traefik labels to `docker-compose.coolify.yml` to ensure proper SSL certificate generation:

```yaml
labels:
  # Existing Coolify labels
  - "coolify.managed=true"
  - "coolify.type=application"
  - "coolify.name=frontend"
  - "coolify.port=80"
  - "coolify.domain=${COOLIFY_URL:-cowans.apps.iaminawe.net}"
  - "coolify.https=true"
  
  # Added Traefik labels for SSL
  - "traefik.enable=true"
  - "traefik.http.routers.frontend.rule=Host(`${COOLIFY_URL:-cowans.apps.iaminawe.net}`)"
  - "traefik.http.routers.frontend.entrypoints=https"
  - "traefik.http.routers.frontend.tls=true"
  - "traefik.http.routers.frontend.tls.certresolver=letsencrypt"
  - "traefik.http.services.frontend.loadbalancer.server.port=80"
  
  # HTTP to HTTPS redirect
  - "traefik.http.routers.frontend-http.rule=Host(`${COOLIFY_URL:-cowans.apps.iaminawe.net}`)"
  - "traefik.http.routers.frontend-http.entrypoints=http"
  - "traefik.http.routers.frontend-http.middlewares=redirect-to-https"
  - "traefik.http.middlewares.redirect-to-https.redirectscheme.scheme=https"
```

## Steps to Fix in Coolify:

1. **Update Environment Variable**:
   ```
   COOLIFY_URL=cowans.apps.iaminawe.net
   ```

2. **In Coolify Dashboard**:
   - Go to your application settings
   - Under "Domains", ensure `cowans.apps.iaminawe.net` is set
   - Enable "Generate SSL Certificate"
   - Enable "Force HTTPS"

3. **DNS Verification**:
   - Ensure `cowans.apps.iaminawe.net` points to your Coolify server IP
   - Test with: `nslookup cowans.apps.iaminawe.net`

4. **Let's Encrypt Rate Limits**:
   - If you've attempted multiple deployments, you might hit rate limits
   - Wait 1 hour between attempts if you see rate limit errors

5. **Check Traefik Logs**:
   ```bash
   docker logs traefik
   ```
   Look for certificate generation attempts and errors

## Alternative Approaches:

### Option 1: Use Coolify's Built-in Domain Settings
Instead of docker-compose labels, configure directly in Coolify:
1. Remove all Traefik labels from docker-compose.yml
2. In Coolify UI, go to Application > Settings > Domains
3. Add `cowans.apps.iaminawe.net`
4. Enable SSL generation

### Option 2: Custom Certificate
If Let's Encrypt fails:
1. Upload your own SSL certificate in Coolify
2. Go to Settings > SSL Certificates
3. Add custom certificate for the domain

## Debugging Commands:

```bash
# Check if domain resolves correctly
dig cowans.apps.iaminawe.net

# Test SSL certificate
openssl s_client -connect cowans.apps.iaminawe.net:443 -servername cowans.apps.iaminawe.net

# Check Traefik configuration
docker exec traefik cat /etc/traefik/traefik.yml

# View Traefik dynamic configuration
docker exec traefik cat /etc/traefik/dynamic/*
```

## Common Issues:

1. **Port 80 not accessible**: Let's Encrypt needs port 80 for HTTP challenge
2. **DNS not propagated**: Wait 5-10 minutes after DNS changes
3. **Firewall blocking**: Ensure ports 80 and 443 are open
4. **Wrong domain in labels**: Verify COOLIFY_URL environment variable