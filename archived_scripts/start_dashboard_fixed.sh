#!/bin/bash

# Script initialization with timestamps
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
LOG_PREFIX="[${TIMESTAMP}]"

echo "${LOG_PREFIX} Starting Cowan's Product Feed Dashboard..."

# Function to kill processes on exit
cleanup() {
    echo "${LOG_PREFIX} Stopping dashboard services..."
    if [ ! -z "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null
    fi
    if [ ! -z "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null
    fi
    exit
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM EXIT

# Check if we're in the correct directory
if [ ! -d "web_dashboard" ]; then
    echo "${LOG_PREFIX} Error: web_dashboard directory not found!"
    echo "Please run this script from the project root directory."
    exit 1
fi

# Check for required Python dependencies
echo "${LOG_PREFIX} Checking Python dependencies..."
cd web_dashboard/backend

# Check if virtual environment exists
if [ -d "venv" ]; then
    echo "${LOG_PREFIX} Activating virtual environment..."
    source venv/bin/activate
fi

# Check for .env file
if [ ! -f ".env" ]; then
    echo "${LOG_PREFIX} Warning: .env file not found in backend directory"
    echo "Creating .env file from example..."
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "${LOG_PREFIX} Created .env file. Please update it with your configuration."
    fi
fi

# Check if database exists
if [ ! -f "database.db" ]; then
    echo "${LOG_PREFIX} Database not found. Initializing..."
    
    # Initialize database with Alembic if available
    if [ -f "alembic.ini" ]; then
        echo "${LOG_PREFIX} Running database migrations..."
        python -m alembic upgrade head
        
        if [ $? -eq 0 ]; then
            echo "${LOG_PREFIX} ✓ Database migrations completed"
        else
            echo "${LOG_PREFIX} ✗ Database migration failed"
            echo "${LOG_PREFIX} Trying direct initialization..."
            python init_db.py --skip-prompt
        fi
    else
        # Direct initialization
        python init_db.py --skip-prompt
    fi
    
    # Create default admin user if database was just created
    if [ -f "database.db" ]; then
        echo "${LOG_PREFIX} Creating default admin user..."
        python -c "
import sys
sys.path.append('.')
from database import init_database, db_session_scope
from repositories import UserRepository

# Initialize database first
init_database()

# Create admin user
try:
    with db_session_scope() as session:
        user_repo = UserRepository(session)
        existing = user_repo.get_by_email('admin@cowans.com')
        if not existing:
            admin = user_repo.create_user(
                email='admin@cowans.com',
                password='changeme123',
                first_name='Admin',
                last_name='User',
                is_admin=True
            )
            session.commit()
            print('✓ Created admin user: admin@cowans.com / changeme123')
            print('Please change the password after first login!')
        else:
            print('✓ Admin user already exists')
except Exception as e:
    print(f'Warning: Could not create admin user: {e}')
    print('You can create one manually with: python manage_db.py create-admin <email> <password>')
"
    fi
else
    echo "${LOG_PREFIX} ✓ Database already exists"
fi

# Start backend
echo "${LOG_PREFIX} Starting backend server on port 3560..."
python app.py &
BACKEND_PID=$!

# Check if backend started successfully
sleep 2
if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo "${LOG_PREFIX} ✗ Backend failed to start!"
    echo "Check the logs for errors."
    exit 1
fi

echo "${LOG_PREFIX} ✓ Backend server started (PID: $BACKEND_PID)"

# Check frontend dependencies
cd ../../frontend
if [ ! -d "node_modules" ]; then
    echo "${LOG_PREFIX} Installing frontend dependencies..."
    npm install
    if [ $? -ne 0 ]; then
        echo "${LOG_PREFIX} ✗ Failed to install frontend dependencies"
        exit 1
    fi
fi

# Start frontend
echo "${LOG_PREFIX} Starting frontend server on port 3055..."
npm start &
FRONTEND_PID=$!

# Wait for frontend to start
sleep 3
if ! kill -0 $FRONTEND_PID 2>/dev/null; then
    echo "${LOG_PREFIX} ✗ Frontend failed to start!"
    echo "Check if port 3055 is already in use."
    exit 1
fi

echo "${LOG_PREFIX} ✓ Frontend server started (PID: $FRONTEND_PID)"

# Display startup information
echo ""
echo "════════════════════════════════════════════════════════════════"
echo "✅ Dashboard is running!"
echo "════════════════════════════════════════════════════════════════"
echo "🌐 Frontend: http://localhost:3055"
echo "📡 Backend API: http://localhost:3560"
echo "📚 API Docs: http://localhost:3560/api/docs"
echo ""
echo "🔑 Default Login Credentials:"
echo "   Admin: admin@cowans.com / changeme123"
echo "   Test: test@example.com / test123"
echo ""
echo "📋 Available API Endpoints:"
echo "   - /api/auth/* - Authentication"
echo "   - /api/import/* - Etilize import management"
echo "   - /api/shopify/* - Shopify sync operations"
echo "   - /api/xorosoft/* - Xorosoft API integration"
echo ""
echo "Press Ctrl+C to stop all servers"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Monitor processes
while true; do
    # Check if backend is still running
    if ! kill -0 $BACKEND_PID 2>/dev/null; then
        echo "${LOG_PREFIX} Backend process died unexpectedly!"
        cleanup
    fi
    
    # Check if frontend is still running
    if ! kill -0 $FRONTEND_PID 2>/dev/null; then
        echo "${LOG_PREFIX} Frontend process died unexpectedly!"
        cleanup
    fi
    
    sleep 5
done