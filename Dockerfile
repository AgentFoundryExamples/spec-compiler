# Multi-stage Dockerfile for spec-compiler service
# Optimized for Cloud Run deployment with non-root user

# Stage 1: Base image with dependencies
FROM python:3.11-slim AS base

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
# Note: --trusted-host flags may be needed in some environments with SSL issues
# In production with proper SSL certificates, these flags can be removed
RUN pip install --no-cache-dir --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt

# Stage 2: Runtime image
FROM python:3.11-slim AS runtime

# Install minimal runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser -u 1000 appuser

# Set working directory
WORKDIR /app

# Copy Python packages from base stage
COPY --from=base /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=base /usr/local/bin /usr/local/bin

# Copy application source
COPY src/ ./src/

# Set PYTHONPATH so imports work correctly
ENV PYTHONPATH=/app/src

# Change ownership to non-root user
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port (Cloud Run will override this)
EXPOSE 8080

# Set default PORT env var (Cloud Run will provide this)
ENV PORT=8080

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT}/health').read()" || exit 1

# Run uvicorn with workers <= 2 as specified
# Use exec form to ensure proper signal handling for graceful shutdown
CMD ["sh", "-c", "exec uvicorn spec_compiler.app.main:app --host 0.0.0.0 --port ${PORT} --workers 1"]
