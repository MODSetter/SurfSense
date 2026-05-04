"""Re-raise still-pending subagent interrupts at the parent graph level.

After ``subagent.[a]invoke(Command(resume=...))`` returns, the subagent may
still hold a pending interrupt (e.g. the LLM produced a follow-up tool call
that fired a fresh ``interrupt()``). The parent's pregel cannot see that
interrupt because it lives in a separate compiled graph; we re-raise it here
so the parent's SSE stream surfaces it as the next approval card.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.runnables import Runnable
from langgraph.types import interrupt as _lg_interrupt

from .resume import get_first_pending_subagent_interrupt

logger = logging.getLogger(__name__)


def maybe_propagate_subagent_interrupt(
    subagent: Runnable,
    sub_config: dict[str, Any],
    subagent_type: str,
) -> None:
    """Re-raise a still-pending subagent interrupt at the parent so the SSE stream surfaces it."""
    get_state_sync = getattr(subagent, "get_state", None)
    if not callable(get_state_sync):
        return
    try:
        snapshot = get_state_sync(sub_config)
    except Exception:  # pragma: no cover - defensive
        logger.debug(
            "Subagent get_state failed during re-interrupt check",
            exc_info=True,
        )
        return
    _pending_id, pending_value = get_first_pending_subagent_interrupt(snapshot)
    if pending_value is None:
        return
    logger.info(
        "Re-raising subagent %r interrupt to parent (multi-step HITL)",
        subagent_type,
    )
    _lg_interrupt(pending_value)


async def amaybe_propagate_subagent_interrupt(
    subagent: Runnable,
    sub_config: dict[str, Any],
    subagent_type: str,
) -> None:
    """Async counterpart of :func:`maybe_propagate_subagent_interrupt`."""
    aget_state = getattr(subagent, "aget_state", None)
    if not callable(aget_state):
        return
    try:
        snapshot = await aget_state(sub_config)
    except Exception:  # pragma: no cover - defensive
        logger.debug(
            "Subagent aget_state failed during re-interrupt check",
            exc_info=True,
        )
        return
    _pending_id, pending_value = get_first_pending_subagent_interrupt(snapshot)
    if pending_value is None:
        return
    logger.info(
        "Re-raising subagent %r interrupt to parent (multi-step HITL)",
        subagent_type,
    )
    _lg_interrupt(pending_value)
