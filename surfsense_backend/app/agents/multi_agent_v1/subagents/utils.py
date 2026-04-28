"""Shared helpers for multi-agent v1 subagents."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.new_chat.llm_config import (
    create_chat_litellm_from_agent_config,
    load_agent_config,
)


async def load_llm_for_request(
    *,
    session: AsyncSession,
    llm_config_id: int,
    search_space_id: int,
) -> Any | None:
    """Load the configured chat model for a subagent run."""
    agent_config = await load_agent_config(
        session=session,
        config_id=llm_config_id,
        search_space_id=search_space_id,
    )
    if agent_config is None:
        return None
    return create_chat_litellm_from_agent_config(agent_config)


def build_subagent_input_state(
    *,
    goal: str,
    stream_kwargs: dict[str, Any],
) -> dict[str, Any]:
    """Build the initial state payload passed to a subagent."""
    return {
        "messages": [HumanMessage(content=goal)],
        "search_space_id": stream_kwargs["search_space_id"],
        "request_id": read_optional_nonempty_string(
            stream_kwargs, "request_id", "unknown"
        ),
        "turn_id": f"subagent:{read_optional_integer(stream_kwargs, 'chat_id') or 'unknown'}",
        "architecture_mode": "multi_agent_v1_subagent",
    }


def build_subagent_run_config(
    *,
    stream_kwargs: dict[str, Any],
    scope: str,
) -> dict[str, Any]:
    """Build runnable config with a scope-specific thread id."""
    return {
        "configurable": {
            "thread_id": build_subagent_thread_id(stream_kwargs=stream_kwargs, scope=scope),
            "request_id": read_optional_nonempty_string(
                stream_kwargs, "request_id", "unknown"
            ),
            "turn_id": f"subagent:{read_optional_integer(stream_kwargs, 'chat_id') or 'unknown'}",
            "architecture_mode": "multi_agent_v1_subagent",
        },
        "recursion_limit": 40,
    }


def build_subagent_error_result(error_class: str) -> dict[str, Any]:
    """Build a standardized error result payload for subagents."""
    return {
        "status": "error",
        "summary": "",
        "evidence": [],
        "artifacts": [],
        "needs_human": False,
        "error_class": error_class,
    }


def extract_final_ai_message_text_from_state(state: Any) -> str:
    """Return the latest AI message text from an agent state payload."""
    if not isinstance(state, dict):
        return ""
    messages = state.get("messages")
    if not isinstance(messages, Sequence):
        return ""
    for message in reversed(messages):
        if isinstance(message, AIMessage):
            return extract_plain_text_from_message_content(message).strip()
    return ""


def extract_plain_text_from_message_content(message: BaseMessage) -> str:
    """Flatten a LangChain message content payload into plain text."""
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
        return "\n".join(part for part in parts if part)
    return str(content)


def build_disabled_tools_list(disabled_tools: Any) -> list[str]:
    """Normalize disabled tools input to a list of tool names."""
    if not isinstance(disabled_tools, list):
        return []
    return [tool_name for tool_name in disabled_tools if isinstance(tool_name, str)]


def read_optional_nonempty_string(
    payload: dict[str, Any],
    key: str,
    default: str | None = None,
) -> str | None:
    """Read a non-empty string from payload, otherwise return default."""
    value = payload.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return default


def read_optional_integer(payload: dict[str, Any], key: str) -> int | None:
    """Read an integer from payload when present and valid."""
    value = payload.get(key)
    if isinstance(value, int):
        return value
    return None


def build_subagent_thread_id(*, stream_kwargs: dict[str, Any], scope: str) -> str:
    """Build a stable thread id for a scope-specific subagent run."""
    chat_id = read_optional_integer(stream_kwargs, "chat_id")
    if chat_id is None:
        return "ma-subagent:unknown"
    return f"ma-subagent:{chat_id}:{scope}"
