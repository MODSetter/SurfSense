"""Citation fragment for the main agent (chunk-tagged context only)."""

from __future__ import annotations

from ..load_md import read_prompt_md


def build_citations_section(*, citations_enabled: bool) -> str:
    name = "citations_on.md" if citations_enabled else "citations_off.md"
    fragment = read_prompt_md(name)
    return f"\n{fragment}\n" if fragment else ""
