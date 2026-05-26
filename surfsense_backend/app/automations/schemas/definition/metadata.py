"""``MetadataBlock`` — the ``metadata`` section of the automation definition."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class MetadataBlock(BaseModel):
    """Free-form metadata attached to the automation definition.

    Unlike the rest of the envelope this block tolerates unknown keys
    (``extra='allow'``) — it's a deliberate extension point for
    UI annotations, NL-generator breadcrumbs, custom tags, etc.

    Two fields are first-class so the rest of the system can rely on
    them without reaching into the loose extras:

    ``tags`` — used by the UI for filtering and grouping.
    ``created_from_nl`` — set by the NL generator so we can later
    measure how many runs came from natural-language authoring.
    """

    model_config = ConfigDict(extra="allow")

    tags: list[str] = Field(
        default_factory=list,
        description="UI-facing tags. No semantic meaning to the engine.",
    )
    created_from_nl: bool = Field(
        default=False,
        description=(
            "True when the definition was produced by the NL "
            "generator (set automatically by the generator path; "
            "human-authored definitions keep this false)."
        ),
    )
