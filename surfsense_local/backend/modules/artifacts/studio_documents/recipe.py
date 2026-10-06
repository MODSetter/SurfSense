"""How a version's spec is made, so Regenerate repeats it rather than the spec.

Studio drafts from the sources or refines another version, and asks a model
either way; the agent's script document has no recipe: its spec is its source.
"""

from dataclasses import dataclass
from typing import Any

from modules.artifacts.made_file import made_by
from modules.artifacts.script_documents.spec import (
    DocumentSpec,
    SpecKind,
    spec_from_metadata,
    spec_kind,
)

RECIPE_KEY = "recipe"
DRAFT = "draft"
REFINE = "refine"


@dataclass(frozen=True)
class Refinement:
    """Rewrite `base` as `instruction` asks, in one model call."""

    instruction: str
    base: DocumentSpec


def drafted() -> dict[str, Any]:
    return {"kind": DRAFT}


def refined(instruction: str, base: DocumentSpec) -> dict[str, Any]:
    return {"kind": REFINE, "instruction": instruction, "base": base.as_metadata()}


def refinement(metadata: dict[str, Any] | None) -> Refinement | None:
    recipe = (metadata or {}).get(RECIPE_KEY)
    if not isinstance(recipe, dict) or recipe.get("kind") != REFINE:
        return None
    return Refinement(recipe["instruction"], spec_from_metadata(recipe["base"]))


def figure_sources(metadata: dict[str, Any] | None) -> list[int]:
    """The sources whose figures a refine may place: those its draft was grounded on."""
    meta = metadata or {}
    grounded = meta.get("grounded_document_ids")
    return list(
        grounded if grounded is not None else meta.get("source_document_ids") or []
    )


def studio_made(metadata: dict[str, Any] | None) -> bool:
    """Whether Studio drafted or refined this version; the agent's scripts keep no recipe."""
    return RECIPE_KEY in (metadata or {})


def renders_as_stored(metadata: dict[str, Any] | None) -> bool:
    """Whether the job asks no model: the agent's scripts, and files a tool made."""
    if made_by(metadata) is not None:
        return True
    return spec_kind(metadata) is not None and not studio_made(metadata)


def shown_spec_kind(metadata: dict[str, Any] | None) -> SpecKind | None:
    """The kind a version has, or will have once its pending refine is written."""
    found = refinement(metadata)
    return spec_kind(metadata) or (found.base.kind if found else None)
