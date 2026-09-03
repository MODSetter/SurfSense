"""Infographic preset and prompt contracts."""

from .presets import (
    AUTO_STYLE_ID,
    QUESTION_PRESET_ID,
    QUESTION_PRESET_VERSION,
    VISUAL_STYLE_PRESETS,
    get_visual_style,
    resolve_visual_style,
)
from .prompt import assemble_infographic_prompt
from .schemas import ResolvedVisualStyle, VisualStylePreset

__all__ = [
    "AUTO_STYLE_ID",
    "QUESTION_PRESET_ID",
    "QUESTION_PRESET_VERSION",
    "VISUAL_STYLE_PRESETS",
    "ResolvedVisualStyle",
    "VisualStylePreset",
    "assemble_infographic_prompt",
    "get_visual_style",
    "resolve_visual_style",
]
