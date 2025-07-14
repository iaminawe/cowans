#!/bin/bash
# Performance Monitoring Script for Cowans Deployment
# Monitors Docker containers, build times, and system resources

set -e

echo "🔍 Cowans Performance Monitor"
echo "============================"
echo "Timestamp: $(date)"
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to check Docker container stats
check_containers() {
    echo "📦 Docker Container Status:"
    echo "-------------------------"
    
    # Get container stats
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.NetIO}}\t{{.BlockIO}}" | grep -E "(NAME|cowans)" || echo "No cowans containers running"
    echo ""
}

# Function to check build cache
check_build_cache() {
    echo "🏗️  Docker Build Cache:"
    echo "-------------------"
    
    # Check BuildKit cache
    docker buildx du --verbose 2>/dev/null | head -10 || echo "BuildKit not available"
    
    # Check regular build cache
    echo ""
    echo "Image sizes:"
    docker images --format "table {{.Repository}}:{{.Tag}}\t{{.Size}}\t{{.CreatedSince}}" | grep -E "(REPOSITORY|cowans)" || true
    echo ""
}

# Function to check system resources
check_system_resources() {
    echo "💻 System Resources:"
    echo "-----------------"
    
    # CPU usage
    echo -n "CPU Load: "
    uptime | awk -F'load average:' '{print $2}'
    
    # Memory usage
    echo "Memory Usage:"
    free -h | grep -E "(total|Mem:|Swap:)" || true
    
    # Disk usage
    echo ""
    echo "Disk Usage:"
    df -h | grep -E "(Filesystem|/$|/var/lib/docker)" || true
    echo ""
}

# Function to check database connections
check_database_connections() {
    echo "🗄️  Database Connection Pool:"
    echo "-------------------------"
    
    # Try to get pool status from the monitoring endpoint
    if command -v curl &> /dev/null; then
        echo "Checking pool status..."
        curl -s http://localhost:3560/api/pool-status 2>/dev/null | python3 -m json.tool || echo "Pool status endpoint not available"
    else
        echo "curl not installed - skipping pool check"
    fi
    echo ""
}

# Function to check Redis status
check_redis_status() {
    echo "📊 Redis Status:"
    echo "-------------"
    
    # Check if Redis container is running
    if docker ps | grep -q redis; then
        docker exec $(docker ps -qf "name=redis") redis-cli INFO server | grep -E "(redis_version|uptime_in_seconds|connected_clients|used_memory_human)" || echo "Redis info not available"
    else
        echo "Redis container not running"
    fi
    echo ""
}

# Function to check recent build times
check_build_times() {
    echo "⏱️  Recent Build Performance:"
    echo "-------------------------"
    
    # Check for build log files
    if ls build_log_*_*.log 2>/dev/null | head -5; then
        echo "Recent build logs found:"
        for log in $(ls -t build_log_*_*.log 2>/dev/null | head -3); do
            duration=$(grep -E "Build completed in [0-9]+ seconds" "$log" 2>/dev/null | tail -1 | grep -oE "[0-9]+ seconds" || echo "N/A")
            echo "  - $log: $duration"
        done
    else
        echo "No recent build logs found"
    fi
    echo ""
}

# Function to generate performance summary
generate_summary() {
    echo "📈 Performance Summary:"
    echo "--------------------"
    
    # Check container count
    container_count=$(docker ps --filter "name=cowans" -q | wc -l)
    echo "Active Containers: $container_count"
    
    # Check total memory usage
    total_mem=$(docker stats --no-stream --format "{{.MemPerc}}" | grep -oE "[0-9.]+" | awk '{sum+=$1} END {print sum}')
    echo "Total Memory Usage: ${total_mem:-0}%"
    
    # Check if optimized Dockerfile is being used
    if docker inspect cowans-backend 2>/dev/null | grep -q "Dockerfile.coolify.optimized"; then
        echo -e "Build Optimization: ${GREEN}✓ Active${NC}"
    else
        echo -e "Build Optimization: ${YELLOW}⚠ Not detected${NC}"
    fi
    
    # Check if BuildKit is enabled
    if docker version | grep -q "buildkit"; then
        echo -e "BuildKit: ${GREEN}✓ Enabled${NC}"
    else
        echo -e "BuildKit: ${YELLOW}⚠ Not enabled${NC}"
    fi
    echo ""
}

# Function to provide optimization recommendations
provide_recommendations() {
    echo "💡 Optimization Recommendations:"
    echo "-----------------------------"
    
    # Check if using optimized Dockerfile
    if ! docker inspect cowans-backend 2>/dev/null | grep -q "Dockerfile.coolify.optimized"; then
        echo "• Switch to optimized Dockerfile for 40-60% faster builds"
    fi
    
    # Check memory usage
    mem_percent=$(free | grep Mem | awk '{print int($3/$2 * 100)}')
    if [ "$mem_percent" -gt 80 ]; then
        echo "• High memory usage detected ($mem_percent%). Consider scaling or optimizing"
    fi
    
    # Check Docker disk usage
    docker_usage=$(df -h /var/lib/docker 2>/dev/null | tail -1 | awk '{print int($5)}' || echo 0)
    if [ "$docker_usage" -gt 80 ]; then
        echo "• Docker disk usage high ($docker_usage%). Run: docker system prune"
    fi
    
    # Check for old images
    old_images=$(docker images -f "dangling=true" -q | wc -l)
    if [ "$old_images" -gt 5 ]; then
        echo "• $old_images dangling images found. Run: docker image prune"
    fi
    
    echo ""
}

# Main execution
main() {
    check_containers
    check_build_cache
    check_system_resources
    check_database_connections
    check_redis_status
    check_build_times
    generate_summary
    provide_recommendations
    
    echo "✅ Performance check complete!"
    echo "Run with watch for continuous monitoring: watch -n 10 $0"
}

# Run main function
main