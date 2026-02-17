#!/bin/bash
set -e

# ─────────────────────────────────────────────────────────────
# SERVICE_ROLE controls which process(es) this container runs.
#
#   api     – FastAPI backend only  (runs migrations on startup)
#   worker  – Celery worker only
#   beat    – Celery beat scheduler only
#   all     – All three in one container (legacy / dev default)
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

# ── Database migrations (only for api / all) ─────────────────
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

    if timeout 60 alembic upgrade head 2>&1; then
        echo "Migrations completed successfully."
    else
        echo "WARNING: Migration failed or timed out. Continuing anyway..."
        echo "You may need to run migrations manually: alembic upgrade head"
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
        # When no queues specified, consume from BOTH the default queue and
        # the connectors queue. Without --queues, Celery only consumes from
        # the default queue, leaving connector indexing tasks stuck.
        DEFAULT_Q="${CELERY_TASK_DEFAULT_QUEUE:-surfsense}"
        QUEUE_ARGS="--queues=${DEFAULT_Q},${DEFAULT_Q}.connectors"
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
    api)
        run_migrations
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
        echo "ERROR: Unknown SERVICE_ROLE '${SERVICE_ROLE}'. Use: api, worker, beat, or all"
        exit 1
        ;;
esac

echo "All requested services started. PIDs: ${PIDS[*]}"

# Wait for any process to exit
wait -n

# If we get here, one process exited unexpectedly
exit $?
