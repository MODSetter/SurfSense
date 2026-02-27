from app.agents.new_chat.tools.video.prompts.remotion import (
    MAX_ATTEMPTS,
    REMOTION_SYSTEM_PROMPT,
    build_error_correction_prompt,
    build_user_prompt,
)
from app.agents.new_chat.tools.video.prompts.skills import (
    SKILL_DETECTION_PROMPT,
    detect_skills,
)

__all__ = [
    "MAX_ATTEMPTS",
    "REMOTION_SYSTEM_PROMPT",
    "SKILL_DETECTION_PROMPT",
    "build_error_correction_prompt",
    "build_user_prompt",
    "detect_skills",
]
