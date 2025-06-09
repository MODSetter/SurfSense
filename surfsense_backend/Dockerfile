# syntax=docker/dockerfile:1.5
ARG TARGETPLATFORM
FROM --platform=${TARGETPLATFORM} python:3.12-slim AS builder

WORKDIR /app

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONUNBUFFERED=1

# Install system dependencies
RUN --mount=type=cache,target=/var/cache/apt \
    apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY pyproject.toml uv.lock ./

# Install python dependencies
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir uv && \
    uv pip install --system --no-cache-dir -e .

# Install Playwright browsers for web scraping if needed
ARG INSTALL_PLAYWRIGHT=false
RUN if [ "$INSTALL_PLAYWRIGHT" = "true" ]; then \
      pip install playwright && playwright install --with-deps chromium ; \
    fi

# --- Runtime Stage ---
FROM --platform=${TARGETPLATFORM} python:3.12-slim AS runtime

WORKDIR /app

# Prevent uvloop compatibility issues
ENV PYTHONPATH=/app
ENV UVICORN_LOOP=asyncio

RUN useradd -u 1001 -r -s /sbin/nologin appuser

COPY --from=builder /usr/local /usr/local
# Copy source code
COPY . .

USER appuser

# Run
EXPOSE 8000
CMD ["python", "main.py"] 