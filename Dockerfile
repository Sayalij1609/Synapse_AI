# ============================================================
# Stage 1: Build React Frontend
# ============================================================
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

# Cache npm dependencies layer
COPY frontend/package*.json ./
RUN npm ci || npm install

# Build production assets into dist/
COPY frontend/ ./
RUN npm run build


# ============================================================
# Stage 2: Production Python Runner
# ============================================================
FROM python:3.12-slim AS runner

# Environment-based configuration
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    ENVIRONMENT=production \
    LOG_LEVEL=INFO \
    REQUEST_TIMEOUT_SECONDS=120 \
    DB_POOL_SIZE=10 \
    DB_MAX_OVERFLOW=20 \
    AUTO_MIGRATE=true

WORKDIR /app

# Install minimal OS runtime packages (curl for healthcheck, libpq5 for PostgreSQL)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Create dedicated non-root user and group (UID/GID 1001)
RUN groupadd -g 1001 appgroup && \
    useradd -u 1001 -g appgroup -m -s /bin/bash appuser

# Install Python backend dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy database migration configuration and root entrypoints
COPY --chown=appuser:appgroup alembic.ini .
COPY --chown=appuser:appgroup alembic/ ./alembic/
COPY --chown=appuser:appgroup migrate.py .
COPY --chown=appuser:appgroup app.py .

# Copy modular backend application
COPY --chown=appuser:appgroup backend/ ./backend/

# Copy compiled React production build from Stage 1
COPY --from=frontend-builder --chown=appuser:appgroup /app/frontend/dist ./frontend/dist

# Create runtime directories for data persistence with non-root ownership
RUN mkdir -p /app/data /app/chroma_db && \
    chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Expose HTTP port
EXPOSE 8000

# Container liveness health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Execute FastAPI through uvicorn with graceful shutdown and keep-alive tuning
CMD ["sh", "-c", "exec uvicorn app:app --host 0.0.0.0 --port ${PORT} --timeout-keep-alive 65 --graceful-timeout 30"]