"""Background memory extraction for the SurfSense agent.

After each agent response, if the agent did not call ``update_memory`` during
the turn, this module runs a lightweight LLM call to decide whether the user's
message contains any long-term information worth persisting.

Only user (personal) memory is handled here — team memory relies on explicit
agent calls.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from langchain_core.messages import HumanMessage
from sqlalchemy import select

from app.agents.new_chat.tools.update_memory import _save_memory
from app.db import User, shielded_async_session

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
- Use the same ## section structure as the existing memory.
- Keep entries as single concise bullet points (under 120 chars each).
- Every bullet MUST start with a (YYYY-MM-DD) date prefix.
- If a new fact contradicts an existing entry, update the existing entry.
- Do not duplicate information that is already present.
- Standard sections: \
"## About the user", "## Preferences", "## Instructions"

If nothing is worth remembering, output exactly: NO_UPDATE

<current_memory>
{current_memory}
</current_memory>

<user_message>
{user_message}
</user_message>"""


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
            )
            logger.info(
                "Background memory extraction for user %s: %s",
                uid,
                save_result.get("status"),
            )
    except Exception:
        logger.exception("Background user memory extraction failed")
