"""Project ``workspace_tree_text`` from state into a SystemMessage."""

from __future__ import annotations

import time
from typing import Any

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain_core.messages import SystemMessage
from langgraph.runtime import Runtime

from app.agents.chat.multi_agent_chat.shared.state.filesystem_state import (
    SurfSenseFilesystemState,
)
from app.utils.perf import get_perf_logger

_perf_log = get_perf_logger()


class KbContextProjectionMiddleware(AgentMiddleware):  # type: ignore[type-arg]
    """Emit the ``<workspace_tree>`` from shared state.

    Read-only consumer: no DB, no LLM, no state writes. The orchestrator's
    ``KnowledgeTreeMiddleware`` populates ``workspace_tree_text``; this
    projection lets a subagent put the same tree in front of its own LLM call.
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
        if not tree_text:
            _perf_log.info(
                "[kb_context_projection] tree=0 elapsed=%.3fs",
                time.perf_counter() - start,
            )
            return None

        messages = list(state.get("messages") or [])
        insert_at = max(len(messages) - 1, 0)
        messages.insert(insert_at, SystemMessage(content=tree_text))
        _perf_log.info(
            "[kb_context_projection] tree_chars=%d elapsed=%.3fs",
            len(tree_text),
            time.perf_counter() - start,
        )
        return {"messages": messages}


def build_kb_context_projection_mw() -> KbContextProjectionMiddleware:
    return KbContextProjectionMiddleware()


__all__ = [
    "KbContextProjectionMiddleware",
    "build_kb_context_projection_mw",
]
