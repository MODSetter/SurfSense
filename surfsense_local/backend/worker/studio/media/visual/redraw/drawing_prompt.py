"""The words a picture was drawn from, which a redraw starts from.

Kept as `drawing_prompt` from the first version that keeps it; a picture drawn
before has only its recipe's prompt, or the body Studio wrote under its title.
"""

from typing import Any

from modules.artifacts.drawn_images.recipe import image_drawing_of
from modules.artifacts.models import Artifact
from worker.studio.media.visual.infographic.style import in_infographic_style

KEY = "drawing_prompt"


def kept_drawing_prompt(prompt: str) -> dict[str, Any]:
    return {KEY: prompt}


def changed(prompt: str, instruction: str) -> str:
    """The prompt with one more change, so changes add up from version to version."""
    return f"{prompt}\n\nChange: {instruction}"


def drawing_prompt_of(artifact: Artifact) -> str:
    meta = artifact.artifact_metadata or {}
    kept = meta.get(KEY)
    if isinstance(kept, str) and kept.strip():
        return kept
    drawing = image_drawing_of(meta)
    if drawing is not None:
        # Drawn as the agent wrote it, in Studio's style for an infographic.
        if artifact.format == "infographic":
            return in_infographic_style(drawing.prompt)
        return drawing.prompt
    return _below_title(artifact.document.content or "", artifact.document.title)


def _below_title(body: str, title: str) -> str:
    """Studio's image body is `# <title>` and then the prompt it drew."""
    heading = f"# {title}"
    text = body[len(heading) :] if body.startswith(heading) else body
    return text.strip() or title
