"""
Tools registry for SurfSense deep agent.

This module provides a registry pattern for managing tools in the SurfSense agent.
It makes it easy for OSS contributors to add new tools by:
1. Creating a tool factory function in a new file in this directory
2. Registering the tool in the BUILTIN_TOOLS list below

Example of adding a new tool:
------------------------------
1. Create your tool file (e.g., `tools/my_tool.py`):

    from langchain_core.tools import tool
    from sqlalchemy.ext.asyncio import AsyncSession

    def create_my_tool(search_space_id: int, db_session: AsyncSession):
        @tool
        async def my_tool(param: str) -> dict:
            '''My tool description.'''
            # Your implementation
            return {"result": "success"}
        return my_tool

2. Import and register in this file:

    from .my_tool import create_my_tool

    # Add to BUILTIN_TOOLS list:
    ToolDefinition(
        name="my_tool",
        description="Description of what your tool does",
        factory=lambda deps: create_my_tool(
            search_space_id=deps["search_space_id"],
            db_session=deps["db_session"],
        ),
        requires=["search_space_id", "db_session"],
    ),
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from langchain_core.tools import BaseTool

from .display_image import create_display_image_tool
from .knowledge_base import create_search_knowledge_base_tool
from .link_preview import create_link_preview_tool
from .podcast import create_generate_podcast_tool
from .scrape_webpage import create_scrape_webpage_tool
from .search_surfsense_docs import create_search_surfsense_docs_tool

# =============================================================================
# Tool Definition
# =============================================================================


@dataclass
class ToolDefinition:
    """
    Definition of a tool that can be added to the agent.

    Attributes:
        name: Unique identifier for the tool
        description: Human-readable description of what the tool does
        factory: Callable that creates the tool. Receives a dict of dependencies.
        requires: List of dependency names this tool needs (e.g., "search_space_id", "db_session")
        enabled_by_default: Whether the tool is enabled when no explicit config is provided
    """

    name: str
    description: str
    factory: Callable[[dict[str, Any]], BaseTool]
    requires: list[str] = field(default_factory=list)
    enabled_by_default: bool = True


# =============================================================================
# Built-in Tools Registry
# =============================================================================

# Registry of all built-in tools
# Contributors: Add your new tools here!
BUILTIN_TOOLS: list[ToolDefinition] = [
    # Core tool - searches the user's knowledge base
    ToolDefinition(
        name="search_knowledge_base",
        description="Search the user's personal knowledge base for relevant information",
        factory=lambda deps: create_search_knowledge_base_tool(
            search_space_id=deps["search_space_id"],
            db_session=deps["db_session"],
            connector_service=deps["connector_service"],
        ),
        requires=["search_space_id", "db_session", "connector_service"],
    ),
    # Podcast generation tool
    ToolDefinition(
        name="generate_podcast",
        description="Generate an audio podcast from provided content",
        factory=lambda deps: create_generate_podcast_tool(
            search_space_id=deps["search_space_id"],
            db_session=deps["db_session"],
        ),
        requires=["search_space_id", "db_session"],
    ),
    # Link preview tool - fetches Open Graph metadata for URLs
    ToolDefinition(
        name="link_preview",
        description="Fetch metadata for a URL to display a rich preview card",
        factory=lambda deps: create_link_preview_tool(),
        requires=[],
    ),
    # Display image tool - shows images in the chat
    ToolDefinition(
        name="display_image",
        description="Display an image in the chat with metadata",
        factory=lambda deps: create_display_image_tool(),
        requires=[],
    ),
    # Web scraping tool - extracts content from webpages
    ToolDefinition(
        name="scrape_webpage",
        description="Scrape and extract the main content from a webpage",
        factory=lambda deps: create_scrape_webpage_tool(
            firecrawl_api_key=deps.get("firecrawl_api_key"),
        ),
        requires=[],  # firecrawl_api_key is optional
    ),
    # Note: write_todos is now provided by TodoListMiddleware from deepagents
    # Surfsense documentation search tool
    ToolDefinition(
        name="search_surfsense_docs",
        description="Search Surfsense documentation for help with using the application",
        factory=lambda deps: create_search_surfsense_docs_tool(
            db_session=deps["db_session"],
        ),
        requires=["db_session"],
    ),
    # =========================================================================
    # ADD YOUR CUSTOM TOOLS BELOW
    # =========================================================================
    # Example:
    # ToolDefinition(
    #     name="my_custom_tool",
    #     description="What my tool does",
    #     factory=lambda deps: create_my_custom_tool(...),
    #     requires=["search_space_id"],
    # ),
]


# =============================================================================
# Registry Functions
# =============================================================================


def get_tool_by_name(name: str) -> ToolDefinition | None:
    """Get a tool definition by its name."""
    for tool_def in BUILTIN_TOOLS:
        if tool_def.name == name:
            return tool_def
    return None


def get_all_tool_names() -> list[str]:
    """Get names of all registered tools."""
    return [tool_def.name for tool_def in BUILTIN_TOOLS]


def get_default_enabled_tools() -> list[str]:
    """Get names of tools that are enabled by default."""
    return [tool_def.name for tool_def in BUILTIN_TOOLS if tool_def.enabled_by_default]


def build_tools(
    dependencies: dict[str, Any],
    enabled_tools: list[str] | None = None,
    disabled_tools: list[str] | None = None,
    additional_tools: list[BaseTool] | None = None,
) -> list[BaseTool]:
    """
    Build the list of tools for the agent.

    Args:
        dependencies: Dict containing all possible dependencies:
            - search_space_id: The search space ID
            - db_session: Database session
            - connector_service: Connector service instance
            - firecrawl_api_key: Optional Firecrawl API key
        enabled_tools: Explicit list of tool names to enable. If None, uses defaults.
        disabled_tools: List of tool names to disable (applied after enabled_tools).
        additional_tools: Extra tools to add (e.g., custom tools not in registry).

    Returns:
        List of configured tool instances ready for the agent.

    Example:
        # Use all default tools
        tools = build_tools(deps)

        # Use only specific tools
        tools = build_tools(deps, enabled_tools=["search_knowledge_base", "link_preview"])

        # Use defaults but disable podcast
        tools = build_tools(deps, disabled_tools=["generate_podcast"])

        # Add custom tools
        tools = build_tools(deps, additional_tools=[my_custom_tool])
    """
    # Determine which tools to enable
    if enabled_tools is not None:
        tool_names_to_use = set(enabled_tools)
    else:
        tool_names_to_use = set(get_default_enabled_tools())

    # Apply disabled list
    if disabled_tools:
        tool_names_to_use -= set(disabled_tools)

    # Build the tools
    tools: list[BaseTool] = []
    for tool_def in BUILTIN_TOOLS:
        if tool_def.name not in tool_names_to_use:
            continue

        # Check that all required dependencies are provided
        missing_deps = [dep for dep in tool_def.requires if dep not in dependencies]
        if missing_deps:
            raise ValueError(
                f"Tool '{tool_def.name}' requires dependencies: {missing_deps}"
            )

        # Create the tool
        tool = tool_def.factory(dependencies)
        tools.append(tool)

    # Add any additional custom tools
    if additional_tools:
        tools.extend(additional_tools)

    return tools
