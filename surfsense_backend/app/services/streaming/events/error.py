"""Single terminal error path chat streaming must route through."""

from __future__ import annotations

from typing import Any

from ..emitter import Emitter, attach_emitted_by
from ..envelope import format_sse


def format_error(
    error_text: str,
    *,
    error_code: str | None = None,
    extra: dict[str, Any] | None = None,
    emitter: Emitter | None = None,
) -> str:
    payload: dict[str, Any] = {"type": "error", "errorText": error_text}
    if error_code:
        payload["errorCode"] = error_code
    if extra:
        payload.update(extra)
    return format_sse(attach_emitted_by(payload, emitter))
