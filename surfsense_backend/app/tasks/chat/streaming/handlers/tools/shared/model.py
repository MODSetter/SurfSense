"""In-progress thinking-step title and bullet lines."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ToolStartThinking:
    title: str
    items: list[str]
    include_items_on_frame: bool = True
