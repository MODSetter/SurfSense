"""Live case 9: two reports merged under a DRAFT watermark, and a form filled, in one turn.

Both are jobs for the PDF tools, not for a document script: the user's files
must come back as new PDFs in Studio and stay as they were.
"""

import io

import pypdf
import pypdfium2 as pdfium
import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from tests.live.live_agent import LiveAgent
from tests.live.turn_renders import made_ids

pytestmark = pytest.mark.live

CASE = "pdf-merge-and-form"
TURN = (
    "Merge the Bergen and Stavanger terminal reports into one PDF, Bergen first, "
    "with a DRAFT watermark across every page. Then fill in the site visit "
    "request form for me: Ingrid Halvorsen from Fjordline Logistics, "
    "ingrid.halvorsen@fjordline.example, visiting the Stavanger terminal on "
    "14 November 2026. I have done the safety briefing."
)
# Each report's pages, as each page names itself.
BERGEN = [f"Bergen terminal Q3 2026, page {n} of 3" for n in (1, 2, 3)]
STAVANGER = [f"Stavanger terminal Q3 2026, page {n} of 2" for n in (1, 2)]
SITES = ["Bergen terminal", "Stavanger terminal", "Haugesund depot"]
FILLED_TEXT = {
    "Visitor name": "Ingrid Halvorsen",
    "Company": "Fjordline Logistics",
    "Email": "ingrid.halvorsen@fjordline.example",
}
PAGE_TOOLS = ("surfsense_pdf_pages", "surfsense_pdf_stamp")
FORM_TOOL = "surfsense_pdf_form"


async def test_the_agent_merges_stamps_and_fills_with_the_pdf_tools(
    live: LiveAgent,
) -> None:
    """A merged PDF with every page stamped, a filled copy of the form, and the three sources untouched."""
    uploaded = {
        "Bergen terminal Q3 report.pdf": _report(BERGEN),
        "Stavanger terminal Q3 report.pdf": _report(STAVANGER),
        "Site visit request.pdf": _form(),
    }
    ids = {name: await live.upload(name, data) for name, data in uploaded.items()}
    await live.wait_ready(*ids.values())
    thread = await live.thread()

    frames = await live.turn(thread, TURN)

    made = [i for tool in PAGE_TOOLS for i in made_ids(frames, tool)]
    assert made, "the turn made no PDF with the page or stamp tools"
    pages_of = {i: _page_texts(await live.file(i)) for i in made}
    merged = [i for i, pages in pages_of.items() if _is_stamped_merge(pages)]
    assert merged, (
        "no PDF holds Bergen's pages then Stavanger's, each with DRAFT: "
        f"{ {i: [p[:60] for p in pages] for i, pages in pages_of.items()} }"
    )

    filled = made_ids(frames, FORM_TOOL)
    assert filled, "the turn filled no form with the form tool"
    values = _form_values(await live.file(filled[-1]))
    for field, wanted in FILLED_TEXT.items():
        assert _same(values.get(field), wanted), (
            f"{field} holds {values.get(field)!r}, not {wanted!r}"
        )
    assert values.get("Site") == "Stavanger terminal", (
        f"Site holds {values.get('Site')!r}"
    )
    assert _is_the_visit_date(values.get("Visit date")), (
        f"Visit date holds {values.get('Visit date')!r}"
    )
    assert values.get("Safety briefing done") not in (None, "", "/Off", "Off"), (
        "the safety briefing box is not ticked"
    )

    for name, data in uploaded.items():
        assert live.original(ids[name]) == data, f"{name} was changed"


def _is_stamped_merge(pages: list[str]) -> bool:
    """Bergen's three pages then Stavanger's two, and DRAFT on every one."""
    wanted = [*BERGEN, *STAVANGER]
    return len(pages) == len(wanted) and all(
        own in _flat(page) and "DRAFT" in page.upper()
        for own, page in zip(wanted, pages, strict=True)
    )


def _is_the_visit_date(value: str | None) -> bool:
    """14 November 2026 in any common spelling: 2026-11-14, 14/11/2026, 14 Nov 2026."""
    text = (value or "").lower()
    return (
        "2026" in text
        and "14" in text
        and ("nov" in text or "11" in text.replace("2026", ""))
    )


def _same(value: str | None, wanted: str) -> bool:
    return value is not None and _flat(value).casefold() == wanted.casefold()


def _flat(text: str) -> str:
    return " ".join(text.split())


def _page_texts(data: bytes) -> list[str]:
    document = pdfium.PdfDocument(data)
    try:
        return [page.get_textpage().get_text_range() for page in document]
    finally:
        document.close()


def _form_values(data: bytes) -> dict[str, str]:
    """Each field's value; the user asked for no locked copy, so the fields stay."""
    fields = pypdf.PdfReader(io.BytesIO(data)).get_fields() or {}
    assert fields, "the filled form was flattened, though nobody asked to lock it"
    return {name: str(field.get("/V", "")) for name, field in fields.items()}


def _report(pages: list[str]) -> bytes:
    """A terminal's quarterly report: each page names itself, then a few facts."""
    out = io.BytesIO()
    drawing = canvas.Canvas(out, pagesize=A4)
    for number, heading in enumerate(pages, 1):
        drawing.setFont("Helvetica-Bold", 16)
        drawing.drawString(72, 780, heading)
        drawing.setFont("Helvetica", 11)
        for row, line in enumerate(_FACTS[number - 1]):
            drawing.drawString(72, 740 - 18 * row, line)
        drawing.showPage()
    drawing.save()
    return out.getvalue()


_FACTS = [
    [
        "Containers handled: 41,280 TEU, up 6% on Q2.",
        "Average truck turnaround: 38 minutes.",
        "Crane availability: 96.4%.",
    ],
    [
        "Safety: two near misses reported, no lost-time injuries.",
        "Gate 3 resurfacing finished on 22 August.",
    ],
    [
        "Outlook: the new reefer stacks open in January.",
        "Headcount at quarter end: 212.",
    ],
]


def _form() -> bytes:
    """The terminal operator's one-page site visit request, with fields to fill."""
    out = io.BytesIO()
    drawing = canvas.Canvas(out, pagesize=A4)
    fields = drawing.acroForm
    drawing.setFont("Helvetica-Bold", 16)
    drawing.drawString(72, 790, "Site visit request")
    drawing.setFont("Helvetica", 11)
    rows = ["Visitor name", "Company", "Email", "Visit date"]
    for row, name in enumerate(rows):
        y = 740 - 40 * row
        drawing.drawString(72, y + 5, name)
        fields.textfield(name=name, x=200, y=y, width=300, height=20)
    drawing.drawString(72, 585, "Site")
    fields.choice(
        name="Site", options=SITES, value=SITES[0], x=200, y=580, width=200, height=20
    )
    drawing.drawString(100, 545, "I have completed the online safety briefing")
    fields.checkbox(name="Safety briefing done", x=72, y=540, size=15)
    drawing.showPage()
    drawing.save()
    return out.getvalue()
