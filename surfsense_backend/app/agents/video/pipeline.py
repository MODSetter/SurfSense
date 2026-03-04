"""One-shot video generation pipeline.

Flow: load skills -> LLM call -> write files -> tsc -> render -> download MP4.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.video.constants import (
    MAX_TYPESCRIPT_FIX_ATTEMPTS,
    REMOTION_SKILLS_DIR,
)
from app.agents.video.llm import (
    build_video_generation_prompt,
    invoke_video_llm,
    parse_llm_response,
)
from app.agents.video.prompts_v2 import (
    ERROR_CORRECTION_PROMPT,
    SYSTEM_PROMPT,
)
from app.agents.video.renderer import (
    download_rendered_video,
    render_composition_to_mp4,
    upload_component_files,
    upload_remotion_root_config,
    validate_typescript,
)
from app.agents.video.sandbox import delete_sandbox, get_or_create_sandbox
from app.services.llm_service import get_video_llm

logger = logging.getLogger(__name__)


def _load_remotion_skills() -> str:
    """Read V2 example skill files and concatenate them."""
    V2_FILES = [
        "example-concept-explainer.md",
        "example-architecture-diagram.md",
        "example-data-presentation.md",
    ]
    skill_parts = []
    for name in V2_FILES:
        md_file = REMOTION_SKILLS_DIR / name
        if md_file.exists():
            content = md_file.read_text(encoding="utf-8").strip()
            if content:
                skill_parts.append(content)
    logger.info("[video/pipeline] Loaded %d Remotion skill files", len(skill_parts))
    return "\n\n---\n\n".join(skill_parts)


async def generate_video(
    session: AsyncSession,
    search_space_id: int,
    thread_id: int | str,
    topic: str,
    source_content: str,
) -> str:
    """Generate a video end-to-end. Returns the local filesystem path to the rendered MP4."""
    llm = await get_video_llm(session, search_space_id)
    if not llm:
        raise ValueError("No LLM configured. Please configure a language model in Settings.")

    sandbox = await get_or_create_sandbox(thread_id)

    try:
        return await _run_pipeline(sandbox, llm, thread_id, topic, source_content)
    finally:
        await delete_sandbox(thread_id)


async def _run_pipeline(sandbox, llm, thread_id, topic, source_content) -> str:
    """Run the generation pipeline inside the sandbox."""
    skills_text = _load_remotion_skills()
    system_prompt = SYSTEM_PROMPT
    if skills_text:
        system_prompt += (
            "\n\n═══════════════════════════════════════════════════════════════════════════════\n"
            "REMOTION REFERENCE GUIDE\n"
            "═══════════════════════════════════════════════════════════════════════════════\n\n"
            + skills_text
        )

    user_prompt = build_video_generation_prompt(topic, source_content)
    logger.info("[video/pipeline] Generating component for: '%s'", topic)

    llm_raw_response = await invoke_video_llm(llm, system_prompt, user_prompt)
    component_files, composition_id, duration_in_frames = parse_llm_response(llm_raw_response)

    await upload_component_files(sandbox, component_files)
    await upload_remotion_root_config(sandbox, component_files, composition_id, duration_in_frames)

    typescript_errors = await validate_typescript(sandbox)

    if typescript_errors and MAX_TYPESCRIPT_FIX_ATTEMPTS > 0:
        logger.warning("[video/pipeline] TypeScript errors found, attempting LLM fix...")
        error_correction_prompt = ERROR_CORRECTION_PROMPT.format(
            errors=typescript_errors[:3000],
            code=component_files[0]["content"][:8000],
            composition_id=composition_id,
            duration_in_frames=duration_in_frames,
        )
        corrected_response = await invoke_video_llm(llm, system_prompt, error_correction_prompt)
        component_files, composition_id, duration_in_frames = parse_llm_response(corrected_response)

        await upload_component_files(sandbox, component_files)
        await upload_remotion_root_config(sandbox, component_files, composition_id, duration_in_frames)
        typescript_errors = await validate_typescript(sandbox)

    if typescript_errors:
        raise ValueError(f"TypeScript validation failed after retries:\n{typescript_errors[:1000]}")

    rendered_video_path = await render_composition_to_mp4(sandbox, composition_id)
    downloaded_video_path = await download_rendered_video(sandbox, rendered_video_path, thread_id)
    logger.info("[video/pipeline] Video saved to: %s", downloaded_video_path)
    return str(downloaded_video_path)
