"""
SurfSense deep agent implementation.

This module provides the factory function for creating SurfSense deep agents
with configurable tools via the tools registry.
"""

from collections.abc import Sequence

from deepagents import create_deep_agent
from langchain_core.tools import BaseTool
from langchain_litellm import ChatLiteLLM
from langgraph.types import Checkpointer
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.new_chat.context import SurfSenseContextSchema
from app.agents.new_chat.system_prompt import build_surfsense_system_prompt
from app.agents.new_chat.tools import build_tools
from app.services.connector_service import ConnectorService

# =============================================================================
# Deep Agent Factory
# =============================================================================


def create_surfsense_deep_agent(
    llm: ChatLiteLLM,
    search_space_id: int,
    db_session: AsyncSession,
    connector_service: ConnectorService,
    checkpointer: Checkpointer,
    enabled_tools: list[str] | None = None,
    disabled_tools: list[str] | None = None,
    additional_tools: Sequence[BaseTool] | None = None,
    firecrawl_api_key: str | None = None,
):
    """
    Create a SurfSense deep agent with configurable tools.

    The agent comes with built-in tools that can be configured:
    - search_knowledge_base: Search the user's personal knowledge base
    - generate_podcast: Generate audio podcasts from content
    - link_preview: Fetch rich previews for URLs
    - display_image: Display images in chat
    - scrape_webpage: Extract content from webpages

    Args:
        llm: ChatLiteLLM instance for the agent's language model
        search_space_id: The user's search space ID
        db_session: Database session for tools that need DB access
        connector_service: Initialized connector service for knowledge base search
        checkpointer: LangGraph checkpointer for conversation state persistence.
                      Use AsyncPostgresSaver for production or MemorySaver for testing.
        enabled_tools: Explicit list of tool names to enable. If None, all default tools
                      are enabled. Use this to limit which tools are available.
        disabled_tools: List of tool names to disable. Applied after enabled_tools.
                       Use this to exclude specific tools from the defaults.
        additional_tools: Extra custom tools to add beyond the built-in ones.
                         These are always added regardless of enabled/disabled settings.
        firecrawl_api_key: Optional Firecrawl API key for premium web scraping.
                          Falls back to Chromium/Trafilatura if not provided.

    Returns:
        CompiledStateGraph: The configured deep agent

    Examples:
        # Create agent with all default tools
        agent = create_surfsense_deep_agent(llm, search_space_id, db_session, ...)

        # Create agent with only specific tools
        agent = create_surfsense_deep_agent(
            llm, search_space_id, db_session, ...,
            enabled_tools=["search_knowledge_base", "link_preview"]
        )

        # Create agent without podcast generation
        agent = create_surfsense_deep_agent(
            llm, search_space_id, db_session, ...,
            disabled_tools=["generate_podcast"]
        )

        # Add custom tools
        agent = create_surfsense_deep_agent(
            llm, search_space_id, db_session, ...,
            additional_tools=[my_custom_tool]
        )
    """
    # Build dependencies dict for the tools registry
    dependencies = {
        "search_space_id": search_space_id,
        "db_session": db_session,
        "connector_service": connector_service,
        "firecrawl_api_key": firecrawl_api_key,
    }

    # Build tools using the registry
    tools = build_tools(
        dependencies=dependencies,
        enabled_tools=enabled_tools,
        disabled_tools=disabled_tools,
        additional_tools=list(additional_tools) if additional_tools else None,
    )

    # Create the deep agent with system prompt and checkpointer
    agent = create_deep_agent(
        model=llm,
        tools=tools,
        system_prompt=build_surfsense_system_prompt(),
        context_schema=SurfSenseContextSchema,
        checkpointer=checkpointer,
    )

    return agent
