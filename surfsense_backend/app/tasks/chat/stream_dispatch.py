"""Thin architecture dispatch seam for chat streaming entrypoints."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from app.agents.multi_agent_v1.entrypoint import MultiAgentEntrypoint
from app.agents.new_chat.architecture_mode import (
    ArchitectureMode,
    parse_architecture_mode,
)
from app.tasks.chat.stream_new_chat import stream_new_chat, stream_resume_chat


def _resolve_mode(mode_value: str) -> ArchitectureMode:
    return parse_architecture_mode(mode_value) or ArchitectureMode.SINGLE_AGENT


def dispatch_new_chat_stream(
    *,
    architecture_mode: str,
    stream_kwargs: dict[str, Any],
) -> AsyncGenerator[str, None]:
    mode = _resolve_mode(architecture_mode)
    if mode == ArchitectureMode.SINGLE_AGENT:
        return stream_new_chat(**stream_kwargs)
    entrypoint = MultiAgentEntrypoint()
    return entrypoint.stream_new_chat(
        fallback_streamer=stream_new_chat,
        fallback_kwargs=stream_kwargs,
    )


def dispatch_resume_chat_stream(
    *,
    architecture_mode: str,
    stream_kwargs: dict[str, Any],
) -> AsyncGenerator[str, None]:
    mode = _resolve_mode(architecture_mode)
    if mode == ArchitectureMode.SINGLE_AGENT:
        return stream_resume_chat(**stream_kwargs)
    entrypoint = MultiAgentEntrypoint()
    return entrypoint.stream_resume_chat(
        fallback_streamer=stream_resume_chat,
        fallback_kwargs=stream_kwargs,
    )
