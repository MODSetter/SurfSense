"""Studio's PowerPoint and Excel scripts run in the real script runner's process."""

import time
from functools import partial

import pytest

from modules.llm.profile import Tier
from modules.llm.resolution import ResolvedGeneration
from worker.document_script.run import run_document_script
from worker.studio.office import pipeline as office
from worker.studio.office.pptx import pptx
from worker.studio.office.xlsx import xlsx
from worker.studio.script_document import pipeline as script_document
from worker.studio.shared import generate

pytestmark = pytest.mark.integration

MODEL = ResolvedGeneration(
    type("Selection", (), {"name": "qwen3:8b", "tier": Tier.CAPABLE})(), None
)

SECRET = "fake-worker-secret-1999"

_WORKBOOK_OF_THE_SECRET = (
    "# title: Environment\n"
    "import os\n"
    "import xlsxwriter\n"
    "book = xlsxwriter.Workbook(os.environ['OUTPUT_PATH'])\n"
    "sheet = book.add_worksheet('Seen')\n"
    "sheet.write(0, 0, os.environ.get('SURFSENSE_LOCAL_SECRET', 'no secret'))\n"
    "sheet.write(1, 0, os.environ.get('STUDIO_FAKE_API_KEY', 'no key'))\n"
    "book.close()\n"
)

_DECK = (
    "# title: Cassini\n"
    "import os\n"
    "from pptx import Presentation\n"
    "deck = Presentation()\n"
    "slide = deck.slides.add_slide(deck.slide_layouts[1])\n"
    "slide.shapes.title.text = 'Cassini'\n"
    "slide.placeholders[1].text = 'Arrival in 2004.'\n"
    "deck.save(os.environ['OUTPUT_PATH'])\n"
)


def _model(monkeypatch: pytest.MonkeyPatch, reply: str) -> None:
    monkeypatch.setattr(generate, "run_model", lambda *a, **k: reply)


def test_a_deck_script_writes_a_real_deck(monkeypatch: pytest.MonkeyPatch) -> None:
    """The happy path through the real child: bytes, title and the deck's text."""
    _model(monkeypatch, _DECK)

    built = office.render(pptx, MODEL, [], None)

    assert built.primary is not None
    assert built.primary.startswith(b"PK\x03\x04")
    assert built.title == "Cassini"
    assert "Arrival in 2004." in built.markdown


def test_a_script_sees_none_of_the_workers_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The script's environment is built from scratch, not inherited."""
    monkeypatch.setenv("SURFSENSE_LOCAL_SECRET", SECRET)
    monkeypatch.setenv("STUDIO_FAKE_API_KEY", SECRET)
    _model(monkeypatch, _WORKBOOK_OF_THE_SECRET)

    built = office.render(xlsx, MODEL, [], None)

    assert SECRET not in built.markdown
    assert "no secret" in built.markdown
    assert "no key" in built.markdown


def test_a_script_that_loops_forever_is_stopped_at_its_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each attempt is killed at the limit; the job fails instead of waiting."""
    monkeypatch.setattr(
        script_document,
        "run_document_script",
        partial(run_document_script, timeout_seconds=1),
    )
    _model(monkeypatch, "while True:\n    pass\n")
    started = time.monotonic()

    with pytest.raises(RuntimeError, match="timed out after 1 s"):
        office.render(pptx, MODEL, [], None)

    assert time.monotonic() - started < 60
