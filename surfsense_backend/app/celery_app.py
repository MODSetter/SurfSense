"""Celery application configuration and setup."""

import os

from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_process_init
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


@worker_process_init.connect
def init_worker(**kwargs):
    """Initialize the LLM Router when a Celery worker process starts.

    This ensures the Auto mode (LiteLLM Router) is available for background tasks
    like document summarization.
    """
    from app.config import initialize_llm_router

    initialize_llm_router()


# Get Celery configuration from environment
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
CELERY_TASK_DEFAULT_QUEUE = os.getenv("CELERY_TASK_DEFAULT_QUEUE", "surfsense")

# Get schedule checker interval from environment
# Format: "<number><unit>" where unit is 'm' (minutes) or 'h' (hours)
# Examples: "1m" (every minute), "5m" (every 5 minutes), "1h" (every hour)
SCHEDULE_CHECKER_INTERVAL = os.getenv("SCHEDULE_CHECKER_INTERVAL", "2m")


def parse_schedule_interval(interval: str) -> dict:
    """Parse interval string into crontab parameters.

    Args:
        interval: String like "1m", "5m", "1h", etc.

    Returns:
        Dict with crontab parameters (minute, hour)
    """
    interval = interval.strip().lower()

    # Extract number and unit
    if interval.endswith("m") or interval.endswith("min"):
        # Minutes
        num = int(interval.rstrip("min"))
        if num == 1:
            return {"minute": "*", "hour": "*"}
        else:
            return {"minute": f"*/{num}", "hour": "*"}
    elif interval.endswith("h") or interval.endswith("hour"):
        # Hours
        num = int(interval.rstrip("hour"))
        if num == 1:
            return {"minute": "0", "hour": "*"}
        else:
            return {"minute": "0", "hour": f"*/{num}"}
    else:
        # Default to every minute if parsing fails
        return {"minute": "*", "hour": "*"}


# Parse the schedule interval
schedule_params = parse_schedule_interval(SCHEDULE_CHECKER_INTERVAL)

# Create Celery app
celery_app = Celery(
    "surfsense",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.celery_tasks.document_tasks",
        "app.tasks.celery_tasks.podcast_tasks",
        "app.tasks.celery_tasks.connector_tasks",
        "app.tasks.celery_tasks.schedule_checker_task",
        "app.tasks.celery_tasks.blocknote_migration_tasks",
        "app.tasks.celery_tasks.document_reindex_tasks",
        "app.tasks.celery_tasks.stale_notification_cleanup_task",
        "app.tasks.celery_tasks.connector_deletion_task",
    ],
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_default_queue=CELERY_TASK_DEFAULT_QUEUE,
    task_default_exchange=CELERY_TASK_DEFAULT_QUEUE,
    task_default_routing_key=CELERY_TASK_DEFAULT_QUEUE,
    # Task execution settings
    task_track_started=True,
    task_time_limit=28800,  # 8 hour hard limit
    task_soft_time_limit=28200,  # 7 hours 50 minutes soft limit
    # Result backend settings
    result_expires=86400,  # Results expire after 24 hours
    result_extended=True,
    # Worker settings
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    # Retry settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # Broker settings
    broker_connection_retry_on_startup=True,
    # Beat scheduler settings
    beat_max_loop_interval=60,  # Check every minute
)

# Configure Celery Beat schedule
# This uses a meta-scheduler pattern: instead of creating individual Beat schedules
# for each connector, we have ONE schedule that checks the database at the configured interval
# for connectors that need indexing. This provides dynamic scheduling without restarts.
celery_app.conf.beat_schedule = {
    "check-periodic-connector-schedules": {
        "task": "check_periodic_schedules",
        "schedule": crontab(**schedule_params),
        "options": {
            "expires": 30,  # Task expires after 30 seconds if not picked up
        },
    },
    # Cleanup stale connector indexing notifications every 5 minutes
    # This detects tasks that crashed or timed out without proper cleanup
    # and marks their notifications as failed so users don't see perpetual "syncing"
    "cleanup-stale-indexing-notifications": {
        "task": "cleanup_stale_indexing_notifications",
        "schedule": crontab(minute="*/5"),  # Every 5 minutes
        "options": {
            "expires": 60,  # Task expires after 60 seconds if not picked up
        },
    },
}
