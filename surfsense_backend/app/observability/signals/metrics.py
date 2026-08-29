"""Generic metric mechanism: meter access and safe record/add."""

from __future__ import annotations

import contextlib
import logging
from functools import lru_cache
from typing import Any

from app.observability.core import config
from app.observability.core.attributes import clean_attributes
from app.observability.core.resource import INSTRUMENTATION_NAME, package_version

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_meter():
    from opentelemetry import metrics

    return metrics.get_meter(INSTRUMENTATION_NAME, package_version())


def record(instrument: Any, value: int | float, attrs: dict[str, Any]) -> None:
    if not config.is_enabled():
        return
    with contextlib.suppress(Exception):
        instrument.record(value, clean_attributes(attrs))


def add(instrument: Any, value: int, attrs: dict[str, Any]) -> None:
    if not config.is_enabled():
        return
    with contextlib.suppress(Exception):
        instrument.add(value, clean_attributes(attrs))


def attrs_with_error_category(
    attrs: dict[str, Any], error_category: str | None
) -> dict[str, Any]:
    """Append ``error.category`` only when a category is known."""
    return {**attrs, "error.category": error_category} if error_category else attrs


@lru_cache(maxsize=1)
def _perf_elapsed():
    return get_meter().create_histogram(
        "surfsense.perf.elapsed_ms",
        unit="ms",
        description="Elapsed time recorded by SurfSense perf timers.",
    )


def record_perf_elapsed(duration_ms: float, *, label: str) -> None:
    """Generic elapsed-time timer (not domain-specific)."""
    record(_perf_elapsed(), duration_ms, {"label": label})
