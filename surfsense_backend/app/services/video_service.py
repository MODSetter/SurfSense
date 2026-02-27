import logging

from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.new_chat.tools.video.prompts import (
    REMOTION_SYSTEM_PROMPT,
    build_error_correction_prompt,
    build_user_prompt,
    detect_skills,
)
from app.agents.new_chat.tools.video.skills import get_combined_skill_content
from app.services.llm_service import get_video_llm
from app.utils.content_utils import strip_code_fences

logger = logging.getLogger(__name__)


async def generate_video_code(
    session: AsyncSession,
    search_space_id: int,
    topic: str,
    source_content: str,
    attempt: int,
    error: str | None,
) -> str:
    """Generate a Remotion React component for the given topic and source content.

    Mirrors the official Remotion template flow:
      1. Classify the prompt to detect which skill docs apply (e.g. transitions, charts).
      2. Inject matching skill docs into the system prompt so the LLM has precise API guidance.
      3. Call the LLM once to produce the component code.

    On retry attempts the error context replaces the normal user prompt so the LLM
    can self-correct without changing anything else.
    """
    llm = await get_video_llm(session, search_space_id)
    if not llm:
        raise ValueError("No LLM configured. Please configure a language model in Settings.")

    # Step 1 — skill detection: one fast LLM call to classify the prompt.
    detected_skills = await detect_skills(llm, topic)
    skill_content = get_combined_skill_content(detected_skills)

    # Step 2 — build enhanced system prompt by appending relevant skill docs.
    system_prompt = (
        f"{REMOTION_SYSTEM_PROMPT}\n\n## SKILL-SPECIFIC GUIDANCE\n{skill_content}"
        if skill_content
        else REMOTION_SYSTEM_PROMPT
    )

    if detected_skills:
        logger.info(
            "[video] Detected skills for '%s': %s", topic, ", ".join(detected_skills)
        )

    # Step 3 — build user message: normal on first attempt, error-correction on retries.
    user_content = (
        build_error_correction_prompt(topic, source_content, error, attempt)
        if error and attempt > 1
        else build_user_prompt(topic, source_content)
    )

    response = await llm.ainvoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_content),
        ]
    )

    raw = response.content
    if not raw or not isinstance(raw, str):
        raise ValueError("LLM returned empty content.")

    code = strip_code_fences(raw)
    if not code:
        raise ValueError("Could not extract component code from LLM response.")

    logger.info(
        "[video] Generated component for '%s' attempt=%d (%d chars)",
        topic,
        attempt,
        len(code),
    )

    return code
