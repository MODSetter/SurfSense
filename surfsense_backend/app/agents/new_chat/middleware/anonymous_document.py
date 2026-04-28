"""Lightweight middleware that loads the anonymous-session document into state.

Anonymous chats receive a single uploaded document via Redis (no DB row,
read-only). This middleware loads it once on the first turn into
``state['kb_anon_doc']`` so:

* :class:`KnowledgeTreeMiddleware` can render the synthetic ``/documents``
  view without touching the DB.
* :class:`KnowledgePriorityMiddleware` skips hybrid search and emits a
  degenerate priority list.
* :class:`KBPostgresBackend` (``als_info`` / ``aread`` / ``_load_file_data``)
  recognises the synthetic path.

The middleware is a no-op when ``anon_session_id`` is not provided or when
the document is already cached in state.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain.agents.middleware import AgentMiddleware, AgentState
from langgraph.runtime import Runtime

from app.agents.new_chat.filesystem_state import SurfSenseFilesystemState
from app.agents.new_chat.path_resolver import DOCUMENTS_ROOT, safe_filename

logger = logging.getLogger(__name__)


class AnonymousDocumentMiddleware(AgentMiddleware):  # type: ignore[type-arg]
    """Load the anonymous user's uploaded document from Redis into state."""

    tools = ()
    state_schema = SurfSenseFilesystemState

    def __init__(self, *, anon_session_id: str | None) -> None:
        self.anon_session_id = anon_session_id

    async def abefore_agent(  # type: ignore[override]
        self,
        state: AgentState,
        runtime: Runtime[Any],
    ) -> dict[str, Any] | None:
        del runtime
        if not self.anon_session_id:
            return None
        if state.get("kb_anon_doc"):
            return None

        anon_doc = await self._load_anon_document()
        if anon_doc is None:
            return None
        return {"kb_anon_doc": anon_doc}

    async def _load_anon_document(self) -> dict[str, Any] | None:
        """Read ``anon:doc:<session_id>`` from Redis."""
        try:
            import redis.asyncio as aioredis  # local import to keep cold paths cheap

            from app.config import config

            redis_client = aioredis.from_url(
                config.REDIS_APP_URL, decode_responses=True
            )
            try:
                redis_key = f"anon:doc:{self.anon_session_id}"
                data = await redis_client.get(redis_key)
                if not data:
                    return None
                payload = json.loads(data)
            finally:
                await redis_client.aclose()
        except Exception as exc:
            logger.warning("Failed to load anonymous document from Redis: %s", exc)
            return None

        title = str(payload.get("filename") or "uploaded_document")
        content = str(payload.get("content") or "")
        path = f"{DOCUMENTS_ROOT}/{safe_filename(title)}"
        return {
            "path": path,
            "title": title,
            "content": content,
            "chunks": [{"chunk_id": -1, "content": content}] if content else [],
        }


__all__ = ["AnonymousDocumentMiddleware"]
