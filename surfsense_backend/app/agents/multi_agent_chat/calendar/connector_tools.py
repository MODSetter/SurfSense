"""Google Calendar connector LangChain tools (``new_chat`` factories)."""

from __future__ import annotations

from langchain_core.tools import BaseTool
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.multi_agent_chat.shared.deps import connector_binding
from app.agents.new_chat.tools.google_calendar import (
    create_create_calendar_event_tool,
    create_delete_calendar_event_tool,
    create_search_calendar_events_tool,
    create_update_calendar_event_tool,
)


def build_google_calendar_connector_tools(
    *,
    db_session: AsyncSession,
    search_space_id: int,
    user_id: str,
) -> list[BaseTool]:
    d = connector_binding(
        db_session=db_session,
        search_space_id=search_space_id,
        user_id=user_id,
    )
    return [
        create_search_calendar_events_tool(**d),
        create_create_calendar_event_tool(**d),
        create_update_calendar_event_tool(**d),
        create_delete_calendar_event_tool(**d),
    ]
