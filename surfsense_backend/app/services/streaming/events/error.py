"""Single terminal error path chat streaming must route through."""

from __future__ import annotations

from typing import Any

from ..emitter import Emitter, attach_emitted_by
from ..envelope import format_sse


def format_error(
    message: str,
    *,
    error_code: str | None = None,
    diagnostic: str | None = None,
    extra: dict[str, Any] | None = None,
    emitter: Emitter | None = None,
) -> str:
    payload: dict[str, Any] = dict(extra or {})
    payload.update({"type": "error", "message": message})
    if error_code:
        payload["errorCode"] = error_code
    if diagnostic:
        payload["diagnostic"] = diagnostic
    return format_sse(attach_emitted_by(payload, emitter))
