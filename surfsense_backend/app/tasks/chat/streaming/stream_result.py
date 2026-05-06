"""Mutable facts collected while streaming one agent turn."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class StreamResult:
    accumulated_text: str = ""
    is_interrupted: bool = False
    interrupt_value: dict[str, Any] | None = None
    sandbox_files: list[str] = field(default_factory=list)
    agent_called_update_memory: bool = False
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
    assistant_message_id: int | None = None
    content_builder: Any | None = field(default=None, repr=False)
