#!/usr/bin/env python
"""
Fix backend issues and restart with proper initialization
"""

import os
import sys
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """Fix backend initialization issues."""
    
    # Ensure we're in the backend directory
    backend_dir = Path(__file__).parent
    os.chdir(backend_dir)
    logger.info(f"Working directory: {os.getcwd()}")
    
    # Check for .env file
    env_file = backend_dir / '.env'
    if not env_file.exists():
        logger.warning(".env file not found in backend directory")
        # Check parent directories
        parent_env = backend_dir.parent.parent / '.env'
        if parent_env.exists():
            logger.info(f"Found .env at {parent_env}")
            # Load from parent
            from dotenv import load_dotenv
            load_dotenv(parent_env)
        else:
            logger.error("No .env file found!")
            return 1
    else:
        from dotenv import load_dotenv
        load_dotenv(env_file)
    
    # Verify critical environment variables
    required_vars = ['OPENAI_API_KEY', 'SHOPIFY_SHOP_URL', 'SHOPIFY_ACCESS_TOKEN']
    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)
    
    if missing:
        logger.warning(f"Missing environment variables: {missing}")
    
    # Initialize database
    try:
        logger.info("Initializing database...")
        from database import init_database, DatabaseUtils
        init_database(create_tables=True)
        
        # Seed initial data
        logger.info("Seeding initial data...")
        DatabaseUtils.seed_initial_data()
        
        # Check database health
        from database import database_health_check
        health = database_health_check()
        logger.info(f"Database health: {health}")
        
        if health['status'] != 'healthy':
            logger.error(f"Database unhealthy: {health}")
            return 1
            
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        return 1
    
    # Test icon generator
    try:
        logger.info("Testing icon generator...")
        from icon_generator_openai import icon_generator_openai
        
        # Check if GPT-4 enhancer is available
        if icon_generator_openai.gpt4_enhancer:
            logger.info("GPT-4 prompt enhancer is available")
        else:
            logger.warning("GPT-4 prompt enhancer not available")
            
    except Exception as e:
        logger.error(f"Icon generator initialization failed: {e}")
    
    # Create necessary directories
    dirs_to_create = [
        'logs',
        'data/category_icons',
        'data/generated_icons',
        'data/temp'
    ]
    
    for dir_path in dirs_to_create:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        logger.info(f"Ensured directory exists: {dir_path}")
    
    logger.info("Backend initialization complete!")
    logger.info("You can now start the Flask app with: python app.py")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())