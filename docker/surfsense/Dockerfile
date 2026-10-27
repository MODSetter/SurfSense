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
# A cache mount keeps the store across local rebuilds; CI's fresh builders use the registry cache.
RUN --mount=type=cache,id=pnpm-store,target=/pnpm-store pnpm install --frozen-lockfile --store-dir /pnpm-store
COPY surfsense_local/frontend/ ./
# One version with the desktop app; About shows it, as Electron's does there.
COPY surfsense_local/VERSION ../VERSION
RUN VITE_API_BASE=/api VITE_SURFSENSE_RUNTIME=docker \
    VITE_SURFSENSE_VERSION="$(cat ../VERSION)" pnpm build

# opencode and ripgrep, staged by the desktop's pinned script.
FROM node AS opencode
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates unzip \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src/surfsense_local
COPY surfsense_local/runtimes/ runtimes/
RUN mkdir -p electron && node runtimes/opencode/stage.mjs

# The local model runtimes, staged by the desktop's own scripts with the image's
# variant: one source per runtime, shared with the desktop (ADR 0073, gpu.md).
# On the final image's Ubuntu, so what links here runs there.
FROM ${UBUNTU_IMAGE} AS toolchain
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates git cmake ninja-build g++ unzip libgomp1 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=node /usr/local/bin/node /usr/local/bin/node
WORKDIR /src/surfsense_local
COPY surfsense_local/runtimes/ runtimes/

# llama.cpp: upstream's CPU build at the desktop's pin.
FROM toolchain AS llamacpp
RUN node runtimes/fetch-llamacpp.mjs --variant cpu --out /runtimes/llamacpp

# sd.cpp: the desktop's recipe, without Vulkan.
FROM toolchain AS sdcpp
RUN node runtimes/sdcpp/stage.mjs --variant cpu --out /runtimes/sdcpp --strict

# audio.cpp and eSpeak: the desktop's Linux build, which is CPU-only already.
FROM toolchain AS audiocpp
RUN node runtimes/audiocpp/stage.mjs --out /runtimes/audiocpp --strict

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

# The bundled models: embeddings, the parser pack, speech detection and the voice
# the installers ship, so podcasts work from the first start; nothing downloads them later.
FROM backend AS models
RUN .venv/bin/python scripts/fetch_embedding_model.py models \
    && .venv/bin/python scripts/fetch_docling_models.py models \
    && .venv/bin/python scripts/fetch_silero_vad.py models \
    && .venv/bin/python scripts/fetch_bundled_voice.py models

# The backend's `image`-marked tests on the image's Ubuntu, Python and bundled models,
# never shipped. docker-tests.yml mounts tests/ in, which the build context leaves out.
FROM models AS backend-tests
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen \
    && apt-get update && apt-get install -y --no-install-recommends tini \
    && rm -rf /var/lib/apt/lists/*
# uid 1000 under tini, as the image runs: a script's read-only source and its reaped helpers depend on both.
USER 1000
ENV HOME=/tmp
ENTRYPOINT ["tini", "-g", "--"]
CMD [".venv/bin/pytest", "-p", "no:cacheprovider", "-m", "image"]

FROM python AS runtime
# curl: the Claude dialog's install command downloads Claude Code with it.
# libgomp1: llama.cpp's upstream CPU build threads with OpenMP.
# The rest, about 21 MB: what Office support's LibreOffice, unpacked into /data,
# links against for a headless conversion, and a font to lay pages out with.
RUN apt-get update && apt-get install -y --no-install-recommends tini curl libgomp1 \
        libxinerama1 libx11-xcb1 libxext6 libsm6 libfontconfig1 fonts-dejavu-core \
        libnss3 libdbus-1-3 libcairo2 libglib2.0-0t64 libcups2t64 \
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
COPY --from=llamacpp /runtimes/llamacpp/ /app/runtimes/llamacpp/
COPY --from=sdcpp /runtimes/sdcpp/ /app/runtimes/sdcpp/
COPY --from=audiocpp /runtimes/audiocpp/ /app/runtimes/audiocpp/
COPY surfsense_local/sidecars/ /app/surfsense_local/sidecars/
COPY surfsense_local/headless/ /app/surfsense_local/headless/
COPY docker/surfsense/caddy/ /app/caddy/

# HOME on the volume for every process, `docker compose exec` included, so Claude Code
# installs where the backend looks (~/.local/bin) and keeps across image updates.
ENV HOME=/data/home \
    PATH=/data/home/.local/bin:$PATH
ENV SURFSENSE_LOCAL_DATA_DIR=/data \
    SURFSENSE_LOCAL_RUNTIMES_DIR=/app/runtimes \
    SURFSENSE_LOCAL_CADDYFILE=/app/caddy/Caddyfile \
    SURFSENSE_LOCAL_FRONTEND_DIR=/app/surfsense_local/frontend/dist \
    SURFSENSE_LOCAL_PUBLIC_PORT=4929 \
    SURFSENSE_LOCAL_CORS_ORIGINS=""

USER surfsense
VOLUME /data
EXPOSE 80 443
# A first start migrates and loads the parser pack before the API answers.
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --start-interval=5s --retries=3 \
    CMD ["node", "-e", "fetch('http://localhost/api/health').then((r) => process.exit(r.ok ? 0 : 1), () => process.exit(1))"]
ENTRYPOINT ["tini", "-g", "--"]
CMD ["node", "/app/surfsense_local/headless/main.ts"]
