# Unified Dashboard System

## Overview

The Cowan's Product Feed Integration System now features a unified startup script that combines database initialization, backend API, and frontend dashboard into a single, easy-to-use launcher.

## Quick Start

### One-Command Launch

```bash
./start.sh
```

This single command will:
1. ✅ Check all dependencies (Python, Node.js, npm)
2. ✅ Initialize the SQLite database if needed
3. ✅ Install all required packages
4. ✅ Start the backend API server
5. ✅ Start the frontend React application
6. ✅ Optionally start Celery workers for background tasks

## Features

### 🚀 Automatic Database Setup
- Creates database schema on first run
- Sets up Alembic migrations
- Optionally seeds test data
- Creates default admin user if no test data

### 🔍 Health Checks
- Validates port availability before starting
- Checks database health
- Monitors service startup
- Provides clear error messages

### 📊 Integrated Logging
- All services log to `logs/` directory
- Backend logs: `logs/backend.log`
- Frontend logs: `logs/frontend.log`
- Celery logs: `logs/celery.log` (if enabled)

### 🛡️ Process Management
- Graceful shutdown with Ctrl+C
- Cleans up all child processes
- Handles interrupts properly

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    start.sh (Main Entry)                     │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│            start_dashboard_unified.sh                        │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Database   │  │   Backend    │  │   Frontend   │      │
│  │    Setup     │  │   (Flask)    │  │   (React)    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│         │                  │                  │              │
│         ▼                  ▼                  ▼              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   SQLite     │  │  Port 3560   │  │  Port 3055   │      │
│  │   Database   │  │   REST API   │  │   Web UI     │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

## First-Time Setup

When running for the first time, the system will:

1. **Create Virtual Environment**
   ```
   Creating Python virtual environment...
   ✓ Virtual environment created
   ```

2. **Install Dependencies**
   ```
   Installing Python dependencies...
   Installing frontend dependencies...
   ```

3. **Initialize Database**
   ```
   Database not found. Initializing...
   Would you like to seed the database with test data? (y/N)
   ```

4. **Start Services**
   ```
   ✓ Backend is running
   ✓ Frontend is running
   ```

## Configuration

### Ports
Edit `start_dashboard_unified.sh` to change default ports:
```bash
BACKEND_PORT=3560    # Flask API
FRONTEND_PORT=3055   # React App
```

### Database
- Location: `web_dashboard/backend/database.db`
- Type: SQLite with WAL mode
- Automatic backups before migrations

### Authentication
Default admin credentials:
- Email: `admin@cowans.com`
- Password: `admin123`

## Advanced Usage

### Start with Custom Options

```bash
# Skip test data prompt
echo "N" | ./start.sh

# Auto-accept test data
echo "Y" | ./start.sh

# Start with Celery worker
echo -e "Y\nY" | ./start.sh
```

### Database Management

While the system is running, open a new terminal:

```bash
cd web_dashboard/backend
source venv/bin/activate

# Backup database
python manage_db.py backup

# Check health
python manage_db.py health

# Add more test data
python manage_db.py seed products --count 100
```

### Development Mode

The unified script automatically:
- Enables Flask development mode
- Disables browser auto-opening
- Enables hot reloading for both frontend and backend

## Troubleshooting

### Port Already in Use
```
✗ Port 3560 is already in use (backend)
```
**Solution**: Kill the process using the port or change the port in the script.

### Database Locked
```
database is locked
```
**Solution**: The system uses WAL mode to prevent this. If it occurs, restart the services.

### Frontend Won't Start
```
✗ Frontend failed to start. Check logs/frontend.log
```
**Solution**: Check the log file and ensure all npm dependencies are installed.

### Permission Denied
```
bash: ./start.sh: Permission denied
```
**Solution**: Make the script executable:
```bash
chmod +x start.sh start_dashboard_unified.sh
```

## Stopping the System

Press `Ctrl+C` in the terminal where you started the system. This will:
1. Stop the frontend server
2. Stop the backend server
3. Stop Celery workers (if running)
4. Clean up all processes

## System Requirements

- **Python**: 3.8 or higher
- **Node.js**: 14.x or higher
- **npm**: 6.x or higher
- **SQLite**: 3.x (included with Python)
- **RAM**: 2GB minimum
- **Disk**: 500MB free space

## Next Steps

After starting the system:

1. **Access the Dashboard**: http://localhost:3055
2. **Login**: Use the default admin credentials
3. **Generate Icons**: Use the batch icon generation feature
4. **Import Products**: Run the product import workflow
5. **Monitor Sync**: Check sync logs in the dashboard

## Integration with Existing Scripts

The unified system works seamlessly with existing scripts:

```bash
# Run product import (in another terminal)
cd scripts
python run_import.py

# The dashboard will show real-time updates
```

## Benefits of Unified System

1. **Single Entry Point**: One command starts everything
2. **Automatic Setup**: No manual database initialization
3. **Health Monitoring**: Ensures all services are running
4. **Clean Shutdown**: Properly stops all services
5. **Integrated Logging**: Centralized log management
6. **Error Recovery**: Clear error messages and solutions

## Support

For issues or questions:
1. Check the logs in the `logs/` directory
2. Run `python manage_db.py health` for database issues
3. Refer to `docs/DATABASE_INTEGRATION_GUIDE.md`
4. Check individual component documentation