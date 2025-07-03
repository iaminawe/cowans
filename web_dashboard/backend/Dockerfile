FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/data /app/icons /app/logs /app/backups

# Create a non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Initialize database on container start
RUN echo '#!/bin/sh\n\
if [ ! -f /app/data/database.db ]; then\n\
    echo "Initializing database..."\n\
    cd /app && python init_db.py --force --skip-prompt\n\
fi\n\
exec python app.py' > /app/entrypoint.sh && \
    chmod +x /app/entrypoint.sh

# Expose port
EXPOSE 3560

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:3560/health || exit 1

# Set entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]