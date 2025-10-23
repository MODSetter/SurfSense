"""Celery application configuration and setup."""

import os

from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get Celery configuration from environment
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

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
    # Task execution settings
    task_track_started=True,
    task_time_limit=3600,  # 1 hour hard limit
    task_soft_time_limit=3000,  # 50 minutes soft limit
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
# for each connector, we have ONE schedule that checks the database every minute
# for connectors that need indexing. This provides dynamic scheduling without restarts.
celery_app.conf.beat_schedule = {
    "check-periodic-connector-schedules": {
        "task": "check_periodic_schedules",
        "schedule": crontab(minute="*"),  # Run every minute
        "options": {
            "expires": 30,  # Task expires after 30 seconds if not picked up
        },
    },
}
