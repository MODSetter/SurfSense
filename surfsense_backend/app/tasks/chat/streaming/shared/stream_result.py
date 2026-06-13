"""Per-turn streaming state shared between the orchestrator and event loop."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


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
    # ``persist_assistant_shell`` right after the user row is persisted. ``None``
    # for the legacy/anonymous code paths that don't opt in to server-side
    # ``ContentPart[]`` projection.
    assistant_message_id: int | None = None
    # In-memory mirror of the FE's assistant-ui ``ContentPartsState``, populated
    # by the lifecycle methods called from the streaming event loop at each
    # ``streaming_service.format_*`` yield site. Snapshot in the streaming
    # ``finally`` to produce the rich JSONB persisted by
    # ``finalize_assistant_turn``. ``repr=False`` keeps the log-on-error path
    # (``StreamResult`` is logged in some error branches) from dumping a
    # potentially-large parts list.
    content_builder: Any | None = field(default=None, repr=False)
    # User-visible assistant message parts derived from the final LangGraph
    # state. Used after streaming completes as a provider-agnostic persistence
    # backfill when no text chunks reached the live stream.
    final_message_parts: list[dict[str, Any]] = field(default_factory=list)
