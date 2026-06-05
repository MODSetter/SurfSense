"""Project ``workspace_tree_text`` + ``kb_priority`` from state into SystemMessages."""

from __future__ import annotations

import time
from typing import Any

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain_core.messages import SystemMessage
from langgraph.runtime import Runtime

from app.agents.multi_agent_chat.shared.state.filesystem_state import (
    SurfSenseFilesystemState,
)
from app.utils.perf import get_perf_logger

from .knowledge_search import _render_priority_message

_perf_log = get_perf_logger()


class KbContextProjectionMiddleware(AgentMiddleware):  # type: ignore[type-arg]
    """Emit ``<workspace_tree>`` + ``<priority_documents>`` from shared state.

    Read-only consumer: no DB, no LLM, no state writes. The orchestrator's
    renderer middlewares populate the source fields; this projection lets any
    agent (orchestrator or subagent) put the same content in front of its
    own LLM call.
    """

    tools = ()
    state_schema = SurfSenseFilesystemState

    def before_agent(  # type: ignore[override]
        self,
        state: AgentState,
        runtime: Runtime[Any],
    ) -> dict[str, Any] | None:
        del runtime
        start = time.perf_counter()
        tree_text = state.get("workspace_tree_text")
        priority = state.get("kb_priority")
        if not tree_text and not priority:
            _perf_log.info(
                "[kb_context_projection] tree=0 priority=0 elapsed=%.3fs",
                time.perf_counter() - start,
            )
            return None

        messages = list(state.get("messages") or [])
        insert_at = max(len(messages) - 1, 0)
        tree_chars = 0
        if tree_text:
            tree_chars = len(tree_text)
            messages.insert(insert_at, SystemMessage(content=tree_text))
        priority_count = 0
        if priority:
            priority_count = len(priority) if hasattr(priority, "__len__") else 1
            messages.insert(insert_at, _render_priority_message(priority))
        _perf_log.info(
            "[kb_context_projection] tree_chars=%d priority_items=%d elapsed=%.3fs",
            tree_chars,
            priority_count,
            time.perf_counter() - start,
        )
        return {"messages": messages}


def build_kb_context_projection_mw() -> KbContextProjectionMiddleware:
    return KbContextProjectionMiddleware()


__all__ = [
    "KbContextProjectionMiddleware",
    "build_kb_context_projection_mw",
]
