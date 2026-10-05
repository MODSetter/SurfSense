"""Live case 3: the demo's three turns, from sources ingested by the real pipeline to a Word proposal, its edit and a PDF.

07-create-and-edit-mvp, "What the user sees".
"""

import hashlib
import io
import zipfile

import docx
import pytest

from modules.documents.source_figures import figure_file
from shared.db import create_session_factory
from tests.live import demo_sources
from tests.live.live_agent import LiveAgent, steps
from tests.live.turn_renders import assert_pages_checked, ready_versions, sees_pages

pytestmark = pytest.mark.live

CASE = "demo-flow"
TURNS = (
    "Draft a two-page client proposal from these sources as a Word document, "
    "with a pricing table.",
    "Make the executive summary shorter, add a timeline table and a bar chart of "
    "the yearly costs, and put our logo on the cover.",
    "Now a PDF version for the client.",
)


async def test_the_agent_drafts_edits_and_exports_a_proposal(live: LiveAgent) -> None:
    """Two versions of the Word file and a PDF; the edit has the timeline, the chart and the logo.

    A self-check may render extra versions within a turn, so the edit is the
    last Word version the second turn rendered, not necessarily v2. A failed
    render keeps its number, so a document's first ready version may be v2.
    """
    report = await live.upload(
        "Fleet telematics assessment.pdf", demo_sources.assessment_report()
    )
    logo = await live.upload("Kestrel logo.png", demo_sources.our_logo())
    notes = await live.upload("Kickoff notes.docx", demo_sources.kickoff_notes())
    await live.wait_ready(report, logo, notes)
    thread = await live.thread()

    replies = [await live.turn(thread, text) for text in TURNS]

    artifacts = await live.artifacts()
    made = {a["id"]: a for a in artifacts if a["status"] == "ready"}
    documents = ready_versions(artifacts)
    word = [key for key in documents if key[0] == "docx"]
    assert word, "no Word document was made"
    root = word[0][1]
    assert len(documents[word[0]]) >= 2, f"no second Word version: {documents[word[0]]}"
    assert any(f == "pdf" for f, _ in documents), "no PDF was made"

    rendered_in_the_edit = [
        made[s["artifact"]["id"]]
        for s in steps(replies[1], "surfsense_render_document")
        if s["artifact"] is not None and s["artifact"]["id"] in made
    ]
    assert rendered_in_the_edit, "the edit rendered no version"
    edit = rendered_in_the_edit[-1]
    assert (edit["format"], edit["version"]["root_id"]) == ("docx", root), edit
    name = f"v{edit['version']['number']}"
    data = await live.file(edit["id"])
    tables = docx.Document(io.BytesIO(data)).tables
    assert len(tables) >= 2, (
        f"{name} has {len(tables)} tables, not pricing and timeline"
    )
    pictures = _pictures(data)
    logo_png = _logo_png(live, logo)
    assert hashlib.sha256(logo_png).hexdigest() in pictures, (
        f"{name} does not place our logo"
    )
    assert len(pictures) >= 2, f"{name} has no chart beside the logo"

    if not sees_pages(live):
        return
    # Renders attach their pages, so no `read` of a preview is needed.
    assert [e for e in live.proxy.exchanges if e.images], (
        "no page image reached the model"
    )
    # Any image counts above, even a refused one or the logo; these need the pages.
    for turn, reply in enumerate(replies, start=1):
        await assert_pages_checked(live, reply, f"turn {turn}")


def _pictures(word: bytes) -> set[str]:
    """The hash of every picture the Word file holds."""
    with zipfile.ZipFile(io.BytesIO(word)) as package:
        return {
            hashlib.sha256(package.read(name)).hexdigest()
            for name in package.namelist()
            if name.startswith("word/media/")
        }


def _logo_png(live: LiveAgent, logo_id: int) -> bytes:
    """The logo as SurfSense keeps it for scripts: the source's one figure."""
    with create_session_factory(live.engine)() as session:
        return figure_file(session, live.workspace_id, f"{logo_id}-1").read_bytes()
