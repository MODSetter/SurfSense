"""How an edited version is made, so Regenerate repeats the edit on the same base.

The recipe names the base rather than copying its bytes: deleting the document
deletes every version, so the base cannot go while a later version names it.
"""

from dataclasses import dataclass
from typing import Any

from modules.artifacts.studio_documents.recipe import RECIPE_KEY

IMAGE_EDIT = "image_edit"


@dataclass(frozen=True)
class ImageEdit:
    instruction: str
    base_artifact_id: int


def image_edited(instruction: str, base_artifact_id: int) -> dict[str, Any]:
    return {
        "kind": IMAGE_EDIT,
        "instruction": instruction,
        "base_artifact_id": base_artifact_id,
    }


def image_edit_of(metadata: dict[str, Any] | None) -> ImageEdit | None:
    recipe = (metadata or {}).get(RECIPE_KEY)
    if not isinstance(recipe, dict) or recipe.get("kind") != IMAGE_EDIT:
        return None
    return ImageEdit(recipe["instruction"], recipe["base_artifact_id"])
