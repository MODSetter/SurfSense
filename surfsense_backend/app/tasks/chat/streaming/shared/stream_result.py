"""Per-turn streaming state shared between the orchestrator and event loop."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.tasks.chat.streaming.activity_timing import ActivityTimer


@dataclass
class StreamResult:
    accumulated_text: str = ""
    is_interrupted: bool = False
    sandbox_files: list[str] = field(default_factory=list)
    request_id: str | None = None
    turn_id: str = ""
    filesystem_mode: str = "cloud"
    client_platform: str = "web"
    intent_detected: str = "chat_only"
    intent_confidence: float = 0.0
    write_attempted: bool = False
    write_succeeded: bool = False
    verification_succeeded: bool = False
    commit_gate_passed: bool = True
    commit_gate_reason: str = ""
    # Pre-allocated assistant ``new_chat_messages.id`` for this turn, captured by
    # ``persist_assistant_shell`` right after the user row is persisted.
    assistant_message_id: int | None = None
    # Server-side content-part projection populated alongside SSE emission.
    # Snapshot in ``finally`` for ``finalize_assistant_turn``. ``repr=False``
    # prevents error logs from dumping a potentially large parts list.
    content_builder: Any | None = field(default=None, repr=False)
    activity_state: Any | None = field(default=None, repr=False)
    activity_timer: ActivityTimer = field(
        default_factory=ActivityTimer.start, repr=False
    )
    # User-visible assistant message parts derived from the final LangGraph
    # state. Used after streaming completes as a provider-agnostic persistence
    # backfill when no text chunks reached the live stream.
    final_message_parts: list[dict[str, Any]] = field(default_factory=list)
    # Per-conversation citation registry captured from the final LangGraph state
    # (a ``CitationRegistry`` or its serialized dict). Read at finalize to rewrite
    # the model's ``[n]`` ordinals into ``[citation:<payload>]`` markers.
    citation_registry: Any | None = field(default=None, repr=False)
