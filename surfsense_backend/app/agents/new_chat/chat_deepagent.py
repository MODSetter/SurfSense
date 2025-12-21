"""
SurfSense deep agent implementation.

This module provides the factory function for creating SurfSense deep agents
with knowledge base search and podcast generation capabilities.
"""

from collections.abc import Sequence

from deepagents import create_deep_agent
from langchain_core.tools import BaseTool
from langchain_litellm import ChatLiteLLM
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.new_chat.context import SurfSenseContextSchema
from app.agents.new_chat.knowledge_base import create_search_knowledge_base_tool
from app.agents.new_chat.podcast import create_generate_podcast_tool
from app.agents.new_chat.system_prompt import build_surfsense_system_prompt
from app.services.connector_service import ConnectorService

# =============================================================================
# Deep Agent Factory
# =============================================================================


def create_surfsense_deep_agent(
    llm: ChatLiteLLM,
    search_space_id: int,
    db_session: AsyncSession,
    connector_service: ConnectorService,
    user_id: str | None = None,
    user_instructions: str | None = None,
    enable_citations: bool = True,
    enable_podcast: bool = True,
    additional_tools: Sequence[BaseTool] | None = None,
):
    """
    Create a SurfSense deep agent with knowledge base search and podcast generation capabilities.

    Args:
        llm: ChatLiteLLM instance
        search_space_id: The user's search space ID
        db_session: Database session
        connector_service: Initialized connector service
        user_id: The user's ID (required for podcast generation)
        user_instructions: Optional user instructions to inject into the system prompt.
                          These will be added to the system prompt to customize agent behavior.
        enable_citations: Whether to include citation instructions in the system prompt (default: True).
                         When False, the agent will not be instructed to add citations to responses.
        enable_podcast: Whether to include the podcast generation tool (default: True).
                       When True and user_id is provided, the agent can generate podcasts.
        additional_tools: Optional sequence of additional tools to inject into the agent.
                         The search_knowledge_base tool will always be included.

    Returns:
        CompiledStateGraph: The configured deep agent
    """
    # Create the search tool with injected dependencies
    search_tool = create_search_knowledge_base_tool(
        search_space_id=search_space_id,
        db_session=db_session,
        connector_service=connector_service,
    )

    # Combine search tool with any additional tools
    tools = [search_tool]

    # Add podcast tool if enabled and user_id is provided
    if enable_podcast and user_id:
        podcast_tool = create_generate_podcast_tool(
            search_space_id=search_space_id,
            db_session=db_session,
            user_id=str(user_id),
        )
        tools.append(podcast_tool)

    if additional_tools:
        tools.extend(additional_tools)

    # Create the deep agent with user-configurable system prompt
    agent = create_deep_agent(
        model=llm,
        tools=tools,
        system_prompt=build_surfsense_system_prompt(
            user_instructions=user_instructions,
            enable_citations=enable_citations,
        ),
        context_schema=SurfSenseContextSchema,
    )

    return agent
