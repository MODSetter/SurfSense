"""``start_watch`` tool — bind a recurring watch to the current chat.

Creates a ``schedule`` + ``chat_message`` automation that re-posts the question
into this chat on a cadence, so the agent re-answers against the chat's memory.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException
from langchain_core.tools import tool

from app.auth.context import AuthContext
from app.automations.services.automation import AutomationService
from app.automations.services.chat_watch import create_watch
from app.db import async_session_maker

logger = logging.getLogger(__name__)


def create_start_watch_tool(
    *,
    workspace_id: int | None,
    thread_id: int | str | None,
    auth_context: AuthContext | None,
):
    """Build the ``start_watch`` tool bound to the current chat.

    ``thread_id`` and ``auth_context`` are injected from the chat session so the
    model never guesses them; a fresh session is opened per call.
    """

    @tool
    async def start_watch(message: str, cron: str, timezone: str) -> dict[str, Any]:
        """Keep watching: re-run this question on a schedule in THIS chat.

        Use when the user wants an answer refreshed on a cadence without
        re-asking (e.g. "check this page every weekday and tell me what
        changed"). The watch re-posts ``message`` into this chat on the
        schedule; the user sees new answers here and can say "stop watching"
        to cancel.

        Args:
            message: The question to re-ask each run, self-contained (include
                the URL / target). Written as if the user asked it again.
            cron: Five-field cron expression for the cadence
                (e.g. "0 9 * * 1-5" = weekdays at 09:00).
            timezone: IANA timezone for the schedule (e.g. "UTC",
                "Africa/Kigali"). Ask the user if unclear.

        Returns:
            ``{"status": "watching", "automation_id": int, "name": str,
            "cron": str, "timezone": str}`` on success.
            ``{"status": "error", "message": str}`` when the watch could not
            be created (e.g. workspace model not billable for automations).
        """
        if thread_id is None or auth_context is None:
            return {
                "status": "error",
                "message": "Watches can only be started from inside a chat.",
            }

        try:
            async with async_session_maker() as session:
                service = AutomationService(session=session, auth=auth_context)
                created = await create_watch(
                    service,
                    workspace_id=int(workspace_id) if workspace_id is not None else 0,
                    thread_id=int(thread_id),
                    message=message,
                    cron=cron,
                    timezone=timezone,
                )
        except HTTPException as exc:
            return {"status": "error", "message": str(exc.detail)}
        except Exception as exc:
            from langgraph.errors import GraphInterrupt

            if isinstance(exc, GraphInterrupt):
                raise
            logger.exception("start_watch failed")
            return {"status": "error", "message": f"could not start watch: {exc}"}

        return {
            "status": "watching",
            "automation_id": created.id,
            "name": created.name,
            "cron": cron,
            "timezone": timezone,
        }

    return start_watch


__all__ = ["create_start_watch_tool"]
