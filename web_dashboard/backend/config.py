"""Configuration module for the backend."""
import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Base configuration."""
    SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-key")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_ALGORITHM = "HS256"
    
    # Redis configuration
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # Celery configuration
    CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
    CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)
    CELERY_TASK_SERIALIZER = 'json'
    CELERY_RESULT_SERIALIZER = 'json'
    CELERY_ACCEPT_CONTENT = ['json']
    CELERY_TIMEZONE = 'UTC'
    CELERY_ENABLE_UTC = True
    
    # Script execution configuration
    SCRIPTS_BASE_PATH = os.path.join('/app', 'scripts')
    DATA_PATH = os.path.join('/app', 'data')
    LOG_PATH = os.path.join('/app', 'logs')
    
    # Ensure log directory exists
    try:
        os.makedirs(LOG_PATH, exist_ok=True)
    except PermissionError:
        # Directory will be created by Docker with proper permissions
        pass
    
    # Images storage path - ensure it's in app directory
    IMAGES_STORAGE_PATH = os.path.join('/app', 'data', 'generated_icons')
    # Only create directory if we have permissions (defer to Dockerfile setup)
    try:
        os.makedirs(IMAGES_STORAGE_PATH, exist_ok=True)
    except PermissionError:
        # Directory will be created by Docker with proper permissions
        pass
    
    # FTP Configuration
    FTP_HOST = os.getenv('FTP_HOST')
    FTP_USERNAME = os.getenv('FTP_USERNAME')
    FTP_PASSWORD = os.getenv('FTP_PASSWORD')
    
    # Shopify Configuration
    SHOPIFY_SHOP_URL = os.getenv("SHOPIFY_SHOP_URL")
    SHOPIFY_ACCESS_TOKEN = os.getenv("SHOPIFY_ACCESS_TOKEN")
    
    # OpenAI Configuration
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "dall-e-3")
    OPENAI_IMAGE_SIZE = os.getenv("OPENAI_IMAGE_SIZE", "1024x1024")
    OPENAI_IMAGE_QUALITY = os.getenv("OPENAI_IMAGE_QUALITY", "standard")
    OPENAI_MAX_RETRIES = int(os.getenv("OPENAI_MAX_RETRIES", "3"))
    OPENAI_TIMEOUT = int(os.getenv("OPENAI_TIMEOUT", "60"))
    OPENAI_RATE_LIMIT_RPM = int(os.getenv("OPENAI_RATE_LIMIT_RPM", "50"))  # Requests per minute
    OPENAI_RATE_LIMIT_TPM = int(os.getenv("OPENAI_RATE_LIMIT_TPM", "40000"))  # Tokens per minute
    
    # Image Storage Configuration  
    IMAGES_BASE_URL = os.getenv("IMAGES_BASE_URL", "/api/images/")
    IMAGES_MAX_SIZE = int(os.getenv("IMAGES_MAX_SIZE", "5242880"))  # 5MB max file size
    IMAGES_ALLOWED_FORMATS = ['PNG', 'JPEG', 'JPG', 'WEBP']
    
    # Batch Processing Configuration
    BATCH_SIZE_DEFAULT = int(os.getenv("BATCH_SIZE_DEFAULT", "5"))
    BATCH_TIMEOUT = int(os.getenv("BATCH_TIMEOUT", "300"))  # 5 minutes
    BATCH_MAX_CONCURRENT = int(os.getenv("BATCH_MAX_CONCURRENT", "3"))
    
    # Socket.IO configuration
    SOCKETIO_MESSAGE_QUEUE = REDIS_URL
    SOCKETIO_ASYNC_MODE = 'threading'
    
    # Job configuration
    MAX_JOB_RUNTIME = 3600  # 1 hour max runtime
    JOB_RETENTION_DAYS = 7  # Keep job history for 7 days
    
    # Icon generation configuration
    ICON_STORAGE_PATH = os.path.join(DATA_PATH, 'category_icons')
    ICON_MAX_SIZE = 512  # Maximum icon size in pixels
    ICON_DEFAULT_SIZE = 128  # Default icon size
    ICON_SUPPORTED_FORMATS = ['PNG', 'JPEG', 'SVG']
    ICON_BATCH_MAX_SIZE = 100  # Maximum categories per batch
    
    # Database configuration
    DATABASE_URL = os.getenv("DATABASE_URL")
    DATABASE_POOL_SIZE = int(os.getenv("DATABASE_POOL_SIZE", "10"))
    DATABASE_MAX_OVERFLOW = int(os.getenv("DATABASE_MAX_OVERFLOW", "20"))
    DATABASE_POOL_TIMEOUT = int(os.getenv("DATABASE_POOL_TIMEOUT", "30"))
    DATABASE_POOL_RECYCLE = int(os.getenv("DATABASE_POOL_RECYCLE", "3600"))
    DATABASE_ECHO = os.getenv("DATABASE_ECHO", "false").lower() == "true"
    
    # Migration configuration
    MIGRATION_AUTO_UPGRADE = os.getenv("MIGRATION_AUTO_UPGRADE", "false").lower() == "true"
    MIGRATION_BACKUP_BEFORE_UPGRADE = os.getenv("MIGRATION_BACKUP_BEFORE_UPGRADE", "true").lower() == "true"

class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    TESTING = False
    
    # Development database configuration
    @property
    def DATABASE_URL(self):
        if super().DATABASE_URL:
            return super().DATABASE_URL
        # Default to SQLite for development
        db_path = os.path.join(os.path.dirname(__file__), 'dev_database.db')
        return f"sqlite:///{db_path}"
    
    DATABASE_ECHO = True  # Enable SQL logging in development

class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    TESTING = False
    
    # Production database configuration
    @property
    def DATABASE_URL(self):
        if super().DATABASE_URL:
            return super().DATABASE_URL
        # Default to PostgreSQL for production
        return os.getenv("DATABASE_URL", "postgresql://user:password@localhost/production_db")
    
    DATABASE_ECHO = False  # Disable SQL logging in production

# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}