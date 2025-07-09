#!/bin/bash

# Main startup script for Cowan's Product Feed Integration System
# This is the primary entry point for starting the entire system

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

clear

echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════════════════════════════════╗"
echo "║                                                                       ║"
echo "║           Cowan's Product Feed Integration System                     ║"
echo "║                                                                       ║"
echo "║           Automated Shopify Product Management Platform               ║"
echo "║                                                                       ║"
echo "╚═══════════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""

# Check which script exists and use the appropriate one
if [ -f "start_dashboard_unified.sh" ]; then
    echo -e "${GREEN}Starting unified dashboard with database integration...${NC}"
    echo ""
    ./start_dashboard_unified.sh
elif [ -f "start_dashboard.sh" ]; then
    echo -e "${GREEN}Starting basic dashboard...${NC}"
    echo ""
    ./start_dashboard.sh
else
    echo "Error: No startup script found!"
    echo "Please ensure you're running this from the project root directory."
    exit 1
fi