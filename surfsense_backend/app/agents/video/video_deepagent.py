"""
Factory for the video deep agent.

Creates a deepagent wired with:
  - The official Remotion system prompt + agent workflow instructions
  - 6 sandbox tools (write_file, read_file, delete_file, list_files, run_tsc, render_video)
  - The official Remotion skill files (remotion-best-practices)
"""

from __future__ import annotations

from deepagents import create_deep_agent
from langchain.agents.structured_output import AutoStrategy
from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel, Field

from app.agents.new_chat.sandbox import _TimeoutAwareSandbox
from app.agents.video.prompts import SYSTEM_PROMPT
from app.agents.video.sandbox import SKILLS_SANDBOX_PATH
from app.agents.video.tools import build_video_tools


class VideoAgentOutput(BaseModel):
    """Structured output always returned by the video deep agent, success or failure.

    On success: success=True, mp4_sandbox_path and composition_id are set, error is None.
    On failure: success=False, error describes what went wrong, mp4_sandbox_path is None.
    """

    success: bool = Field(
        description="True if the video was rendered successfully, False otherwise."
    )
    mp4_sandbox_path: str | None = Field(
        default=None,
        description="Absolute path inside the sandbox to the rendered MP4 file. "
                    "Set only when success is True.",
    )
    composition_id: str | None = Field(
        default=None,
        description="The Remotion composition ID that was rendered. "
                    "Set only when success is True.",
    )
    error: str | None = Field(
        default=None,
        description="Human-readable error message explaining why generation failed. "
                    "Set only when success is False.",
    )


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
        response_format=AutoStrategy(VideoAgentOutput),
    )
