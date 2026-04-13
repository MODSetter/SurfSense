# SurfSense - Suggested Commands

## Docker Services (Infrastructure)
```bash
# Start all infra services (db + pgadmin)
cd /Users/luisphan/Documents/GitHub/SurfSense
docker compose -f docker/docker-compose.dev.yml --env-file docker/.env up -d db pgadmin

# Start zero-cache standalone (BE & FE run local)
docker run -d \
  --name surfsense-zero-cache \
  --network surfsense-dev_default \
  --add-host "host.docker.internal:host-gateway" \
  -p 4848:4848 \
  -v surfsense-dev-zero-cache:/data \
  -e ZERO_UPSTREAM_DB="postgresql://postgres:postgres@surfsense-dev-db-1:5432/surfsense?sslmode=disable" \
  -e ZERO_CVR_DB="postgresql://postgres:postgres@surfsense-dev-db-1:5432/surfsense?sslmode=disable" \
  -e ZERO_CHANGE_DB="postgresql://postgres:postgres@surfsense-dev-db-1:5432/surfsense?sslmode=disable" \
  -e ZERO_REPLICA_FILE="/data/zero.db" \
  -e ZERO_ADMIN_PASSWORD="surfsense-zero-admin" \
  -e ZERO_APP_PUBLICATIONS="zero_publication" \
  -e ZERO_NUM_SYNC_WORKERS="4" \
  -e ZERO_UPSTREAM_MAX_CONNS="20" \
  -e ZERO_CVR_MAX_CONNS="30" \
  -e ZERO_QUERY_URL="http://host.docker.internal:3000/api/zero/query" \
  -e ZERO_MUTATE_URL="http://host.docker.internal:3000/api/zero/mutate" \
  rocicorp/zero:0.26.2

# SearXNG: reuse mrholmes-searxng trên port 8888
# Redis: reuse redis-server local trên localhost:6379/1
```

## Backend (FastAPI)
```bash
cd /Users/luisphan/Documents/GitHub/SurfSense/surfsense_backend
uv sync                        # install deps
uv run alembic upgrade head    # run migrations
uv run python main.py --reload # start dev server on port 8001
# OR Celery worker:
uv run celery -A app.celery_app worker -Q surfsense --loglevel=info
```

## Frontend (Next.js)
```bash
cd /Users/luisphan/Documents/GitHub/SurfSense/surfsense_web
pnpm install
pnpm dev                       # http://localhost:3000

# DB commands (drizzle)
pnpm db:generate
pnpm db:migrate
pnpm db:studio                 # Drizzle Studio UI
```

## Ports Summary
| Service       | Port  | Notes |
|---------------|-------|-------|
| PostgreSQL    | 5432  | docker |
| pgAdmin       | 5050  | docker, http://localhost:5050 |
| Redis (local) | 6379  | db=1 for SurfSense |
| SearXNG       | 8888  | shared mrholmes-searxng |
| zero-cache    | 4848  | docker standalone |
| Backend       | 8001  | port 8000 used by chainlens |
| Frontend      | 3000  | Next.js |

## Health Checks
```bash
curl http://localhost:8001/health    # {"status":"ok"}
curl http://localhost:3000           # HTML
nc -z localhost 4848 && echo OK     # zero-cache
redis-cli ping                       # PONG
docker ps --filter "name=surfsense" # docker services
```
