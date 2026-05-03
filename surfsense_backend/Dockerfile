FROM python:3.12-slim

WORKDIR /app

# Install system dependencies including SSL tools, CUDA dependencies, and Tesseract OCR
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    ca-certificates \
    curl \
    wget \
    unzip \
    gnupg2 \
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

# Install Pandoc 3.x from GitHub as a fallback for Linux where pypandoc_binary
# may not bundle pandoc (apt ships 2.17 which has broken table rendering).
# pypandoc_binary bundles pandoc on Windows/macOS; on Linux it picks this up.
RUN ARCH=$(dpkg --print-architecture) && \
    wget -qO /tmp/pandoc.deb "https://github.com/jgm/pandoc/releases/download/3.9/pandoc-3.9-1-${ARCH}.deb" && \
    dpkg -i /tmp/pandoc.deb && \
    rm /tmp/pandoc.deb

# Update certificates and install SSL tools
RUN update-ca-certificates
RUN pip install --upgrade certifi pip-system-certs

# Copy requirements
COPY pyproject.toml .
COPY uv.lock .

# Install all Python dependencies from uv.lock for deterministic builds.
#
# `uv pip install -e .` re-resolves from pyproject.toml and ignores uv.lock,
# which lets prod silently drift to newer upstream versions on every rebuild
# (e.g. deepagents 0.4.x -> 0.5.x breaking the FilesystemMiddleware imports).
# Exporting the lock to requirements.txt and feeding it to `uv pip install`
# pins every transitive package to the exact version captured in uv.lock.
#
# Note on torch/CUDA: we do NOT install torch from a separate cu* index here.
# PyPI's torch wheels for Linux x86_64 already ship CUDA-enabled and pull
# nvidia-cudnn-cu13, nvidia-nccl-cu13, triton, etc. as install deps (all
# captured in uv.lock). Installing from cu121 first only wasted ~2GB of
# downloads that the lock-based install immediately replaced. If a specific
# CUDA version is needed (driver compatibility, etc.), wire it through
# [tool.uv.sources] in pyproject.toml so the lock stays the source of truth.
RUN pip install --no-cache-dir uv && \
    uv export --frozen --no-dev --no-hashes --no-emit-project \
        --format requirements-txt -o /tmp/requirements.txt && \
    uv pip install --system --no-cache-dir -r /tmp/requirements.txt && \
    rm /tmp/requirements.txt

# Set SSL environment variables dynamically
RUN CERTIFI_PATH=$(python -c "import certifi; print(certifi.where())") && \
    echo "Setting SSL_CERT_FILE to $CERTIFI_PATH" && \
    echo "export SSL_CERT_FILE=$CERTIFI_PATH" >> /root/.bashrc && \
    echo "export REQUESTS_CA_BUNDLE=$CERTIFI_PATH" >> /root/.bashrc
ENV SSL_CERT_FILE=/usr/local/lib/python3.12/site-packages/certifi/cacert.pem
ENV REQUESTS_CA_BUNDLE=/usr/local/lib/python3.12/site-packages/certifi/cacert.pem

# Pre-download EasyOCR models to avoid runtime SSL issues
RUN mkdir -p /root/.EasyOCR/model
RUN wget --no-check-certificate https://github.com/JaidedAI/EasyOCR/releases/download/v1.3/english_g2.zip -O /root/.EasyOCR/model/english_g2.zip || true
RUN wget --no-check-certificate https://github.com/JaidedAI/EasyOCR/releases/download/pre-v1.1.6/craft_mlt_25k.zip -O /root/.EasyOCR/model/craft_mlt_25k.zip || true
RUN cd /root/.EasyOCR/model && (unzip -o english_g2.zip || true) && (unzip -o craft_mlt_25k.zip || true)

# Pre-download Docling models
RUN python -c "try:\n    from docling.document_converter import DocumentConverter\n    conv = DocumentConverter()\nexcept:\n    pass" || true

# Install Playwright browsers for web scraping (the playwright package itself
# is already installed via uv.lock above)
RUN playwright install chromium --with-deps

# Copy source code
COPY . .

# Install the project itself in editable mode. Dependencies were already
# installed deterministically from uv.lock above, so --no-deps prevents any
# re-resolution that could pull newer versions.
RUN uv pip install --system --no-cache-dir --no-deps -e .

# Copy and set permissions for entrypoint script
# Use dos2unix to ensure LF line endings (fixes CRLF issues from Windows checkouts)
COPY scripts/docker/entrypoint.sh /app/scripts/docker/entrypoint.sh
RUN dos2unix /app/scripts/docker/entrypoint.sh && chmod +x /app/scripts/docker/entrypoint.sh

# Shared temp directory for file uploads between API and Worker containers.
# Python's tempfile module uses TMPDIR, so uploaded files land here.
# Mount the SAME volume at /shared_tmp on both API and Worker in Coolify.
RUN mkdir -p /shared_tmp
ENV TMPDIR=/shared_tmp

# Prevent uvloop compatibility issues
ENV PYTHONPATH=/app
ENV UVICORN_LOOP=asyncio

# Tune glibc malloc to return freed memory to the OS more aggressively.
# Without these, Python's gc.collect() frees objects but the underlying
# C heap pages stay mapped (RSS never drops) due to sbrk fragmentation.
ENV MALLOC_MMAP_THRESHOLD_=65536
ENV MALLOC_TRIM_THRESHOLD_=131072
ENV MALLOC_MMAP_MAX_=65536

# SERVICE_ROLE controls which process this container runs:
#   api     – FastAPI backend only (runs migrations on startup)
#   worker  – Celery worker only
#   beat    – Celery beat scheduler only
#   all     – All three (legacy / dev default)
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

# Run
EXPOSE 8000-8001
CMD ["/app/scripts/docker/entrypoint.sh"]