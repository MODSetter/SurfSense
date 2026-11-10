"""How a picture the agent asked for is made, so Regenerate paints the same prompt,
at the same shape, from the same reference pictures."""

from dataclasses import dataclass
from typing import Any, cast

from modules.artifacts.studio_documents.recipe import RECIPE_KEY
from modules.llm.providers.picture_shape import SHAPES, Shape

IMAGE_DRAWN = "image_drawn"


@dataclass(frozen=True)
class ImageDrawing:
    prompt: str
    shape: Shape | None = None
    # Artifact ids of the pictures it keeps the characters and style of.
    references: tuple[int, ...] = ()


def image_drawn(
    prompt: str, shape: Shape | None = None, references: tuple[int, ...] = ()
) -> dict[str, Any]:
    recipe: dict[str, Any] = {"kind": IMAGE_DRAWN, "prompt": prompt}
    if shape is not None:
        recipe["shape"] = shape
    if references:
        recipe["references"] = list(references)
    return recipe


def image_drawing_of(metadata: dict[str, Any] | None) -> ImageDrawing | None:
    recipe = (metadata or {}).get(RECIPE_KEY)
    if not isinstance(recipe, dict) or recipe.get("kind") != IMAGE_DRAWN:
        return None
    shape = recipe.get("shape")
    return ImageDrawing(
        recipe["prompt"],
        cast(Shape, shape) if shape in SHAPES else None,
        tuple(int(i) for i in recipe.get("references") or ()),
    )
