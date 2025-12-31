# ===== BUILDER STAGE =====
FROM docker.io/library/python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies including Node.js for Vite
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (includes Pillow for tile generation)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy map tile generation script and source image
COPY scripts/slice_map.py /app/scripts/
COPY frontend/public/img/World_Map_8k.webp /app/frontend/public/img/

# Generate map tiles at build time
RUN python /app/scripts/slice_map.py

# Build frontend with Vite
COPY frontend/ /app/frontend/
WORKDIR /app/frontend
RUN npm install && npm run build

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
COPY --from=builder /app/frontend/public/img/tiles /usr/share/nginx/html/img/tiles

# Copy Vite-built frontend from builder
COPY --from=builder /app/frontend/dist /usr/share/nginx/html/

# Copy data files (always needed)
COPY data/ /app/data/

COPY backend/ /app/backend/

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
