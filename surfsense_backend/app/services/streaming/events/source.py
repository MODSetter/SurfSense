"""Source and file reference events."""

from __future__ import annotations

from typing import Any

from ..emitter import Emitter, attach_emitted_by
from ..envelope import format_sse


def format_source_url(
    url: str,
    *,
    source_id: str | None = None,
    title: str | None = None,
    emitter: Emitter | None = None,
) -> str:
    payload: dict[str, Any] = {
        "type": "source-url",
        "sourceId": source_id or url,
        "url": url,
    }
    if title:
        payload["title"] = title
    return format_sse(attach_emitted_by(payload, emitter))


def format_source_document(
    source_id: str,
    *,
    media_type: str = "file",
    title: str | None = None,
    description: str | None = None,
    emitter: Emitter | None = None,
) -> str:
    payload: dict[str, Any] = {
        "type": "source-document",
        "sourceId": source_id,
        "mediaType": media_type,
    }
    if title:
        payload["title"] = title
    if description:
        payload["description"] = description
    return format_sse(attach_emitted_by(payload, emitter))


def format_file(
    url: str,
    media_type: str,
    *,
    emitter: Emitter | None = None,
) -> str:
    payload: dict[str, Any] = {
        "type": "file",
        "url": url,
        "mediaType": media_type,
    }
    return format_sse(attach_emitted_by(payload, emitter))
