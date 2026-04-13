# SurfSense Development Guide

## Prerequisites
- **Node.js**: v18+ with `pnpm` (managed via packageManager: "pnpm@10.24.0").
- **Python**: v3.12+ for the FastAPI backend.
- **Docker & Docker Compose**: Required for spin-up of PostgreSQL (pgvector), Redis, SearXNG, and Zero-Cache.
- **Git**

## Monorepo Setup

The SurfSense project relies on a multi-part configuration.
The core directories include:
- `surfsense_web/`: Next.js frontend (App Router)
- `surfsense_backend/`: FastAPI backend with language models and Celery integration.
- `docker/`: Docker compose files.

## Environment Configuration
You must configure environmental variables before starting the platform.
1. Copy `.env.example` to `.env` in the root folder, and also in individual sub-projects if needed.
2. Typical variables include `DATABASE_URL`, `REDIS_URL`, `SEARXNG_SECRET`, and frontend endpoints (`NEXT_PUBLIC_FASTAPI_BACKEND_URL`).

## Starting the Infrastructure (Docker)
For local development, it is highly recommended to offload the database and cache to Docker:
```bash
# In the project root or docker folder
docker compose -f docker/docker-compose.dev.yml up -d db redis searxng zero-cache
```

## Running the Web Frontend
The frontend uses Next.js with Zero for local-first syncing.
```bash
cd surfsense_web
pnpm install
pnpm dev
# Runs on http://localhost:3000
```

## Running the Backend
The backend utilizes Python FastAPI.
```bash
cd surfsense_backend
# Set up virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -e .[dev]

# Start the API SERVER
uvicorn app.main:app --reload --port 8929

# Start Celery Worker (In a separate terminal)
celery -A app.celery_app worker --loglevel=info

# Start Celery Beat (For scheduled tasks)
celery -A app.celery_app beat --loglevel=info
```

## Testing Protocol
- Backend tests use `pytest` with `pytest-asyncio`. Run from `surfsense_backend` via `pytest`.
- Backend code standards are maintained with `ruff`.

## Contribution Guidelines
- Ensure `ruff` linting passes before committing python code.
- All dependencies for the frontend should be added using `pnpm`.
- Ensure new backend models have Alembic migrations generated.
