"""Compile a domain agent graph from a co-located prompt + tool list."""

from __future__ import annotations

from collections.abc import Sequence

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from app.agents.multi_agent_chat.shared.prompt_loader import read_prompt_md


def build_domain_agent(
    llm: BaseChatModel,
    tools: Sequence[BaseTool],
    *,
    prompt_package: str,
    prompt_stem: str = "domain_prompt",
):
    """``create_agent`` + ``{prompt_stem}.md`` loaded from ``prompt_package``."""
    system_prompt = read_prompt_md(prompt_package, prompt_stem)
    return create_agent(
        llm,
        system_prompt=system_prompt,
        tools=list(tools),
    )
