"""``stop_watch`` — stop watching in the current chat.

Deletes every watch automation bound to this chat, so it reverts to a normal
chat. Operates on the current thread only; the model passes no arguments.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException
from langchain_core.tools import tool

from app.auth.context import AuthContext
from app.automations.services.automation import AutomationService
from app.automations.services.chat_watch import (
    find_watches_for_thread,
    stop_watch as stop_watch_service,
)
from app.db import async_session_maker

logger = logging.getLogger(__name__)


def create_stop_watch_tool(
    *,
    workspace_id: int | None,
    thread_id: int | str | None,
    auth_context: AuthContext | None,
):
    """Build the ``stop_watch`` tool bound to the current chat."""

    @tool
    async def stop_watch() -> dict[str, Any]:
        """Stop watching in THIS chat (cancel the recurring re-asks).

        Use when the user says something like "stop watching", "cancel the
        watch", or "you can stop checking now". The chat reverts to a normal
        chat. No arguments — it acts on the current chat.

        Returns:
            ``{"status": "stopped", "stopped_ids": [int], "count": int}`` when
            watches were removed, ``{"status": "not_watching", ...}`` when there
            was nothing to stop, or ``{"status": "error", "message": str}``.
        """
        if thread_id is None or auth_context is None:
            return {
                "status": "error",
                "message": "Watches can only be managed from inside a chat.",
            }

        try:
            async with async_session_maker() as session:
                service = AutomationService(session=session, auth=auth_context)
                watches = await find_watches_for_thread(
                    service,
                    workspace_id=int(workspace_id) if workspace_id is not None else 0,
                    thread_id=int(thread_id),
                )
                if not watches:
                    return {
                        "status": "not_watching",
                        "message": "This chat has no active watch.",
                    }
                stopped_ids = []
                for watch in watches:
                    await stop_watch_service(service, automation_id=watch.id)
                    stopped_ids.append(watch.id)
        except HTTPException as exc:
            return {"status": "error", "message": str(exc.detail)}
        except Exception as exc:
            logger.exception("stop_watch failed")
            return {"status": "error", "message": f"could not stop watch: {exc}"}

        return {
            "status": "stopped",
            "stopped_ids": stopped_ids,
            "count": len(stopped_ids),
        }

    return stop_watch


__all__ = ["create_stop_watch_tool"]
