"""Configurable inputs for the transcript-drafting graph."""

from __future__ import annotations

from dataclasses import dataclass, fields

from langchain_core.runnables import RunnableConfig

from app.podcasts.schemas import PodcastSpec


@dataclass(kw_only=True)
class TranscriptConfig:
    """The approved spec and user focus that drive drafting."""

    search_space_id: int
    spec: PodcastSpec
    focus: str | None = None

    @classmethod
    def from_runnable_config(
        cls, config: RunnableConfig | None = None
    ) -> TranscriptConfig:
        configurable = (config.get("configurable") or {}) if config else {}
        names = {f.name for f in fields(cls) if f.init}
        return cls(**{k: v for k, v in configurable.items() if k in names})
