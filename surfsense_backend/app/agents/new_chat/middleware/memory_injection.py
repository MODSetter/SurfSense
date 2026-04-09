"""Memory injection middleware for the SurfSense agent.

Loads the user's personal memory (User.memory_md) and, for shared threads,
the team memory (SearchSpace.shared_memory_md) from the database and injects
them into the system prompt as <user_memory> / <team_memory> XML blocks on
every turn.  This ensures the LLM always has the full memory context without
requiring a tool call.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.runtime import Runtime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.new_chat.tools.update_memory import MEMORY_HARD_LIMIT
from app.db import ChatVisibility, SearchSpace, User, shielded_async_session

logger = logging.getLogger(__name__)


class MemoryInjectionMiddleware(AgentMiddleware):  # type: ignore[type-arg]
    """Injects memory markdown into the conversation on every turn."""

    tools = ()

    def __init__(
        self,
        *,
        user_id: str | UUID | None,
        search_space_id: int,
        thread_visibility: ChatVisibility | None = None,
    ) -> None:
        self.user_id = UUID(user_id) if isinstance(user_id, str) else user_id
        self.search_space_id = search_space_id
        self.visibility = thread_visibility or ChatVisibility.PRIVATE

    async def abefore_agent(  # type: ignore[override]
        self,
        state: AgentState,
        runtime: Runtime[Any],
    ) -> dict[str, Any] | None:
        del runtime
        messages = state.get("messages") or []
        if not messages:
            return None

        last_message = messages[-1]
        if not isinstance(last_message, HumanMessage):
            return None

        memory_blocks: list[str] = []

        async with shielded_async_session() as session:
            if self.user_id is not None:
                user_memory, display_name = await self._load_user_memory(session)
                if display_name:
                    first_name = display_name.split()[0]
                    memory_blocks.append(f"<user_name>{first_name}</user_name>")
                if user_memory:
                    chars = len(user_memory)
                    memory_blocks.append(
                        f'<user_memory chars="{chars}" limit="{MEMORY_HARD_LIMIT}">\n'
                        f"{user_memory}\n"
                        f"</user_memory>"
                    )

            if self.visibility == ChatVisibility.SEARCH_SPACE:
                team_memory = await self._load_team_memory(session)
                if team_memory:
                    chars = len(team_memory)
                    memory_blocks.append(
                        f'<team_memory chars="{chars}" limit="{MEMORY_HARD_LIMIT}">\n'
                        f"{team_memory}\n"
                        f"</team_memory>"
                    )

        if not memory_blocks:
            return None

        memory_text = "\n\n".join(memory_blocks)
        memory_msg = SystemMessage(content=memory_text)

        new_messages = list(messages)
        insert_idx = 1 if len(new_messages) > 1 else 0
        new_messages.insert(insert_idx, memory_msg)

        return {"messages": new_messages}

    async def _load_user_memory(self, session: AsyncSession) -> tuple[str | None, str | None]:
        """Return (memory_content, display_name)."""
        try:
            result = await session.execute(
                select(User.memory_md, User.display_name).where(User.id == self.user_id)
            )
            row = result.one_or_none()
            if row is None:
                return None, None
            return row.memory_md or None, row.display_name
        except Exception:
            logger.exception("Failed to load user memory")
            return None, None

    async def _load_team_memory(self, session: AsyncSession) -> str | None:
        try:
            result = await session.execute(
                select(SearchSpace.shared_memory_md).where(
                    SearchSpace.id == self.search_space_id
                )
            )
            row = result.scalar_one_or_none()
            return row if row else None
        except Exception:
            logger.exception("Failed to load team memory")
            return None
