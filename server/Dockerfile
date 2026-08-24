# ==========================================
# Stage 1: Builder - Install dependencies
# ==========================================
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system dependencies needed for building Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency resolution
RUN pip install --no-cache-dir uv

# Copy only dependency files to leverage Docker cache
COPY pyproject.toml .

# Export requirements and install to a custom prefix
# This creates a clean, portable Python environment
RUN uv pip compile pyproject.toml -o requirements.txt && \
    uv pip install --no-cache-dir --python /usr/local/bin/python --prefix=/install -r requirements.txt && \
    # Remove unnecessary files to reduce size
    find /install -type d -name "tests" -o -name "test" -o -name "__pycache__" | xargs rm -rf && \
    find /install -type f -name "*.pyc" -o -name "*.pyo" | xargs rm -rf && \
    # Strip debug symbols from shared libraries
    find /install -name "*.so" -exec strip --strip-unneeded {} \; 2>/dev/null || true

# ==========================================
# Stage 2: Runtime - Minimal final image
# ==========================================
FROM python:3.12-slim AS runtime

ARG APP_ENV=production

ENV APP_ENV=${APP_ENV} \
    PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    PYTHONPATH=/app

# Install only runtime dependencies (libpq for PostgreSQL)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libgomp1 \
    libgfortran5 \
    libopenblas0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Remove pip, setuptools, and wheel from runtime to save space (~7 MB)
# These are not needed in production as all dependencies are already installed
RUN pip uninstall -y pip setuptools wheel || true

# Create non-root user before copying files
RUN useradd -m -u 1000 appuser

WORKDIR /app

# Copy only necessary application files
COPY --chown=appuser:appuser app/ ./app/
COPY --chown=appuser:appuser alembic/ ./alembic/
COPY --chown=appuser:appuser alembic.ini ./
COPY --chown=appuser:appuser scripts/docker-entrypoint.sh ./scripts/

# Make entrypoint executable
RUN chmod +x /app/scripts/docker-entrypoint.sh

# Switch to non-root user
USER appuser

EXPOSE 8000

ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--loop", "uvloop"] 