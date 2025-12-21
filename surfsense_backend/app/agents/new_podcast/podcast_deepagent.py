"""
SurfSense podcast deep agent implementation.

This module provides the factory function for creating SurfSense podcast deep agents
with podcast generation capability.
"""

from collections.abc import Sequence

from deepagents import create_deep_agent
from langchain_core.tools import BaseTool
from langchain_litellm import ChatLiteLLM
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.new_chat.knowledge_base import create_search_knowledge_base_tool
from app.services.connector_service import ConnectorService

from .context import PodcastContextSchema
from .podcast_tools import (
    create_generate_podcast_audio_tool,
    create_generate_podcast_transcript_tool,
)
from .system_prompt import build_podcast_system_prompt

# =============================================================================
# Podcast Deep Agent Factory
# =============================================================================


def create_surfsense_podcast_agent(
    llm: ChatLiteLLM,
    search_space_id: int,
    db_session: AsyncSession,
    connector_service: ConnectorService,
    user_instructions: str | None = None,
    additional_tools: Sequence[BaseTool] | None = None,
):
    """
    Create a SurfSense podcast deep agent with podcast generation capability.

    The agent has access to:
    1. search_knowledge_base - to find content from the user's knowledge base
    2. generate_podcast_transcript - to create a podcast script from content
    3. generate_podcast_audio - to convert transcripts to audio files

    Args:
        llm: ChatLiteLLM instance for the agent's reasoning and podcast generation
        search_space_id: The user's search space ID
        db_session: Database session for queries
        connector_service: Initialized connector service for knowledge base search
        user_instructions: Optional user instructions to inject into the system prompt.
                          These customize the podcast generation style (e.g., "make it funny")
        additional_tools: Optional sequence of additional tools to inject into the agent.
                         The core podcast tools will always be included.

    Returns:
        CompiledStateGraph: The configured podcast deep agent ready for invocation

    Example:
        ```python
        from app.agents.new_podcast import create_surfsense_podcast_agent

        agent = create_surfsense_podcast_agent(
            llm=llm,
            search_space_id=123,
            db_session=session,
            connector_service=connector_service,
            user_instructions="Create an educational podcast about the topic",
        )

        result = await agent.ainvoke({
            "messages": [HumanMessage(content="Create a podcast about my recent notes on AI")],
            "search_space_id": 123,
        })
        ```
    """
    # Create the knowledge base search tool
    search_tool = create_search_knowledge_base_tool(
        search_space_id=search_space_id,
        db_session=db_session,
        connector_service=connector_service,
    )

    # Create podcast transcript generation tool (uses the same LLM as the agent)
    transcript_tool = create_generate_podcast_transcript_tool(
        llm=llm,
    )

    # Create podcast audio generation tool
    audio_tool = create_generate_podcast_audio_tool()

    # Combine all tools
    tools = [search_tool, transcript_tool, audio_tool]
    if additional_tools:
        tools.extend(additional_tools)

    # Create the deep agent with podcast-specific system prompt
    agent = create_deep_agent(
        model=llm,
        tools=tools,
        system_prompt=build_podcast_system_prompt(
            user_instructions=user_instructions,
        ),
        context_schema=PodcastContextSchema,
    )

    return agent

