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

# Install palworld-save-tools in its own layer so the deps above stay cached.
# SAVETOOLS_REF defaults to main (floats — each CI build gets upstream's latest).
# SAVETOOLS_CACHEBUST is referenced in the RUN so a changing value (CI passes the
# run id) busts ONLY this layer's cache, forcing @main to re-resolve. Pass a fixed
# ref (tag/SHA) via SAVETOOLS_REF for a reproducible, frozen build on demand.
ARG SAVETOOLS_REF=main
ARG SAVETOOLS_CACHEBUST=dev
RUN echo "savetools-cachebust=${SAVETOOLS_CACHEBUST}" && \
    pip install --no-cache-dir \
    "palworld-save-tools @ git+https://github.com/oMaN-Rod/palworld-save-tools.git@${SAVETOOLS_REF}"

# Build frontend with Vite
COPY frontend/ /app/frontend/

# Generate map tiles from the committed source image. This MUST run after the
# frontend COPY above -- it writes into frontend/public/img/tiles, and copying
# frontend/ afterwards would clobber the freshly generated tiles (which is what
# used to happen: the build sliced tiles, then overwrote them with the stale
# committed set). Tiles are gitignored and .dockerignored, so this is the only
# thing that produces them in the image.
COPY scripts/slice_map.py /app/scripts/
RUN python /app/scripts/slice_map.py

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
