"""A PowerPoint file with no slides, like a template, which Docling refuses for having no pages."""

import re
from pathlib import Path

from modules.agent.previews.office_counts import slide_count

EMU_PER_INCH = 914_400
ASPECTS = {"16:9": 16 / 9, "16:10": 16 / 10, "4:3": 4 / 3}


def describe_slideless_deck(path: Path) -> str | None:
    """Markdown saying it is a template, with its slide size and layout names;
    None for any other file, a deck that does not open included."""
    if path.suffix.lower() != ".pptx" or slide_count(path) != 0:
        return None
    from pptx import Presentation

    try:
        deck = Presentation(str(path))
        if len(deck.slides):
            return None
    except Exception:
        return None  # broken, not empty: Docling's refusal says why

    blocks = ["PowerPoint template with no slides."]
    try:
        blocks += _size(deck.slide_width, deck.slide_height)
        names = [
            # One line each: a break would read as a heading or another layout.
            re.sub(r"\s*[\r\n]\s*", " ", layout.name)
            for master in deck.slide_masters
            for layout in master.slide_layouts
            if layout.name
        ]
    except Exception:  # what it is matters more than the detail
        return blocks[0]
    if names:
        blocks.append("Slide layouts, in order:")
        blocks.append("\n".join(f"- {name}" for name in names))
    return "\n\n".join(blocks)


def _size(width: int | None, height: int | None) -> list[str]:
    if not width or not height:
        return []
    aspect = next(
        (
            f" ({name})"
            for name, ratio in ASPECTS.items()
            if abs(width / height - ratio) < 0.01
        ),
        "",
    )
    return [
        f"Slide size: {width / EMU_PER_INCH:.4g} x {height / EMU_PER_INCH:.4g} in{aspect}."
    ]
