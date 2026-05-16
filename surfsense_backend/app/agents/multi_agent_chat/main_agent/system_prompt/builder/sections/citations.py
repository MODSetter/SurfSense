"""``<citations>`` section — on/off variant based on workspace configuration."""

from __future__ import annotations

from ..load_md import read_prompt_md


def build_citations_section(*, citations_enabled: bool) -> str:
    variant = "on" if citations_enabled else "off"
    fragment = read_prompt_md(f"citations/{variant}.md")
    return f"\n{fragment}\n" if fragment else ""
