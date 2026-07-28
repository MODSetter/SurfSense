"""Commit messages for a turn's revision: model-generated subject, deterministic fallback."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from typing import Any

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You write git commit messages for a knowledge-base revision. "
    "Reply with ONE line only: an imperative subject in Conventional Commits "
    "style (e.g. 'docs: add meeting notes'). No quotes, no body, no trailers."
)

# ponytail: previews cap prompt size; a huge turn still gets a decent subject
# from the first files alone. Upgrade path: real unified diffs.
_MAX_FILES_IN_PROMPT = 20
_MAX_PREVIEW_CHARS = 300


def fallback_commit_message(
    *, writes: Mapping[str, bytes], removes: Iterable[str]
) -> str:
    """Deterministic subject used whenever generation fails; never raises."""
    removed = list(removes)
    parts: list[str] = []
    if writes:
        parts.append(f"update {len(writes)} file(s)")
    if removed:
        parts.append(f"remove {len(removed)} file(s)")
    return "chore: " + ", ".join(parts)


def _describe_changes(writes: Mapping[str, bytes], removes: Iterable[str]) -> str:
    lines: list[str] = []
    for path, content in list(writes.items())[:_MAX_FILES_IN_PROMPT]:
        preview = content[:_MAX_PREVIEW_CHARS].decode("utf-8", errors="replace")
        lines.append(f"WRITE {path}\n{preview}")
    for path in list(removes)[:_MAX_FILES_IN_PROMPT]:
        lines.append(f"REMOVE {path}")
    return "\n\n".join(lines)


async def generate_commit_message(
    llm: Any | None, *, writes: Mapping[str, bytes], removes: Iterable[str]
) -> str:
    """One-line subject for the turn's revision. Falls back rather than raise:
    a commit must never be lost to message generation. ``llm=None`` (the
    disconnect fallback path) uses the deterministic subject directly."""
    if llm is None:
        return fallback_commit_message(writes=writes, removes=removes)
    try:
        reply = await llm.ainvoke(
            [("system", _SYSTEM_PROMPT), ("human", _describe_changes(writes, removes))]
        )
        content = getattr(reply, "content", "")
        if not isinstance(content, str):
            content = str(content)
        subject = content.strip().splitlines()[0].strip() if content.strip() else ""
        if subject:
            return subject
    except Exception:
        logger.warning("Commit message generation failed; using fallback", exc_info=True)
    return fallback_commit_message(writes=writes, removes=removes)
