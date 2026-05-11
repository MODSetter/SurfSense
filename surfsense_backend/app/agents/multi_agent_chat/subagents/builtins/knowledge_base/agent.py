"""`knowledge_base` route: ``SubAgent`` spec for the SurfSense KB specialist.

The KB subagent owns the `/documents/` workspace: reading, writing, editing,
searching, and organising user documents.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from deepagents import SubAgent
from langchain_core.language_models import BaseChatModel

from app.agents.multi_agent_chat.subagents.shared.md_file_reader import (
    read_md_file,
)
from app.agents.multi_agent_chat.subagents.shared.subagent_builder import (
    pack_subagent,
)

NAME = "knowledge_base"


def build_subagent(
    *,
    dependencies: dict[str, Any],
    model: BaseChatModel | None = None,
    extra_middleware: Sequence[Any] | None = None,
    **_: Any,
) -> SubAgent:
    """Build the knowledge-base subagent spec.

    The FS toolset and SurfSense filesystem middleware land in a follow-up
    commit (``kb_middleware``); at this stage ``tools`` is intentionally
    empty so the spec is structurally valid but inert.
    """
    del dependencies  # plumbed for symmetry; no per-route tools at this stage.
    description = read_md_file(__package__, "description").strip()
    if not description:
        description = (
            "Handles knowledge-base reads, writes, edits, and organisation."
        )
    system_prompt = read_md_file(__package__, "system_prompt").strip()
    return pack_subagent(
        name=NAME,
        description=description,
        system_prompt=system_prompt,
        tools=[],
        model=model,
        extra_middleware=extra_middleware,
    )
