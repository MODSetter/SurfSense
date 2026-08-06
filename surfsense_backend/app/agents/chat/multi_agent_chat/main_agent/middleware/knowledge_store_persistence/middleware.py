"""End-of-turn hook: commit the turn's working copy as one revision."""

from __future__ import annotations

from typing import Any

from langchain.agents.middleware import AgentMiddleware, AgentState
from langgraph.config import get_config
from langgraph.runtime import Runtime

from app.agents.chat.multi_agent_chat.main_agent.middleware.knowledge_store_persistence.commit_turn import (
    commit_turn_working_copy,
)


class KnowledgeStorePersistenceMiddleware(AgentMiddleware):  # type: ignore[type-arg]
    """Runs the commit body after the agent's turn (git-native write path)."""

    def __init__(
        self,
        *,
        workspace_id: int,
        created_by_id: str | None,
        thread_id: int | None,
        llm: Any,
    ) -> None:
        self.workspace_id = workspace_id
        self.created_by_id = created_by_id
        self.thread_id = thread_id
        self.llm = llm

    async def aafter_agent(  # type: ignore[override]
        self,
        state: AgentState,
        runtime: Runtime[Any],
    ) -> dict[str, Any] | None:
        del state, runtime  # the working copy on disk is the pending state
        return await commit_turn_working_copy(
            workspace_id=self.workspace_id,
            thread_id=self._resolve_thread_id(),
            created_by_id=self.created_by_id,
            llm=self.llm,
        )

    def _resolve_thread_id(self) -> int | str | None:
        """Live thread id from the active config, so one cached compiled graph
        commits against the correct thread across many chats (same pattern as
        ``kb_persistence``)."""
        try:
            config = get_config()
        except Exception:
            config = None
        if isinstance(config, dict):
            value = (config.get("configurable") or {}).get("thread_id")
            if value is not None:
                return value
        return self.thread_id
