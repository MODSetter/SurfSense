#!/bin/bash
# =============================================================================
# E2E entrypoint for the multi-stage Dockerfile's `e2e` target.
#
# Dispatches on SERVICE_ROLE to the test-only entrypoints under tests/e2e/.
# Those scripts apply sys.modules hijacks and LLM/embedding patches BEFORE
# importing production app code (see tests/e2e/run_backend.py for rationale).
#
# Production never sees this file: tests/ is excluded from the production
# stage, and the production stage uses scripts/docker/entrypoint.sh.
# =============================================================================
set -euo pipefail

SERVICE_ROLE="${SERVICE_ROLE:-api}"
echo "[e2e-entrypoint] starting role=${SERVICE_ROLE}"

wait_for_db() {
    # Block until the database is reachable. We don't loop forever — Compose
    # depends_on/healthchecks already gate on db readiness, this is just
    # belt-and-suspenders so a slow first connection doesn't race migrations.
    for i in {1..60}; do
        echo "[e2e-entrypoint] db check attempt ${i}/60"
        if python -c "from app.db import engine; import asyncio; asyncio.run(engine.dispose())"; then
            echo "[e2e-entrypoint] db reachable after ${i} attempts"
            return 0
        fi
        sleep 1
    done
    echo "[e2e-entrypoint] ERROR: db not reachable after 60s" >&2
    return 1
}

case "${SERVICE_ROLE}" in
    api)
        wait_for_db
        echo "[e2e-entrypoint] running alembic upgrade head"
        alembic upgrade head
        # `exec` so SIGTERM from `docker stop` reaches Python directly,
        # without a shell wrapper interposing.
        exec python tests/e2e/run_backend.py
        ;;
    worker)
        # Worker doesn't run migrations — the api role does that exactly once.
        # We still wait for db so Celery's broker connection check doesn't
        # race against an unready Postgres on cold start.
        wait_for_db
        exec python tests/e2e/run_celery.py
        ;;
    *)
        echo "[e2e-entrypoint] ERROR: unknown SERVICE_ROLE='${SERVICE_ROLE}' (expected: api | worker)" >&2
        exit 1
        ;;
esac
