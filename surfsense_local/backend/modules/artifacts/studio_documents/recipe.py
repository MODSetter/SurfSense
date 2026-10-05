"""How a version's spec is made, so Regenerate repeats it rather than the spec.

Studio drafts from the sources or refines another version, and asks a model
either way; the agent's script document has no recipe: its spec is its source.
"""

from dataclasses import dataclass
from typing import Any

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


def renders_as_stored(metadata: dict[str, Any] | None) -> bool:
    """Whether the job runs the stored spec and asks no model: the agent's scripts."""
    return spec_kind(metadata) is not None and RECIPE_KEY not in (metadata or {})


def shown_spec_kind(metadata: dict[str, Any] | None) -> SpecKind | None:
    """The kind a version has, or will have once its pending refine is written."""
    found = refinement(metadata)
    return spec_kind(metadata) or (found.base.kind if found else None)
