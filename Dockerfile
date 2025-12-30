# ===== BUILDER STAGE =====
FROM docker.io/library/python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (includes Pillow for tile generation)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy map tile generation script and source image
COPY scripts/slice_map.py /app/scripts/
COPY frontend/img/World_Map_8k.webp /app/frontend/img/

# Generate map tiles at build time
RUN python /app/scripts/slice_map.py

# ===== RUNTIME STAGE =====
FROM docker.io/library/python:3.11-slim

# Build argument for development mode (default: false)
ARG DEV_MODE=false

# Install only runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    supervisor \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy generated map tiles from builder
COPY --from=builder /app/frontend/img/tiles /usr/share/nginx/html/img/tiles

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
    fi \
    && rm -rf /tmp/supervisor

# Create saves directory
RUN mkdir -p /app/saves

# Expose port
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost/health || exit 1

# Start supervisor
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
