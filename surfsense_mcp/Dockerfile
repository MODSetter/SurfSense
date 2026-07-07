# syntax=docker.io/docker/dockerfile:1
# SurfSense MCP Server — remote (streamable-http) image.
# Serves /mcp (per-request API key, no baked secret) and a public /health probe.

# Stage 1: deps frozen from uv.lock so rebuilds never drift.
FROM python:3.12-slim AS deps

WORKDIR /app

# curl is used by the container healthcheck probe against /health.
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv && \
    uv export --frozen --no-dev --no-emit-project --no-hashes \
        --format requirements-txt -o /tmp/requirements.txt && \
    uv pip install --system --no-cache-dir -r /tmp/requirements.txt && \
    rm /tmp/requirements.txt


# Stage 2: project source; --no-deps since deps are already installed above.
FROM deps AS production

COPY . .
RUN uv pip install --system --no-cache-dir --no-deps -e .

ENV PYTHONUNBUFFERED=1 \
    SURFSENSE_MCP_TRANSPORT=streamable-http \
    SURFSENSE_MCP_HOST=0.0.0.0 \
    SURFSENSE_MCP_PORT=8080 \
    SURFSENSE_BASE_URL=https://api.surfsense.com

EXPOSE 8080

CMD ["python", "-m", "surfsense_mcp"]
