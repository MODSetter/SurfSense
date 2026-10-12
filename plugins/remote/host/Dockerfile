# syntax=docker.io/docker/dockerfile:1
# The plugin host: one image for every SurfSense plugin, deployed to Azure Container Apps.
#
# The build context is plugins/, so the image can carry the signed registry beside
# remote/ once it exists:
#   docker build -f plugins/remote/host/Dockerfile -t surfsense-plugins plugins
#   docker run --env-file plugins/remote/host/.env -p 8000:8000 surfsense-plugins
# Settings are environment variables; host/.env.example lists them.

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

WORKDIR /srv/remote

# Dependencies first, frozen from uv.lock, so a code change reuses this layer.
COPY remote/host/pyproject.toml remote/host/uv.lock host/
RUN pip install --no-cache-dir uv \
    && uv export --project host --frozen --no-dev --no-hashes \
        --format requirements-txt -o /tmp/requirements.txt \
    && uv pip install --system --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

# Chromium and the system libraries it needs, for Scrapling's fetchers; then
# patchright's own build, which its stealth fetchers launch.
RUN scrapling install \
    && python -m patchright install chromium \
    && chmod -R a+rX "$PLAYWRIGHT_BROWSERS_PATH"

# plugins/remote/ is the import root: `python -m host` runs from here.
COPY remote/ .
RUN chmod +x host/entrypoint.sh

RUN useradd --create-home --uid 10001 plugins
USER plugins

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/health', timeout=4)"
CMD ["host/entrypoint.sh"]
