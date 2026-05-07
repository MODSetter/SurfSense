"""Mutable counters and maps for one agent stream."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentEventRelayState:
    """Tracks text, thinking steps, tool depth, and pending tool-call metadata."""

    accumulated_text: str = ""
    current_text_id: str | None = None
    thinking_step_counter: int = 0
    tool_step_ids: dict[str, str] = field(default_factory=dict)
    completed_step_ids: set[str] = field(default_factory=set)
    last_active_step_id: str | None = None
    last_active_step_title: str = ""
    last_active_step_items: list[str] = field(default_factory=list)
    just_finished_tool: bool = False
    active_tool_depth: int = 0
    called_update_memory: bool = False
    current_reasoning_id: str | None = None
    pending_tool_call_chunks: list[dict[str, Any]] = field(default_factory=list)
    lc_tool_call_id_by_run: dict[str, str] = field(default_factory=dict)
    file_path_by_run: dict[str, str] = field(default_factory=dict)
    index_to_meta: dict[int, dict[str, str]] = field(default_factory=dict)
    ui_tool_call_id_by_run: dict[str, str] = field(default_factory=dict)
    current_lc_tool_call_id: dict[str, str | None] = field(
        default_factory=lambda: {"value": None}
    )

    @classmethod
    def for_invocation(
        cls,
        *,
        initial_step_id: str | None = None,
        initial_step_title: str = "",
        initial_step_items: list[str] | None = None,
    ) -> AgentEventRelayState:
        counter = 1 if initial_step_id else 0
        return cls(
            thinking_step_counter=counter,
            last_active_step_id=initial_step_id,
            last_active_step_title=initial_step_title,
            last_active_step_items=list(initial_step_items or []),
        )

    def next_thinking_step_id(self, step_prefix: str) -> str:
        self.thinking_step_counter += 1
        return f"{step_prefix}-{self.thinking_step_counter}"
