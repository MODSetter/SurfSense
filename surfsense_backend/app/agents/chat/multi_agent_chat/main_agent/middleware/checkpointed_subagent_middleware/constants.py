"""Tuning constants for the checkpointed subagent middleware.

``EXCLUDED_STATE_KEYS`` and ``DEFAULT_SUBAGENT_RECURSION_LIMIT`` are part of the
subagent-invocation contract shared with subagents and now live in
``app.agents.chat.multi_agent_chat.subagents.shared.invocation``.
"""

from __future__ import annotations

import os


def _read_timeout_env(name: str, default: float) -> float:
    """Parse ``name`` from the environment; fall back to ``default`` on bad values.

    Kept as a free function so the module-level constants stay constants
    after import; tests can monkeypatch this and re-evaluate via
    ``importlib.reload`` if they need a different value mid-process.
    """
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


# Wall-clock budget for a single ``task(subagent, ...)`` invocation.
# Subagents that run hot (image generation with slow vendors, KB writes
# behind a sluggish embedder) can otherwise wedge the orchestrator until
# the next checkpoint heartbeat. ``0`` disables the timeout entirely.
DEFAULT_SUBAGENT_INVOKE_TIMEOUT_SECONDS: float = _read_timeout_env(
    "SURFSENSE_SUBAGENT_INVOKE_TIMEOUT_SECONDS",
    default=300.0,
)


def _read_int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


# Maximum number of children that ``task(..., tasks=[...])`` runs in
# parallel via ``asyncio.gather`` + ``Semaphore``. Bounded so a runaway
# fanout cannot starve unrelated subagents (each child still owns an
# LLM call + DB session). Set ``SURFSENSE_TASK_BATCH_CONCURRENCY=1`` to
# effectively serialise batches without changing the schema.
DEFAULT_SUBAGENT_BATCH_CONCURRENCY: int = _read_int_env(
    "SURFSENSE_TASK_BATCH_CONCURRENCY",
    default=3,
)

# Max number of children in a single batched ``task`` call. Hard upper
# bound is a safety net for prompt-injection / runaway loops; the orchestrator
# rarely needs more than a handful of concurrent specialists.
MAX_SUBAGENT_BATCH_SIZE: int = _read_int_env(
    "SURFSENSE_TASK_BATCH_MAX_SIZE",
    default=8,
)


# Soft threshold for per-turn cumulative ``task(...)`` invocations across
# **all** subagents. Once the sum of ``state['billable_calls']`` values
# crosses this number, the runtime appends a one-shot warning ToolMessage
# instructing the orchestrator to wrap up the turn. Tunable so heavy-research
# turns (which legitimately need 15+ specialist calls) don't trip the alarm
# in production. Set to ``0`` to disable the warning entirely.
DEFAULT_SUBAGENT_BILLABLE_THRESHOLD: int = _read_int_env(
    "SURFSENSE_SUBAGENT_BILLABLE_THRESHOLD",
    default=15,
)
