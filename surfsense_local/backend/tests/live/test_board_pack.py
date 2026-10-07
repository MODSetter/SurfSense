"""Live case 8: a vague request, "something I can send to the board", then a section added at the end.

The agent picks the format itself; it must make a Word file or a PDF, not ask, and say what it assumed.
"""

import io
import re

import docx
import pytest

from tests.live.live_agent import LiveAgent, answer, steps
from tests.live.pdf_file import PdfFile
from tests.live.turn_renders import (
    Version,
    assert_next_version,
    assert_pages_checked,
    last_version,
)
from tests.live.word_file import WordFile

pytestmark = pytest.mark.live

CASE = "board-pack"
TURNS = (
    "Make me something I can send to the board from these.",
    "Add a short 'Decisions needed' section at the end.",
)
_SAYS_WHAT_IT_ASSUMED = re.compile(
    r"assum|I went with|I chose|I picked|I opted|I've gone with|I have gone with",
    re.IGNORECASE,
)
_NAMES_THE_FORMAT = re.compile(r"\bWord\b|\.docx|\bPDF\b", re.IGNORECASE)


async def test_the_agent_turns_a_vague_ask_into_a_board_document(
    live: LiveAgent,
) -> None:
    """v1 is a Word file or a PDF with the format and assumptions stated; v2 ends with the decisions."""
    results = await live.note("Q3 2026 results", _RESULTS)
    hiring = await live.note("Hiring update, September 2026", _HIRING)
    risks = await live.upload("Risk register extract.docx", _risk_register())
    await live.wait_ready(results, hiring, risks)
    thread = await live.thread()

    first = await live.turn(thread, TURNS[0])
    assert not steps(first, "surfsense_create_artifact"), (
        "turn 1 sent the board document to Studio instead of rendering it"
    )
    draft = await last_version(live, first, "turn 1")
    assert draft.format in {"docx", "pdf"}, f"turn 1 made {draft}"
    await assert_pages_checked(live, first, "turn 1")
    said = answer(first)
    assert _NAMES_THE_FORMAT.search(said), f"turn 1 does not say what it made: {said}"
    assert _SAYS_WHAT_IT_ASSUMED.search(said), (
        f"turn 1 does not say what it assumed: {said}"
    )

    second = await live.turn(thread, TURNS[1])
    edit = await last_version(live, second, "turn 2")
    assert_next_version(draft, edit, "turn 2")
    await assert_pages_checked(live, second, "turn 2")
    ending = await _last_heading(live, edit)
    assert "decision" in ending.lower(), (
        f"v{edit.number} ends with '{ending}', not the decisions"
    )


async def _last_heading(live: LiveAgent, version: Version) -> str:
    """The document's last heading, Word or PDF."""
    data = await live.file(version.id)
    if version.format == "docx":
        headings = [h.text for h in WordFile(data).headings]
    else:
        headings = PdfFile(data).headings
    return headings[-1] if headings else ""


_RESULTS = (
    "Q3 2026 (July-September), Kestrel Data Works. Revenue 2.41 million EUR, up "
    "18% on Q3 2025 and 4% above plan. Gross margin 61% (plan 63%): two fixed-"
    "price projects ran over, Halvorsen discovery by 22 days and the Aurora "
    "migration estimate. Operating cash flow 310,000 EUR; cash at 30 September "
    "1.9 million EUR, about nine months of costs. New customers: 5, lost: 1 "
    "(Brandt Logistics, moved in-house). Recurring support revenue is now 27% of "
    "the total, up from 21% a year ago. Pipeline for Q4: 3.2 million EUR "
    "weighted, of which Halvorsen rollout 52,000 EUR is waiting on their board."
)
_HIRING = (
    "Headcount 38 on 30 September (plan 41). We hired two data engineers in "
    "August. Three senior roles are open: a delivery lead for the Nordics, a "
    "machine learning engineer and a second project manager. The delivery lead "
    "search has run 14 weeks; the recruiter suggests raising the salary band by "
    "8% or hiring in Tallinn instead. Attrition in the last twelve months: 4 "
    "people, 11%."
)


def _risk_register() -> bytes:
    """Three open risks with owners and what we propose."""
    register = docx.Document()
    register.add_heading("Risk register: open items for Q4 2026", 1)
    table = register.add_table(rows=1, cols=4)
    table.style = "Table Grid"
    for cell, label in zip(
        table.rows[0].cells,
        ("Risk", "Likelihood", "Owner", "Proposed action"),
        strict=True,
    ):
        cell.text = label
    for row in (
        (
            "Fixed-price overruns erode margin",
            "High",
            "COO",
            "Move discovery work to time and materials from January",
        ),
        (
            "Delivery lead role unfilled into peak",
            "Medium",
            "CEO",
            "Approve the 8% higher band or a Tallinn hire",
        ),
        (
            "One customer is 19% of revenue",
            "Medium",
            "CFO",
            "Cap any one customer at 15% of the 2027 plan",
        ),
    ):
        cells = table.add_row().cells
        for cell, text in zip(cells, row, strict=True):
            cell.text = text
    out = io.BytesIO()
    register.save(out)
    return out.getvalue()
