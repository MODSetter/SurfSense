"""Deterministic ``.txt`` / ``.md`` → single PDF via reportlab.

Used wherever a benchmark needs the same source bytes fed to both the
native-PDF arm and the SurfSense ingestion arm. The head-to-head
comparison is fair only if the *same* PDF is the input to both arms,
which is why we go to lengths to make the rendering deterministic.

Determinism notes:

* We pin the PDF metadata to a fixed creation date and producer
  (``reportlab`` accepts neither directly, but ``Canvas.setAuthor`` and
  the absence of an ``info`` mutator means the bytes only differ by
  ``CreationDate`` / ``ModDate``). We post-process the PDF to scrub
  those if ``deterministic=True`` is passed.
* Page size, font, margins, and tab handling are fixed in code so the
  same input yields the same byte output across machines.
* PDF/A is overkill for our use; basic PDF 1.4 is what every model
  expects.
"""

from __future__ import annotations

import io
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)


@dataclass
class RenderedPdf:
    path: Path
    n_pages_estimate: int
    n_chars: int


_PDF_DATE_KEY = re.compile(rb"/(?:CreationDate|ModDate)\s*\(D:[^)]*\)")
# reportlab also writes a `/ID [<hex1><hex2>]` trailer entry that
# embeds a per-run hash. Scrub it so two renders of the same input
# produce the same bytes.
_PDF_ID_ARRAY = re.compile(rb"/ID\s*\[\s*<[^>]*>\s*<[^>]*>\s*\]")


def _scrub_dates(pdf_bytes: bytes) -> bytes:
    """Remove ``CreationDate`` / ``ModDate`` / trailer ``/ID`` so the
    file is byte-deterministic across runs."""

    pdf_bytes = _PDF_DATE_KEY.sub(b"/CreationDate (D:19700101000000Z)", pdf_bytes)
    pdf_bytes = _PDF_ID_ARRAY.sub(b"/ID [<00><00>]", pdf_bytes)
    return pdf_bytes


_DEFAULT_STYLES = getSampleStyleSheet()


def _build_body_style() -> ParagraphStyle:
    base = _DEFAULT_STYLES["BodyText"]
    style = ParagraphStyle(
        "EvalBody",
        parent=base,
        fontName="Helvetica",
        fontSize=10.5,
        leading=14,
        spaceAfter=6,
        spaceBefore=0,
    )
    return style


def _build_heading_style() -> ParagraphStyle:
    base = _DEFAULT_STYLES["Heading2"]
    style = ParagraphStyle(
        "EvalHeading",
        parent=base,
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=18,
        spaceAfter=10,
        spaceBefore=8,
    )
    return style


def _normalise_paragraphs(text: str) -> list[str]:
    """Split a text blob into paragraphs while preserving blank-line structure."""

    blocks: list[list[str]] = [[]]
    for line in text.splitlines():
        stripped = line.rstrip()
        if stripped == "":
            if blocks[-1]:
                blocks.append([])
            continue
        blocks[-1].append(stripped)
    paragraphs: list[str] = []
    for block in blocks:
        if not block:
            continue
        # Join lines within a paragraph with spaces (text-from-PDF style).
        paragraphs.append(" ".join(block))
    return paragraphs


def _escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def render_pdf(
    *,
    title: str,
    sections: Sequence[tuple[str | None, str]],
    output_path: Path,
    deterministic: bool = True,
) -> RenderedPdf:
    """Render one PDF from a list of ``(section_heading, section_text)`` tuples.

    ``section_heading`` may be ``None`` for an unnamed section. Each
    section is followed by a page break so the model's PDF parser sees
    a clean structural boundary between source files.
    """

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        title=title,
        author="surfsense-evals",
        subject="Eval input",
        creator="surfsense-evals",
    )

    body_style = _build_body_style()
    heading_style = _build_heading_style()
    title_style = ParagraphStyle(
        "EvalTitle",
        parent=_DEFAULT_STYLES["Title"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        spaceAfter=14,
    )

    flow: list = [Paragraph(_escape_html(title), title_style)]
    total_chars = 0
    for index, (heading, text) in enumerate(sections):
        if index > 0:
            flow.append(PageBreak())
        if heading:
            flow.append(Paragraph(_escape_html(heading), heading_style))
        for paragraph in _normalise_paragraphs(text):
            total_chars += len(paragraph)
            flow.append(Paragraph(_escape_html(paragraph), body_style))
            flow.append(Spacer(1, 4))

    doc.build(flow)
    pdf_bytes = buffer.getvalue()
    if deterministic:
        pdf_bytes = _scrub_dates(pdf_bytes)
    output_path.write_bytes(pdf_bytes)

    # Conservative page estimate: ~3000 chars per LETTER page at 10.5pt.
    n_pages = max(1, total_chars // 3000 + len(sections))
    return RenderedPdf(path=output_path, n_pages_estimate=n_pages, n_chars=total_chars)


@dataclass
class PdfImage:
    """One image to embed inside a section.

    ``caption`` is rendered below the image (italic). ``max_width_in``
    caps the rendered width in inches; height auto-scales to preserve
    aspect ratio (read with PIL).
    """

    path: Path
    caption: str = ""
    max_width_in: float = 5.5  # default leaves margin for LETTER 8.5"


def _make_image_flowable(image: PdfImage) -> Image:
    """Build a reportlab Image flowable scaled to fit page width."""

    reader = ImageReader(str(image.path))
    iw, ih = reader.getSize()
    if iw <= 0 or ih <= 0:
        raise ValueError(f"Invalid image dimensions for {image.path}: {iw}x{ih}")
    target_w = image.max_width_in * inch
    target_h = target_w * (ih / iw)
    # Cap height too — some medical images are extreme portrait.
    max_h = 7.0 * inch
    if target_h > max_h:
        target_h = max_h
        target_w = target_h * (iw / ih)
    return Image(str(image.path), width=target_w, height=target_h)


def render_pdf_with_images(
    *,
    title: str,
    sections: Sequence[tuple[str | None, str, Sequence[PdfImage] | None]],
    output_path: Path,
    deterministic: bool = True,
    page_break_between_sections: bool = False,
) -> RenderedPdf:
    """Render a PDF that mixes text and embedded images.

    Each section is ``(heading, body_text, images)``. Images render
    inline after the body text, each followed by an italic caption.
    Set ``page_break_between_sections=True`` if you want explicit
    structural boundaries (mostly useful for multi-case PDFs); the
    default keeps everything on one page when possible (so a single
    MedXpertQA case is one PDF page with case + images + options).
    """

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        title=title,
        author="surfsense-evals",
        subject="Eval input",
        creator="surfsense-evals",
    )

    body_style = _build_body_style()
    heading_style = _build_heading_style()
    caption_style = ParagraphStyle(
        "EvalCaption",
        parent=body_style,
        fontSize=9,
        leading=11,
        textColor="#444",
        spaceBefore=2,
        spaceAfter=10,
    )
    title_style = ParagraphStyle(
        "EvalTitle",
        parent=_DEFAULT_STYLES["Title"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        spaceAfter=14,
    )

    flow: list = [Paragraph(_escape_html(title), title_style)]
    total_chars = 0
    for index, (heading, text, images) in enumerate(sections):
        if index > 0 and page_break_between_sections:
            flow.append(PageBreak())
        if heading:
            flow.append(Paragraph(_escape_html(heading), heading_style))
        for paragraph in _normalise_paragraphs(text):
            total_chars += len(paragraph)
            flow.append(Paragraph(_escape_html(paragraph), body_style))
            flow.append(Spacer(1, 4))
        for image in images or []:
            try:
                img_flow = _make_image_flowable(image)
            except Exception:  # noqa: BLE001 — bad image shouldn't kill PDF
                continue
            grouped = [img_flow]
            if image.caption:
                grouped.append(Paragraph(_escape_html(image.caption), caption_style))
            else:
                grouped.append(Spacer(1, 8))
            flow.append(KeepTogether(grouped))

    doc.build(flow)
    pdf_bytes = buffer.getvalue()
    if deterministic:
        pdf_bytes = _scrub_dates(pdf_bytes)
    output_path.write_bytes(pdf_bytes)

    n_pages = max(1, total_chars // 3000 + len(sections))
    return RenderedPdf(path=output_path, n_pages_estimate=n_pages, n_chars=total_chars)


def render_text_files_to_pdf(
    *,
    title: str,
    files: Iterable[Path],
    output_path: Path,
    deterministic: bool = True,
) -> RenderedPdf:
    """Convenience wrapper: read a list of text files, render to one PDF.

    The heading of each section is the file's name (no extension), so
    e.g. ``admission_note.txt`` becomes a section header ``admission_note``
    in the rendered PDF. Useful for any text-only benchmark that ships
    a corpus as separate ``.txt`` / ``.md`` shards per logical document.
    """

    sections: list[tuple[str | None, str]] = []
    for path in files:
        path = Path(path)
        text = path.read_text(encoding="utf-8")
        sections.append((path.stem, text))
    return render_pdf(
        title=title,
        sections=sections,
        output_path=output_path,
        deterministic=deterministic,
    )


# Tiny self-check — handy when debugging.
def _self_test() -> None:  # pragma: no cover
    out = Path("./_render_self_test.pdf")
    sections = [
        ("intro", "Hello world.\n\nThis is a test."),
        ("body", "Line one.\nLine two."),
    ]
    rendered = render_pdf(title="Self test", sections=sections, output_path=out)
    print(f"wrote {rendered.path} ({rendered.n_chars} chars)")


# Importing ``datetime`` keeps the timezone helper handy if a future
# benchmark wants to embed a real timestamp without losing determinism.
_NOW_FROZEN = datetime(2026, 5, 11, tzinfo=UTC)
