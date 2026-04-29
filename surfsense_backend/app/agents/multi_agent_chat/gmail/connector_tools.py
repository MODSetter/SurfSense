"""Gmail connector LangChain tools (``new_chat`` factories; order matches registry)."""

from __future__ import annotations

from langchain_core.tools import BaseTool
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.multi_agent_chat.shared.deps import connector_binding
from app.agents.new_chat.tools.gmail import (
    create_create_gmail_draft_tool,
    create_read_gmail_email_tool,
    create_search_gmail_tool,
    create_send_gmail_email_tool,
    create_trash_gmail_email_tool,
    create_update_gmail_draft_tool,
)


def build_gmail_connector_tools(
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
        create_search_gmail_tool(**d),
        create_read_gmail_email_tool(**d),
        create_create_gmail_draft_tool(**d),
        create_send_gmail_email_tool(**d),
        create_trash_gmail_email_tool(**d),
        create_update_gmail_draft_tool(**d),
    ]
