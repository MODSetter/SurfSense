"""Mutable counters and maps for one agent stream."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentEventRelayState:
    """Tracks text, thinking steps, tool depth, and pending tool-call metadata.

    ``active_span_id`` groups steps/tools for one open ``task`` episode.
    ``active_task_run_id`` is the LangGraph ``run_id`` of that ``task`` so we
    only clear the span when that run ends (not when child tools end). Handlers
    will set/clear these via ``task_span`` helpers in a later change.
    """

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
    # Open ``task`` delegation span (one id shared by nested activity); unset outside.
    active_span_id: str | None = None
    active_task_run_id: str | None = None
    # Span id minted when a ``task`` tool_call_chunk registers (before ``on_tool_start``).
    pending_task_span_by_lc: dict[str, str] = field(default_factory=dict)

    def span_metadata_if_active(self) -> dict[str, Any] | None:
        """``{"spanId": ...}`` when a span is active; ``None`` otherwise."""
        if self.active_span_id:
            return {"spanId": self.active_span_id}
        return None

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
