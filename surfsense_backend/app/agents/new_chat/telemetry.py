"""Architecture telemetry logging for chat execution modes."""

from __future__ import annotations

import json
from typing import Any

from app.utils.perf import get_perf_logger

_perf_log = get_perf_logger()


def log_architecture_telemetry(
    *,
    phase: str,
    architecture_mode: str,
    orchestrator_used: bool,
    worker_count: int,
    retry_count: int,
    latency_ms: float,
    token_total: int,
    request_id: str | None = None,
    turn_id: str | None = None,
    status: str = "ok",
    source: str = "new_chat",
    extra: dict[str, Any] | None = None,
) -> None:
    payload: dict[str, Any] = {
        "phase": phase,
        "source": source,
        "status": status,
        "architecture_mode": architecture_mode,
        "orchestrator_used": orchestrator_used,
        "worker_count": worker_count,
        "retry_count": retry_count,
        "latency_ms": round(latency_ms, 2),
        "token_total": token_total,
        "request_id": request_id or "unknown",
        "turn_id": turn_id or "unknown",
    }
    if extra:
        payload.update(extra)
    _perf_log.info("[architecture_telemetry] %s", json.dumps(payload, ensure_ascii=False))
