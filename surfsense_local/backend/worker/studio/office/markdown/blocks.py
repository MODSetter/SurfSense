"""The document a Markdown spec describes, as both builders walk it."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Span:
    """A run of text with one set of marks."""

    text: str
    bold: bool = False
    italic: bool = False
    code: bool = False
    strike: bool = False
    href: str | None = None


Spans = tuple[Span, ...]


@dataclass(frozen=True)
class Heading:
    level: int
    spans: Spans


@dataclass(frozen=True)
class Paragraph:
    spans: Spans


@dataclass(frozen=True)
class ListBlock:
    ordered: bool
    # Each item is its own blocks: a paragraph, then any nested list.
    items: tuple[tuple["Block", ...], ...]


@dataclass(frozen=True)
class Table:
    header: tuple[Spans, ...]
    rows: tuple[tuple[Spans, ...], ...]


@dataclass(frozen=True)
class Figure:
    """A source figure; `name` is None when the target is not `image:<name>`."""

    name: str | None
    caption: str


@dataclass(frozen=True)
class ChartBlock:
    """A chart to draw, or the table and note it falls back to."""

    chart: "ChartSpec | None"
    fallback: Table | None
    note: str


@dataclass(frozen=True)
class Code:
    text: str


@dataclass(frozen=True)
class Quote:
    blocks: tuple["Block", ...]


@dataclass(frozen=True)
class Rule:
    pass


@dataclass(frozen=True)
class ChartSpec:
    kind: str  # bar, line or pie
    title: str
    labels: tuple[str, ...]
    series: tuple[tuple[str, tuple[float, ...]], ...]


Block = (
    Heading | Paragraph | ListBlock | Table | Figure | ChartBlock | Code | Quote | Rule
)
