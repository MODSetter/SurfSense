"""Host/runtime telemetry: process + GC observable gauges."""

from __future__ import annotations

import gc
import logging
from typing import Any

from app.observability.core import config
from app.observability.signals import metrics as m

logger = logging.getLogger(__name__)

_OBSERVABLES_REGISTERED = False


def _snapshot_value(key: str, transform: Any = None) -> list[Any]:
    from opentelemetry.metrics import Observation

    from app.utils.perf import system_snapshot

    snap = system_snapshot()
    value = snap.get(key)
    if not isinstance(value, int | float) or value < 0:
        return []
    if transform is not None:
        value = transform(value)
    return [Observation(value)]


def _observe_gc_collections(_options: Any) -> list[Any]:
    from opentelemetry.metrics import Observation

    return [
        Observation(count, {"generation": str(generation)})
        for generation, count in enumerate(gc.get_count())
    ]


def register_runtime_observables() -> None:
    """Register process/runtime observable gauges once per process."""
    global _OBSERVABLES_REGISTERED
    if _OBSERVABLES_REGISTERED or not config.is_enabled():
        return

    meter = m.get_meter()
    try:
        meter.create_observable_gauge(
            "process.runtime.cpython.memory.rss",
            callbacks=[
                lambda _options: _snapshot_value(
                    "rss_mb", lambda v: float(v) * 1024 * 1024
                )
            ],
            unit="By",
            description="Resident set size of the SurfSense backend process.",
        )
        meter.create_observable_gauge(
            "process.runtime.cpython.cpu.utilization",
            callbacks=[
                lambda _options: _snapshot_value(
                    "cpu_percent", lambda v: float(v) / 100.0
                )
            ],
            unit="1",
            description="CPU utilization of the SurfSense backend process.",
        )
        meter.create_observable_gauge(
            "process.runtime.cpython.threads",
            callbacks=[lambda _options: _snapshot_value("threads")],
            unit="{thread}",
            description="Thread count of the SurfSense backend process.",
        )
        meter.create_observable_gauge(
            "process.runtime.cpython.open_fds",
            callbacks=[lambda _options: _snapshot_value("open_fds")],
            unit="{fd}",
            description="Open file descriptor count of the SurfSense backend process.",
        )
        meter.create_observable_gauge(
            "python.asyncio.tasks",
            callbacks=[lambda _options: _snapshot_value("asyncio_tasks")],
            unit="{task}",
            description="Live asyncio task count in the current event loop.",
        )
        meter.create_observable_gauge(
            "process.runtime.cpython.gc.collections",
            callbacks=[_observe_gc_collections],
            unit="{collection}",
            description="CPython GC counters by generation.",
        )
    except Exception:
        logger.warning("Failed to register OTel runtime observables", exc_info=True)
        return

    _OBSERVABLES_REGISTERED = True
