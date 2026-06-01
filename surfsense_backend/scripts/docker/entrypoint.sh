#!/bin/bash
set -e

# ─────────────────────────────────────────────────────────────
# SERVICE_ROLE controls which process(es) this container runs.
#
#   migrate – Run `alembic upgrade head`, verify zero_publication,
#             then exit 0. Used by the dedicated `migrations` service
#             in docker-compose.yml so downstream services can gate
#             on `condition: service_completed_successfully`.
#   api     – FastAPI backend only (does NOT run migrations)
#   worker  – Celery worker only
#   beat    – Celery beat scheduler only
#   all     – migrations + api + worker + beat in one container
#             (legacy / dev default; fails fast on migration error)
#
# Set SERVICE_ROLE as an environment variable in Coolify for
# each service deployment.
# ─────────────────────────────────────────────────────────────
SERVICE_ROLE="${SERVICE_ROLE:-all}"
echo "Starting SurfSense with SERVICE_ROLE=${SERVICE_ROLE}"

# ── Autoscale defaults (override via env) ────────────────────
#   CELERY_MAX_WORKERS  – max concurrent worker processes
#   CELERY_MIN_WORKERS  – min workers kept warm
#   CELERY_QUEUES       – comma-separated queues to consume
#                         (empty = all queues for backward compat)
CELERY_MAX_WORKERS="${CELERY_MAX_WORKERS:-10}"
CELERY_MIN_WORKERS="${CELERY_MIN_WORKERS:-2}"
CELERY_MAX_TASKS_PER_CHILD="${CELERY_MAX_TASKS_PER_CHILD:-50}"
CELERY_QUEUES="${CELERY_QUEUES:-}"

# ── Graceful shutdown ────────────────────────────────────────
PIDS=()

cleanup() {
    echo "Shutting down services..."
    for pid in "${PIDS[@]}"; do
        kill -TERM "$pid" 2>/dev/null || true
    done
    for pid in "${PIDS[@]}"; do
        wait "$pid" 2>/dev/null || true
    done
    exit 0
}

trap cleanup SIGTERM SIGINT

# ── Database migrations (only for migrate / all) ─────────────
# Fail-fast contract:
#   - alembic upgrade head must succeed within ${MIGRATION_TIMEOUT:-900}s
#   - zero_publication must exist in pg_publication afterwards
# Either failure exits non-zero so the dedicated `migrations` compose
# service exits non-zero, halting the rest of the stack instead of
# silently producing a half-built system that crash-loops zero-cache.
run_migrations() {
    echo "Running database migrations..."
    for i in {1..30}; do
        if python -c "from app.db import engine; import asyncio; asyncio.run(engine.dispose())" 2>/dev/null; then
            echo "Database is ready."
            break
        fi
        echo "Waiting for database... ($i/30)"
        sleep 1
    done

    local timeout_secs="${MIGRATION_TIMEOUT:-900}"
    echo "Running alembic upgrade head (timeout=${timeout_secs}s)..."
    if ! timeout "${timeout_secs}" alembic upgrade head; then
        echo "ERROR: alembic upgrade head failed (or exceeded ${timeout_secs}s timeout)." >&2
        echo "Refusing to start. Inspect the error above and re-run." >&2
        exit 1
    fi
    echo "Migrations completed successfully."

    echo "Verifying zero_publication exists in Postgres..."
    local pub_oid
    pub_oid=$(python <<'PY' 2>/dev/null || true
import asyncio
import sys
from sqlalchemy import text
from app.db import engine


async def get_oid():
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT oid FROM pg_publication WHERE pubname = 'zero_publication'")
        )
        row = result.first()
        if row is None:
            sys.exit(1)
        print(int(row[0]))


asyncio.run(get_oid())
PY
)
    if [ -z "${pub_oid}" ]; then
        echo "ERROR: zero_publication is missing from Postgres after running alembic." >&2
        echo "This usually means migration 116 (or a later publication migration) did not run." >&2
        echo "Inspect alembic state with:" >&2
        echo "  docker compose exec db psql -U \"\$DB_USER\" -d \"\$DB_NAME\" -c 'SELECT * FROM alembic_version;'" >&2
        exit 1
    fi
    echo "zero_publication verified (oid=${pub_oid})."

    # Stale-replica safety net: if /zero-init is mounted (i.e. we are the
    # dedicated `migrations` compose service), drop a marker file when the
    # publication oid changed (or on first run) so the wrapped zero-cache
    # entrypoint can wipe /data/zero.db before starting. This recovers from
    # the case where a previous zero-cache crashed mid-init and left a
    # half-built SQLite replica without a `_zero.tableMetadata` table.
    if [ -d /zero-init ]; then
        local stored_oid=""
        [ -f /zero-init/last_pub_oid ] && stored_oid=$(cat /zero-init/last_pub_oid 2>/dev/null || true)
        if [ -z "${stored_oid}" ] || [ "${stored_oid}" != "${pub_oid}" ]; then
            echo "Publication oid changed (stored=${stored_oid:-<none>}, current=${pub_oid}); writing /zero-init/needs_reset."
            : > /zero-init/needs_reset
            chmod 666 /zero-init/needs_reset 2>/dev/null || true
        fi
        echo "${pub_oid}" > /zero-init/last_pub_oid
        chmod 666 /zero-init/last_pub_oid 2>/dev/null || true
        # World-writable dir so the (possibly non-root) zero-cache container
        # can `rm -f /zero-init/needs_reset` after acting on the marker.
        chmod 777 /zero-init 2>/dev/null || true
    fi
}

# ── Service starters ─────────────────────────────────────────
start_api() {
    echo "Starting FastAPI Backend..."
    python main.py &
    PIDS+=($!)
    echo "  FastAPI PID=${PIDS[-1]}"
}

start_worker() {
    QUEUE_ARGS=""
    if [ -n "${CELERY_QUEUES}" ]; then
        QUEUE_ARGS="--queues=${CELERY_QUEUES}"
    else
        # When no queues specified, consume from the default, connectors, and
        # gateway maintenance queues. Without --queues, Celery only consumes
        # from the default queue, leaving connector/gateway maintenance tasks stuck.
        DEFAULT_Q="${CELERY_TASK_DEFAULT_QUEUE:-surfsense}"
        QUEUE_ARGS="--queues=${DEFAULT_Q},${DEFAULT_Q}.connectors,${DEFAULT_Q}.gateway"
    fi

    echo "Starting Celery Worker (autoscale=${CELERY_MAX_WORKERS},${CELERY_MIN_WORKERS}, max-tasks-per-child=${CELERY_MAX_TASKS_PER_CHILD}, queues=${CELERY_QUEUES:-all})..."
    celery -A app.celery_app worker \
        --loglevel=info \
        --autoscale="${CELERY_MAX_WORKERS},${CELERY_MIN_WORKERS}" \
        --max-tasks-per-child="${CELERY_MAX_TASKS_PER_CHILD}" \
        --prefetch-multiplier=1 \
        -Ofair \
        ${QUEUE_ARGS} &
    PIDS+=($!)
    echo "  Celery Worker PID=${PIDS[-1]}"
}

start_beat() {
    echo "Starting Celery Beat..."
    celery -A app.celery_app beat --loglevel=info &
    PIDS+=($!)
    echo "  Celery Beat PID=${PIDS[-1]}"
}

# ── Main: run based on role ──────────────────────────────────
case "${SERVICE_ROLE}" in
    migrate)
        run_migrations
        echo "Migrations complete; exiting cleanly."
        exit 0
        ;;
    api)
        start_api
        ;;
    worker)
        start_worker
        ;;
    beat)
        start_beat
        ;;
    all)
        run_migrations
        start_api
        sleep 5
        start_worker
        sleep 3
        start_beat
        ;;
    *)
        echo "ERROR: Unknown SERVICE_ROLE '${SERVICE_ROLE}'. Use: migrate, api, worker, beat, or all"
        exit 1
        ;;
esac

echo "All requested services started. PIDs: ${PIDS[*]}"

# Wait for any process to exit
wait -n

# If we get here, one process exited unexpectedly
exit $?
