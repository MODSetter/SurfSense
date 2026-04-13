# SurfSense Deployment Guide

## Overview
SurfSense uses Docker and Docker Compose as its primary mechanism for deployment, scaling, and infrastructure orchestration. CI/CD is fully managed via GitHub Actions mapping to GitHub Container Registry (GHCR).

## Docker Compose Production Stack
Located at `docker/docker-compose.yml`, the production stack orchestrates:
1.  **db**: `pgvector/pgvector:pg17` (Postgres 17 with vector search).
2.  **redis**: `redis:8-alpine` (Task queuing and caching).
3.  **searxng**: Private metasearch instance (`searxng/searxng`).
4.  **backend**: The FastAPI application serving REST endpoints (`ghcr.io/modsetter/surfsense-backend:latest`).
5.  **celery_worker**: Background processing worker.
6.  **celery_beat**: Background cron/recurring tasks scheduler.
7.  **zero-cache**: `rocicorp/zero:0.26.2` (Sync engine connecting Postgres and Next.js).
8.  **frontend**: Next.js App Router Web Interface (`ghcr.io/modsetter/surfsense-web:latest`).

## CI/CD Pipeline (GitHub Actions)
The workflow is defined at `.github/workflows/docker-build.yml`.

### Triggers
- Automatic on pushes to `main` and `dev` branches for paths inside `surfsense_backend/**` and `surfsense_web/**`.
- Manual via `workflow_dispatch`.

### Stages
1. **Tag Release (`tag_release`)**:
   - Calculates the App Version from the `VERSION` file.
   - Automatically increments build numbers and creates Git Tags.
2. **Build (`build`)**:
   - Compiles independent Docker images for `backend` and `web`.
   - Utilizes a matrix to build multi-architecture images (`linux/amd64` and `linux/arm64`).
   - Caches layers using GitHub Actions cache (`type=gha`).
   - Exports the docker image digest into temporary artifacts.
3. **Manifest Creation (`create_manifest`)**:
   - Takes the isolated `amd64` and `arm64` images and merges them into a single manifest list.
   - Pushes to `ghcr.io/modsetter/surfsense-backend` and `ghcr.io/modsetter/surfsense-web`.

## Environment Handling
- **Frontend Build args**: Next.js requires environment constants baked at build time (e.g. `NEXT_PUBLIC_FASTAPI_BACKEND_URL`). The GH Action pipes dummy values `__NEXT_PUBLIC_FASTAPI_BACKEND_URL__` which are presumably swapped via `docker-entrypoint.sh` at runtime execution.
- **Backend Configuration**: Read exclusively via Docker Compose `env_file` mapping to `.env` dynamically.

## Update & Maintenance
- Images pushed to GHCR automatically tag with the repository commit and 'latest'.
- Watchtower (`com.centurylinklabs.watchtower.enable=true` label on containers) can be used alongside this stack to enable automatic Rolling Updates when GHCR provides a new version.
