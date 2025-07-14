#!/bin/bash
# Docker Build Performance Test
# Compares original vs optimized Dockerfile build times

set -e

echo "🧪 Docker Build Performance Test"
echo "================================"

# Configuration
ORIGINAL_DOCKERFILE="web_dashboard/backend/Dockerfile.coolify"
OPTIMIZED_DOCKERFILE="web_dashboard/backend/Dockerfile.coolify.optimized"
IMAGE_PREFIX="cowans-test"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Check if files exist
if [ ! -f "$ORIGINAL_DOCKERFILE" ]; then
    echo "❌ Original Dockerfile not found: $ORIGINAL_DOCKERFILE"
    exit 1
fi

if [ ! -f "$OPTIMIZED_DOCKERFILE" ]; then
    echo "❌ Optimized Dockerfile not found: $OPTIMIZED_DOCKERFILE"
    exit 1
fi

# Function to build and time
build_and_time() {
    local dockerfile=$1
    local tag=$2
    local description=$3
    
    echo ""
    echo "🏗️  Building $description..."
    echo "📁 Dockerfile: $dockerfile"
    
    local start_time=$(date +%s)
    
    # Build with BuildKit enabled
    DOCKER_BUILDKIT=1 docker build \
        -f "$dockerfile" \
        -t "$tag" \
        --progress=plain \
        . > "build_log_${tag}_${TIMESTAMP}.log" 2>&1
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    echo "✅ Build completed in ${duration} seconds"
    
    # Get image size
    local size=$(docker images --format "table {{.Size}}" "$tag" | tail -n 1)
    echo "📦 Image size: $size"
    
    return $duration
}

# Clean up previous test images
echo "🧹 Cleaning up previous test images..."
docker rmi "${IMAGE_PREFIX}-original:test" 2>/dev/null || true
docker rmi "${IMAGE_PREFIX}-optimized:test" 2>/dev/null || true

# Test original Dockerfile
echo ""
echo "===================="
echo "Testing Original Build"
echo "===================="

build_and_time "$ORIGINAL_DOCKERFILE" "${IMAGE_PREFIX}-original:test" "Original Dockerfile"
ORIGINAL_TIME=$?

# Clear build cache for fair comparison
echo ""
echo "🗑️  Clearing build cache for fair comparison..."
docker builder prune -f >/dev/null 2>&1

# Test optimized Dockerfile  
echo ""
echo "======================"
echo "Testing Optimized Build"
echo "======================"

build_and_time "$OPTIMIZED_DOCKERFILE" "${IMAGE_PREFIX}-optimized:test" "Optimized Dockerfile"
OPTIMIZED_TIME=$?

# Calculate improvement
echo ""
echo "📊 Performance Comparison"
echo "========================"
echo "Original build time:  ${ORIGINAL_TIME} seconds"
echo "Optimized build time: ${OPTIMIZED_TIME} seconds"

if [ $OPTIMIZED_TIME -lt $ORIGINAL_TIME ]; then
    local improvement=$((ORIGINAL_TIME - OPTIMIZED_TIME))
    local percentage=$(( (improvement * 100) / ORIGINAL_TIME ))
    echo "🎯 Improvement: ${improvement} seconds (${percentage}% faster)"
else
    local regression=$((OPTIMIZED_TIME - ORIGINAL_TIME))
    echo "⚠️  Regression: ${regression} seconds slower"
fi

# Compare image sizes
echo ""
echo "📦 Image Size Comparison"
echo "======================="
docker images --format "table {{.Repository}}:{{.Tag}}\t{{.Size}}" | grep "$IMAGE_PREFIX"

# Cleanup
echo ""
echo "🧹 Cleaning up test images..."
docker rmi "${IMAGE_PREFIX}-original:test" 2>/dev/null || true
docker rmi "${IMAGE_PREFIX}-optimized:test" 2>/dev/null || true

echo ""
echo "✅ Performance test complete!"
echo "📋 Build logs saved as build_log_*_${TIMESTAMP}.log"