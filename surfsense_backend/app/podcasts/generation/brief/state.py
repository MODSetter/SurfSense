"""Mutable state threaded through the brief-planning graph."""

from __future__ import annotations

from dataclasses import dataclass

from app.podcasts.schemas import PodcastSpec


@dataclass
class BriefState:
    """The proposed spec the graph produces; inputs arrive via the config."""

    spec: PodcastSpec | None = None
