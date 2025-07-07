#!/bin/bash

# ========================================
# Cowan's Product Dashboard - Main Startup Script
# ========================================
# This is the MAIN script to start the dashboard
# Usage: ./start_dashboard.sh

echo "╔══════════════════════════════════════════════════════╗"
echo "║     Cowan's Product Dashboard - Starting Up          ║"
echo "╚══════════════════════════════════════════════════════╝"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the directory of this script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

# Check Python version
echo -e "${BLUE}Checking Python version...${NC}"
python3 --version

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv venv
fi

# Activate virtual environment
echo -e "${BLUE}Activating virtual environment...${NC}"
source venv/bin/activate

# Install/Update dependencies
echo -e "${YELLOW}Installing/updating dependencies...${NC}"
pip install -r requirements.txt -q

# Create necessary directories
echo -e "${BLUE}Creating necessary directories...${NC}"
mkdir -p logs/jobs
mkdir -p ../../data

# Check if .env file exists
if [ ! -f "../../.env" ]; then
    echo -e "${RED}Warning: .env file not found!${NC}"
    echo -e "${YELLOW}Creating .env from template...${NC}"
    if [ -f "../../.env.example" ]; then
        cp ../../.env.example ../../.env
        echo -e "${GREEN}Created .env file. Please update it with your credentials.${NC}"
    else
        echo -e "${RED}No .env.example found. Please create .env file manually.${NC}"
    fi
fi

# Database initialization
echo -e "${BLUE}Initializing database...${NC}"
python -c "from database import initialize; initialize()" 2>/dev/null || echo -e "${YELLOW}Database already initialized${NC}"

# Start the Flask application
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║          Dashboard Starting Successfully!            ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}🌐 Dashboard URL:${NC} ${GREEN}http://localhost:5000${NC}"
echo -e "${BLUE}📊 API Base URL:${NC} ${GREEN}http://localhost:5000/api${NC}"
echo -e "${BLUE}🔌 WebSocket URL:${NC} ${GREEN}ws://localhost:5000${NC}"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop the dashboard${NC}"
echo ""

# Trap to handle shutdown gracefully
trap 'echo -e "\n${YELLOW}Shutting down dashboard...${NC}"; exit 0' INT TERM

# Start Flask with better error handling
python app.py 2>&1 | while IFS= read -r line; do
    # Color code the output
    if [[ $line == *"ERROR"* ]]; then
        echo -e "${RED}$line${NC}"
    elif [[ $line == *"WARNING"* ]]; then
        echo -e "${YELLOW}$line${NC}"
    elif [[ $line == *"Running on"* ]] || [[ $line == *"started"* ]]; then
        echo -e "${GREEN}$line${NC}"
    else
        echo "$line"
    fi
done