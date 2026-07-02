"""``refresh_watch`` — run the current chat's watch now (manual refresh).

Enqueues an immediate run of every watch bound to this chat, instead of waiting
for the next scheduled fire. Operates on the current thread only.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException
from langchain_core.tools import tool

from app.auth.context import AuthContext
from app.automations.services.automation import AutomationService
from app.automations.services.chat_watch import find_watches_for_thread, run_watch_now
from app.db import async_session_maker

logger = logging.getLogger(__name__)


def create_refresh_watch_tool(
    *,
    workspace_id: int | None,
    thread_id: int | str | None,
    auth_context: AuthContext | None,
):
    """Build the ``refresh_watch`` tool bound to the current chat."""

    @tool
    async def refresh_watch() -> dict[str, Any]:
        """Run THIS chat's watch now (a manual refresh).

        Use when the user says "check now", "refresh", or "run it again"
        without waiting for the schedule. No arguments — it acts on the
        current chat. The refreshed answer arrives as a new turn shortly after.

        Returns:
            ``{"status": "refreshing", "refreshed_ids": [int], "count": int}``
            when runs were enqueued, ``{"status": "not_watching", ...}`` when
            there is no watch, or ``{"status": "error", "message": str}``.
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
                        "message": "This chat has no active watch to refresh.",
                    }
                refreshed_ids = []
                for watch in watches:
                    await run_watch_now(service, automation_id=watch.id)
                    refreshed_ids.append(watch.id)
        except HTTPException as exc:
            return {"status": "error", "message": str(exc.detail)}
        except Exception as exc:
            logger.exception("refresh_watch failed")
            return {"status": "error", "message": f"could not refresh watch: {exc}"}

        return {
            "status": "refreshing",
            "refreshed_ids": refreshed_ids,
            "count": len(refreshed_ids),
        }

    return refresh_watch


__all__ = ["create_refresh_watch_tool"]
