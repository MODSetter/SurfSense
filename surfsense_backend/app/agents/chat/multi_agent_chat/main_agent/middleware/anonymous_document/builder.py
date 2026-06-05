"""Anonymous document hydration from Redis (cloud only)."""

from __future__ import annotations

from app.agents.chat.multi_agent_chat.shared.filesystem_selection import FilesystemMode

from .middleware import AnonymousDocumentMiddleware


def build_anonymous_doc_mw(
    *,
    filesystem_mode: FilesystemMode,
    anon_session_id: str | None,
) -> AnonymousDocumentMiddleware | None:
    if filesystem_mode != FilesystemMode.CLOUD:
        return None
    return AnonymousDocumentMiddleware(anon_session_id=anon_session_id)
