# syntax=docker/dockerfile:1.9
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder

# Use bash shell with pipefail option for better error detection
SHELL ["sh", "-exc"]

# Set environment variables for uv
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=python3.11 \
    UV_PROJECT_ENVIRONMENT=/app

# Install only dependencies first (cached layer)
# Using bind mounts to avoid copying unnecessary files
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync \
        --locked \
        --no-dev \
        --no-install-project

# Copy the application code
COPY . /src
WORKDIR /src

# Install the application itself (separate layer for better caching)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync \
        --locked \
        --no-dev \
        --no-editable

##########################################################################

# Production stage - only runtime dependencies
FROM python:3.11-slim-bookworm

SHELL ["sh", "-exc"]

# Add virtualenv to PATH
ENV PATH=/app/bin:$PATH
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -r app && \
    useradd -r -d /app -g app app

# Copy the pre-built virtualenv from builder
COPY --from=builder --chown=app:app /app /app

# Copy application code
COPY --chown=app:app . /app

# Create necessary directories with correct permissions
RUN mkdir -p /app/logs /app/output /app/reports && \
    chown -R app:app /app/logs /app/output /app/reports && \
    chmod -R 777 /app/logs /app/output /app/reports

# Switch to non-root user
USER app
WORKDIR /app

# Environment variables
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=3007
ENV ALLOWED_ORIGINS="*"

# Healthcheck
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:3007/sse || exit 1

EXPOSE 3007

# Run the application
CMD ["python", "main.py"] 