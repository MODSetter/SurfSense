from collections.abc import Callable
from pathlib import Path

from worker.studio.builders.types import Builder, Built, Source
from worker.studio.builders.util import as_list, as_text, parse_json, slug

MIME = "application/pdf"

_SCHEMA = (
    'Return only JSON, no prose: {"title": str, "sections": '
    '[{"heading": str, "paragraphs": [str]}]}.'
)

# A Unicode TTF so non-Latin sources render; the core PDF fonts are Latin-1 only.
# ponytail: probes the OS font here. Ceiling: a machine without DejaVu falls back
# to Helvetica and non-Latin text degrades to '?'. Upgrade path: bundle the TTF
# in a model pack like bge-small, then point this at models_dir.
_UNICODE_FONTS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
)


def prompt(_sources: list[Source], user_prompt: str | None) -> str:
    focus = f" Emphasise: {user_prompt}." if user_prompt else ""
    return (
        "Write a structured document from the sources below, using their facts "
        "only." + focus + " " + _SCHEMA
    )


def build(raw: str, _sources: list[Source]) -> Built:
    spec = parse_json(raw)
    title = as_text(spec.get("title")) or "Document"

    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    family, safe = _font(pdf)

    # w=0 fills the line; NEXT/LMARGIN returns to the left so the next block has
    # the full width again instead of the sliver left after the previous one.
    def block(text: str, size: int, height: float) -> None:
        pdf.set_font(family, size=size)
        pdf.multi_cell(0, height, safe(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    lines = [f"# {title}"]
    block(title, 20, 10)
    pdf.ln(2)

    for section in as_list(spec.get("sections")):
        if not isinstance(section, dict):
            continue
        heading = as_text(section.get("heading"))
        if heading:
            lines.append(f"\n## {heading}")
            block(heading, 14, 8)
        for paragraph in as_list(section.get("paragraphs")):
            text = as_text(paragraph)
            if text:
                lines.append(text)
                block(text, 11, 6)
                pdf.ln(1)

    return Built(
        title=title,
        markdown="\n".join(lines),
        primary=bytes(pdf.output()),
        primary_mime=MIME,
        primary_filename=f"{slug(title, 'document')}.pdf",
    )


def _font(pdf: object) -> tuple[str, Callable[[str], str]]:
    """A Unicode font if one is on disk, else Helvetica with Latin-1 fallback."""
    for candidate in _UNICODE_FONTS:
        if Path(candidate).is_file():
            pdf.add_font("body", "", candidate)  # type: ignore[attr-defined]
            return "body", lambda text: text
    return "Helvetica", lambda text: text.encode("latin-1", "replace").decode("latin-1")


pdf = Builder(key="pdf", prompt=prompt, build=build)
