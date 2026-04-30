"""Load ``*.md`` prompt files from co-located packages (domain slices ship ``domain_prompt.md``)."""

from __future__ import annotations

from importlib import resources


def read_prompt_md(package: str, stem: str) -> str:
    """Read ``{stem}.md`` from the given import package (e.g. ``…expert_agent.connectors.gmail``)."""
    try:
        ref = resources.files(package).joinpath(f"{stem}.md")
        if not ref.is_file():
            return ""
        text = ref.read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError, OSError, TypeError):
        return ""
    if text.endswith("\n"):
        text = text[:-1]
    return text
