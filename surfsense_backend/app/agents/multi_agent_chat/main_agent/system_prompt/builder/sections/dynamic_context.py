"""``<dynamic_context>`` section — visibility-aware (private vs team thread)."""

from __future__ import annotations

from app.db import ChatVisibility

from ..load_md import read_prompt_md


def build_dynamic_context_section(*, visibility: ChatVisibility) -> str:
    variant = "team" if visibility == ChatVisibility.SEARCH_SPACE else "private"
    fragment = read_prompt_md(f"dynamic_context/{variant}.md")
    return f"\n{fragment}\n" if fragment else ""
