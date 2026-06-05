"""``<memory_protocol>`` section — visibility-aware (user vs team memory)."""

from __future__ import annotations

from app.db import ChatVisibility

from ..load_md import read_prompt_md


def build_memory_protocol_section(*, visibility: ChatVisibility) -> str:
    variant = "team" if visibility == ChatVisibility.SEARCH_SPACE else "private"
    fragment = read_prompt_md(f"memory_protocol/{variant}.md")
    return f"\n{fragment}\n" if fragment else ""
