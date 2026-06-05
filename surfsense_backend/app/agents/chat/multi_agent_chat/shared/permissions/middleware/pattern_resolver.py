"""Per-tool pattern resolution.

A :data:`PatternResolver` turns a tool's ``args`` dict into a list of
wildcard patterns evaluated against the layered rulesets. The first
pattern is conventionally the bare tool name (catch-all); later entries
narrow down to specific resources (file paths, ids, etc.).

Tools without a custom resolver fall back to :func:`default_pattern_resolver`,
which yields only the bare tool name.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

PatternResolver = Callable[[dict[str, Any]], list[str]]


def default_pattern_resolver(name: str) -> PatternResolver:
    def _resolve(args: dict[str, Any]) -> list[str]:
        del args
        return [name]

    return _resolve


__all__ = ["PatternResolver", "default_pattern_resolver"]
