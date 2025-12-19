"""
Test script for create_deep_agent with ChatLiteLLM from global_llm_config.yaml

This demonstrates:
1. Loading LLM config from global_llm_config.yaml
2. Creating a ChatLiteLLM instance
3. Using context_schema to add custom state fields
4. Creating a search_knowledge_base tool similar to fetch_relevant_documents
"""

import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict

import yaml
from deepagents import create_deep_agent
from langchain_core.tools import BaseTool
from langchain_litellm import ChatLiteLLM
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.connector_service import ConnectorService

from .knowledge_base import create_search_knowledge_base_tool

# Add parent directory to path so 'app' module can be found when running directly
_THIS_FILE = Path(__file__).resolve()
_BACKEND_ROOT = _THIS_FILE.parent.parent.parent.parent  # surfsense_backend/
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


# =============================================================================
# LLM Configuration Loading
# =============================================================================


def load_llm_config_from_yaml(llm_config_id: int = -1) -> dict | None:
    """
    Load a specific LLM config from global_llm_config.yaml.

    Args:
        llm_config_id: The id of the config to load (default: -1)

    Returns:
        LLM config dict or None if not found
    """
    # Get the config file path
    base_dir = Path(__file__).resolve().parent.parent.parent.parent
    config_file = base_dir / "app" / "config" / "global_llm_config.yaml"

    # Fallback to example file if main config doesn't exist
    if not config_file.exists():
        config_file = base_dir / "app" / "config" / "global_llm_config.example.yaml"
        if not config_file.exists():
            print("Error: No global_llm_config.yaml or example file found")
            return None

    try:
        with open(config_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)
            configs = data.get("global_llm_configs", [])
            for cfg in configs:
                if isinstance(cfg, dict) and cfg.get("id") == llm_config_id:
                    return cfg

            print(f"Error: Global LLM config id {llm_config_id} not found")
            return None
    except Exception as e:
        print(f"Error loading config: {e}")
        return None


def create_chat_litellm_from_config(llm_config: dict) -> ChatLiteLLM | None:
    """
    Create a ChatLiteLLM instance from a global LLM config.

    Args:
        llm_config: LLM configuration dictionary from YAML

    Returns:
        ChatLiteLLM instance or None on error
    """
    # Provider mapping (same as in llm_service.py)
    provider_map = {
        "OPENAI": "openai",
        "ANTHROPIC": "anthropic",
        "GROQ": "groq",
        "COHERE": "cohere",
        "GOOGLE": "gemini",
        "OLLAMA": "ollama",
        "MISTRAL": "mistral",
        "AZURE_OPENAI": "azure",
        "OPENROUTER": "openrouter",
        "XAI": "xai",
        "BEDROCK": "bedrock",
        "VERTEX_AI": "vertex_ai",
        "TOGETHER_AI": "together_ai",
        "FIREWORKS_AI": "fireworks_ai",
        "DEEPSEEK": "openai",
        "ALIBABA_QWEN": "openai",
        "MOONSHOT": "openai",
        "ZHIPU": "openai",
    }

    # Build the model string
    if llm_config.get("custom_provider"):
        model_string = f"{llm_config['custom_provider']}/{llm_config['model_name']}"
    else:
        provider = llm_config.get("provider", "").upper()
        provider_prefix = provider_map.get(provider, provider.lower())
        model_string = f"{provider_prefix}/{llm_config['model_name']}"

    # Create ChatLiteLLM instance
    litellm_kwargs = {
        "model": model_string,
        "api_key": llm_config.get("api_key"),
    }

    # Add optional parameters
    if llm_config.get("api_base"):
        litellm_kwargs["api_base"] = llm_config["api_base"]

    # Add any additional litellm parameters
    if llm_config.get("litellm_params"):
        litellm_kwargs.update(llm_config["litellm_params"])

    return ChatLiteLLM(**litellm_kwargs)


# =============================================================================
# Custom Context Schema
# =============================================================================


class SurfSenseContextSchema(TypedDict):
    """
    Custom state schema for the SurfSense deep agent.

    This extends the default agent state with custom fields.
    The default state already includes:
    - messages: Conversation history
    - todos: Task list from TodoListMiddleware
    - files: Virtual filesystem from FilesystemMiddleware

    We're adding fields needed for knowledge base search:
    - search_space_id: The user's search space ID
    - db_session: Database session (injected at runtime)
    - connector_service: Connector service instance (injected at runtime)
    """

    search_space_id: int
    # These are runtime-injected and won't be serialized
    # db_session and connector_service are passed when invoking the agent


# =============================================================================
# Citation Instructions
# =============================================================================

SURFSENSE_CITATION_INSTRUCTIONS = """
<citation_instructions>
CRITICAL CITATION REQUIREMENTS:

1. For EVERY piece of information you include from the documents, add a citation in the format [citation:chunk_id] where chunk_id is the exact value from the `<chunk id='...'>` tag inside `<document_content>`.
2. Make sure ALL factual statements from the documents have proper citations.
3. If multiple chunks support the same point, include all relevant citations [citation:chunk_id1], [citation:chunk_id2].
4. You MUST use the exact chunk_id values from the `<chunk id='...'>` attributes. Do not create your own citation numbers.
5. Every citation MUST be in the format [citation:chunk_id] where chunk_id is the exact chunk id value.
6. Never modify or change the chunk_id - always use the original values exactly as provided in the chunk tags.
7. Do not return citations as clickable links.
8. Never format citations as markdown links like "([citation:5](https://example.com))". Always use plain square brackets only.
9. Citations must ONLY appear as [citation:chunk_id] or [citation:chunk_id1], [citation:chunk_id2] format - never with parentheses, hyperlinks, or other formatting.
10. Never make up chunk IDs. Only use chunk_id values that are explicitly provided in the `<chunk id='...'>` tags.
11. If you are unsure about a chunk_id, do not include a citation rather than guessing or making one up.

<document_structure_example>
The documents you receive are structured like this:

<document>
<document_metadata>
  <document_id>42</document_id>
  <document_type>GITHUB_CONNECTOR</document_type>
  <title><![CDATA[Some repo / file / issue title]]></title>
  <url><![CDATA[https://example.com]]></url>
  <metadata_json><![CDATA[{{"any":"other metadata"}}]]></metadata_json>
</document_metadata>

<document_content>
  <chunk id='123'><![CDATA[First chunk text...]]></chunk>
  <chunk id='124'><![CDATA[Second chunk text...]]></chunk>
</document_content>
</document>

IMPORTANT: You MUST cite using the chunk ids (e.g. 123, 124). Do NOT cite document_id.
</document_structure_example>

<citation_format>
- Every fact from the documents must have a citation in the format [citation:chunk_id] where chunk_id is the EXACT id value from a `<chunk id='...'>` tag
- Citations should appear at the end of the sentence containing the information they support
- Multiple citations should be separated by commas: [citation:chunk_id1], [citation:chunk_id2], [citation:chunk_id3]
- No need to return references section. Just citations in answer.
- NEVER create your own citation format - use the exact chunk_id values from the documents in the [citation:chunk_id] format
- NEVER format citations as clickable links or as markdown links like "([citation:5](https://example.com))". Always use plain square brackets only
- NEVER make up chunk IDs if you are unsure about the chunk_id. It is better to omit the citation than to guess
</citation_format>

<citation_examples>
CORRECT citation formats:
- [citation:5]
- [citation:chunk_id1], [citation:chunk_id2], [citation:chunk_id3]

INCORRECT citation formats (DO NOT use):
- Using parentheses and markdown links: ([citation:5](https://github.com/MODSetter/SurfSense))
- Using parentheses around brackets: ([citation:5])
- Using hyperlinked text: [link to source 5](https://example.com)
- Using footnote style: ... library¹
- Making up source IDs when source_id is unknown
- Using old IEEE format: [1], [2], [3]
- Using source types instead of IDs: [citation:GITHUB_CONNECTOR] instead of [citation:5]
</citation_examples>

<citation_output_example>
Based on your GitHub repositories and video content, Python's asyncio library provides tools for writing concurrent code using the async/await syntax [citation:5]. It's particularly useful for I/O-bound and high-level structured network code [citation:5].

The key advantage of asyncio is that it can improve performance by allowing other code to run while waiting for I/O operations to complete [citation:12]. This makes it excellent for scenarios like web scraping, API calls, database operations, or any situation where your program spends time waiting for external resources.

However, from your video learning, it's important to note that asyncio is not suitable for CPU-bound tasks as it runs on a single thread [citation:12]. For computationally intensive work, you'd want to use multiprocessing instead.
</citation_output_example>
</citation_instructions>
"""


# =============================================================================
# System Prompt
# =============================================================================


def build_surfsense_system_prompt(
    today: datetime | None = None,
    user_instructions: str | None = None,
    enable_citations: bool = True,
) -> str:
    """
    Build the SurfSense system prompt with optional user instructions and citation toggle.

    Args:
        today: Optional datetime for today's date (defaults to current UTC date)
        user_instructions: Optional user instructions to inject into the system prompt
        enable_citations: Whether to include citation instructions in the prompt (default: True)

    Returns:
        Complete system prompt string
    """
    resolved_today = (today or datetime.now(UTC)).astimezone(UTC).date().isoformat()

    # Build user instructions section if provided
    user_section = ""
    if user_instructions and user_instructions.strip():
        user_section = f"""
<user_instructions>
{user_instructions.strip()}
</user_instructions>
"""

    # Include citation instructions only if enabled
    citation_section = (
        f"\n{SURFSENSE_CITATION_INSTRUCTIONS}" if enable_citations else ""
    )

    return f"""
<system_instruction>
You are SurfSense, a reasoning and acting AI agent designed to answer user questions using the user's personal knowledge base.

Today's date (UTC): {resolved_today}

</system_instruction>{user_section}
<tools>
You have access to the following tools:
- search_knowledge_base: Search the user's personal knowledge base for relevant information.
  - Args:
    - query: The search query - be specific and include key terms
    - top_k: Number of results to retrieve (default: 10)
    - start_date: Optional ISO date/datetime (e.g. "2025-12-12" or "2025-12-12T00:00:00+00:00")
    - end_date: Optional ISO date/datetime (e.g. "2025-12-19" or "2025-12-19T23:59:59+00:00")
    - connectors_to_search: Optional list of connector enums to search. If omitted, searches all.
  - Returns: Formatted string with relevant documents and their content
</tools>
<tool_call_examples>
- User: "Fetch all my notes and what's in them?"
  - Call: `search_knowledge_base(query="*", top_k=50, connectors_to_search=["NOTE"])`

- User: "What did I discuss on Slack last week about the React migration?"
  - Call: `search_knowledge_base(query="React migration", connectors_to_search=["SLACK_CONNECTOR"], start_date="YYYY-MM-DD", end_date="YYYY-MM-DD")`
</tool_call_examples>{citation_section}
"""


SURFSENSE_SYSTEM_PROMPT = build_surfsense_system_prompt()


# =============================================================================
# Deep Agent Factory
# =============================================================================


def create_surfsense_deep_agent(
    llm: ChatLiteLLM,
    search_space_id: int,
    db_session: AsyncSession,
    connector_service: ConnectorService,
    user_instructions: str | None = None,
    enable_citations: bool = True,
    additional_tools: Sequence[BaseTool] | None = None,
):
    """
    Create a SurfSense deep agent with knowledge base search capability.

    Args:
        llm: ChatLiteLLM instance
        search_space_id: The user's search space ID
        db_session: Database session
        connector_service: Initialized connector service
        user_instructions: Optional user instructions to inject into the system prompt.
                          These will be added to the system prompt to customize agent behavior.
        enable_citations: Whether to include citation instructions in the system prompt (default: True).
                         When False, the agent will not be instructed to add citations to responses.
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
