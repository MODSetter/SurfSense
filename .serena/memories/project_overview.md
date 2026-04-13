# SurfSense - Project Overview

## Purpose
Open-source alternative to NotebookLM — personal knowledge base with AI chat, 25+ external connectors (Google Drive, Notion, Jira, Slack...), real-time multiplayer, desktop app, podcast/video generation.

## Tech Stack
- **Backend**: Python 3.12, FastAPI, Celery (Redis broker), PostgreSQL (pgvector), Alembic, LiteLLM, LangGraph, uv package manager
- **Frontend**: Next.js 16 (Turbopack), React 19, TypeScript, Tailwind v4, Jotai, @rocicorp/zero (real-time sync), pnpm
- **Real-time**: zero-cache (rocicorp/zero:0.26.2) → Postgres logical replication
- **Services (Docker)**: PostgreSQL pgvector, Redis, SearXNG, pgAdmin, zero-cache
- **Desktop**: Electron (surfsense_desktop/)
- **Browser Extension**: surfsense_browser_extension/

## Architecture
```
surfsense_backend/   - FastAPI + Celery workers
surfsense_web/       - Next.js frontend
surfsense_desktop/   - Electron desktop app
surfsense_browser_extension/ - Browser extension
docker/              - docker-compose.dev.yml & .env
```
