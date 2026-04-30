"""Compile the supervisor agent graph (supervisor prompt + caller-supplied routing tools)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import app.agents.multi_agent_chat.supervisor as supervisor_pkg

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.types import Checkpointer

from app.agents.multi_agent_chat.core.prompts import read_prompt_md


def build_supervisor_agent(
    llm: BaseChatModel,
    *,
    tools: Sequence[BaseTool],
    checkpointer: Checkpointer | None = None,
    middleware: Sequence[Any] | None = None,
    context_schema: Any | None = None,
):
    """Compile the supervisor **agent** (graph). ``tools`` = output of ``build_supervisor_routing_tools``."""
    system_prompt = read_prompt_md(supervisor_pkg.__name__, "supervisor_prompt")
    kwargs: dict[str, Any] = {
        "system_prompt": system_prompt,
        "tools": list(tools),
        "checkpointer": checkpointer,
    }
    if middleware is not None:
        kwargs["middleware"] = list(middleware)
    if context_schema is not None:
        kwargs["context_schema"] = context_schema
    agent = create_agent(llm, **kwargs)
    if middleware is not None or context_schema is not None:
        return agent.with_config(
            {
                "recursion_limit": 10_000,
                "metadata": {"ls_integration": "multi_agent_supervisor"},
            }
        )
    return agent
