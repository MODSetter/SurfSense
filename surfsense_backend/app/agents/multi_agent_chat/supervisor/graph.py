"""Compile the supervisor agent graph (supervisor prompt + caller-supplied routing tools)."""

from __future__ import annotations

from collections.abc import Sequence

import app.agents.multi_agent_chat.supervisor as supervisor_pkg

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.types import Checkpointer

from app.agents.multi_agent_chat.shared.prompt_loader import read_prompt_md


def build_supervisor_agent(
    llm: BaseChatModel,
    *,
    tools: Sequence[BaseTool],
    checkpointer: Checkpointer | None = None,
):
    """Compile the supervisor **agent** (graph). ``tools`` = output of ``build_supervisor_routing_tools``."""
    system_prompt = read_prompt_md(supervisor_pkg.__name__, "supervisor_prompt")
    return create_agent(
        llm,
        system_prompt=system_prompt,
        tools=list(tools),
        checkpointer=checkpointer,
    )
