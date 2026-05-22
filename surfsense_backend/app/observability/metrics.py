"""Custom OpenTelemetry metrics for SurfSense.

This module owns all SurfSense-specific metric instruments. Callers use the
small helper functions below instead of constructing instruments directly so
attribute names and cardinality stay consistent across the backend.
"""

from __future__ import annotations

import contextlib
import gc
import logging
from functools import lru_cache
from importlib import metadata
from typing import Any

from app.observability import otel

logger = logging.getLogger(__name__)

_INSTRUMENTATION_NAME = "surfsense.platform"
_OBSERVABLES_REGISTERED = False


def _package_version() -> str:
    with contextlib.suppress(metadata.PackageNotFoundError):
        return metadata.version("surf-new-backend")
    return "unknown"


def _is_enabled() -> bool:
    return otel.is_enabled()


def _clean_attrs(attrs: dict[str, Any]) -> dict[str, str | int | float | bool]:
    """Drop empty values and coerce low-cardinality attrs to OTel-safe scalars."""
    cleaned: dict[str, str | int | float | bool] = {}
    for key, value in attrs.items():
        if value is None:
            continue
        if isinstance(value, bool | int | float):
            cleaned[key] = value
            continue
        text = str(value)
        if text:
            cleaned[key] = text
    return cleaned


def _record(callable_obj: Any, value: int | float, attrs: dict[str, Any]) -> None:
    if not _is_enabled():
        return
    with contextlib.suppress(Exception):
        callable_obj.record(value, _clean_attrs(attrs))


def _add(callable_obj: Any, value: int, attrs: dict[str, Any]) -> None:
    if not _is_enabled():
        return
    with contextlib.suppress(Exception):
        callable_obj.add(value, _clean_attrs(attrs))


@lru_cache(maxsize=1)
def _get_meter():
    from opentelemetry import metrics

    return metrics.get_meter(_INSTRUMENTATION_NAME, _package_version())


@lru_cache(maxsize=1)
def _model_call_duration():
    return _get_meter().create_histogram(
        "surfsense.model.call.duration",
        unit="ms",
        description="Duration of SurfSense LLM model calls.",
    )


@lru_cache(maxsize=1)
def _model_token_usage():
    return _get_meter().create_histogram(
        "gen_ai.client.token.usage",
        unit="{token}",
        description="Token usage reported by GenAI model responses.",
    )


@lru_cache(maxsize=1)
def _tool_call_duration():
    return _get_meter().create_histogram(
        "surfsense.tool.call.duration",
        unit="ms",
        description="Duration of SurfSense agent tool calls.",
    )


@lru_cache(maxsize=1)
def _tool_call_errors():
    return _get_meter().create_counter(
        "surfsense.tool.call.errors",
        description="Count of SurfSense agent tool call errors.",
    )


@lru_cache(maxsize=1)
def _kb_search_duration():
    return _get_meter().create_histogram(
        "surfsense.kb.search.duration",
        unit="ms",
        description="Duration of SurfSense knowledge-base search calls.",
    )


@lru_cache(maxsize=1)
def _compaction_runs():
    return _get_meter().create_counter(
        "surfsense.compaction.runs",
        description="Count of SurfSense conversation compaction runs.",
    )


@lru_cache(maxsize=1)
def _permission_asks():
    return _get_meter().create_counter(
        "surfsense.permission.asks",
        description="Count of SurfSense permission asks.",
    )


@lru_cache(maxsize=1)
def _interrupts():
    return _get_meter().create_counter(
        "surfsense.interrupt.raised",
        description="Count of SurfSense interrupts raised.",
    )


@lru_cache(maxsize=1)
def _indexing_document_duration():
    return _get_meter().create_histogram(
        "surfsense.indexing.document.duration",
        unit="s",
        description="Duration of SurfSense document indexing.",
    )


@lru_cache(maxsize=1)
def _indexing_document_outcome():
    return _get_meter().create_counter(
        "surfsense.indexing.document.outcome",
        description="Count of SurfSense document indexing outcomes.",
    )


@lru_cache(maxsize=1)
def _connector_sync_duration():
    return _get_meter().create_histogram(
        "surfsense.connector.sync.duration",
        unit="s",
        description="Duration of SurfSense connector sync tasks.",
    )


@lru_cache(maxsize=1)
def _connector_sync_outcome():
    return _get_meter().create_counter(
        "surfsense.connector.sync.outcome",
        description="Count of SurfSense connector sync outcomes.",
    )


@lru_cache(maxsize=1)
def _auth_failures():
    return _get_meter().create_counter(
        "surfsense.auth.failures",
        description="Count of SurfSense authentication failures.",
    )


@lru_cache(maxsize=1)
def _rate_limit_rejections():
    return _get_meter().create_counter(
        "surfsense.rate_limit.rejections",
        description="Count of SurfSense rate-limit rejections.",
    )


@lru_cache(maxsize=1)
def _perf_elapsed():
    return _get_meter().create_histogram(
        "surfsense.perf.elapsed_ms",
        unit="ms",
        description="Elapsed time recorded by SurfSense perf timers.",
    )


@lru_cache(maxsize=1)
def _chat_request_duration():
    return _get_meter().create_histogram(
        "surfsense.chat.request.duration",
        unit="ms",
        description="Duration of SurfSense streamed chat requests.",
    )


@lru_cache(maxsize=1)
def _chat_request_outcome():
    return _get_meter().create_counter(
        "surfsense.chat.request.outcome",
        description="Count of SurfSense chat request outcomes.",
    )


@lru_cache(maxsize=1)
def _subagent_invoke_duration():
    return _get_meter().create_histogram(
        "surfsense.subagent.invoke.duration",
        unit="ms",
        description="Duration of SurfSense subagent invocations.",
    )


@lru_cache(maxsize=1)
def _subagent_invoke_outcome():
    return _get_meter().create_counter(
        "surfsense.subagent.invoke.outcome",
        description="Count of SurfSense subagent invocation outcomes.",
    )


@lru_cache(maxsize=1)
def _etl_extract_duration():
    return _get_meter().create_histogram(
        "surfsense.etl.extract.duration",
        unit="s",
        description="Duration of SurfSense ETL extraction.",
    )


@lru_cache(maxsize=1)
def _etl_extract_outcome():
    return _get_meter().create_counter(
        "surfsense.etl.extract.outcome",
        description="Count of SurfSense ETL extraction outcomes.",
    )


@lru_cache(maxsize=1)
def _celery_heartbeat_refreshes():
    return _get_meter().create_counter(
        "surfsense.celery.heartbeat.refreshes",
        description="Count of SurfSense Celery heartbeat refreshes.",
    )


@lru_cache(maxsize=1)
def _celery_heartbeat_failures():
    return _get_meter().create_counter(
        "surfsense.celery.heartbeat.failures",
        description="Count of SurfSense Celery heartbeat failures.",
    )


def record_model_call_duration(
    duration_ms: float, *, model: str | None, provider: str | None
) -> None:
    _record(
        _model_call_duration(),
        duration_ms,
        {
            "gen_ai.request.model": model,
            "gen_ai.provider.name": provider,
        },
    )


def record_model_token_usage(
    *,
    input_tokens: int | None,
    output_tokens: int | None,
    model: str | None,
    provider: str | None,
) -> None:
    base = {
        "gen_ai.request.model": model,
        "gen_ai.provider.name": provider,
        "gen_ai.operation.name": "chat",
    }
    if input_tokens is not None:
        _record(
            _model_token_usage(),
            int(input_tokens),
            {**base, "gen_ai.token.type": "input"},
        )
    if output_tokens is not None:
        _record(
            _model_token_usage(),
            int(output_tokens),
            {**base, "gen_ai.token.type": "output"},
        )


def record_tool_call_duration(duration_ms: float, *, tool_name: str) -> None:
    _record(_tool_call_duration(), duration_ms, {"tool.name": tool_name})


def record_tool_call_error(*, tool_name: str) -> None:
    _add(_tool_call_errors(), 1, {"tool.name": tool_name})


def record_kb_search_duration(
    duration_ms: float, *, search_space_id: int | None, surface: str
) -> None:
    _record(
        _kb_search_duration(),
        duration_ms,
        {"search_space.id": search_space_id, "search.surface": surface},
    )


def record_compaction_run(*, reason: str | None) -> None:
    _add(_compaction_runs(), 1, {"compaction.reason": reason or "unknown"})


def record_permission_ask(*, permission: str) -> None:
    _add(_permission_asks(), 1, {"permission.permission": permission})


def record_interrupt(*, interrupt_type: str) -> None:
    _add(_interrupts(), 1, {"interrupt.type": interrupt_type})


def record_indexing_document_duration(
    duration_s: float, *, document_type: str | None
) -> None:
    _record(
        _indexing_document_duration(),
        duration_s,
        {"document.type": document_type or "unknown"},
    )


def record_indexing_document_outcome(*, document_type: str | None, status: str) -> None:
    _add(
        _indexing_document_outcome(),
        1,
        {"document.type": document_type or "unknown", "status": status},
    )


def record_connector_sync_duration(
    duration_s: float, *, connector_type: str | None
) -> None:
    _record(
        _connector_sync_duration(),
        duration_s,
        {"connector.type": connector_type or "unknown"},
    )


def record_connector_sync_outcome(*, connector_type: str | None, status: str) -> None:
    _add(
        _connector_sync_outcome(),
        1,
        {"connector.type": connector_type or "unknown", "status": status},
    )


def record_auth_failure(*, reason: str) -> None:
    _add(_auth_failures(), 1, {"reason": reason})


def record_rate_limit_rejection(*, scope: str) -> None:
    _add(_rate_limit_rejections(), 1, {"scope": scope})


def record_perf_elapsed(duration_ms: float, *, label: str) -> None:
    _record(_perf_elapsed(), duration_ms, {"label": label})


def record_chat_request_duration(
    duration_ms: float,
    *,
    flow: str,
    outcome: str,
    agent_mode: str | None = None,
) -> None:
    _record(
        _chat_request_duration(),
        duration_ms,
        {"chat.flow": flow, "outcome": outcome, "agent.mode": agent_mode},
    )


def record_chat_request_outcome(
    *,
    flow: str,
    outcome: str,
    agent_mode: str | None = None,
) -> None:
    _add(
        _chat_request_outcome(),
        1,
        {"chat.flow": flow, "outcome": outcome, "agent.mode": agent_mode},
    )


def record_subagent_invoke_duration(
    duration_ms: float,
    *,
    subagent_type: str,
    path: str | None,
    outcome: str,
) -> None:
    _record(
        _subagent_invoke_duration(),
        duration_ms,
        {
            "subagent.type": subagent_type,
            "subagent.path": path or "unknown",
            "outcome": outcome,
        },
    )


def record_subagent_invoke_outcome(
    *,
    subagent_type: str,
    path: str | None,
    outcome: str,
) -> None:
    _add(
        _subagent_invoke_outcome(),
        1,
        {
            "subagent.type": subagent_type,
            "subagent.path": path or "unknown",
            "outcome": outcome,
        },
    )


def record_etl_extract_duration(
    duration_s: float,
    *,
    etl_service: str | None,
    content_type: str | None,
    status: str,
) -> None:
    _record(
        _etl_extract_duration(),
        duration_s,
        {
            "etl.service": etl_service or "unknown",
            "content.type": content_type or "unknown",
            "status": status,
        },
    )


def record_etl_extract_outcome(
    *,
    etl_service: str | None,
    content_type: str | None,
    status: str,
) -> None:
    _add(
        _etl_extract_outcome(),
        1,
        {
            "etl.service": etl_service or "unknown",
            "content.type": content_type or "unknown",
            "status": status,
        },
    )


def record_celery_heartbeat_refresh(*, heartbeat_type: str) -> None:
    _add(_celery_heartbeat_refreshes(), 1, {"heartbeat.type": heartbeat_type})


def record_celery_heartbeat_failure(*, heartbeat_type: str) -> None:
    _add(_celery_heartbeat_failures(), 1, {"heartbeat.type": heartbeat_type})


def _runtime_snapshot_value(key: str, transform: Any = None) -> list[Any]:
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
    if _OBSERVABLES_REGISTERED or not _is_enabled():
        return

    meter = _get_meter()
    try:
        # Each callback returns the value for a single gauge except GC, whose
        # callback carries a generation attribute.
        meter.create_observable_gauge(
            "process.runtime.cpython.memory.rss",
            callbacks=[
                lambda _options: _runtime_snapshot_value(
                    "rss_mb", lambda v: float(v) * 1024 * 1024
                )
            ],
            unit="By",
            description="Resident set size of the SurfSense backend process.",
        )
        meter.create_observable_gauge(
            "process.runtime.cpython.cpu.utilization",
            callbacks=[
                lambda _options: _runtime_snapshot_value(
                    "cpu_percent", lambda v: float(v) / 100.0
                )
            ],
            unit="1",
            description="CPU utilization of the SurfSense backend process.",
        )
        meter.create_observable_gauge(
            "process.runtime.cpython.threads",
            callbacks=[lambda _options: _runtime_snapshot_value("threads")],
            unit="{thread}",
            description="Thread count of the SurfSense backend process.",
        )
        meter.create_observable_gauge(
            "process.runtime.cpython.open_fds",
            callbacks=[lambda _options: _runtime_snapshot_value("open_fds")],
            unit="{fd}",
            description="Open file descriptor count of the SurfSense backend process.",
        )
        meter.create_observable_gauge(
            "python.asyncio.tasks",
            callbacks=[lambda _options: _runtime_snapshot_value("asyncio_tasks")],
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


__all__ = [
    "record_auth_failure",
    "record_celery_heartbeat_failure",
    "record_celery_heartbeat_refresh",
    "record_chat_request_duration",
    "record_chat_request_outcome",
    "record_compaction_run",
    "record_connector_sync_duration",
    "record_connector_sync_outcome",
    "record_etl_extract_duration",
    "record_etl_extract_outcome",
    "record_indexing_document_duration",
    "record_indexing_document_outcome",
    "record_interrupt",
    "record_kb_search_duration",
    "record_model_call_duration",
    "record_model_token_usage",
    "record_perf_elapsed",
    "record_permission_ask",
    "record_rate_limit_rejection",
    "record_subagent_invoke_duration",
    "record_subagent_invoke_outcome",
    "record_tool_call_duration",
    "record_tool_call_error",
    "register_runtime_observables",
]
