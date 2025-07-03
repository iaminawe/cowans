#!/bin/bash

# Backend startup script for Cowan's Product Feed Integration System

echo "Starting backend services..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Redis is installed
if ! command -v redis-server &> /dev/null; then
    echo -e "${RED}Redis is not installed. Please install Redis first.${NC}"
    echo "On macOS: brew install redis"
    echo "On Ubuntu: sudo apt-get install redis-server"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo -e "${YELLOW}Installing Python dependencies...${NC}"
pip install -r requirements.txt

# Create necessary directories
mkdir -p logs/jobs
mkdir -p ../../../data

# Start Redis in the background
echo -e "${YELLOW}Starting Redis...${NC}"
redis-server --daemonize yes

# Check if Redis started successfully
sleep 2
if redis-cli ping > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Redis is running${NC}"
else
    echo -e "${RED}✗ Failed to start Redis${NC}"
    exit 1
fi

# Start Celery worker in the background (optional)
echo -e "${YELLOW}Starting Celery worker...${NC}"
celery -A celery_app worker --loglevel=info --detach

# Start Flask application
echo -e "${YELLOW}Starting Flask application...${NC}"
echo -e "${GREEN}Backend is starting at http://localhost:5000${NC}"
echo -e "${GREEN}Press Ctrl+C to stop all services${NC}"

# Trap to clean up on exit
trap cleanup EXIT

cleanup() {
    echo -e "\n${YELLOW}Shutting down services...${NC}"
    
    # Stop Celery
    pkill -f "celery worker"
    
    # Stop Redis
    redis-cli shutdown
    
    echo -e "${GREEN}All services stopped.${NC}"
}

# Start Flask with SocketIO support
python app.py