# Multi-stage Dockerfile for Local Image Toolkit
FROM python:3.12-slim-bookworm AS base

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    U2NET_HOME=/app/models

WORKDIR /app

# Install runtime system packages for Pillow, libheif (AVIF), libpng, and image processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libheif-dev \
    libheif1 \
    libjpeg-dev \
    zlib1g-dev \
    libpng-dev \
    libwebp-dev \
    libtiff-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-privileged user and directories
RUN groupadd -g 1000 appgroup && \
    useradd -u 1000 -g appgroup -s /bin/bash -m appuser && \
    mkdir -p /app/models /app/uploads /app/output /app/temp && \
    chown -R appuser:appgroup /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=appuser:appgroup app /app/app
COPY --chown=appuser:appgroup tests /app/tests

USER appuser

EXPOSE 8000

# Healthcheck verifies local HTTP responsiveness
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
