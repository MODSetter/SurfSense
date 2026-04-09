"""Background memory extraction for the SurfSense agent.

After each agent response, if the agent did not call ``update_memory`` during
the turn, this module can run a lightweight LLM call to decide whether the
latest message contains long-term information worth persisting.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from langchain_core.messages import HumanMessage
from sqlalchemy import select

from app.agents.new_chat.tools.update_memory import _save_memory
from app.db import SearchSpace, User, shielded_async_session

logger = logging.getLogger(__name__)

_MEMORY_EXTRACT_PROMPT = """\
You are a memory extraction assistant. Analyze the user's message and decide \
if it contains any long-term information worth persisting to memory.

Worth remembering: preferences, background/identity, goals, projects, \
instructions, tools/languages they use, decisions, expertise, workplace — \
durable facts that will matter in future conversations.

NOT worth remembering: greetings, one-off factual questions, session \
logistics, ephemeral requests, follow-up clarifications with no new personal \
info, things that only matter for the current task.

If the message contains memorizable information, output the FULL updated \
memory document with the new facts merged into the existing content. Follow \
these rules:
- Preserve any existing ## headings; create new ones if useful.
- Keep entries as single concise bullet points (under 120 chars each).
- Every bullet MUST use format: - (YYYY-MM-DD) [fact|pref|instr] text
  [fact] = durable facts, [pref] = preferences, [instr] = standing instructions.
- If a new fact contradicts an existing entry, update the existing entry.
- Do not duplicate information that is already present.

If nothing is worth remembering, output exactly: NO_UPDATE

<current_memory>
{current_memory}
</current_memory>

<user_message>
{user_message}
</user_message>"""

_TEAM_MEMORY_EXTRACT_PROMPT = """\
You are a team-memory extraction assistant. Analyze the latest message and \
decide if it contains durable TEAM-level information worth persisting.

Decision policy:
- Prioritize recall for durable team context, while avoiding personal-only facts.
- Do NOT require explicit consensus language. A direct team-level statement can
  be stored if it is stable and broadly useful for future team chats.
- If evidence is weak or clearly tentative, output NO_UPDATE.

Worth remembering (team-level only):
- Decisions and defaults that guide future team work
- Team conventions/standards (naming, review policy, coding norms)
- Stable org/project facts (locations, ownership, constraints)
- Long-lived architecture/process facts
- Ongoing priorities that are likely relevant beyond this turn

NOT worth remembering:
- Personal preferences or biography of one person
- Questions, brainstorming, tentative ideas, or speculation
- One-off requests, status updates, TODOs, logistics for this session
- Information scoped only to a single ephemeral task

If the message contains memorizable team information, output the FULL updated \
team memory document with new facts merged into existing content. Follow rules:
- Preserve any existing ## headings; create new ones if useful.
- Keep entries as single concise bullet points (under 120 chars each).
- Every bullet MUST use format: - (YYYY-MM-DD) [fact] text
  Team memory uses ONLY the [fact] marker. Never use [pref] or [instr].
- If a new fact contradicts an existing entry, update the existing entry.
- Do not duplicate existing information.
- Preserve neutral team phrasing; avoid person-specific memory unless role-anchored.

If nothing is worth remembering, output exactly: NO_UPDATE

<current_team_memory>
{current_memory}
</current_team_memory>

<latest_message_author>
{author}
</latest_message_author>

<latest_message>
{user_message}
</latest_message>"""


async def extract_and_save_memory(
    *,
    user_message: str,
    user_id: str | None,
    llm: Any,
) -> None:
    """Background task: extract memorizable info and persist it.

    Designed to be fire-and-forget — catches all exceptions internally.
    """
    if not user_id:
        return

    try:
        uid = UUID(user_id) if isinstance(user_id, str) else user_id

        async with shielded_async_session() as session:
            result = await session.execute(select(User).where(User.id == uid))
            user = result.scalars().first()
            if not user:
                return

            old_memory = user.memory_md
            prompt = _MEMORY_EXTRACT_PROMPT.format(
                current_memory=old_memory or "(empty)",
                user_message=user_message,
            )
            response = await llm.ainvoke(
                [HumanMessage(content=prompt)],
                config={"tags": ["surfsense:internal", "memory-extraction"]},
            )
            text = (
                response.content
                if isinstance(response.content, str)
                else str(response.content)
            ).strip()

            if text == "NO_UPDATE" or not text:
                logger.debug("Memory extraction: no update needed (user %s)", uid)
                return

            save_result = await _save_memory(
                updated_memory=text,
                old_memory=old_memory,
                llm=llm,
                apply_fn=lambda content: setattr(user, "memory_md", content),
                commit_fn=session.commit,
                rollback_fn=session.rollback,
                label="memory",
                scope="user",
            )
            logger.info(
                "Background memory extraction for user %s: %s",
                uid,
                save_result.get("status"),
            )
    except Exception:
        logger.exception("Background user memory extraction failed")


async def extract_and_save_team_memory(
    *,
    user_message: str,
    search_space_id: int | None,
    llm: Any,
    author_display_name: str | None = None,
) -> None:
    """Background task: extract team-level memory and persist it.

    Runs only for shared threads. Designed to be fire-and-forget and catches
    exceptions internally.
    """
    if not search_space_id:
        return

    try:
        async with shielded_async_session() as session:
            result = await session.execute(
                select(SearchSpace).where(SearchSpace.id == search_space_id)
            )
            space = result.scalars().first()
            if not space:
                return

            old_memory = space.shared_memory_md
            prompt = _TEAM_MEMORY_EXTRACT_PROMPT.format(
                current_memory=old_memory or "(empty)",
                author=author_display_name or "Unknown team member",
                user_message=user_message,
            )
            response = await llm.ainvoke(
                [HumanMessage(content=prompt)],
                config={"tags": ["surfsense:internal", "team-memory-extraction"]},
            )
            text = (
                response.content
                if isinstance(response.content, str)
                else str(response.content)
            ).strip()

            if text == "NO_UPDATE" or not text:
                logger.debug(
                    "Team memory extraction: no update needed (space %s)",
                    search_space_id,
                )
                return

            save_result = await _save_memory(
                updated_memory=text,
                old_memory=old_memory,
                llm=llm,
                apply_fn=lambda content: setattr(space, "shared_memory_md", content),
                commit_fn=session.commit,
                rollback_fn=session.rollback,
                label="team memory",
                scope="team",
            )
            logger.info(
                "Background team memory extraction for space %s: %s",
                search_space_id,
                save_result.get("status"),
            )
    except Exception:
        logger.exception("Background team memory extraction failed")
