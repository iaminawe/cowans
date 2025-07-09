"""Configuration additions for ChatGPT integration."""

# Add these to your main config.py file in the Config class:

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

# Add this to ensure directories exist:
# Ensure images directory exists
IMAGES_STORAGE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "generated_icons")
os.makedirs(IMAGES_STORAGE_PATH, exist_ok=True)