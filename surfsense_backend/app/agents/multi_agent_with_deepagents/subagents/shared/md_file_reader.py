"""Load markdown files shipped alongside a route package."""

from __future__ import annotations

from importlib import resources


def read_md_file(package: str, stem: str) -> str:
    """Load ``{stem}.md`` from ``package`` via importlib resources, or return empty."""
    ref = resources.files(package).joinpath(f"{stem}.md")
    if not ref.is_file():
        return ""
    text = ref.read_text(encoding="utf-8")
    return text.rstrip("\n")
