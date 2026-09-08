"""What one code-generated document format is, and how to load its skill."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files


@dataclass(frozen=True)
class Office:
    """One code-generated document format: how to frame it and store its bytes."""

    key: str
    mime: str
    ext: str
    stem: str
    label: str
    library: str
    skill: str


def load_skill(package: str) -> str:
    """The authoring skill that ships beside a format's module."""
    return (files(package) / "SKILL.md").read_text(encoding="utf-8").strip()
