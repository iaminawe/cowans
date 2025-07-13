#!/usr/bin/env python3
"""
One-time database initialization script for production deployments.

This script creates database tables and seeds initial data.
Use this instead of setting INIT_DATABASE=true to avoid repeated seeding.

Usage:
    python init_database_once.py
    
Environment Variables:
    - DATABASE_URL: PostgreSQL connection string
    - FLASK_ENV: Set to 'production' to skip test data seeding
"""

import os
import sys
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Initialize database tables and seed initial data."""
    try:
        # Import after setting up environment
        from database import init_database, DatabaseUtils, database_health_check
        
        logger.info("🔄 Initializing database tables...")
        
        # Always create tables if they don't exist
        init_database(create_tables=True)
        logger.info("✅ Database tables initialized")
        
        # Seed initial data (respects production environment check)
        logger.info("🌱 Seeding initial data...")
        try:
            DatabaseUtils.seed_initial_data()
            logger.info("✅ Initial data seeded successfully")
        except Exception as seed_error:
            logger.warning(f"⚠️  Failed to seed initial data: {seed_error}")
        
        # Verify database health
        logger.info("🏥 Checking database health...")
        health = database_health_check()
        if health.get('status') == 'healthy':
            logger.info("✅ Database health check passed")
        else:
            logger.error(f"❌ Database health check failed: {health}")
            return 1
            
        logger.info("🎉 Database initialization completed successfully!")
        return 0
        
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())