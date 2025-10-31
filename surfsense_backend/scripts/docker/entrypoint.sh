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

echo "Starting FastAPI Backend..."
python main.py &
backend_pid=$!

# Wait a bit for backend to initialize
sleep 5

echo "Starting Celery Worker..."
celery -A app.celery_app worker --loglevel=info &
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

