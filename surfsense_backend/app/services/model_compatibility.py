"""Verdicts for the model compatibility sweep, and the blocklist it feeds.

OpenRouter lists hundreds of models that pass our capability filters on
metadata alone. Some of them still cannot serve a turn through this agent
harness — the ``:batch`` variants route to an async API, delisted ids 404, and
some providers reject our tool-call message shape. The sweep in
``scripts/sweep_model_compatibility.py`` probes each one and records a verdict
here; the catalogue reads the blocked ids back on startup and on every refresh.

The bias is deliberate: only a failure that is definitively about *this model*
blocks it. Everything else stays ``UNKNOWN`` and the model keeps its listing,
because a bad key or a five-minute provider outage would otherwise empty the
catalogue in a single sweep.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy import select

from app.services.llm_error_adapter import LLMErrorCategory, adapt_llm_exception

logger = logging.getLogger(__name__)

# Longest error body we keep per model. Enough to identify the failure in a
# dashboard without turning the table into a log sink.
ERROR_EXCERPT_LIMIT = 500


class CompatibilityStatus(StrEnum):
    OK = "ok"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class ProbeStage(StrEnum):
    """The three escalating probes, in the order the sweep runs them."""

    STREAM = "stream"
    TOOL_BIND = "tool_bind"
    TOOL_RESULT = "tool_result"


# Failures that are a property of the model, not of the moment. A 404 means the
# id does not serve chat completions; a 400/422 means the model rejects the
# request shape every agent turn uses.
#
# Deliberately absent: AUTH_FAILED and PERMISSION_DENIED (account-level — a bad
# key fails every model at once), and every transient category (rate limits,
# timeouts, gateway and connection errors).
_PERMANENT_FAILURE_CATEGORIES: frozenset[LLMErrorCategory] = frozenset(
    {
        LLMErrorCategory.MODEL_NOT_FOUND,
        LLMErrorCategory.BAD_REQUEST,
    }
)


@dataclass(frozen=True)
class CompatibilityVerdict:
    status: CompatibilityStatus
    failure_stage: ProbeStage | None = None
    error_code: str | None = None
    error_excerpt: str | None = None


def classify_probe_failure(exc: BaseException) -> tuple[CompatibilityStatus, str]:
    """Map a probe exception to ``(status, error_code)``."""
    category = adapt_llm_exception(exc).category
    status = (
        CompatibilityStatus.BLOCKED
        if category in _PERMANENT_FAILURE_CATEGORIES
        else CompatibilityStatus.UNKNOWN
    )
    return status, category.value


def verdict_from_stages(
    results: dict[ProbeStage, BaseException | None],
) -> CompatibilityVerdict:
    """Reduce per-stage outcomes to one verdict, reporting the first failure.

    Stages are evaluated in ``ProbeStage`` order regardless of dict ordering,
    so the recorded ``failure_stage`` is always the earliest one that broke.
    """
    for stage in ProbeStage:
        exc = results.get(stage)
        if exc is None:
            continue
        status, error_code = classify_probe_failure(exc)
        return CompatibilityVerdict(
            status=status,
            failure_stage=stage,
            error_code=error_code,
            error_excerpt=str(exc)[:ERROR_EXCERPT_LIMIT],
        )
    return CompatibilityVerdict(status=CompatibilityStatus.OK)


def blocked_model_ids() -> set[str]:
    """Every model id currently marked ``BLOCKED``, shared through Postgres so
    all four uvicorn workers converge on the same blocklist.

    Sync because ``initialize_openrouter_integration`` runs from both the
    FastAPI lifespan and the Celery worker bootstrap, and the latter has no
    event loop. Async callers should hand it to a thread.

    Returns an empty set on any failure: an unreachable table must never stop a
    worker from booting with a full catalogue.
    """
    from sqlalchemy import create_engine

    from app.agents.chat.runtime.checkpointer import get_postgres_connection_string
    from app.db import ModelCompatibility

    query = select(ModelCompatibility.model_id).where(
        ModelCompatibility.status == CompatibilityStatus.BLOCKED
    )
    engine = None
    try:
        engine = create_engine(get_postgres_connection_string())
        with engine.connect() as connection:
            return {row[0] for row in connection.execute(query)}
    except Exception as exc:
        logger.warning("model compatibility blocklist unavailable: %s", exc)
        return set()
    finally:
        if engine is not None:
            engine.dispose()


__all__ = [
    "CompatibilityStatus",
    "CompatibilityVerdict",
    "ProbeStage",
    "blocked_model_ids",
    "classify_probe_failure",
    "verdict_from_stages",
]
