"""
Factory for the video deep agent.

Creates a deepagent wired with:
  - The official Remotion system prompt + agent workflow instructions
  - 6 sandbox tools (write_file, read_file, delete_file, list_files, run_tsc, render_video)
  - The official Remotion skill files (remotion-best-practices)
"""

from __future__ import annotations

from deepagents import create_deep_agent
from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.memory import MemorySaver

from app.agents.new_chat.sandbox import _TimeoutAwareSandbox
from app.agents.video.prompts import SYSTEM_PROMPT
from app.agents.video.sandbox import SKILLS_SANDBOX_PATH
from app.agents.video.tools import build_video_tools


async def create_video_deep_agent(
    llm: BaseChatModel,
    sandbox: _TimeoutAwareSandbox,
):
    """Create the video deep agent.

    Uses an in-memory checkpointer — video generation is one-shot per invocation.
    Skills are loaded from the sandbox with progressive disclosure: the agent reads
    SKILL.md and only loads the rule files relevant to the user's request.

    Args:
        llm: The language model to use.
        sandbox: A running Daytona sandbox with skills already uploaded
                 (via get_or_create_video_sandbox).

    Returns:
        CompiledStateGraph: The configured video deep agent.
    """
    tools = build_video_tools(sandbox)

    return create_deep_agent(
        model=llm,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
        checkpointer=MemorySaver(),
        backend=sandbox,
        skills=[SKILLS_SANDBOX_PATH],
    )
