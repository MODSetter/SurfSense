"""The LibreOffice stand-in for Electron's Word snapshots, on a machine that may lack LibreOffice."""

import sys

import pytest

from tests.live import word_printer
from tests.live.word_printer import WordPrinter

pytestmark = pytest.mark.unit

# Nothing listens here: a printer that polled would only meet refused connections.
NOWHERE = "http://127.0.0.1:9"


def test_without_libreoffice_the_run_goes_on_without_word_pages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The cases that need no Word preview still run, and the reason is kept for the run folder."""
    monkeypatch.setattr(word_printer, "SOFFICE", None)

    with WordPrinter(NOWHERE) as printer:
        pass

    assert printer.summary() == {
        "unavailable": "OSError: LibreOffice is not installed",
        "printed": 0,
        "failures": [],
    }


def test_a_libreoffice_that_cannot_print_is_the_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A soffice that exits non-zero leaves Word previews to say the desktop app is not running."""
    # Python refuses LibreOffice's arguments and exits non-zero, as a broken soffice would.
    monkeypatch.setattr(word_printer, "SOFFICE", sys.executable)

    with WordPrinter(NOWHERE) as printer:
        pass

    reason = printer.summary()["unavailable"]
    assert reason is not None
    assert reason.startswith("CalledProcessError")
