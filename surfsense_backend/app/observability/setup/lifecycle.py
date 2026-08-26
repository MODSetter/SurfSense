"""Process-level OpenTelemetry init and shutdown orchestration."""

from __future__ import annotations

from typing import Any

from app.observability.core import config
from app.observability.setup import instrumentation, providers


def init_otel(
    app: Any | None = None,
    *,
    traces: bool = True,
    metrics: bool = True,
    logs: bool = True,
) -> None:
    """Initialize OpenTelemetry for a FastAPI or Celery process."""
    if config.is_disabled() or not config.is_configured():
        config.reload_for_tests()
        return

    if traces:
        providers.install_traces()
    if metrics:
        providers.install_metrics()

    config.reload_for_tests()

    if metrics:
        from app.observability.domains import runtime

        runtime.register_runtime_observables()

    if logs:
        providers.install_logging()
        instrumentation.instrument_logging()

    instrumentation.instrument_libraries(app)


def shutdown_otel(timeout_millis: int = 5000) -> None:
    """Best-effort flush and shutdown of all installed providers."""
    providers.shutdown(timeout_millis)
