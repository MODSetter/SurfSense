"""``<agent_identity>`` section — visibility-aware, with ``{resolved_today}`` injection."""

from __future__ import annotations

from app.db import ChatVisibility

from ..load_md import read_prompt_md


def build_identity_section(
    *,
    visibility: ChatVisibility,
    resolved_today: str,
) -> str:
    variant = "team" if visibility == ChatVisibility.SEARCH_SPACE else "private"
    fragment = read_prompt_md(f"identity/{variant}.md")
    if not fragment:
        return ""
    return "\n" + fragment.format(resolved_today=resolved_today) + "\n"
