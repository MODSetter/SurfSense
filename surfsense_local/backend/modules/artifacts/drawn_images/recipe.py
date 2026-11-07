"""How a picture the agent asked for is made, so Regenerate paints the same prompt."""

from dataclasses import dataclass
from typing import Any

from modules.artifacts.studio_documents.recipe import RECIPE_KEY

IMAGE_DRAWN = "image_drawn"


@dataclass(frozen=True)
class ImageDrawing:
    prompt: str


def image_drawn(prompt: str) -> dict[str, Any]:
    return {"kind": IMAGE_DRAWN, "prompt": prompt}


def image_drawing_of(metadata: dict[str, Any] | None) -> ImageDrawing | None:
    recipe = (metadata or {}).get(RECIPE_KEY)
    if not isinstance(recipe, dict) or recipe.get("kind") != IMAGE_DRAWN:
        return None
    return ImageDrawing(recipe["prompt"])
