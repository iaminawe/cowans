FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies including gunicorn
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY ./web_dashboard/backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install gunicorn for production
RUN pip install --no-cache-dir gunicorn[gevent]

# Copy application code
COPY ./web_dashboard/backend .

# Copy scripts directory
COPY ./scripts /app/scripts

# Copy frontend build files for serving
COPY ./frontend/build /app/frontend/build

# Create a non-root user first
RUN useradd -m -u 1000 appuser

# Create necessary directories with proper ownership
RUN mkdir -p /app/data /app/data/generated_icons /app/icons /app/logs /app/backups && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Create production entrypoint
RUN echo '#!/bin/sh\n\
# Ensure all required directories exist with proper permissions\n\
mkdir -p /app/data/generated_icons /app/logs /app/icons\n\
\n\
# Check if we are in production mode\n\
if [ "$FLASK_ENV" = "production" ]; then\n\
    echo "Starting in production mode with Gunicorn..."\n\
    exec gunicorn --bind 0.0.0.0:3560 \\\n\
        --workers 4 \\\n\
        --worker-class gevent \\\n\
        --worker-connections 1000 \\\n\
        --timeout 120 \\\n\
        --keep-alive 5 \\\n\
        --max-requests 1000 \\\n\
        --max-requests-jitter 100 \\\n\
        --access-logfile - \\\n\
        --error-logfile - \\\n\
        --capture-output \\\n\
        app:app\n\
else\n\
    echo "Starting in development mode..."\n\
    exec python app.py\n\
fi' > /app/entrypoint.sh && \
    chmod +x /app/entrypoint.sh

# Expose port
EXPOSE 3560

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:3560/health || exit 1

# Set entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]