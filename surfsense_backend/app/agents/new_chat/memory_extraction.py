"""Post-response memory extraction for the SurfSense agent.

After each agent response, a background task calls a lightweight LLM to decide
whether the user's message contains any long-term information worth persisting
(preferences, background, goals, instructions, etc.).  This ensures memory
updates are never missed regardless of whether the main agent called
``update_memory`` during the conversation.

The function re-reads memory from the database so it always sees the latest
state — including any updates the agent may have already made.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from langchain_core.messages import HumanMessage
from sqlalchemy import select

from app.agents.new_chat.tools.update_memory import _save_memory
from app.db import ChatVisibility, SearchSpace, User, shielded_async_session

logger = logging.getLogger(__name__)

_MEMORY_EXTRACT_PROMPT = """\
You are a memory extraction assistant. Analyze the user's message and decide \
if it contains any long-term information worth persisting to memory.

Worth remembering: preferences, background/identity, goals, projects, \
instructions, tools/languages they use, decisions, expertise, workplace.

NOT worth remembering: greetings, one-off factual questions, session \
logistics, ephemeral requests, follow-up clarifications with no new personal info.

If the message contains memorizable information, output the FULL updated \
memory document with the new facts merged into the existing content. Follow \
these rules:
- Use the same ## section structure as the existing memory.
- Keep entries as single concise bullet points (under 120 chars each).
- Add (YYYY-MM) date suffixes on time-sensitive entries.
- Never remove or modify sections marked with (pinned).
- If a new fact contradicts an existing entry, update the existing entry.
- Do not duplicate information that is already present.
- Standard sections: \
"## About the user (pinned)", "## Preferences", "## Instructions (pinned)", \
"## Current context"

If nothing is worth remembering, output exactly: NO_UPDATE

<current_memory>
{current_memory}
</current_memory>

<user_message>
{user_message}
</user_message>"""

_TEAM_MEMORY_EXTRACT_PROMPT = """\
You are a memory extraction assistant for a team workspace. Analyze the \
user's message and decide if it contains any long-term team information \
worth persisting to the shared memory.

Worth remembering: team decisions, conventions, coding standards, key facts \
about the project/team, processes, architecture decisions.

NOT worth remembering: greetings, personal preferences, one-off questions, \
ephemeral requests.

If the message contains memorizable information, output the FULL updated \
memory document with the new facts merged into the existing content. Follow \
these rules:
- Use the same ## section structure as the existing memory.
- Keep entries as single concise bullet points (under 120 chars each).
- Add (YYYY-MM) date suffixes on time-sensitive entries.
- Never remove or modify sections marked with (pinned).
- Standard sections: \
"## Team decisions (pinned)", "## Conventions (pinned)", "## Key facts", \
"## Current priorities"

If nothing is worth remembering, output exactly: NO_UPDATE

<current_memory>
{current_memory}
</current_memory>

<user_message>
{user_message}
</user_message>"""


async def _call_extraction_llm(
    llm: Any,
    prompt_template: str,
    current_memory: str,
    user_message: str,
) -> str | None:
    """Run the extraction LLM and return the updated memory, or ``None``."""
    prompt = prompt_template.format(
        current_memory=current_memory or "(empty)",
        user_message=user_message,
    )
    response = await llm.ainvoke(
        [HumanMessage(content=prompt)],
        config={"tags": ["surfsense:internal", "memory-extraction"]},
    )
    text = (
        response.content if isinstance(response.content, str) else str(response.content)
    ).strip()

    if text == "NO_UPDATE" or not text:
        return None
    return text


async def extract_and_save_memory(
    *,
    user_message: str,
    user_id: str | None,
    search_space_id: int,
    thread_visibility: ChatVisibility | None,
    llm: Any,
) -> None:
    """Background task: extract memorizable info and persist it.

    This function is designed to be fire-and-forget — it catches all
    exceptions internally and never propagates them.
    """
    if not user_id:
        return

    visibility = thread_visibility or ChatVisibility.PRIVATE

    try:
        await _extract_user_memory(user_message, user_id, llm)
    except Exception:
        logger.exception("Background user memory extraction failed")

    if visibility == ChatVisibility.SEARCH_SPACE:
        try:
            await _extract_team_memory(user_message, search_space_id, llm)
        except Exception:
            logger.exception("Background team memory extraction failed")


async def _extract_user_memory(
    user_message: str,
    user_id: str,
    llm: Any,
) -> None:
    """Extract and persist user memory updates."""
    uid = UUID(user_id) if isinstance(user_id, str) else user_id

    async with shielded_async_session() as session:
        result = await session.execute(select(User).where(User.id == uid))
        user = result.scalars().first()
        if not user:
            return

        old_memory = user.memory_md
        updated = await _call_extraction_llm(
            llm, _MEMORY_EXTRACT_PROMPT, old_memory or "", user_message
        )
        if updated is None:
            logger.debug("Memory extraction: no update needed (user %s)", uid)
            return

        save_result = await _save_memory(
            updated_memory=updated,
            old_memory=old_memory,
            llm=llm,
            apply_fn=lambda content: setattr(user, "memory_md", content),
            commit_fn=session.commit,
            rollback_fn=session.rollback,
            label="memory",
        )
        logger.info(
            "Background memory extraction for user %s: %s",
            uid,
            save_result.get("status"),
        )


async def _extract_team_memory(
    user_message: str,
    search_space_id: int,
    llm: Any,
) -> None:
    """Extract and persist team memory updates."""
    async with shielded_async_session() as session:
        result = await session.execute(
            select(SearchSpace).where(SearchSpace.id == search_space_id)
        )
        space = result.scalars().first()
        if not space:
            return

        old_memory = space.shared_memory_md
        updated = await _call_extraction_llm(
            llm, _TEAM_MEMORY_EXTRACT_PROMPT, old_memory or "", user_message
        )
        if updated is None:
            logger.debug(
                "Team memory extraction: no update needed (space %s)",
                search_space_id,
            )
            return

        save_result = await _save_memory(
            updated_memory=updated,
            old_memory=old_memory,
            llm=llm,
            apply_fn=lambda content: setattr(space, "shared_memory_md", content),
            commit_fn=session.commit,
            rollback_fn=session.rollback,
            label="team memory",
        )
        logger.info(
            "Background team memory extraction for space %s: %s",
            search_space_id,
            save_result.get("status"),
        )
