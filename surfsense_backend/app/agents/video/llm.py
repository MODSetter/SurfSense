"""LLM interaction for the video pipeline.

Handles invoking the LLM, parsing the structured JSON response,
and extracting component metadata from generated code.
"""

from __future__ import annotations

import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.video.constants import (
    COMPONENT_EXPORT_PATTERN,
    DEFAULT_COMPONENT_NAME,
    DEFAULT_COMPOSITION_ID,
    DEFAULT_DURATION_IN_FRAMES,
)

logger = logging.getLogger(__name__)


def build_video_generation_prompt(topic: str, source_content: str) -> str:
    """Build the user prompt that describes what video to generate."""
    return (
        f"Create a professional animated video about: {topic}\n\n"
        f"Source content to visualize:\n\n{source_content}"
    )


async def invoke_video_llm(llm, system_prompt: str, user_prompt: str) -> str:
    """Send system + user messages to the LLM and return the raw text response."""
    response = await llm.ainvoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ],
        reasoning_effort="high",
        drop_params=True,
    )
    response_text = response.content
    if not response_text or not isinstance(response_text, str):
        raise ValueError("LLM returned empty response.")
    return response_text


def parse_llm_response(llm_raw_output: str) -> tuple[list[dict], str, int]:
    """Parse the LLM's JSON output into (component_files, composition_id, duration_in_frames)."""
    stripped_json = llm_raw_output.strip()

    if stripped_json.startswith("```"):
        first_newline = stripped_json.index("\n")
        stripped_json = stripped_json[first_newline + 1:]
    if stripped_json.endswith("```"):
        stripped_json = stripped_json[: stripped_json.rfind("```")]
    stripped_json = stripped_json.strip()

    try:
        parsed_output = json.loads(stripped_json)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"LLM did not return valid JSON. First 500 chars: {stripped_json[:500]}"
        ) from exc

    component_files = parsed_output.get("files")
    if not component_files or not isinstance(component_files, list):
        raise ValueError("LLM output missing 'files' array.")

    composition_id = parsed_output.get("composition_id", DEFAULT_COMPOSITION_ID)
    duration_in_frames = parsed_output.get("duration_in_frames", DEFAULT_DURATION_IN_FRAMES)

    for file_entry in component_files:
        if "path" not in file_entry or "content" not in file_entry:
            raise ValueError(
                f"File entry missing 'path' or 'content': {file_entry.get('path', '?')}"
            )

    return component_files, composition_id, duration_in_frames


def extract_component_name(component_code: str) -> str:
    """Extract the exported component name (e.g. 'MyComp') from generated TSX code."""
    match = COMPONENT_EXPORT_PATTERN.search(component_code)
    return match.group(1) if match else DEFAULT_COMPONENT_NAME
