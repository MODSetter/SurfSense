"""Memory injection middleware for the SurfSense agent.

Injects memory markdown into the system prompt on every turn:
- Private threads: only personal memory (<user_memory>)
- Shared threads: only team memory (<team_memory>)
"""

from __future__ import annotations

import logging
import time
from typing import Any
from uuid import UUID

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.runtime import Runtime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import ChatVisibility, SearchSpace, User, shielded_async_session
from app.services.memory import MEMORY_HARD_LIMIT, MEMORY_SOFT_LIMIT
from app.utils.perf import get_perf_logger

logger = logging.getLogger(__name__)
_perf_log = get_perf_logger()


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

        start = time.perf_counter()
        db_elapsed = 0.0
        memory_blocks: list[str] = []
        scope = "team" if self.visibility == ChatVisibility.SEARCH_SPACE else "user"

        async with shielded_async_session() as session:
            db_start = time.perf_counter()
            if self.visibility == ChatVisibility.SEARCH_SPACE:
                team_memory = await self._load_team_memory(session)
                if team_memory:
                    chars = len(team_memory)
                    memory_blocks.append(
                        f'<team_memory chars="{chars}" limit="{MEMORY_HARD_LIMIT}">\n'
                        f"{team_memory}\n"
                        f"</team_memory>"
                    )
                    if chars > MEMORY_SOFT_LIMIT:
                        memory_blocks.append(
                            f"<memory_warning>Team memory is at "
                            f"{chars:,}/{MEMORY_HARD_LIMIT:,} characters and approaching "
                            f"the hard limit. On your next update_memory call, consolidate "
                            f"by merging duplicates, removing outdated entries, and "
                            f"shortening descriptions before adding anything new."
                            f"</memory_warning>"
                        )
            elif self.user_id is not None:
                user_memory, display_name = await self._load_user_memory(session)
                if display_name and display_name.strip():
                    first_name = display_name.strip().split()[0]
                    memory_blocks.append(f"<user_name>{first_name}</user_name>")
                if user_memory:
                    chars = len(user_memory)
                    memory_blocks.append(
                        f'<user_memory chars="{chars}" limit="{MEMORY_HARD_LIMIT}">\n'
                        f"{user_memory}\n"
                        f"</user_memory>"
                    )
                    if chars > MEMORY_SOFT_LIMIT:
                        memory_blocks.append(
                            f"<memory_warning>Your personal memory is at "
                            f"{chars:,}/{MEMORY_HARD_LIMIT:,} characters and approaching "
                            f"the hard limit. On your next update_memory call, consolidate "
                            f"by merging duplicates, removing outdated entries, and "
                            f"shortening descriptions before adding anything new."
                            f"</memory_warning>"
                        )

        db_elapsed = time.perf_counter() - db_start

        if not memory_blocks:
            _perf_log.info(
                "[memory_injection] scope=%s injected=0 db=%.3fs total=%.3fs",
                scope,
                db_elapsed,
                time.perf_counter() - start,
            )
            return None

        memory_text = "\n\n".join(memory_blocks)
        memory_msg = SystemMessage(content=memory_text)

        new_messages = list(messages)
        insert_idx = 1 if len(new_messages) > 1 else 0
        new_messages.insert(insert_idx, memory_msg)

        _perf_log.info(
            "[memory_injection] scope=%s injected=1 chars=%d db=%.3fs total=%.3fs",
            scope,
            len(memory_text),
            db_elapsed,
            time.perf_counter() - start,
        )
        return {"messages": new_messages}

    async def _load_user_memory(
        self, session: AsyncSession
    ) -> tuple[str | None, str | None]:
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
