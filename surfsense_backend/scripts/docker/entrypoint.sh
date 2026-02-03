#!/bin/bash
set -e

# Function to handle shutdown gracefully
cleanup() {
    echo "Shutting down services..."
    kill -TERM "$backend_pid" "$celery_worker_pid" "$celery_beat_pid" 2>/dev/null || true
    wait "$backend_pid" "$celery_worker_pid" "$celery_beat_pid" 2>/dev/null || true
    exit 0
}

trap cleanup SIGTERM SIGINT

# Run database migrations with safeguards
echo "Running database migrations..."
# Wait for database to be ready (max 30 seconds)
for i in {1..30}; do
    if python -c "from app.db import engine; import asyncio; asyncio.run(engine.dispose())" 2>/dev/null; then
        echo "Database is ready."
        break
    fi
    echo "Waiting for database... ($i/30)"
    sleep 1
done

# Run migrations with timeout (60 seconds max)
if timeout 60 alembic upgrade head 2>&1; then
    echo "Migrations completed successfully."
else
    echo "WARNING: Migration failed or timed out. Continuing anyway..."
    echo "You may need to run migrations manually: alembic upgrade head"
fi

echo "Starting FastAPI Backend..."
python main.py &
backend_pid=$!

# Wait a bit for backend to initialize
sleep 5

echo "Starting Celery Worker..."
celery -A app.celery_app worker --loglevel=info --autoscale=128,4 &
celery_worker_pid=$!

# Wait a bit for worker to initialize
sleep 3

echo "Starting Celery Beat..."
celery -A app.celery_app beat --loglevel=info &
celery_beat_pid=$!

echo "All services started. PIDs: Backend=$backend_pid, Worker=$celery_worker_pid, Beat=$celery_beat_pid"

# Wait for any process to exit
wait -n

# If we get here, one process exited, so exit with its status
exit $?
