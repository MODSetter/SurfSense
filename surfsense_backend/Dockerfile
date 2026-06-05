# =============================================================================
# SurfSense Backend — Multi-stage Dockerfile
# =============================================================================
# Graph: base → deps → models → {e2e, production}
#   e2e        — tests/ via additional_contexts (docker-compose.e2e.yml)
#   production — published ghcr.io image (docker-build.yml pins target)
# =============================================================================

# ─── Stage 1: base (system deps, Pandoc, certificates) ──────────────────────
FROM python:3.12-slim AS base

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    ca-certificates \
    curl \
    wget \
    unzip \
    gnupg2 \
    ffmpeg \
    espeak-ng \
    libsndfile1 \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    dos2unix \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN which ffmpeg && ffmpeg -version

# Pandoc 3.x from GitHub Releases — apt ships 2.17 which has broken table rendering.
# pypandoc_binary bundles pandoc on Windows/macOS; on Linux it picks up this binary.
RUN ARCH=$(dpkg --print-architecture) && \
    wget -qO /tmp/pandoc.deb "https://github.com/jgm/pandoc/releases/download/3.9/pandoc-3.9-1-${ARCH}.deb" && \
    dpkg -i /tmp/pandoc.deb && \
    rm /tmp/pandoc.deb

RUN update-ca-certificates
RUN pip install --upgrade certifi pip-system-certs

ENV SSL_CERT_FILE=/usr/local/lib/python3.12/site-packages/certifi/cacert.pem
ENV REQUESTS_CA_BUNDLE=/usr/local/lib/python3.12/site-packages/certifi/cacert.pem
ENV SURFSENSE_ALLOW_STATIC_FFMPEG_DOWNLOAD=FALSE


# ─── Stage 2: deps (Python deps frozen from uv.lock) ────────────────────────
FROM base AS deps

COPY pyproject.toml uv.lock ./

# Install all Python dependencies from uv.lock for deterministic builds.
#
# `uv pip install -e .` re-resolves from pyproject.toml and ignores uv.lock,
# which lets prod silently drift to newer upstream versions on every rebuild
# (e.g. deepagents 0.4.x -> 0.5.x breaking the FilesystemMiddleware imports).
# Exporting the lock to requirements.txt and feeding it to `uv pip install`
# pins every transitive package to the exact version captured in uv.lock.
#
# Note on torch/CUDA: the export must always select either the cpu or CUDA
# extra declared in pyproject.toml. A no-extra export would resolve torch from
# PyPI on Linux, which currently pulls CUDA-enabled wheels and nvidia-* deps.
# Keep CUDA version selection in [tool.uv.sources] so uv.lock remains the
# source of truth. The install step also needs the matching PyTorch index,
# because requirements.txt preserves the +cpu/+cu wheel pins but not uv's
# package source metadata.
ARG USE_CUDA=false
ARG CUDA_EXTRA=cu128
RUN pip install --no-cache-dir uv && \
    if [ "$USE_CUDA" = "true" ]; then EXTRA="$CUDA_EXTRA"; else EXTRA="cpu"; fi && \
    TORCH_INDEX="https://download.pytorch.org/whl/${EXTRA}" && \
    uv export --frozen --no-dev --no-hashes --no-emit-project \
        --extra "$EXTRA" \
        --format requirements-txt -o /tmp/requirements.txt && \
    uv pip install --system --no-cache-dir \
        --index "$TORCH_INDEX" \
        --index-strategy unsafe-best-match \
        -r /tmp/requirements.txt && \
    rm /tmp/requirements.txt


# ─── Stage 3: models (pre-baked offline assets) ─────────────────────────────
FROM deps AS models

# Pre-download EasyOCR models to avoid runtime SSL issues
RUN mkdir -p /root/.EasyOCR/model && \
    wget --no-check-certificate https://github.com/JaidedAI/EasyOCR/releases/download/v1.3/english_g2.zip      -O /root/.EasyOCR/model/english_g2.zip      || true && \
    wget --no-check-certificate https://github.com/JaidedAI/EasyOCR/releases/download/pre-v1.1.6/craft_mlt_25k.zip -O /root/.EasyOCR/model/craft_mlt_25k.zip || true && \
    cd /root/.EasyOCR/model && \
    (unzip -o english_g2.zip || true) && \
    (unzip -o craft_mlt_25k.zip || true)

# Pre-download Docling models
RUN printf '%s\n' \
    'try:' \
    '    from docling.document_converter import DocumentConverter' \
    '    DocumentConverter()' \
    'except Exception:' \
    '    pass' \
    | python || true

ARG EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
RUN python -c "from chonkie import AutoEmbeddings; AutoEmbeddings.get_embeddings('${EMBEDDING_MODEL}')"

# Install Playwright browsers (the playwright python package itself is in deps)
RUN playwright install chromium --with-deps

# Shared temp directory for file uploads between API and Worker containers.
# Python's tempfile module uses TMPDIR, so uploaded files land here.
# Mount the SAME volume at /shared_tmp on both API and Worker in Coolify.
RUN mkdir -p /shared_tmp

ENV PYTHONPATH=/app
ENV UVICORN_LOOP=asyncio
ENV TMPDIR=/shared_tmp
ENV PYTHONUNBUFFERED=1

# Tune glibc malloc to return freed memory to the OS more aggressively.
# Without these, Python's gc.collect() frees objects but the underlying
# C heap pages stay mapped (RSS never drops) due to sbrk fragmentation.
ENV MALLOC_MMAP_THRESHOLD_=65536
ENV MALLOC_TRIM_THRESHOLD_=131072
ENV MALLOC_MMAP_MAX_=65536


# ─── Stage 4: e2e (production source + tests/ + e2e entrypoint) ─────────────
# Built via `docker buildx build --target e2e`. The default build target is
# `production` (the last stage), so this stage is opt-in for CI only.
#
# `tests/` is excluded from the main build context by .dockerignore (so prod
# can never accidentally ship test fakes). The e2e stage receives tests/
# through an "additional context" passed by docker-compose.e2e.yml — see
# https://docs.docker.com/reference/compose-file/build/#additional_contexts
FROM models AS e2e

# Same source copy as production. .dockerignore filters out tests/.
COPY . .

# Bring tests/ in via the named additional build context. CI passes
#   --build-context tests-source=./tests
# (or the equivalent additional_contexts entry in docker-compose.e2e.yml).
COPY --from=tests-source . ./tests/

# Install the project itself in editable mode. Dependencies were already
# installed deterministically from uv.lock above, so --no-deps prevents any
# re-resolution that could pull newer versions.
RUN uv pip install --system --no-cache-dir --no-deps -e .

COPY scripts/docker/entrypoint.e2e.sh /app/scripts/docker/entrypoint.e2e.sh
RUN dos2unix /app/scripts/docker/entrypoint.e2e.sh && chmod +x /app/scripts/docker/entrypoint.e2e.sh

# SERVICE_ROLE is overridden per service in docker-compose.e2e.yml (api / worker).
ENV SERVICE_ROLE=api

EXPOSE 8000-8001
CMD ["/app/scripts/docker/entrypoint.e2e.sh"]


# ─── Stage 5: production (published ghcr.io image) ──────────────────────────
# CI pins `target: production`; also the default for `docker build` / dev compose.
FROM models AS production

# Copy source code (tests/ excluded by .dockerignore — production never ships tests).
COPY . .

# Install the project itself in editable mode. Dependencies were already
# installed deterministically from uv.lock above, so --no-deps prevents any
# re-resolution that could pull newer versions.
RUN uv pip install --system --no-cache-dir --no-deps -e .

# Use dos2unix to ensure LF line endings (fixes CRLF issues from Windows checkouts)
COPY scripts/docker/entrypoint.sh /app/scripts/docker/entrypoint.sh
RUN dos2unix /app/scripts/docker/entrypoint.sh && chmod +x /app/scripts/docker/entrypoint.sh

# SERVICE_ROLE controls which process this container runs:
#   migrate – Run alembic upgrade head, verify zero_publication exists, exit 0.
#             Used by the dedicated `migrations` service in docker-compose.yml
#             so downstream services gate on `service_completed_successfully`.
#   api     – FastAPI backend only (does NOT run migrations)
#   worker  – Celery worker only
#   beat    – Celery beat scheduler only
#   all     – migrations + api + worker + beat (legacy / dev default;
#             fails fast on migration error)
ENV SERVICE_ROLE=all

# Celery worker tuning (only used when SERVICE_ROLE=worker or all)
ENV CELERY_MAX_WORKERS=10
ENV CELERY_MIN_WORKERS=2
ENV CELERY_MAX_TASKS_PER_CHILD=50
# CELERY_QUEUES: comma-separated queues to consume (empty = all queues)
#   "surfsense"              – fast tasks only (file uploads, podcasts, etc.)
#   "surfsense.connectors"   – slow connector indexing tasks only
#   ""                       – both queues (default, for single-worker setups)
ENV CELERY_QUEUES=""

EXPOSE 8000-8001
CMD ["/app/scripts/docker/entrypoint.sh"]
