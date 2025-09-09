from collections.abc import AsyncGenerator
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.researcher.configuration import SearchMode
from app.agents.researcher.graph import graph as researcher_graph
from app.agents.researcher.state import State as ResearcherState
from app.agents.alison.graph import graph as alison_graph
from app.agents.alison.state import AlisonState
from app.services.streaming_service import StreamingService


async def stream_connector_search_results(
    user_query: str,
    user_id: str | UUID,
    search_space_id: int,
    session: AsyncSession,
    research_mode: str,
    selected_connectors: list[str],
    langchain_chat_history: list[Any],
    search_mode_str: str,
    document_ids_to_add_in_context: list[int],
    alison_enabled: bool = False,
    user_role: str = "professor",
) -> AsyncGenerator[str, None]:
    """
    Stream connector search results to the client

    Args:
        user_query: The user's query
        user_id: The user's ID (can be UUID object or string)
        search_space_id: The search space ID
        session: The database session
        research_mode: The research mode
        selected_connectors: List of selected connectors
        alison_enabled: Whether the Alison agent is enabled
        user_role: The user's role

    Yields:
        str: Formatted response strings
    """
    streaming_service = StreamingService()
    user_id_str = str(user_id) if isinstance(user_id, UUID) else user_id

    # Simple keyword check to see if the query is IT support-related
    it_support_keywords = ["projector", "mic", "microphone", "zoom", "display", "wifi", "internet"]
    is_it_support_query = any(keyword in user_query.lower() for keyword in it_support_keywords)

    if alison_enabled and is_it_support_query:
        # Use the Alison agent
        config = {
            "configurable": {
                "user_id": user_id_str,
                "user_role": user_role,
            }
        }
        initial_state = AlisonState(
            user_query=user_query,
            db_session=session,
            streaming_service=streaming_service,
            chat_history=langchain_chat_history,
            identified_problem=None,
            troubleshooting_steps=None,
            visual_aids=None,
            escalation_required=False,
            final_response=None,
        )
        async for chunk in alison_graph.astream(
            initial_state,
            config=config,
            stream_mode="custom",
        ):
            if isinstance(chunk, dict) and "yield_value" in chunk:
                yield chunk["yield_value"]
    else:
        # Use the Researcher agent
        if research_mode == "REPORT_GENERAL":
            num_sections = 1
        elif research_mode == "REPORT_DEEP":
            num_sections = 3
        elif research_mode == "REPORT_DEEPER":
            num_sections = 6
        else:
            num_sections = 1

        if search_mode_str == "CHUNKS":
            search_mode = SearchMode.CHUNKS
        elif search_mode_str == "DOCUMENTS":
            search_mode = SearchMode.DOCUMENTS

        config = {
            "configurable": {
                "user_query": user_query,
                "num_sections": num_sections,
                "connectors_to_search": selected_connectors,
                "user_id": user_id_str,
                "search_space_id": search_space_id,
                "search_mode": search_mode,
                "research_mode": research_mode,
                "document_ids_to_add_in_context": document_ids_to_add_in_context,
            }
        }
        initial_state = ResearcherState(
            db_session=session,
            streaming_service=streaming_service,
            chat_history=langchain_chat_history,
        )
        async for chunk in researcher_graph.astream(
            initial_state,
            config=config,
            stream_mode="custom",
        ):
            if isinstance(chunk, dict) and "yield_value" in chunk:
                yield chunk["yield_value"]

    yield streaming_service.format_completion()
