"""The PDF builder: ReportLab's sample stylesheet on A4 with 2 cm margins (decision 12)."""

from collections.abc import Mapping
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, StyleSheet1, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    Flowable,
    HRFlowable,
    Image,
    ListFlowable,
    ListItem,
    SimpleDocTemplate,
    Spacer,
    TableStyle,
    XPreformatted,
)
from reportlab.platypus import Paragraph as PdfParagraph
from reportlab.platypus import Table as PdfTable

from worker.studio.office.markdown.blocks import (
    Block,
    ChartBlock,
    Code,
    Figure,
    Heading,
    ListBlock,
    Paragraph,
    Quote,
    Rule,
    Span,
    Spans,
    Table,
)
from worker.studio.office.markdown.chart import draw_chart
from worker.studio.office.markdown.links import safe_href
from worker.studio.office.markdown.parse import parse_markdown
from worker.studio.office.markdown.pdf_fonts import font_markup

_MARGIN = 2 * cm
_WIDTH = A4[0] - 2 * _MARGIN
# Room left under a figure for its caption, so the two share a page.
_HEIGHT = A4[1] - 2 * _MARGIN - 2 * cm
_QUOTE_INDENT = 1 * cm
# Narrower columns than this wrap a word a letter at a time; a wider table is
# set as several, each repeating the first column so its rows stay named.
_MIN_COLUMN = 1.5 * cm
_MAX_COLUMNS = int(_WIDTH // _MIN_COLUMN)
# Quotes and lists nested deeper than this stop indenting, so text keeps room.
_MAX_NESTING = 6


def markdown_to_pdf(markdown: str, figures: Mapping[str, Path]) -> bytes:
    """The PDF a Markdown spec describes; `figures` maps a figure name to its PNG."""
    styles = getSampleStyleSheet()
    story = _Story(styles, figures).blocks(parse_markdown(markdown))
    buffer = BytesIO()
    SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=_MARGIN,
        rightMargin=_MARGIN,
        topMargin=_MARGIN,
        bottomMargin=_MARGIN,
    ).build(story or [Spacer(1, 1)])
    return buffer.getvalue()


class _Story:
    def __init__(self, styles: StyleSheet1, figures: Mapping[str, Path]) -> None:
        self._styles = styles
        self._figures = figures
        self._caption = ParagraphStyle(
            "FigureCaption", parent=styles["Italic"], spaceAfter=8
        )
        self._nesting = 0

    def blocks(self, blocks: list[Block] | tuple[Block, ...]) -> list[Flowable]:
        story: list[Flowable] = []
        for block in blocks:
            story.extend(self.block(block))
        return story

    def block(self, block: Block) -> list[Flowable]:
        match block:
            case Heading(level, spans):
                return [self._paragraph(spans, f"Heading{min(level, 6)}")]
            case Paragraph(spans):
                return [self._paragraph(spans, "BodyText")]
            case ListBlock():
                return self._list(block)
            case Table():
                return self._table(block)
            case Figure():
                return self._figure(block)
            case ChartBlock():
                return self._chart(block)
            case Code(text):
                return [XPreformatted(font_markup(text), self._styles["Code"])]
            case Quote(inner):
                return self._quote(inner)
            case Rule():
                return [HRFlowable(width="100%", color=colors.grey)]
        return []

    def _paragraph(self, spans: Spans, style: str) -> PdfParagraph:
        return PdfParagraph(_markup(spans), self._styles[style])

    def _quote(self, inner: tuple[Block, ...]) -> list[Flowable]:
        """A one-item list with no bullet: an Indenter cannot sit inside a list."""
        if self._nesting >= _MAX_NESTING:
            return self.blocks(inner)
        item = ListItem(self._nested([inner]), value="")
        return [
            ListFlowable(
                [item], bulletType="bullet", start="", leftIndent=_QUOTE_INDENT
            )
        ]

    def _list(self, block: ListBlock) -> list[Flowable]:
        if self._nesting >= _MAX_NESTING:
            return [flowable for item in block.items for flowable in self.blocks(item)]
        items = [ListItem(self._nested([item])) for item in block.items]
        return [
            ListFlowable(
                items,
                bulletType="1" if block.ordered else "bullet",
                start=1 if block.ordered else None,
            )
        ]

    def _nested(self, groups: list[tuple[Block, ...]]) -> list[Flowable]:
        self._nesting += 1
        try:
            story = [flowable for group in groups for flowable in self.blocks(group)]
        finally:
            self._nesting -= 1
        return story or [Spacer(1, 1)]

    def _table(self, table: Table) -> list[Flowable]:
        rows = [table.header, *table.rows] if table.header else list(table.rows)
        columns = max((len(row) for row in rows), default=0)
        if columns == 0:
            return []
        if columns > _MAX_COLUMNS:
            return [
                flowable
                for part in _column_groups(table, columns)
                for flowable in self._table(part)
            ]
        body = self._styles["BodyText"]
        data = [
            [
                PdfParagraph(
                    _cell_markup(row, column, bold=index == 0 and bool(table.header)),
                    body,
                )
                for column in range(columns)
            ]
            for index, row in enumerate(rows)
        ]
        grid = PdfTable(
            data,
            colWidths=[_WIDTH / columns] * columns,
            repeatRows=1 if table.header else 0,
            # A row taller than the page continues on the next one.
            splitInRow=1,
        )
        style = [
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]
        if table.header:
            style.append(("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke))
        grid.setStyle(TableStyle(style))
        return [grid, Spacer(1, 6)]

    def _figure(self, figure: Figure) -> list[Flowable]:
        path = self._figures.get(figure.name) if figure.name else None
        caption = PdfParagraph(font_markup(figure.caption), self._caption)
        if path is None:
            return [caption]
        return [_image(BytesIO(path.read_bytes())), caption]

    def _chart(self, block: ChartBlock) -> list[Flowable]:
        if block.chart is not None:
            return [_image(BytesIO(draw_chart(block.chart))), Spacer(1, 6)]
        note = PdfParagraph(font_markup(block.note), self._caption)
        table = self._table(block.fallback) if block.fallback is not None else []
        return [note, *table]


def _column_groups(table: Table, columns: int) -> list[Table]:
    """The table cut into tables narrow enough for the page, each led by column one."""
    step = _MAX_COLUMNS - 1
    return [
        Table(
            header=_columns(table.header, start, step) if table.header else (),
            rows=tuple(_columns(row, start, step) for row in table.rows),
        )
        for start in range(1, columns, step)
    ]


def _columns(row: tuple[Spans, ...], start: int, step: int) -> tuple[Spans, ...]:
    return (row[0] if row else (), *row[start : start + step])


def _image(data: BytesIO) -> Image:
    """At its own size in points, or shrunk to fit the frame."""
    width, height = ImageReader(data).getSize()
    data.seek(0)
    scale = min(1.0, _WIDTH / width, _HEIGHT / height)
    return Image(data, width=width * scale, height=height * scale)


def _cell_markup(row: tuple[Spans, ...], column: int, *, bold: bool) -> str:
    text = _markup(row[column]) if column < len(row) else ""
    return f"<b>{text}</b>" if bold and text else text


def _markup(spans: Spans) -> str:
    """ReportLab's paragraph markup, with every character of the text escaped."""
    return "".join(_span_markup(span) for span in spans)


def _span_markup(span: Span) -> str:
    text = font_markup(span.text).replace("\n", "<br/>")
    if span.code:
        text = f'<font face="Courier">{text}</font>'
    if span.bold:
        text = f"<b>{text}</b>"
    if span.italic:
        text = f"<i>{text}</i>"
    if span.strike:
        text = f"<strike>{text}</strike>"
    href = safe_href(span.href)
    if href is not None:
        target = escape(href, {'"': "&quot;"})
        text = f'<a href="{target}" color="blue">{text}</a>'
    return text
