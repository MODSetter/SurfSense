"""Trusted visual-style catalog for infographic generation."""

from __future__ import annotations

import re

from .schemas import ResolvedVisualStyle, VisualStylePreset

QUESTION_PRESET_ID = "infographic.visual-style"
QUESTION_PRESET_VERSION = 1
AUTO_STYLE_ID = "auto"
DEFAULT_STYLE_ID = "sketch-note"

KAWAII = VisualStylePreset(
    id="kawaii",
    version=1,
    label="Kawaii",
    preview_asset="infographic-style/kawaii",
    description=(
        "Use a playful kawaii illustration style with rounded shapes, pastel "
        "colors, thick clean outlines, friendly expressive icons, generous "
        "spacing, and highly legible infographic labels."
    ),
)

CLAY = VisualStylePreset(
    id="clay",
    version=1,
    label="Clay",
    preview_asset="infographic-style/clay",
    description=(
        "Use a tactile three-dimensional clay style with softly modeled forms, "
        "rounded edges, subtle handmade texture, gentle studio lighting, clear "
        "visual grouping, and highly legible infographic labels."
    ),
)

SKETCH_NOTE = VisualStylePreset(
    id="sketch-note",
    version=1,
    label="Sketch Note",
    preview_asset="infographic-style/sketch-note",
    description=(
        "Use a hand-drawn editorial sketchnote style with mostly black ink on "
        "a warm white background, one restrained accent color, simple icons, "
        "arrows, connectors, loose organic lines, generous whitespace, short "
        "hand-lettered headings, and highly legible labels. Avoid photorealism, "
        "dense paragraphs, decorative illegible handwriting, and watermarks."
    ),
)

ANIME = VisualStylePreset(
    id="anime",
    version=1,
    label="Anime",
    preview_asset="infographic-style/anime",
    description=(
        "Use a polished anime-inspired cel-shaded style with expressive "
        "characters or icons, clean linework, vivid controlled color, energetic "
        "composition, clear section hierarchy, and highly legible infographic "
        "labels."
    ),
)

VISUAL_STYLE_PRESETS: tuple[VisualStylePreset, ...] = (
    KAWAII,
    CLAY,
    SKETCH_NOTE,
    ANIME,
)
VISUAL_STYLE_BY_ID = {preset.id: preset for preset in VISUAL_STYLE_PRESETS}

_AUTO_RULES: tuple[tuple[frozenset[str], str], ...] = (
    (
        frozenset({"playful", "children", "child", "beginner", "friendly", "cute"}),
        KAWAII.id,
    ),
    (
        frozenset({"tactile", "product", "craft", "object", "physical", "handmade"}),
        CLAY.id,
    ),
    (
        frozenset({"study", "notes", "brainstorming", "teaching", "concept", "explain"}),
        SKETCH_NOTE.id,
    ),
    (
        frozenset({"entertainment", "gaming", "game", "manga", "dynamic"}),
        ANIME.id,
    ),
)
_WORD_PATTERN = re.compile(r"[a-z0-9]+")


def get_visual_style(style_id: str) -> VisualStylePreset:
    """Return a concrete style or reject unknown and selector-only IDs."""
    try:
        return VISUAL_STYLE_BY_ID[style_id]
    except KeyError:
        raise ValueError(f"Unknown infographic visual style: {style_id}") from None


def resolve_visual_style(requested_id: str, brief: str) -> ResolvedVisualStyle:
    """Resolve ``auto`` deterministically; explicit concrete IDs pass through."""
    if requested_id != AUTO_STYLE_ID:
        return ResolvedVisualStyle(
            requested_id=requested_id,
            preset=get_visual_style(requested_id),
        )

    words = frozenset(_WORD_PATTERN.findall(brief.casefold()))
    resolved_id = next(
        (style_id for signals, style_id in _AUTO_RULES if words & signals),
        DEFAULT_STYLE_ID,
    )
    return ResolvedVisualStyle(
        requested_id=AUTO_STYLE_ID,
        preset=VISUAL_STYLE_BY_ID[resolved_id],
    )


__all__ = [
    "ANIME",
    "AUTO_STYLE_ID",
    "CLAY",
    "DEFAULT_STYLE_ID",
    "KAWAII",
    "QUESTION_PRESET_ID",
    "QUESTION_PRESET_VERSION",
    "SKETCH_NOTE",
    "VISUAL_STYLE_BY_ID",
    "VISUAL_STYLE_PRESETS",
    "get_visual_style",
    "resolve_visual_style",
]
