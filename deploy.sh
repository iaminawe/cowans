#!/bin/bash

# Deployment script for Coolify
# This script prepares the application for Coolify deployment

set -e

echo "🚀 Preparing Cowan's Product Feed Integration for deployment..."

# Check if we're in the right directory
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ Error: docker-compose.yml not found. Please run from project root."
    exit 1
fi

# Use Coolify-specific compose file if deploying to Coolify
if [ "$COOLIFY_DEPLOYMENT" = "true" ] || [ "$1" = "coolify" ]; then
    echo "📋 Using Coolify-optimized docker-compose configuration..."
    cp docker-compose.coolify.yml docker-compose.yml
fi

# Create necessary directories
echo "📁 Creating required directories..."
mkdir -p data logs backups

# Check for .env file
if [ ! -f ".env" ]; then
    echo "⚠️  No .env file found. Creating from example..."
    cp .env.example .env
    echo "📝 Please edit .env with your configuration values"
    exit 1
fi

# Validate required environment variables
required_vars=(
    "JWT_SECRET_KEY"
    "SHOPIFY_SHOP_URL"
    "SHOPIFY_ACCESS_TOKEN"
    "OPENAI_API_KEY"
)

missing_vars=()
for var in "${required_vars[@]}"; do
    if ! grep -q "^${var}=" .env || grep -q "^${var}=your-" .env; then
        missing_vars+=($var)
    fi
done

if [ ${#missing_vars[@]} -ne 0 ]; then
    echo "❌ Missing or unconfigured environment variables:"
    printf '%s\n' "${missing_vars[@]}"
    echo "Please update .env file with actual values"
    exit 1
fi

# Build info file for deployment tracking
echo "📊 Creating build info..."
cat > build_info.json <<EOF
{
  "version": "$(git describe --tags --always 2>/dev/null || echo 'unknown')",
  "commit": "$(git rev-parse HEAD 2>/dev/null || echo 'unknown')",
  "build_date": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "branch": "$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'unknown')"
}
EOF

echo "✅ Deployment preparation complete!"
echo ""
echo "Next steps:"
echo "1. Ensure your .env file has all required values"
echo "2. Commit and push to your Git repository"
echo "3. Deploy via Coolify dashboard"
echo ""
echo "For Coolify deployment:"
echo "- Use 'docker-compose.coolify.yml' as your compose file"
echo "- Set PORT environment variable in Coolify (default: 80)"
echo "- Configure your domain in COOLIFY_URL variable"