FROM python:3.11-slim

# Build argument for development mode (default: false)
ARG DEV_MODE=false

# Install nginx, supervisor, curl, git, and build tools (needed for compiling pyooz)
RUN apt-get update && apt-get install -y \
    nginx \
    supervisor \
    curl \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy data files (always needed)
COPY data/ /app/data/

# Copy application code only in production mode
# In dev mode, these will be mounted as volumes
RUN if [ "$DEV_MODE" = "false" ]; then \
    mkdir -p /app/backend /usr/share/nginx/html; \
    fi

COPY backend/ /app/backend/
COPY frontend/ /usr/share/nginx/html/

# Copy nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf

# Copy supervisor configurations and select the right one based on dev mode
COPY supervisor/ /tmp/supervisor/
RUN if [ "$DEV_MODE" = "true" ]; then \
    cp /tmp/supervisor/supervisord.dev.conf /etc/supervisor/conf.d/supervisord.conf; \
    else \
    cp /tmp/supervisor/supervisord.conf /etc/supervisor/conf.d/supervisord.conf; \
    fi

# Create saves directory
RUN mkdir -p /app/saves

# Expose port
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost/health || exit 1

# Start supervisor
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
