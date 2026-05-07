"""Inputs for orchestrator-owned streaming execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class StreamingContext:
    """Container for dependencies required by ``stream_output``."""

    agent: Any
    config: dict[str, Any]
    input_data: Any
    streaming_service: Any
    step_prefix: str = "thinking"
    initial_step_id: str | None = None
    initial_step_title: str = ""
    initial_step_items: list[str] | None = None
    content_builder: Any | None = None
    runtime_context: Any = None

