"""Configurable inputs for the brief-planning graph."""

from __future__ import annotations

from dataclasses import dataclass, field, fields

from langchain_core.runnables import RunnableConfig

from app.podcasts.duration_limits import (
    DEFAULT_MAX_SECONDS,
    DEFAULT_MIN_SECONDS,
)

# Sensible defaults for a fresh brief; the user adjusts the range at the gate.
DEFAULT_SPEAKER_COUNT = 2


@dataclass(kw_only=True)
class BriefConfig:
    """Signals used to propose a brief; everything here is non-LLM context."""

    speaker_count: int = DEFAULT_SPEAKER_COUNT
    min_seconds: int = DEFAULT_MIN_SECONDS
    max_seconds: int = DEFAULT_MAX_SECONDS
    focus: str | None = None
    last_used_language: str | None = None
    last_used_voices: list[str] = field(default_factory=list)

    @classmethod
    def from_runnable_config(cls, config: RunnableConfig | None = None) -> BriefConfig:
        configurable = (config.get("configurable") or {}) if config else {}
        names = {f.name for f in fields(cls) if f.init}
        return cls(**{k: v for k, v in configurable.items() if k in names})
