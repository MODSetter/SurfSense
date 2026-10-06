"""A fenced `chart` block: read its JSON, draw it, or fall back to a table of its data."""

import functools
import json
import math
from io import BytesIO
from typing import Any

from matplotlib.figure import Figure as PlotFigure
from matplotlib.font_manager import FontProperties, findfont
from matplotlib.ft2font import FT2Font

from worker.studio.office.markdown.blocks import ChartBlock, ChartSpec, Span, Table

KINDS = ("bar", "line", "pie")
# Drawn at print resolution and placed at the page's width.
_SIZE_INCHES = (6.4, 3.6)
_DPI = 200


def read_chart(text: str) -> ChartBlock:
    """The chart the block describes, or why it becomes a table instead."""
    try:
        data = json.loads(text)
    except ValueError:
        return ChartBlock(
            None, None, "This chart could not be drawn: its data is not valid JSON."
        )
    if not isinstance(data, dict):
        return ChartBlock(
            None, None, "This chart could not be drawn: its data is not a JSON object."
        )
    labels = [str(label) for label in _list(data.get("labels"))]
    series = [
        (str(entry.get("name") or ""), _list(entry.get("values")))
        for entry in _list(data.get("series"))
        if isinstance(entry, dict)
    ]
    title = str(data.get("title") or "")
    problem = _problem(data.get("type"), labels, series) or _unprintable(
        [title, *labels, *(name for name, _ in series)]
    )
    if problem is None:
        spec = ChartSpec(
            kind=data["type"],
            title=title,
            labels=tuple(labels),
            series=tuple(
                (name, tuple(float(v) for v in values)) for name, values in series
            ),
        )
        return ChartBlock(spec, None, "")
    lead = f"{title}. " if title else ""
    return ChartBlock(
        None,
        _table(labels, series),
        f"{lead}This chart is shown as a table: {problem}.",
    )


def draw_chart(chart: ChartSpec) -> bytes:
    """The chart as a PNG; the object API needs no display and no pyplot state."""
    figure = PlotFigure(figsize=_SIZE_INCHES, dpi=_DPI)
    axes = figure.add_subplot()
    if chart.kind == "pie":
        ((_name, values),) = chart.series
        axes.pie(values, labels=chart.labels, autopct="%1.0f%%")
        axes.axis("equal")
    elif chart.kind == "line":
        for name, values in chart.series:
            axes.plot(chart.labels, values, marker="o", label=name or None)
    else:
        count = len(chart.series)
        width = 0.8 / count
        positions = range(len(chart.labels))
        for index, (name, values) in enumerate(chart.series):
            offset = (index - (count - 1) / 2) * width
            axes.bar([p + offset for p in positions], values, width, label=name or None)
        axes.set_xticks(list(positions), chart.labels)
    if chart.title:
        axes.set_title(chart.title)
    if chart.kind != "pie" and any(name for name, _ in chart.series):
        axes.legend()
    figure.tight_layout()
    buffer = BytesIO()
    figure.savefig(buffer, format="png")
    return buffer.getvalue()


def _problem(
    kind: Any, labels: list[str], series: list[tuple[str, list[Any]]]
) -> str | None:
    if kind not in KINDS:
        return f"its type must be bar, line or pie, not {json.dumps(kind)}"
    if not labels:
        return "it has no labels"
    if not series:
        return "it has no series"
    for name, values in series:
        if len(values) != len(labels) or not all(_is_number(v) for v in values):
            return f"the series {json.dumps(name)} needs one number per label"
    if kind == "pie" and len(series) != 1:
        return "a pie chart takes exactly one series"
    if kind == "pie" and (
        any(value < 0 for value in series[0][1]) or not any(series[0][1])
    ):
        return "a pie chart needs slices that are not negative and not all zero"
    return None


def _unprintable(texts: list[str]) -> str | None:
    """Why matplotlib would draw boxes: its font lacks letters, as it lacks Chinese."""
    covered = _chart_font_characters()
    if any(ord(c) not in covered for text in texts for c in text if not c.isspace()):
        return "its labels use letters the chart font cannot draw"
    return None


@functools.cache
def _chart_font_characters() -> frozenset[int]:
    return frozenset(FT2Font(findfont(FontProperties())).get_charmap())


def _table(labels: list[str], series: list[tuple[str, list[Any]]]) -> Table | None:
    if not labels and not series:
        return None
    rows = (
        max(len(labels), *(len(values) for _, values in series))
        if series
        else len(labels)
    )
    header = (_cell(""), *(_cell(name) for name, _ in series))
    body = tuple(
        (
            _cell(labels[row] if row < len(labels) else ""),
            *(_cell(_value(values, row)) for _, values in series),
        )
        for row in range(rows)
    )
    return Table(header=header, rows=body)


def _value(values: list[Any], row: int) -> str:
    if row >= len(values):
        return ""
    value = values[row]
    # 15 significant digits: whole numbers stay whole, not 1.23457e+06.
    return f"{value:.15g}" if _is_number(value) else str(value)


def _cell(text: str) -> tuple[Span, ...]:
    return (Span(text),)


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _is_number(value: Any) -> bool:
    """A finite number: JSON's NaN and Infinity, which Python reads, draw nothing."""
    return (
        isinstance(value, int | float)
        and not isinstance(value, bool)
        and math.isfinite(value)
    )
