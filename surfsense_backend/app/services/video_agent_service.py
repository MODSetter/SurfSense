"""
Video agent service — deepagent-based video generation.

Orchestrates the full pipeline:
  1. Get or create a Daytona sandbox with Remotion pre-installed
  2. Create the video deepagent
  3. Invoke it with the user's topic + source content
  4. Download the rendered MP4 from the sandbox
  5. Return the local file path for serving

This runs alongside the existing JIT video_service.py.
Switch between them with the use_agent flag in the API.
"""

from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path

from langchain_core.messages import HumanMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.video import create_video_deep_agent, get_or_create_video_sandbox
from app.agents.video.video_deepagent import VideoAgentOutput
from app.services.llm_service import get_video_llm

logger = logging.getLogger(__name__)

_VIDEO_FILES_DIR = Path(os.environ.get("SANDBOX_FILES_DIR", "sandbox_files")) / "video"


def _build_user_prompt(topic: str, source_content: str) -> str:
    return (
        f"Create a professional Remotion video animation about: {topic}\n\n"
        f"Use the following source content as reference:\n\n{source_content}"
    )


async def generate_video_with_agent(
    session: AsyncSession,
    search_space_id: int,
    thread_id: int | str,
    topic: str,
    source_content: str,
) -> str:
    """Generate a video using the deepagent pipeline.

    Args:
        session: Database session for LLM config lookup.
        search_space_id: The user's search space ID.
        thread_id: Conversation thread ID — used to reuse the same sandbox.
        topic: The video topic (passed by the chat agent).
        source_content: The source content to base the video on.

    Returns:
        Local filesystem path to the rendered MP4 file.

    Raises:
        ValueError: If no LLM is configured or the agent fails to produce an MP4.
    """
    llm = await get_video_llm(session, search_space_id)
    if not llm:
        raise ValueError("No LLM configured. Please configure a language model in Settings.")

    # Get or create the Remotion sandbox for this thread
    sandbox = await get_or_create_video_sandbox(thread_id)

    # Create the video deepagent
    agent = await create_video_deep_agent(llm=llm, sandbox=sandbox)

    # Invoke the agent with the user prompt
    user_prompt = _build_user_prompt(topic, source_content)
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}

    logger.info("[video-agent] Invoking agent for topic: '%s'", topic)
    result = await agent.ainvoke(
        {"messages": [HumanMessage(content=user_prompt)]},
        config=config,
    )

    # Extract structured output from the agent
    output = _parse_agent_output(result)
    if output is None:
        raise ValueError("Agent terminated without producing a structured response.")
    if not output.success:
        raise ValueError(f"Video generation failed: {output.error or 'unknown error'}")

    # Download MP4 from sandbox to local storage
    local_path = await _download_mp4(sandbox, output.mp4_sandbox_path, thread_id)
    logger.info("[video-agent] MP4 saved locally: %s", local_path)

    return str(local_path)


def _parse_agent_output(agent_result: dict) -> VideoAgentOutput | None:
    """Extract the structured output from the agent result state."""
    output = agent_result.get("structured_response")
    if isinstance(output, VideoAgentOutput):
        return output
    return None


async def _download_mp4(
    sandbox,
    sandbox_path: str,
    thread_id: int | str,
) -> Path:
    """Download the rendered MP4 from the sandbox to local storage."""
    import asyncio

    def _download() -> bytes:
        return sandbox._sandbox.fs.download_file(sandbox_path)

    raw: bytes = await asyncio.to_thread(_download)

    local_dir = _VIDEO_FILES_DIR / str(thread_id)
    local_dir.mkdir(parents=True, exist_ok=True)
    local_path = local_dir / Path(sandbox_path).name
    local_path.write_bytes(raw)
    return local_path
