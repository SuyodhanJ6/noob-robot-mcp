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

# Install Chrome and dependencies for Selenium
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gnupg \
    wget \
    unzip \
    libglib2.0-0 \
    libnss3 \
    libgconf-2-4 \
    libfontconfig1 \
    libxcb1 \
    libxkbcommon0 \
    libx11-6 \
    libx11-xcb1 \
    libxcb-dri3-0 \
    libdrm2 \
    libgbm1 \
    libasound2 \
    xvfb \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Chrome using the current Debian repository
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor > /usr/share/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends google-chrome-stable \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -r app && \
    useradd -r -d /app -g app app

# Copy the pre-built virtualenv from builder
COPY --from=builder --chown=app:app /app /app

# Copy application code
COPY --chown=app:app . /app

# Install Selenium and WebDriver Manager using pip directly
RUN pip install selenium==4.15.2 webdriver-manager==4.0.1

# Create necessary directories with correct permissions
RUN mkdir -p /app/logs /app/output /app/reports && \
    chown -R app:app /app/logs /app/output /app/reports && \
    chmod -R 777 /app/logs /app/output /app/reports

# Make the startup script executable
RUN chmod +x /app/start.sh

# Switch to non-root user
USER app
WORKDIR /app

# Environment variables
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=3007
ENV ALLOWED_ORIGINS="*"
# Set paths for Chrome and avoid "no sandbox" issues
ENV CHROME_BIN=/usr/bin/google-chrome
ENV CHROME_PATH=/usr/bin/google-chrome
# Make ChromeDriver executable with --no-sandbox flag
ENV SELENIUM_DRIVER_ARGS='["--no-sandbox", "--headless", "--disable-dev-shm-usage"]'

# Healthcheck
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:3007/sse || exit 1

EXPOSE 3007

# Run the application using our startup script
CMD ["/app/start.sh"] 