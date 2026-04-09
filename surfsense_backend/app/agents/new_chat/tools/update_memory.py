"""Markdown-document memory tool for the SurfSense agent.

Replaces the old row-per-fact save_memory / recall_memory tools with a single
update_memory tool that overwrites a freeform markdown TEXT column.  The LLM
always sees the current memory in <user_memory> / <team_memory> tags injected
by MemoryInjectionMiddleware, so it passes the FULL updated document each time.

Overflow handling:
  - Soft limit (15K chars): advisory warning returned alongside a successful save.
  - Hard limit (25K chars): save rejected; an automatic LLM-driven consolidation
    is attempted before falling back to the error.
  - Pinned sections: headings containing ``(pinned)`` are protected — the system
    rejects any update that drops them and auto-restores them during consolidation.
  - Diff validation: warns when entire ``##`` sections are dropped or when the
    document shrinks by more than 60%.
"""

from __future__ import annotations

import logging
import re
from typing import Any
from uuid import UUID

from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SearchSpace, User

logger = logging.getLogger(__name__)

MEMORY_SOFT_LIMIT = 15_000
MEMORY_HARD_LIMIT = 25_000

_PINNED_RE = re.compile(r"^##\s+.+\(pinned\)", re.MULTILINE)
_SECTION_HEADING_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)


# ---------------------------------------------------------------------------
# Pinned-section helpers
# ---------------------------------------------------------------------------

def _extract_pinned_headings(memory: str) -> set[str]:
    """Return the set of ``## …`` headings that contain ``(pinned)``."""
    return set(_PINNED_RE.findall(memory))


def _extract_section_map(memory: str) -> dict[str, str]:
    """Split *memory* into ``{heading_text: full_section_content}``."""
    sections: dict[str, str] = {}
    parts = _SECTION_HEADING_RE.split(memory)
    # parts: [preamble, heading1, body1, heading2, body2, …]
    for i in range(1, len(parts) - 1, 2):
        heading = parts[i].strip()
        body = parts[i + 1]
        sections[heading] = f"## {heading}\n{body}"
    return sections


def _validate_pinned_preserved(
    old_memory: str | None, new_memory: str
) -> str | None:
    """Return an error message if pinned headings from *old_memory* are missing
    in *new_memory*, else ``None``."""
    if not old_memory:
        return None
    old_pinned = _extract_pinned_headings(old_memory)
    if not old_pinned:
        return None
    new_pinned = _extract_pinned_headings(new_memory)
    dropped = old_pinned - new_pinned
    if dropped:
        names = ", ".join(sorted(dropped))
        return (
            f"Cannot remove pinned sections: {names}. "
            "These sections are protected and must be preserved. "
            "Re-include them and call update_memory again."
        )
    return None


def _restore_missing_pinned(
    old_memory: str, consolidated: str
) -> str:
    """Prepend any pinned sections from *old_memory* that are absent in
    *consolidated*."""
    old_pinned = _extract_pinned_headings(old_memory)
    if not old_pinned:
        return consolidated
    new_pinned = _extract_pinned_headings(consolidated)
    dropped = old_pinned - new_pinned
    if not dropped:
        return consolidated

    old_sections = _extract_section_map(old_memory)
    restored_parts: list[str] = []
    for heading in sorted(dropped):
        raw_heading = heading.removeprefix("## ").strip()
        if raw_heading in old_sections:
            restored_parts.append(old_sections[raw_heading].rstrip())
    if restored_parts:
        return "\n\n".join(restored_parts) + "\n\n" + consolidated
    return consolidated


# ---------------------------------------------------------------------------
# Diff validation
# ---------------------------------------------------------------------------

def _extract_headings(memory: str) -> set[str]:
    """Return all ``## …`` heading texts (without the ``## `` prefix)."""
    return set(_SECTION_HEADING_RE.findall(memory))


def _validate_diff(
    old_memory: str | None, new_memory: str
) -> list[str]:
    """Return a list of warning strings about suspicious changes."""
    if not old_memory:
        return []

    warnings: list[str] = []
    old_headings = _extract_headings(old_memory)
    new_headings = _extract_headings(new_memory)
    dropped = old_headings - new_headings
    if dropped:
        names = ", ".join(sorted(dropped))
        warnings.append(
            f"Sections removed: {names}. "
            "If unintentional, the user can restore from the settings page."
        )

    old_len = len(old_memory)
    new_len = len(new_memory)
    if old_len > 0 and new_len < old_len * 0.4:
        warnings.append(
            f"Memory shrank significantly ({old_len:,} -> {new_len:,} chars). "
            "Possible data loss."
        )
    return warnings


# ---------------------------------------------------------------------------
# Size validation & soft warning
# ---------------------------------------------------------------------------

def _validate_memory_size(content: str) -> dict[str, Any] | None:
    """Return an error/warning dict if *content* is too large, else None."""
    length = len(content)
    if length > MEMORY_HARD_LIMIT:
        return {
            "status": "error",
            "message": (
                f"Memory exceeds {MEMORY_HARD_LIMIT:,} character limit "
                f"({length:,} chars). Consolidate by merging related items, "
                "removing outdated entries, and shortening descriptions. "
                "Then call update_memory again."
            ),
        }
    return None


def _soft_warning(content: str) -> str | None:
    """Return a warning string if content exceeds the soft limit."""
    length = len(content)
    if length > MEMORY_SOFT_LIMIT:
        return (
            f"Memory is at {length:,}/{MEMORY_HARD_LIMIT:,} characters. "
            "Consolidate by merging related items and removing less important "
            "entries on your next update."
        )
    return None


# ---------------------------------------------------------------------------
# Auto-consolidation via a separate LLM call
# ---------------------------------------------------------------------------

_CONSOLIDATION_PROMPT = """\
You are a memory curator. The following memory document exceeds the character \
limit and must be shortened.

RULES:
1. Rewrite the document to be under {target} characters.
2. Sections whose headings contain "(pinned)" MUST be preserved EXACTLY as-is \
   — do not modify, shorten, or remove them.
3. Only consolidate non-pinned content.
4. Priority for keeping content: pinned sections > identity/instructions > \
   preferences > current context.
5. Merge duplicate entries, remove outdated entries, shorten verbose descriptions.
6. Each entry must be a single bullet point.
7. Preserve (YYYY-MM) date suffixes on time-sensitive entries.
8. Output ONLY the consolidated markdown — no explanations, no wrapping.

<memory_document>
{content}
</memory_document>"""


async def _auto_consolidate(
    content: str, llm: Any
) -> str | None:
    """Use a focused LLM call to consolidate *content* under the soft limit.

    Returns the consolidated string, or ``None`` if consolidation fails.
    """
    try:
        prompt = _CONSOLIDATION_PROMPT.format(
            target=MEMORY_SOFT_LIMIT, content=content
        )
        response = await llm.ainvoke(
            [HumanMessage(content=prompt)],
            config={"tags": ["surfsense:internal"]},
        )
        text = (
            response.content
            if isinstance(response.content, str)
            else str(response.content)
        )
        return text.strip()
    except Exception:
        logger.exception("Auto-consolidation LLM call failed")
        return None


# ---------------------------------------------------------------------------
# Shared save-and-respond logic
# ---------------------------------------------------------------------------

async def _save_memory(
    *,
    updated_memory: str,
    old_memory: str | None,
    llm: Any | None,
    apply_fn,
    commit_fn,
    rollback_fn,
    label: str,
) -> dict[str, Any]:
    """Validate, optionally auto-consolidate, save, and return a response dict.

    Parameters
    ----------
    updated_memory : str
        The new document the agent submitted.
    old_memory : str | None
        The previously persisted document (for diff / pinned checks).
    llm : Any | None
        LLM instance for auto-consolidation (may be ``None``).
    apply_fn : callable(str) -> None
        Callback that sets the new memory on the ORM object.
    commit_fn : coroutine
        ``session.commit``.
    rollback_fn : coroutine
        ``session.rollback``.
    label : str
        Human label for log messages (e.g. "user memory", "team memory").
    """
    content = updated_memory

    # --- pinned-section gate (before any size check) ---
    pinned_err = _validate_pinned_preserved(old_memory, content)
    if pinned_err:
        return {"status": "error", "message": pinned_err}

    # --- hard-limit gate with auto-consolidation fallback ---
    size_err = _validate_memory_size(content)
    if size_err:
        if llm is None:
            return size_err

        consolidated = await _auto_consolidate(content, llm)
        if consolidated is None:
            return size_err

        # Restore any pinned sections the consolidation LLM may have dropped
        if old_memory:
            consolidated = _restore_missing_pinned(old_memory, consolidated)

        recheck = _validate_memory_size(consolidated)
        if recheck:
            return recheck

        content = consolidated

    # --- persist ---
    try:
        apply_fn(content)
        await commit_fn()
    except Exception as e:
        logger.exception("Failed to update %s: %s", label, e)
        await rollback_fn()
        return {"status": "error", "message": f"Failed to update {label}: {e}"}

    # --- build response ---
    resp: dict[str, Any] = {"status": "saved", "message": f"{label.capitalize()} updated."}

    if content is not updated_memory:
        resp["notice"] = (
            "Memory was automatically consolidated to fit within limits."
        )

    diff_warnings = _validate_diff(old_memory, content)
    if diff_warnings:
        resp["diff_warnings"] = diff_warnings

    warning = _soft_warning(content)
    if warning:
        resp["warning"] = warning

    return resp


# ---------------------------------------------------------------------------
# Tool factories
# ---------------------------------------------------------------------------

def create_update_memory_tool(
    user_id: str | UUID,
    db_session: AsyncSession,
    llm: Any | None = None,
):
    uid = UUID(user_id) if isinstance(user_id, str) else user_id

    @tool
    async def update_memory(updated_memory: str) -> dict[str, Any]:
        """Update the user's personal memory document.

        Your current memory is shown in <user_memory> in the system prompt.
        When the user shares important long-term information (preferences,
        facts, instructions, context), rewrite the memory document to include
        the new information.  Merge new facts with existing ones, update
        contradictions, remove outdated entries, and keep it concise.

        Args:
            updated_memory: The FULL updated markdown document (not a diff).
        """
        try:
            result = await db_session.execute(
                select(User).where(User.id == uid)
            )
            user = result.scalars().first()
            if not user:
                return {"status": "error", "message": "User not found."}

            old_memory = user.memory_md

            return await _save_memory(
                updated_memory=updated_memory,
                old_memory=old_memory,
                llm=llm,
                apply_fn=lambda content: setattr(user, "memory_md", content),
                commit_fn=db_session.commit,
                rollback_fn=db_session.rollback,
                label="memory",
            )
        except Exception as e:
            logger.exception("Failed to update user memory: %s", e)
            await db_session.rollback()
            return {
                "status": "error",
                "message": f"Failed to update memory: {e}",
            }

    return update_memory


def create_update_team_memory_tool(
    search_space_id: int,
    db_session: AsyncSession,
    llm: Any | None = None,
):
    @tool
    async def update_memory(updated_memory: str) -> dict[str, Any]:
        """Update the team's shared memory document for this search space.

        Your current team memory is shown in <team_memory> in the system
        prompt.  When the team shares important long-term information
        (decisions, conventions, key facts, priorities), rewrite the memory
        document to include the new information.  Merge new facts with
        existing ones, update contradictions, remove outdated entries, and
        keep it concise.

        Args:
            updated_memory: The FULL updated markdown document (not a diff).
        """
        try:
            result = await db_session.execute(
                select(SearchSpace).where(SearchSpace.id == search_space_id)
            )
            space = result.scalars().first()
            if not space:
                return {"status": "error", "message": "Search space not found."}

            old_memory = space.shared_memory_md

            return await _save_memory(
                updated_memory=updated_memory,
                old_memory=old_memory,
                llm=llm,
                apply_fn=lambda content: setattr(space, "shared_memory_md", content),
                commit_fn=db_session.commit,
                rollback_fn=db_session.rollback,
                label="team memory",
            )
        except Exception as e:
            logger.exception("Failed to update team memory: %s", e)
            await db_session.rollback()
            return {
                "status": "error",
                "message": f"Failed to update team memory: {e}",
            }

    return update_memory
