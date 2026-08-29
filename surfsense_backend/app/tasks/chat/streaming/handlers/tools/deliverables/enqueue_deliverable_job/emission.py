"""Preserve the safe pending-video payload required by the live card."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

from app.tasks.chat.streaming.handlers.tools.emission_context import (
    ToolCompletionEmissionContext,
)

_PUBLIC_FIELDS = frozenset({"status", "job_id", "title", "message", "error"})


def public_enqueue_payload(output: Any) -> dict[str, Any]:
    """Decode and allowlist the enqueue result without persisting internals."""
    if isinstance(output, str):
        try:
            output = json.loads(output)
        except (TypeError, ValueError):
            output = None
    if not isinstance(output, dict):
        return {"status": "failed"}
    return {key: output[key] for key in _PUBLIC_FIELDS if key in output}


def iter_completion_emission_frames(
    ctx: ToolCompletionEmissionContext,
) -> Iterator[str]:
    payload = public_enqueue_payload(ctx.tool_output)
    yield ctx.emit_tool_output_card(payload)
    if payload.get("status") == "pending" and payload.get("job_id"):
        yield ctx.streaming_service.format_terminal_info(
            "Video generation is in progress",
            "success",
        )
    else:
        yield ctx.streaming_service.format_terminal_info(
            "Video generation could not start",
            "error",
        )
