# SurfSense backend

FastAPI app: scraper API, knowledge base, auth, and the self-host server.

This is not the desktop sidecar. Desktop Python lives in [`surfsense_local/backend/`](../surfsense_local/backend/).

## You need

- Python 3.12+ and [uv](https://docs.astral.sh/uv/)
- PostgreSQL with [pgvector](https://github.com/pgvector/pgvector)
- Redis (background jobs)

The smallest way to get Postgres and Redis is from the repo root:

```bash
docker compose -f docker/docker-compose.deps-only.yml up -d db redis
```

## Run it

```bash
cp .env.example .env
uv sync
uv run alembic upgrade head
uv run main.py --reload
```

API: http://localhost:8000  
Docs: http://localhost:8000/docs

`.env.example` is the config map. For local Docker Postgres the default `DATABASE_URL` already matches `deps-only`. Set `SECRET_KEY` to something of your own. Leave `SUNSET_MODE` unset.

Uploads, connectors, and other background work need a worker in a second terminal:

```bash
uv run celery -A celery_worker.celery_app worker --loglevel=info --concurrency=1 --pool=solo --queues=surfsense,surfsense.connectors,surfsense.gateway
```

Scheduled jobs need beat as well (`uv run celery -A celery_worker.celery_app beat --loglevel=info`). Skip both until you touch that path.

## Tests

```bash
uv run pytest -m unit
AUTH_TYPE=LOCAL uv run pytest -m integration   # needs Postgres
```

More on the suite: [tests/README.md](tests/README.md).

## UI

The Next.js app is [`surfsense_web/`](../surfsense_web/README.md). It talks to this API. You do not need it for a backend-only change.

Full stack, Google auth, ETL keys, and zero-cache: [manual installation](../surfsense_web/content/docs/manual-installation.mdx).
