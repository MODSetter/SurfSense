"""Celery application configuration and setup."""

import contextlib
import time

from celery import Celery
from celery.schedules import crontab
from celery.signals import (
    before_task_publish,
    task_postrun,
    task_prerun,
    worker_process_init,
)
from dotenv import load_dotenv

try:
    from opentelemetry import trace
except ImportError:  # pragma: no cover - optional OTel dependency
    trace = None  # type: ignore[assignment]

from app.config import config

# Load environment variables
load_dotenv()


@before_task_publish.connect
def _stamp_enqueue_time(headers=None, **_kwargs):
    """Stamp enqueue time so workers can measure queue wait."""
    if headers is None:
        return
    with contextlib.suppress(Exception):
        headers["surfsense.enqueued_at_ns"] = str(time.monotonic_ns())


@task_prerun.connect
def _record_queue_latency(task=None, **_kwargs):
    """Record queue latency and stash task metadata for span enrichment."""
    if task is None:
        return
    try:
        from app.observability import metrics as ot_metrics

        task_name = getattr(task, "name", None) or "unknown"
        operation = ot_metrics.parse_celery_task_label(task_name)
        request = getattr(task, "request", None)
        delivery_info = getattr(request, "delivery_info", None) or {}
        queue = delivery_info.get("routing_key") or "unknown"
        scheduled = bool(
            getattr(request, "eta", None) or getattr(request, "expires", None)
        )

        with contextlib.suppress(Exception):
            request.surfsense_operation = operation
            request.surfsense_queue = queue
            request.surfsense_scheduled = scheduled

        headers = getattr(request, "headers", None) or {}
        enqueued_ns = headers.get("surfsense.enqueued_at_ns")
        if enqueued_ns is None:
            return

        elapsed_s = (time.monotonic_ns() - int(enqueued_ns)) / 1e9
        with contextlib.suppress(Exception):
            request.surfsense_queue_latency_ms = elapsed_s * 1000

        ot_metrics.record_celery_queue_latency(
            elapsed_s,
            task_name=task_name,
            queue=queue,
            scheduled=scheduled,
            operation=operation,
        )
    except Exception:
        pass


@task_postrun.connect
def _set_celery_span_attributes(task=None, **_kwargs):
    """Attach derived queue metadata to the active Celery run span."""
    if task is None or trace is None:
        return

    try:
        request = getattr(task, "request", None)
        if request is None:
            return

        span = trace.get_current_span()

        operation = getattr(request, "surfsense_operation", None)
        if operation:
            span.set_attribute("celery.task.operation", operation)

        latency_ms = getattr(request, "surfsense_queue_latency_ms", None)
        if latency_ms is not None:
            span.set_attribute("celery.queue.latency_ms", latency_ms)
    except Exception:
        pass


@worker_process_init.connect
def init_worker(**kwargs):
    """Initialize the LLM Router and Image Gen Router when a Celery worker process starts.

    This ensures the Auto mode (LiteLLM Router) is available for background tasks
    like agent workflows and image generation.
    """
    from app.observability.bootstrap import init_otel

    init_otel(app=None, traces=True, metrics=True, logs=True)

    from app.config import (
        initialize_image_gen_router,
        initialize_llm_router,
        initialize_openrouter_integration,
        initialize_pricing_registration,
        initialize_vision_llm_router,
    )

    initialize_openrouter_integration()
    initialize_pricing_registration()
    initialize_llm_router()
    initialize_image_gen_router()
    initialize_vision_llm_router()


# Celery configuration, sourced from the central Config singleton
CELERY_BROKER_URL = config.CELERY_BROKER_URL
CELERY_RESULT_BACKEND = config.CELERY_RESULT_BACKEND
CELERY_TASK_DEFAULT_QUEUE = config.CELERY_TASK_DEFAULT_QUEUE

# Schedule checker interval
# Format: "<number><unit>" where unit is 'm' (minutes) or 'h' (hours)
# Examples: "1m" (every minute), "5m" (every 5 minutes), "1h" (every hour)
SCHEDULE_CHECKER_INTERVAL = config.SCHEDULE_CHECKER_INTERVAL
STRIPE_RECONCILIATION_INTERVAL = config.STRIPE_RECONCILIATION_INTERVAL


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
stripe_reconciliation_schedule_params = parse_schedule_interval(
    STRIPE_RECONCILIATION_INTERVAL
)

# Create Celery app
celery_app = Celery(
    "surfsense",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.celery_tasks.document_tasks",
        "app.podcasts.tasks.draft",
        "app.podcasts.tasks.render",
        "app.tasks.celery_tasks.video_presentation_tasks",
        "app.tasks.celery_tasks.connector_tasks",
        "app.tasks.celery_tasks.obsidian_tasks",
        "app.tasks.celery_tasks.schedule_checker_task",
        "app.tasks.celery_tasks.document_reindex_tasks",
        "app.tasks.celery_tasks.stale_notification_cleanup_task",
        "app.tasks.celery_tasks.stripe_reconciliation_task",
        "app.tasks.celery_tasks.auto_reload_task",
        "app.tasks.celery_tasks.gateway_tasks",
        "app.automations.tasks.execute_run",
        "app.automations.triggers.builtin.schedule.selector",
        "app.automations.triggers.builtin.event.selector",
    ],
)

# ── Queue names ──────────────────────────────────────────────
# Default queue  : fast, user-facing tasks (file upload, podcast, reindex, …)
# Connectors queue: slow, long-running indexing tasks (Notion, Gmail, web crawl, …)
CONNECTORS_QUEUE = f"{CELERY_TASK_DEFAULT_QUEUE}.connectors"

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
    # ── Task routing ─────────────────────────────────────────
    # Route slow connector/indexing tasks to a dedicated queue so they
    # never block fast user-facing tasks (file uploads, podcasts, etc.)
    task_routes={
        # Connector indexing tasks → connectors queue
        "index_notion_pages": {"queue": CONNECTORS_QUEUE},
        "index_github_repos": {"queue": CONNECTORS_QUEUE},
        "index_confluence_pages": {"queue": CONNECTORS_QUEUE},
        "index_google_calendar_events": {"queue": CONNECTORS_QUEUE},
        "index_google_gmail_messages": {"queue": CONNECTORS_QUEUE},
        "index_google_drive_files": {"queue": CONNECTORS_QUEUE},
        "index_elasticsearch_documents": {"queue": CONNECTORS_QUEUE},
        "index_crawled_urls": {"queue": CONNECTORS_QUEUE},
        "index_bookstack_pages": {"queue": CONNECTORS_QUEUE},
        "index_composio_connector": {"queue": CONNECTORS_QUEUE},
        "index_obsidian_attachment": {"queue": CONNECTORS_QUEUE},
        # Everything else (document processing, podcasts, reindexing,
        # schedule checker, cleanup) stays on the default fast queue.
        "gateway.reconcile_inbox": {"queue": f"{CELERY_TASK_DEFAULT_QUEUE}.gateway"},
        "gateway.health_check": {"queue": f"{CELERY_TASK_DEFAULT_QUEUE}.gateway"},
        "gateway.retention_sweep": {"queue": f"{CELERY_TASK_DEFAULT_QUEUE}.gateway"},
    },
)

# Imported late (after celery_app is built) to keep the automations triggers
# package out of this module's top-level import graph.
from app.automations.triggers.builtin.schedule.source import (  # noqa: E402
    BEAT_SCHEDULE as SCHEDULE_BEAT_SCHEDULE,
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
    # Reconcile Stripe credit purchases that were paid but remained pending
    "reconcile-pending-stripe-credit-purchases": {
        "task": "reconcile_pending_stripe_credit_purchases",
        "schedule": crontab(**stripe_reconciliation_schedule_params),
        "options": {
            "expires": 60,
        },
    },
    "gateway-reconcile-inbox": {
        "task": "gateway.reconcile_inbox",
        "schedule": crontab(minute="*"),
        "options": {"expires": 60},
    },
    "gateway-health-check": {
        "task": "gateway.health_check",
        "schedule": crontab(minute="*/5"),
        "options": {"expires": 120},
    },
    "gateway-retention-sweep": {
        "task": "gateway.retention_sweep",
        "schedule": crontab(hour="3", minute="17"),
        "options": {"expires": 600},
    },
    # Fire due automation schedule triggers (Beat entry owned by the schedule
    # trigger; see app.automations.triggers.builtin.schedule.source).
    **SCHEDULE_BEAT_SCHEDULE,
}
