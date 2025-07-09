#!/bin/bash

echo "🚀 Initializing Cowan's Product Feed Dashboard..."

# Change to backend directory
cd web_dashboard/backend

# 1. Install Python dependencies if needed
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

echo "📦 Activating virtual environment..."
source venv/bin/activate

echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

# 2. Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file..."
    cp .env.example .env
    echo "✓ Created .env file. Please update it with your configuration."
fi

# 3. Initialize database
echo "🗄️ Initializing database..."
if [ -f "alembic.ini" ]; then
    echo "Running Alembic migrations..."
    python -m alembic upgrade head
else
    echo "Running direct database initialization..."
    python init_db.py --skip-prompt
fi

# 4. Create admin user
echo "👤 Creating admin user..."
python create_admin.py

# 5. Install frontend dependencies
cd ../../frontend
if [ ! -d "node_modules" ]; then
    echo "📦 Installing frontend dependencies..."
    npm install
fi

echo ""
echo "✅ Dashboard initialization complete!"
echo ""
echo "To start the dashboard, run:"
echo "  ./start_dashboard_fixed.sh"
echo ""
echo "Or start services manually:"
echo "  Backend:  cd web_dashboard/backend && python app.py"
echo "  Frontend: cd frontend && npm start"