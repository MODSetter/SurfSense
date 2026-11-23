"""surfsense_docs: a Word document, a PDF or a deck from a few calls, saved at OUTPUT_PATH.

The documents skill's helper (modules/agent/skills/surfsense-documents). Each run
folder gets a copy of this file, so a script can `from surfsense_docs import Doc`
instead of writing python-docx, ReportLab or python-pptx code by hand, and stays
short enough for a small model to write whole. The format follows OUTPUT_PATH's
extension. A script still uses those libraries directly for what this lacks: a
template, a workbook, a layout of its own.

Stored scripts call it, and a document's next version renders its script with
the helper of the app that renders it: keep every call and argument working
(docs/adr/0095-documents-are-scripted-with-a-helper-and-a-short-skill.md).
"""

import html
import os
import re
from dataclasses import dataclass, field
from typing import Any

_BOLD = re.compile(r"\*\*(.+?)\*\*")
_ITALIC = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")


_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def _number(cell: Any) -> float | None:
    """4800, 4800.5 or "4,800" / "4 800" / "EUR 4,800" as a number; None for anything else."""
    if isinstance(cell, bool):
        return None
    if isinstance(cell, (int, float)):
        return float(cell)
    text = re.sub(r"(?i)\b(eur|usd|gbp)\b|[€$£\s,]", "", str(cell))
    return float(text) if _NUMBER.fullmatch(text) else None


def _chart_value(value: Any) -> float:
    """A chart's value as a number, "1,200" or "EUR 1,200" included."""
    number = _number(value)
    if number is None:
        raise ValueError(f"a chart's values are numbers, not {value!r}")
    return number


def _cell(cell: Any) -> str:
    """A number with thousands separators; anything else as written."""
    if isinstance(cell, bool) or not isinstance(cell, (int, float)):
        return str(cell)
    if float(cell).is_integer():
        return f"{int(cell):,}"
    return f"{cell:,.2f}".rstrip("0").rstrip(".")


def _sum_row(label: str, rows: list[list[Any]], width: int) -> list[Any]:
    """The label, then each column's sum over its number cells, as a spreadsheet's SUM skips text ("1,250 a
    month" is skipped); blank for a column with no numbers."""
    out: list[Any] = [label]
    for j in range(1, width):
        values = [
            v for v in (_number(r[j]) for r in rows if j < len(r)) if v is not None
        ]
        out.append(sum(values) if values else "")
    return out


def _table_rows(a: dict[str, Any]) -> list[list[str]]:
    """The header, the rows, the total row when there is one, then `after`."""
    total = [a["total"]] if a["total"] else []
    return [a["header"], *a["rows"], *total, *a["after"]]


def _is_total(a: dict[str, Any], r: int) -> bool:
    """Whether row `r` of `_table_rows` is a total row set in bold."""
    return bool(a["bold_total"]) and r == len(a["rows"]) + 1


@dataclass
class _Block:
    kind: str
    args: dict[str, Any] = field(default_factory=dict)


class Doc:
    """Blocks in reading order; save() lays them out as .docx, .pdf or .pptx."""

    def __init__(
        self, title: str, subtitle: str | None = None, letter: bool = False
    ) -> None:
        self.title = title
        self.subtitle = subtitle
        # US Letter pages instead of A4, for a reader in the US or Canada.
        self.letter = bool(letter)
        self.blocks: list[_Block] = []

    def heading(self, text: str, level: int = 1) -> "Doc":
        self.blocks.append(
            _Block("heading", {"text": str(text), "level": max(1, min(int(level), 3))})
        )
        return self

    def paragraph(self, text: str) -> "Doc":
        """**bold** and *italic* marks work inside the text."""
        self.blocks.append(_Block("paragraph", {"text": str(text)}))
        return self

    def bullets(self, items: list[str]) -> "Doc":
        self.blocks.append(_Block("bullets", {"items": [str(i) for i in items]}))
        return self

    def numbered(self, items: list[str]) -> "Doc":
        self.blocks.append(_Block("numbered", {"items": [str(i) for i in items]}))
        return self

    def table(
        self,
        header: list[str],
        rows: list[list[Any]],
        total: str | list[Any] | None = None,
        bold_total: bool = False,
        after: list[list[Any]] | None = None,
    ) -> "Doc":
        """A header row (bold), the rows, an optional total row (bold only when asked), then `after`.

        `total` as a label ("Total") adds up the number cells (4800 or "4,800") of each column of `rows`,
        skipping text as a spreadsheet's SUM does; as a list it is the total row as given. Rows in `after` come below the total and are not
        added in."""
        if isinstance(total, str):
            total = _sum_row(total, rows, len(header))
        self.blocks.append(
            _Block(
                "table",
                {
                    "header": [str(h) for h in header],
                    "rows": [[_cell(c) for c in r] for r in rows],
                    "total": [_cell(c) for c in total] if total else None,
                    "bold_total": bool(bold_total and total),
                    "after": [[_cell(c) for c in r] for r in (after or [])],
                },
            )
        )
        return self

    def image(
        self, name: str, width_cm: float | None = None, caption: str | None = None
    ) -> "Doc":
        """A source image or a drawn picture by its name (list it in the render call's images)."""
        path = os.path.join(os.environ.get("IMAGES_DIR", "images"), f"{name}.png")
        self.blocks.append(
            _Block("image", {"path": path, "width_cm": width_cm, "caption": caption})
        )
        return self

    def chart(
        self,
        kind: str,
        labels: list[str],
        values: list[float],
        title: str | None = None,
        ylabel: str | None = None,
    ) -> "Doc":
        """A bar, line or pie chart from the numbers given, drawn with matplotlib."""
        self.blocks.append(
            _Block(
                "chart",
                {
                    "kind": kind,
                    "labels": [str(x) for x in labels],
                    "values": [_chart_value(v) for v in values],
                    "title": title,
                    "ylabel": ylabel,
                },
            )
        )
        return self

    def page_break(self) -> "Doc":
        self.blocks.append(_Block("page_break"))
        return self

    def notes(self, text: str) -> "Doc":
        """What the presenter says, in the speaker notes of the slide this falls on.
        A Word document or a PDF leaves it out."""
        self.blocks.append(_Block("notes", {"text": str(text)}))
        return self

    def save(self, path: str | None = None) -> str:
        path = path or os.environ["OUTPUT_PATH"]
        ext = os.path.splitext(path)[1].lower()
        charts = self._draw_charts(os.path.dirname(os.path.abspath(path)))
        if ext == ".docx":
            _docx(self, path, charts)
        elif ext == ".pdf":
            _pdf(self, path, charts)
        elif ext == ".pptx":
            _pptx(self, path, charts)
        else:
            raise ValueError(
                f"surfsense_docs makes .docx, .pdf and .pptx files, not {ext or 'no extension'}"
            )
        return path

    def _draw_charts(self, folder: str) -> dict[int, str]:
        drawn: dict[int, str] = {}
        for i, b in enumerate(self.blocks):
            if b.kind != "chart":
                continue
            import matplotlib.pyplot as plt

            a = b.args
            fig, ax = plt.subplots(figsize=(7, 4))
            if a["kind"] == "pie":
                ax.pie(a["values"], labels=a["labels"], autopct="%1.0f%%")
                ax.axis("equal")
            elif a["kind"] == "line":
                ax.plot(a["labels"], a["values"], marker="o")
            else:
                ax.bar(a["labels"], a["values"])
            if a["title"]:
                ax.set_title(a["title"])
            if a["ylabel"] and a["kind"] != "pie":
                ax.set_ylabel(a["ylabel"])
            fig.tight_layout()
            out = os.path.join(folder, f"_chart_{i}.png")
            fig.savefig(out, dpi=200)
            plt.close(fig)
            drawn[i] = out
        return drawn


def _runs(text: str) -> list[tuple[str, bool, bool]]:
    """Text split into (piece, bold, italic) at **bold** and *italic* marks."""
    out: list[tuple[str, bool, bool]] = []
    pos = 0
    for m in _BOLD.finditer(text):
        out += [(p, False, it) for p, it in _italic_pieces(text[pos : m.start()])]
        out += [(p, True, it) for p, it in _italic_pieces(m.group(1))]
        pos = m.end()
    out += [(p, False, it) for p, it in _italic_pieces(text[pos:])]
    return [r for r in out if r[0]]


def _italic_pieces(text: str) -> list[tuple[str, bool]]:
    out: list[tuple[str, bool]] = []
    pos = 0
    for m in _ITALIC.finditer(text):
        out.append((text[pos : m.start()], False))
        out.append((m.group(1), True))
        pos = m.end()
    out.append((text[pos:], False))
    return out


def _markup(text: str) -> str:
    """ReportLab paragraph markup: escaped text with <b> and <i>."""
    return "".join(
        (f"<b>{html.escape(p)}</b>" if b else html.escape(p))
        if not i
        else (f"<b><i>{html.escape(p)}</i></b>" if b else f"<i>{html.escape(p)}</i>")
        for p, b, i in _runs(text)
    )


def _plain(text: str) -> str:
    return "".join(p for p, _, _ in _runs(text))


def _docx(doc: Doc, path: str, charts: dict[int, str]) -> None:
    import docx
    from docx.enum.text import WD_BREAK
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt
    from PIL import Image as PILImage

    d = docx.Document()
    section = d.sections[0]
    section.page_width, section.page_height = (
        (Cm(21.59), Cm(27.94)) if doc.letter else (Cm(21), Cm(29.7))
    )
    text_width = section.page_width - section.left_margin - section.right_margin
    text_height = section.page_height - section.top_margin - section.bottom_margin
    d.add_heading(doc.title, level=0)
    if doc.subtitle:
        d.add_paragraph(doc.subtitle).runs[0].italic = True

    def add_runs(par, text):
        for piece, bold, italic in _runs(text):
            run = par.add_run(piece)
            run.bold, run.italic = bold, italic

    for i, b in enumerate(doc.blocks):
        a = b.args
        if b.kind == "heading":
            d.add_heading(_plain(a["text"]), level=a["level"])
        elif b.kind == "paragraph":
            add_runs(d.add_paragraph(), a["text"])
        elif b.kind in ("bullets", "numbered"):
            style = "List Bullet" if b.kind == "bullets" else "List Number"
            for item in a["items"]:
                add_runs(d.add_paragraph(style=style), item)
        elif b.kind == "table":
            rows = _table_rows(a)
            ncols = max(len(r) for r in rows)
            t = d.add_table(rows=len(rows), cols=ncols)
            t.style = "Table Grid"
            # Each row's cells once: python-docx's `t.cell(r, c)` rebuilds the
            # whole grid per call, quadratic in a long table.
            for r, (row, table_row) in enumerate(zip(rows, t.rows, strict=True)):
                cells = table_row.cells
                for c in range(ncols):
                    cell = cells[c]
                    cell.text = ""
                    par = cell.paragraphs[0]
                    add_runs(par, row[c] if c < len(row) else "")
                    if r == 0 or _is_total(a, r):
                        for run in par.runs:
                            run.bold = True
                    if r == 0:
                        shade = OxmlElement("w:shd")
                        shade.set(qn("w:val"), "clear")
                        shade.set(qn("w:fill"), "D9E2F3")
                        cell._tc.get_or_add_tcPr().append(shade)
            # The header row repeats on each page a long table runs onto.
            tr_pr = t.rows[0]._tr.get_or_add_trPr()
            header_flag = OxmlElement("w:tblHeader")
            header_flag.set(qn("w:val"), "true")
            tr_pr.append(header_flag)
            d.add_paragraph()
        elif b.kind in ("image", "chart"):
            src = a["path"] if b.kind == "image" else charts[i]
            width = (
                Cm(a["width_cm"])
                if b.kind == "image" and a.get("width_cm")
                else text_width
            )
            width = min(width, text_width)
            with PILImage.open(src) as picture:
                tall = width * picture.height / picture.width > 0.9 * text_height
            if tall:  # short enough to fit a page, at its own proportions
                d.add_picture(src, height=int(0.9 * text_height))
            else:
                d.add_picture(src, width=width)
            if b.kind == "image" and a.get("caption"):
                cap = d.add_paragraph(a["caption"])
                cap.runs[0].italic = True
                cap.runs[0].font.size = Pt(9)
        elif b.kind == "page_break":
            d.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
    d.save(path)


def _pdf(doc: Doc, path: str, charts: dict[int, str]) -> None:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        Image,
        ListFlowable,
        ListItem,
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    styles = getSampleStyleSheet()
    page = SimpleDocTemplate(
        path,
        pagesize=letter if doc.letter else A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title=doc.title,
    )
    width = page.width
    story: list[Any] = [Paragraph(_markup(doc.title), styles["Title"])]
    if doc.subtitle:
        story.append(Paragraph(f"<i>{html.escape(doc.subtitle)}</i>", styles["Normal"]))
        story.append(Spacer(1, 0.4 * cm))
    for i, b in enumerate(doc.blocks):
        a = b.args
        if b.kind == "heading":
            story.append(Paragraph(_markup(a["text"]), styles[f"Heading{a['level']}"]))
        elif b.kind == "paragraph":
            story.append(Paragraph(_markup(a["text"]), styles["BodyText"]))
        elif b.kind in ("bullets", "numbered"):
            items = [
                ListItem(Paragraph(_markup(t), styles["BodyText"])) for t in a["items"]
            ]
            story.append(
                ListFlowable(
                    items,
                    bulletType="bullet" if b.kind == "bullets" else "1",
                    leftIndent=14,
                )
            )
        elif b.kind == "table":
            body = styles["BodyText"]
            rows = _table_rows(a)
            ncols = max(len(r) for r in rows)
            data = [
                [
                    Paragraph(_markup(r[c]) if c < len(r) else "", body)
                    for c in range(ncols)
                ]
                for r in rows
            ]
            for c in range(ncols):  # the header row in bold
                data[0][c] = Paragraph(
                    f"<b>{_markup(rows[0][c]) if c < len(rows[0]) else ''}</b>", body
                )
            if a["bold_total"]:
                ti = len(a["rows"]) + 1
                last = rows[ti]
                data[ti] = [
                    Paragraph(
                        f"<b>{_markup(last[c]) if c < len(last) else ''}</b>", body
                    )
                    for c in range(ncols)
                ]
            t = Table(data, colWidths=[width / ncols] * ncols, repeatRows=1)
            t.setStyle(
                TableStyle(
                    [
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#D9E2F3")),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ]
                )
            )
            story += [t, Spacer(1, 0.4 * cm)]
        elif b.kind in ("image", "chart"):
            src = a["path"] if b.kind == "image" else charts[i]
            img = Image(src)
            want = (
                a["width_cm"] * cm if b.kind == "image" and a.get("width_cm") else width
            )
            # At most the text width, and short enough to fit a page.
            scale = min(
                min(want, width) / img.imageWidth,
                0.9 * page.height / img.imageHeight,
            )
            img.drawWidth, img.drawHeight = (
                img.imageWidth * scale,
                img.imageHeight * scale,
            )
            story.append(img)
            if b.kind == "image" and a.get("caption"):
                story.append(
                    Paragraph(f"<i>{html.escape(a['caption'])}</i>", styles["Italic"])
                )
            story.append(Spacer(1, 0.3 * cm))
        elif b.kind == "page_break":
            story.append(PageBreak())
    page.build(story)


def _pptx(doc: Doc, path: str, charts: dict[int, str]) -> None:
    from pptx import Presentation
    from pptx.util import Cm, Pt

    deck = Presentation()
    deck.slide_width, deck.slide_height = Cm(33.867), Cm(19.05)
    layouts = {layout.name: layout for layout in deck.slide_layouts}
    cover = deck.slides.add_slide(layouts["Title Slide"])
    cover.shapes.title.text = _plain(doc.title)
    if doc.subtitle and len(cover.placeholders) > 1:
        cover.placeholders[1].text = _plain(doc.subtitle)

    # Each heading starts a slide, and a page break the next one under the same
    # title; whatever comes before the first heading goes on one under the
    # document's title. Notes join the slide they fall on, the cover before any
    # block.
    slides: list[tuple[str, list[tuple[int, _Block]]]] = []
    cover_notes: list[str] = []
    for i, b in enumerate(doc.blocks):
        if b.kind == "heading":
            slides.append((_plain(b.args["text"]), []))
        elif b.kind == "notes" and not slides:
            cover_notes.append(b.args["text"])
        elif b.kind == "page_break":
            if slides and any(k.kind != "notes" for _, k in slides[-1][1]):
                slides.append((slides[-1][0], []))
        else:
            if not slides:
                slides.append((_plain(doc.title), []))
            slides[-1][1].append((i, b))
    _set_notes(cover, cover_notes)

    for title, blocks in slides:
        shown = [(i, b) for i, b in blocks if b.kind != "notes"]
        if (
            shown
            and all(b.kind in _TEXT for _, b in shown)
            and sum(_text_lines(b, _BODY_CHARACTERS) for _, b in shown) <= _BODY_LINES
        ):
            slide = deck.slides.add_slide(layouts["Title and Content"])
            slide.shapes.title.text = title
            _fill(slide.placeholders[1].text_frame, shown, Pt(20))
            _set_notes(slide, [b.args["text"] for _, b in blocks if b.kind == "notes"])
        else:
            _laid_out(deck, layouts["Title Only"], title, blocks, charts)
    deck.save(path)


_TEXT = ("paragraph", "bullets", "numbered")
# What a Title and Content slide's body holds at 20 pt, and a text box's line at
# 18 pt across a laid-out slide, in characters: estimates that err short.
_BODY_LINES, _BODY_CHARACTERS, _BOX_CHARACTERS = 10, 70, 100


def _item_lines(text: str, per_line: int) -> int:
    return max(1, -(-len(_plain(text)) // per_line))


def _text_lines(b: _Block, per_line: int) -> int:
    items = [b.args["text"]] if b.kind == "paragraph" else b.args["items"]
    return sum(_item_lines(t, per_line) for t in items)


def _set_notes(slide: Any, notes: list[str]) -> None:
    if notes:
        slide.notes_slide.notes_text_frame.text = "\n".join(notes)


def _laid_out(
    deck: Any,
    layout: Any,
    title: str,
    blocks: list[tuple[int, _Block]],
    charts: dict[int, str],
) -> None:
    """Text, tables and pictures down Title Only slides, top to bottom. What does
    not fit below what is there goes on to another slide under the same title: a
    long list or table runs on, the list's numbering and the table's header row
    with it. Each speaker note goes on the slide its place in the blocks falls on."""
    from pptx.util import Cm, Pt

    left, width = Cm(2), deck.slide_width - Cm(4)
    first_top, bottom = Cm(4), deck.slide_height - Cm(1)
    row_height, least_picture = Cm(0.9), Cm(5)
    line, pad = Cm(1.1), Cm(0.4)
    whole = int((bottom - first_top - pad) / line)
    pages: list[tuple[Any, list[str]]] = []

    def new_slide() -> Any:
        made = deck.slides.add_slide(layout)
        made.shapes.title.text = title
        pages.append((made, []))
        return made

    slide = new_slide()
    top = first_top

    def go_on_if(short: bool) -> None:
        """A slide of its own for what does not fit below what this one holds."""
        nonlocal slide, top
        if short and top > first_top:
            slide, top = new_slide(), first_top

    for i, b in blocks:
        a = b.args
        if b.kind == "notes":
            pages[-1][1].append(a["text"])
        elif b.kind in _TEXT:
            items = [a["text"]] if b.kind == "paragraph" else list(a["items"])
            sizes = [_item_lines(t, _BOX_CHARACTERS) for t in items]
            start = 0
            while start < len(items):
                # A list that would fit a slide of its own moves there whole.
                need, room = sum(sizes[start:]), int((bottom - top - pad) / line)
                go_on_if(need > room and (need <= whole or room < 2))
                room = int((bottom - top - pad) / line)
                end, used = start, 0
                while end < len(items) and (used + sizes[end] <= room or end == start):
                    used, end = used + sizes[end], end + 1
                height = line * used + pad
                box = slide.shapes.add_textbox(left, top, width, height)
                box.text_frame.word_wrap = True
                part = (
                    b
                    if b.kind == "paragraph"
                    else _Block(b.kind, {"items": items[start:end]})
                )
                _fill(box.text_frame, [(i, part)], Pt(18), first_number=start + 1)
                top += height + Cm(0.3)
                start = end
                if start < len(items):
                    slide, top = new_slide(), first_top
        elif b.kind == "table":
            rows = _table_rows(a)
            header, body = rows[0], rows[1:]
            ncols = max(len(r) for r in rows)
            # The total's place among the rows below the header.
            total_at = len(a["rows"]) if a["bold_total"] else None
            start = 0
            while True:
                go_on_if(int((bottom - top) / row_height) - 1 < min(2, len(body)))
                fit = max(1, int((bottom - top) / row_height) - 1)
                chunk = body[start : start + fit]
                bold = {0} | {k + 1 for k in range(len(chunk)) if start + k == total_at}
                height = row_height * (len(chunk) + 1)
                _deck_table(
                    slide, [header, *chunk], ncols, bold, (left, top, width, height)
                )
                top += height + Cm(0.5)
                start += len(chunk)
                if start >= len(body):
                    break
                slide, top = new_slide(), first_top
        elif b.kind in ("image", "chart"):
            src = a["path"] if b.kind == "image" else charts[i]
            caption = a.get("caption") if b.kind == "image" else None
            caption_height = Cm(1.2) if caption else 0
            go_on_if(bottom - top - caption_height < least_picture)
            room = bottom - top - caption_height
            if b.kind == "image" and a.get("width_cm"):
                pic = slide.shapes.add_picture(
                    src, left, top, width=min(Cm(a["width_cm"]), width)
                )
            else:
                pic = slide.shapes.add_picture(src, left, top, height=room)
            scale = min(1.0, width / pic.width, room / pic.height)
            if scale < 1:
                pic.width, pic.height = int(pic.width * scale), int(pic.height * scale)
            top += pic.height
            if caption:
                box = slide.shapes.add_textbox(left, top, width, caption_height)
                box.text_frame.word_wrap = True
                run = box.text_frame.paragraphs[0].add_run()
                run.text = str(caption)
                run.font.italic, run.font.size = True, Pt(12)
                top += caption_height
            top += Cm(0.5)
    for page, notes in pages:
        _set_notes(page, notes)


def _deck_table(
    slide: Any,
    rows: list[list[str]],
    ncols: int,
    bold: set[int],
    box: tuple[int, int, int, int],
) -> None:
    """A table on a slide, the rows in `bold` (by their place here) in bold."""
    from pptx.util import Pt

    shape = slide.shapes.add_table(len(rows), ncols, *box)
    for r, row in enumerate(rows):
        for c in range(ncols):
            cell = shape.table.cell(r, c)
            cell.text = _plain(row[c]) if c < len(row) else ""
            for par in cell.text_frame.paragraphs:
                for run in par.runs:
                    run.font.size = Pt(14)
                    run.font.bold = r in bold


def _fill(
    frame: Any, blocks: list[tuple[int, _Block]], size: Any, first_number: int = 1
) -> None:
    """Paragraphs into a text frame, a list as real list paragraphs: PowerPoint
    draws the bullet or the number, nothing is typed into the text. A numbered
    list that runs on from another slide counts on from `first_number`."""
    first = True
    for _, b in blocks:
        items = [b.args["text"]] if b.kind == "paragraph" else b.args["items"]
        for item in items:
            par = frame.paragraphs[0] if first else frame.add_paragraph()
            first = False
            _list_style(par, b.kind, first_number)
            for piece, bold, italic in _runs(item):
                run = par.add_run()
                run.text, run.font.bold, run.font.italic = piece, bold, italic
                run.font.size = size


def _list_style(par: Any, kind: str, first_number: int = 1) -> None:
    """A bullet, a number or neither, as the paragraph's own formatting."""
    from pptx.oxml.ns import qn

    p_pr = par._p.get_or_add_pPr()
    for tag in ("a:buNone", "a:buChar", "a:buAutoNum"):
        for old in p_pr.findall(qn(tag)):
            p_pr.remove(old)
    if kind == "bullets":
        p_pr.set("marL", "342900")
        p_pr.set("indent", "-342900")
        p_pr.append(p_pr.makeelement(qn("a:buChar"), {"char": "\u2022"}))
    elif kind == "numbered":
        p_pr.set("marL", "342900")
        p_pr.set("indent", "-342900")
        number = {"type": "arabicPeriod"}
        if first_number > 1:
            number["startAt"] = str(first_number)
        p_pr.append(p_pr.makeelement(qn("a:buAutoNum"), number))
    else:
        p_pr.set("marL", "0")
        p_pr.set("indent", "0")
        p_pr.append(p_pr.makeelement(qn("a:buNone"), {}))
