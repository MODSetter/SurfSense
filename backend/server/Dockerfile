# syntax=docker.io/docker/dockerfile:1
# The one SurfSense backend: one image for the backend and every SurfSense plugin.
#
# The build context is backend/; the registry has its own image (backend/plugins/registry/).
#   docker build -f backend/server/Dockerfile -t surfsense-backend backend
#   docker run --env-file backend/server/.env -p 8000:8000 surfsense-backend
# Settings are environment variables; server/.env.example lists them.

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # Outside /root, so the unprivileged user below can launch them.
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PORT=8000

# Real fonts, so a stealth browser's canvas and font fingerprints look like a
# desktop's rather than a bare server's; Xvfb, a virtual display for the headed
# browser TikTok's profile feeds need.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        xvfb \
        fonts-noto-color-emoji \
        fonts-unifont \
        fonts-ipafont-gothic \
        fonts-wqy-zenhei \
        fonts-tlwg-loma-otf \
        fonts-dejavu \
        fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Not /srv/backend: production's usage volume is mounted at /srv/remote/usage/.
WORKDIR /srv/remote

# Dependencies first, frozen from uv.lock, so a code change reuses this layer.
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv \
    && uv export --frozen --no-dev --no-hashes \
        --format requirements-txt -o /tmp/requirements.txt \
    && uv pip install --system --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

# Chromium and the system libraries it needs, for Scrapling's fetchers; then
# patchright's own build, which its stealth fetchers launch.
RUN scrapling install \
    && python -m patchright install chromium \
    && chmod -R a+rX "$PLAYWRIGHT_BROWSERS_PATH"

# backend/ and backend/plugins/ are the two import roots: `python -m server` runs from here.
COPY . .
ENV PYTHONPATH=/srv/remote:/srv/remote/plugins
RUN chmod +x server/entrypoint.sh

# usage/ holds the usage meter's SQLite file (USAGE_DB_PATH), a volume in production;
# a new volume takes this folder's owner, so the host can write it.
RUN useradd --create-home --uid 10001 plugins \
    && mkdir -p usage && chown plugins:plugins usage
USER plugins

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/health', timeout=4)"
CMD ["server/entrypoint.sh"]
