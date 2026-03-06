"""Pydantic models equivalent to the Remotion Zod VideoInput schema.

Designed for LLM structured output — every field carries a description
so the LLM understands what to produce. Array-length constraints are
expressed in descriptions (not Field validators) for provider compatibility.
"""

from __future__ import annotations

from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


# ─── Intro ───────────────────────────────────────────────────────────────────


class IntroSceneInput(BaseModel):
    type: Literal["intro"]
    title: str = Field(description="Main title displayed in the intro scene.")
    subtitle: Optional[str] = Field(
        None, description="Optional subtitle shown below the title."
    )


# ─── Spotlight card items (discriminated on "category") ──────────────────────


class StatItem(BaseModel):
    """A stat/metric card showing a key value."""

    category: Literal["stat"]
    title: str = Field(description="Label for the statistic.")
    value: str = Field(description="The stat value as a string (e.g. '42%', '$1.2M').")
    desc: Optional[str] = Field(None, description="Optional short description.")
    color: str = Field(description="Hex color for the card accent (e.g. '#3b82f6').")


class InfoItem(BaseModel):
    """An information card with a title and description."""

    category: Literal["info"]
    title: str = Field(description="Card heading.")
    subtitle: Optional[str] = Field(None, description="Optional card subtitle.")
    desc: str = Field(description="Body text for the card.")
    tag: Optional[str] = Field(None, description="Optional tag/badge label.")
    color: str = Field(description="Hex accent color.")


class QuoteItem(BaseModel):
    """A quote card."""

    category: Literal["quote"]
    quote: str = Field(description="The quote text.")
    author: str = Field(description="Who said or wrote the quote.")
    role: Optional[str] = Field(None, description="Author's role or title.")
    color: str = Field(description="Hex accent color.")


class ProfileItem(BaseModel):
    """A person/profile card."""

    category: Literal["profile"]
    name: str = Field(description="Person's name.")
    role: str = Field(description="Person's role or title.")
    desc: Optional[str] = Field(None, description="Optional short bio.")
    tag: Optional[str] = Field(None, description="Optional tag/badge.")
    color: str = Field(description="Hex accent color.")


class ProgressItem(BaseModel):
    """A progress/metric card with a numeric value."""

    category: Literal["progress"]
    title: str = Field(description="Label for the progress metric.")
    value: float = Field(description="Current progress value.")
    max: Optional[float] = Field(
        None, description="Maximum value for the progress bar. Defaults to 100 if omitted."
    )
    desc: Optional[str] = Field(None, description="Optional description.")
    color: str = Field(description="Hex accent color.")


class FactItem(BaseModel):
    """A fact/statement card."""

    category: Literal["fact"]
    statement: str = Field(description="The fact or statement text.")
    source: Optional[str] = Field(None, description="Optional source attribution.")
    color: str = Field(description="Hex accent color.")


class DefinitionItem(BaseModel):
    """A term + definition card."""

    category: Literal["definition"]
    term: str = Field(description="The term being defined.")
    definition: str = Field(description="The definition text.")
    example: Optional[str] = Field(None, description="Optional usage example.")
    color: str = Field(description="Hex accent color.")


CardItem = Annotated[
    Union[
        StatItem,
        InfoItem,
        QuoteItem,
        ProfileItem,
        ProgressItem,
        FactItem,
        DefinitionItem,
    ],
    Field(discriminator="category"),
]


class SpotlightSceneInput(BaseModel):
    """A spotlight scene showing 1–8 cards of mixed types."""

    type: Literal["spotlight"]
    items: list[CardItem] = Field(
        description="Array of spotlight cards (1 to 8 items). Each card has a 'category' discriminator."
    )


# ─── Hierarchy (recursive tree) ─────────────────────────────────────────────


class HierarchyNode(BaseModel):
    """A node in a hierarchy tree. Can contain nested children."""

    label: str = Field(description="Display label for this node.")
    color: Optional[str] = Field(None, description="Optional hex color.")
    desc: Optional[str] = Field(None, description="Optional description.")
    children: Optional[list[HierarchyNode]] = Field(
        None, description="Optional child nodes forming the subtree."
    )


class HierarchySceneInput(BaseModel):
    """A hierarchy/tree scene with at least one root node."""

    type: Literal["hierarchy"]
    title: Optional[str] = Field(None, description="Optional scene title.")
    items: list[HierarchyNode] = Field(
        description="Root-level hierarchy nodes (at least 1)."
    )


# ─── List ────────────────────────────────────────────────────────────────────


class ListItem(BaseModel):
    """A single list entry."""

    label: str = Field(description="Primary label text.")
    desc: Optional[str] = Field(None, description="Optional description.")
    value: Optional[Union[str, float]] = Field(
        None, description="Optional value — can be text or a number."
    )
    color: Optional[str] = Field(None, description="Optional hex color.")


class ListSceneInput(BaseModel):
    """A list scene showing items in order (at least 1 item)."""

    type: Literal["list"]
    title: Optional[str] = Field(None, description="Optional scene title.")
    subtitle: Optional[str] = Field(None, description="Optional scene subtitle.")
    items: list[ListItem] = Field(description="The list entries (at least 1).")


# ─── Sequence ────────────────────────────────────────────────────────────────


class SequenceItem(BaseModel):
    """A single step in a sequence/flow."""

    label: str = Field(description="Step label.")
    desc: Optional[str] = Field(None, description="Optional step description.")
    color: Optional[str] = Field(None, description="Optional hex color.")


class SequenceSceneInput(BaseModel):
    """A sequence/flow scene showing ordered steps (at least 1)."""

    type: Literal["sequence"]
    title: Optional[str] = Field(None, description="Optional scene title.")
    subtitle: Optional[str] = Field(None, description="Optional scene subtitle.")
    items: list[SequenceItem] = Field(
        description="The sequence steps (at least 1)."
    )


# ─── Chart ───────────────────────────────────────────────────────────────────


class ChartItem(BaseModel):
    """A single data point in a chart."""

    label: str = Field(description="Data point label (e.g. month name, category).")
    value: float = Field(description="Numeric value for this data point.")
    color: Optional[str] = Field(None, description="Optional hex color for this bar/segment.")


class ChartSceneInput(BaseModel):
    """A chart scene (bar, line, or donut) with at least 1 data point."""

    type: Literal["chart"]
    title: Optional[str] = Field(None, description="Optional chart title.")
    subtitle: Optional[str] = Field(None, description="Optional chart subtitle.")
    xTitle: Optional[str] = Field(None, description="Optional X-axis label.")
    yTitle: Optional[str] = Field(None, description="Optional Y-axis label.")
    items: list[ChartItem] = Field(
        description="Data points for the chart (at least 1)."
    )


# ─── Relation ────────────────────────────────────────────────────────────────


class RelationNode(BaseModel):
    """A node in a relation/network graph."""

    id: str = Field(description="Unique identifier for this node (referenced by edges).")
    label: str = Field(description="Display label.")
    desc: Optional[str] = Field(None, description="Optional description.")
    color: Optional[str] = Field(None, description="Optional hex color.")


class RelationEdge(BaseModel):
    """A directed edge between two relation nodes."""

    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(
        alias="from",
        description="ID of the source node.",
    )
    to: str = Field(description="ID of the target node.")
    label: Optional[str] = Field(None, description="Optional edge label.")


class RelationSceneInput(BaseModel):
    """A relation/network graph scene with nodes and optional edges."""

    type: Literal["relation"]
    title: Optional[str] = Field(None, description="Optional scene title.")
    subtitle: Optional[str] = Field(None, description="Optional scene subtitle.")
    nodes: list[RelationNode] = Field(
        description="Graph nodes (at least 1)."
    )
    edges: list[RelationEdge] = Field(
        default_factory=list,
        description="Directed edges between nodes. Can be empty.",
    )


# ─── Comparison ──────────────────────────────────────────────────────────────


class CompareItem(BaseModel):
    """A single item within a comparison group."""

    label: str = Field(description="Item label.")
    desc: Optional[str] = Field(None, description="Optional description.")


class CompareGroup(BaseModel):
    """A group/column in a comparison (e.g. 'Pros' vs 'Cons')."""

    label: str = Field(description="Group heading.")
    color: Optional[str] = Field(None, description="Optional hex accent color.")
    items: list[CompareItem] = Field(
        description="Items in this group (at least 1)."
    )


class ComparisonSceneInput(BaseModel):
    """A comparison scene with at least 2 groups side by side."""

    type: Literal["comparison"]
    title: Optional[str] = Field(None, description="Optional scene title.")
    subtitle: Optional[str] = Field(None, description="Optional scene subtitle.")
    groups: list[CompareGroup] = Field(
        description="The comparison groups (at least 2)."
    )


# ─── Outro ───────────────────────────────────────────────────────────────────


class OutroSceneInput(BaseModel):
    """Closing scene of the video."""

    type: Literal["outro"]
    title: Optional[str] = Field(None, description="Optional closing title.")
    subtitle: Optional[str] = Field(None, description="Optional closing subtitle.")


# ─── Top-level (discriminated on "type") ─────────────────────────────────────

SceneInput = Annotated[
    Union[
        IntroSceneInput,
        SpotlightSceneInput,
        HierarchySceneInput,
        ListSceneInput,
        SequenceSceneInput,
        ChartSceneInput,
        RelationSceneInput,
        ComparisonSceneInput,
        OutroSceneInput,
    ],
    Field(discriminator="type"),
]


class VideoInput(BaseModel):
    """Complete video input — a sequence of scenes to render.

    The scenes array must contain at least one scene. Typically starts
    with an 'intro' scene and ends with an 'outro' scene, with content
    scenes in between.
    """

    scenes: list[SceneInput] = Field(
        description=(
            "Ordered list of scenes to render in the video (at least 1). "
            "Each scene has a 'type' discriminator that determines its structure. "
            "Available types: intro, spotlight, hierarchy, list, sequence, chart, relation, comparison, outro."
        ),
    )


# -- Request / Response models for API endpoints ---------------------------


class GenerateScriptRequest(BaseModel):
    """Request body for POST /video/generate-script."""

    topic: str = Field(description="Short title for the video.")
    source_content: str = Field(description="Structured content to turn into video scenes.")
