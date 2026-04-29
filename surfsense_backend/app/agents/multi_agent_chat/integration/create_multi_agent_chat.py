"""Single entry: SurfSense connectors + multi-agent stack → compiled supervisor graph."""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel
from langgraph.types import Checkpointer
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.multi_agent_chat.calendar import build_google_calendar_connector_tools
from app.agents.multi_agent_chat.gmail import build_gmail_connector_tools
from app.agents.multi_agent_chat.routing.supervisor_routing import build_supervisor_routing_tools
from app.agents.multi_agent_chat.supervisor import build_supervisor_agent


def create_multi_agent_chat(
    llm: BaseChatModel,
    *,
    db_session: AsyncSession,
    search_space_id: int,
    user_id: str,
    checkpointer: Checkpointer | None = None,
):
    """Build the full multi-agent chat graph (supervisor + Gmail + Calendar sub-agents via ``new_chat`` tools)."""
    routing_tools = build_supervisor_routing_tools(
        llm,
        gmail_tools=build_gmail_connector_tools(
            db_session=db_session,
            search_space_id=search_space_id,
            user_id=user_id,
        ),
        calendar_tools=build_google_calendar_connector_tools(
            db_session=db_session,
            search_space_id=search_space_id,
            user_id=user_id,
        ),
    )
    return build_supervisor_agent(llm, tools=routing_tools, checkpointer=checkpointer)
