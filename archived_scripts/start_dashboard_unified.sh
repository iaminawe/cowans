#!/bin/bash

# Enhanced unified startup script for Cowan's Product Feed Dashboard
# This script handles database initialization, backend, and frontend startup

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
BACKEND_PORT=3560
FRONTEND_PORT=3055
BACKEND_DIR="web_dashboard/backend"
FRONTEND_DIR="frontend"
LOG_DIR="logs"
DB_FILE="$BACKEND_DIR/database.db"

# Function to print colored output
print_status() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check if a port is in use
port_in_use() {
    lsof -i:$1 >/dev/null 2>&1
}

# Function to kill processes on exit
cleanup() {
    print_status "Stopping dashboard services..."
    
    # Kill backend
    if [ ! -z "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null && print_success "Backend stopped"
    fi
    
    # Kill frontend
    if [ ! -z "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null && print_success "Frontend stopped"
    fi
    
    # Kill Celery if running
    if [ ! -z "$CELERY_PID" ]; then
        kill $CELERY_PID 2>/dev/null && print_success "Celery stopped"
    fi
    
    exit
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM EXIT

# Header
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "                 🚀 Cowan's Product Feed Dashboard Launcher"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check dependencies
print_status "Checking dependencies..."

if ! command_exists python; then
    print_error "Python is not installed. Please install Python 3.8 or higher."
    exit 1
fi

if ! command_exists npm; then
    print_error "npm is not installed. Please install Node.js and npm."
    exit 1
fi

print_success "All dependencies found"

# Create log directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Check for port conflicts
print_status "Checking port availability..."

if port_in_use $BACKEND_PORT; then
    print_error "Port $BACKEND_PORT is already in use (backend)"
    echo "Please stop the process using this port or change BACKEND_PORT in this script"
    exit 1
fi

if port_in_use $FRONTEND_PORT; then
    print_error "Port $FRONTEND_PORT is already in use (frontend)"
    echo "Please stop the process using this port or change FRONTEND_PORT in this script"
    exit 1
fi

print_success "Ports are available"

# Initialize Backend
print_status "Initializing backend..."
cd "$BACKEND_DIR"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    print_status "Creating Python virtual environment..."
    python -m venv venv
    print_success "Virtual environment created"
fi

# Activate virtual environment
print_status "Activating virtual environment..."
source venv/bin/activate

# Install/update Python dependencies
print_status "Installing Python dependencies..."
pip install -r requirements.txt --quiet

# Initialize database if it doesn't exist or is empty
if [ ! -f "$DB_FILE" ] || [ ! -s "$DB_FILE" ]; then
    print_warning "Database not found or empty. Initializing..."
    
    # Create database schema
    python -c "
from database import init_database
init_database(create_tables=True)
print('Database tables created successfully')
"
    
    # Run initial migration setup
    if [ -f "alembic.ini" ]; then
        print_status "Setting up database migrations..."
        alembic stamp head
        print_success "Database migrations initialized"
    fi
    
    # Ask if user wants test data
    read -p "Would you like to seed the database with test data? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_status "Seeding database with test data..."
        python manage_db.py seed all
        print_success "Test data created"
    else
        # Create default admin user
        print_status "Creating default admin user..."
        python -c "
from database import db_session_scope
from models import User
from werkzeug.security import generate_password_hash

with db_session_scope() as session:
    # Check if admin already exists
    existing = session.query(User).filter_by(email='admin@cowans.com').first()
    if not existing:
        admin = User(
            email='admin@cowans.com',
            username='admin',
            password_hash=generate_password_hash('admin123'),
            is_admin=True,
            is_active=True
        )
        session.add(admin)
        session.commit()
        print('Default admin user created')
        print('Email: admin@cowans.com')
        print('Password: admin123')
    else:
        print('Admin user already exists')
"
    fi
else
    print_success "Database already exists"
    
    # Check database health
    print_status "Running database health check..."
    python -c "
from db_utils import DatabaseHealthChecker
from database import db_manager, init_database

# Ensure database is initialized
if not db_manager.engine:
    init_database()

checker = DatabaseHealthChecker(db_manager.engine)
report = checker.run_health_check()
if report['status'] == 'healthy':
    print('✓ Database is healthy')
else:
    print('⚠ Database issues detected:', report['summary'])
"
fi

# Start backend
print_status "Starting backend server on port $BACKEND_PORT..."
export FLASK_ENV=development
export DATABASE_URL="sqlite:///$DB_FILE"
cd "$BACKEND_DIR"
python app.py > "../$LOG_DIR/backend.log" 2>&1 &
BACKEND_PID=$!

# Return to root directory
cd ../..

# Wait for backend to start
print_status "Waiting for backend to start..."
for i in {1..30}; do
    if curl -s "http://localhost:$BACKEND_PORT/health" > /dev/null; then
        print_success "Backend is running"
        break
    fi
    if [ $i -eq 30 ]; then
        print_error "Backend failed to start. Check logs/backend.log"
        exit 1
    fi
    sleep 1
done

# Return to root directory
cd ../..

# Initialize Frontend
print_status "Initializing frontend..."
cd "$FRONTEND_DIR"

# Install npm dependencies if needed
if [ ! -d "node_modules" ] || [ package.json -nt node_modules ]; then
    print_status "Installing frontend dependencies..."
    npm install
    print_success "Frontend dependencies installed"
else
    print_success "Frontend dependencies up to date"
fi

# Start frontend
print_status "Starting frontend server on port $FRONTEND_PORT..."
BROWSER=none PORT=$FRONTEND_PORT npm start > "../$LOG_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!

# Wait for frontend to start
print_status "Waiting for frontend to start..."
for i in {1..60}; do
    if curl -s "http://localhost:$FRONTEND_PORT" > /dev/null; then
        print_success "Frontend is running"
        break
    fi
    if [ $i -eq 60 ]; then
        print_error "Frontend failed to start. Check logs/frontend.log"
        exit 1
    fi
    sleep 1
done

# Optional: Start Celery worker for background tasks
cd "../$BACKEND_DIR"
if [ -f "celery_app.py" ] && command_exists celery; then
    read -p "Would you like to start Celery worker for background tasks? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_status "Starting Celery worker..."
        celery -A celery_app worker --loglevel=info > "../$LOG_DIR/celery.log" 2>&1 &
        CELERY_PID=$!
        print_success "Celery worker started"
    fi
fi

# Display success message
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_success "Dashboard is running!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🌐 Frontend URL:    http://localhost:$FRONTEND_PORT"
echo "📡 Backend API:     http://localhost:$BACKEND_PORT"
echo "📊 API Docs:        http://localhost:$BACKEND_PORT/docs"
echo "📁 Database:        $DB_FILE"
echo ""
echo "🔑 Default Login:"
echo "   Email:    admin@cowans.com"
echo "   Password: admin123"
echo ""
echo "📝 Logs are being written to:"
echo "   Backend:  $LOG_DIR/backend.log"
echo "   Frontend: $LOG_DIR/frontend.log"
if [ ! -z "$CELERY_PID" ]; then
    echo "   Celery:   $LOG_DIR/celery.log"
fi
echo ""
echo "Press Ctrl+C to stop all services"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Keep script running
wait