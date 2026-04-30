"""Memory domain agent graph."""

from __future__ import annotations

from collections.abc import Sequence

import app.agents.multi_agent_chat.expert_agent.builtins.memory as memory_pkg
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from app.agents.multi_agent_chat.core.prompts import read_prompt_md
from app.db import ChatVisibility

_PRIVATE_VISIBILITY_POLICY = (
    "This thread is private. Store user-specific long-lived preferences, facts, and instructions."
)
_TEAM_VISIBILITY_POLICY = (
    "This thread is shared with the search space. Store only team-appropriate shared preferences,"
    " facts, and instructions that are safe for all members to inherit."
)


def _render_memory_prompt(thread_visibility: ChatVisibility | None) -> str:
    template = read_prompt_md(memory_pkg.__name__, "domain_prompt")
    policy = (
        _TEAM_VISIBILITY_POLICY
        if thread_visibility == ChatVisibility.SEARCH_SPACE
        else _PRIVATE_VISIBILITY_POLICY
    )
    return template.replace("{{MEMORY_VISIBILITY_POLICY}}", policy)


def build_memory_domain_agent(
    llm: BaseChatModel,
    tools: Sequence[BaseTool],
    *,
    thread_visibility: ChatVisibility | None = None,
):
    """Compiled memory domain-agent graph."""
    return create_agent(
        llm,
        system_prompt=_render_memory_prompt(thread_visibility),
        tools=list(tools),
    )
