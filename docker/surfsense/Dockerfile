# syntax=docker/dockerfile:1.7
# The desktop app's stack without Electron (docs/proposals/docker/README.md).
# Build from the repository root: docker build -f docker/surfsense/Dockerfile .

ARG NODE_IMAGE=node:24.21.0-bookworm-slim
ARG UBUNTU_IMAGE=ubuntu:24.04
ARG CADDY_IMAGE=caddy:2.11.7
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.12.23

FROM ${NODE_IMAGE} AS node
FROM ${CADDY_IMAGE} AS caddy
FROM ${UV_IMAGE} AS uv

# The SPA, calling the API on its own origin.
FROM node AS frontend
RUN corepack enable
WORKDIR /src/surfsense_local/frontend
COPY surfsense_local/frontend/package.json surfsense_local/frontend/pnpm-lock.yaml surfsense_local/frontend/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY surfsense_local/frontend/ ./
RUN VITE_API_BASE=/api VITE_SURFSENSE_RUNTIME=docker pnpm build

# opencode and ripgrep, staged by the desktop's pinned script.
FROM node AS opencode
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates unzip \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src/surfsense_local
COPY surfsense_local/runtimes/ runtimes/
RUN mkdir -p electron && node runtimes/opencode/stage.mjs

# Ubuntu's own Python 3.12, so the venv's interpreter is the one the final image carries.
FROM ${UBUNTU_IMAGE} AS python
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates python3.12 python3.12-venv \
    && rm -rf /var/lib/apt/lists/*

FROM python AS backend
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_PYTHON=/usr/bin/python3.12 UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1
# The backend depends on the plugin manifest rules by a path into backend/.
COPY backend/plugins/bundles/core/manifest/ /app/backend/plugins/bundles/core/manifest/
WORKDIR /app/surfsense_local/backend
COPY surfsense_local/backend/pyproject.toml surfsense_local/backend/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project
COPY surfsense_local/backend/ ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev

# The bundled models: embeddings, the parser pack and speech detection; nothing downloads them later.
FROM backend AS models
RUN .venv/bin/python scripts/fetch_embedding_model.py models \
    && .venv/bin/python scripts/fetch_docling_models.py models \
    && .venv/bin/python scripts/fetch_silero_vad.py models

FROM python AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends tini \
    && rm -rf /var/lib/apt/lists/* \
    && userdel --remove ubuntu \
    && useradd --uid 1000 --create-home --shell /usr/sbin/nologin surfsense \
    && mkdir -p /data && chown surfsense:surfsense /data
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=caddy /usr/bin/caddy /usr/local/bin/caddy
COPY backend/plugins/bundles/core/manifest/ /app/backend/plugins/bundles/core/manifest/
COPY backend/plugins/bundles/core/sdk/ /app/backend/plugins/bundles/core/sdk/
COPY --from=backend /app/surfsense_local/backend/ /app/surfsense_local/backend/
COPY --from=models /app/surfsense_local/backend/models/ /app/surfsense_local/backend/models/
COPY --from=frontend /src/surfsense_local/frontend/dist/ /app/surfsense_local/frontend/dist/
COPY --from=opencode /src/surfsense_local/electron/opencode/ /app/runtimes/opencode/
COPY surfsense_local/sidecars/ /app/surfsense_local/sidecars/
COPY surfsense_local/headless/ /app/surfsense_local/headless/
COPY docker/surfsense/caddy/ /app/caddy/

ENV SURFSENSE_LOCAL_DATA_DIR=/data \
    SURFSENSE_LOCAL_RUNTIMES_DIR=/app/runtimes \
    SURFSENSE_LOCAL_CADDYFILE=/app/caddy/Caddyfile \
    SURFSENSE_LOCAL_FRONTEND_DIR=/app/surfsense_local/frontend/dist \
    SURFSENSE_LOCAL_PUBLIC_PORT=4929 \
    SURFSENSE_LOCAL_CORS_ORIGINS=""

USER surfsense
VOLUME /data
EXPOSE 80
# A first start migrates and loads the parser pack before the API answers.
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --start-interval=5s --retries=3 \
    CMD ["node", "-e", "fetch('http://localhost/api/health').then((r) => process.exit(r.ok ? 0 : 1), () => process.exit(1))"]
ENTRYPOINT ["tini", "-g", "--"]
CMD ["node", "/app/surfsense_local/headless/main.ts"]
