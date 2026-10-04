"""The LibreOffice stand-in for Electron's Word snapshots, on a machine that may lack LibreOffice."""

import sys
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from tests.live import word_printer
from tests.live.word_printer import SOFFICE, WordPrinter

pytestmark = pytest.mark.unit

needs_libreoffice = pytest.mark.skipif(
    SOFFICE is None, reason="the printer polls only once LibreOffice has printed"
)

# Nothing listens here: a printer that polled would only meet refused connections.
NOWHERE = "http://127.0.0.1:9"


def test_without_libreoffice_the_run_goes_on_without_word_pages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The cases that need no Word preview still run, and the reason is kept for the run folder."""
    monkeypatch.setattr(word_printer, "SOFFICE", None)

    with WordPrinter(NOWHERE, "a-key") as printer:
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

    with WordPrinter(NOWHERE, "a-key") as printer:
        pass

    reason = printer.summary()["unavailable"]
    assert reason is not None
    assert reason.startswith("CalledProcessError")


class _SnapshotRoutes(BaseHTTPRequestHandler):
    """The API's snapshot routes with nothing to print, refusing a caller without the key."""

    def do_GET(self) -> None:
        api: SnapshotApi = self.server.api  # type: ignore[attr-defined]
        api.presented.append(self.headers.get("Authorization"))
        held = self.headers.get("Authorization") == f"Bearer {api.key}"
        self.send_response(204 if held else 401)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *args: object) -> None:
        pass


@dataclass
class SnapshotApi:
    key: str
    url: str = ""
    presented: list[str | None] = field(default_factory=list)

    def polled(self) -> bool:
        """Whether the printer has polled within 10 s."""
        deadline = time.monotonic() + 10
        while not self.presented and time.monotonic() < deadline:
            time.sleep(0.05)
        return bool(self.presented)


@pytest.fixture
def snapshot_api() -> Iterator[SnapshotApi]:
    """The snapshot routes on a loopback port of their own."""
    api = SnapshotApi(key="the-key-electron-minted")
    server = ThreadingHTTPServer(("127.0.0.1", 0), _SnapshotRoutes)
    server.api = api  # type: ignore[attr-defined]
    api.url = f"http://127.0.0.1:{server.server_address[1]}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield api
    server.shutdown()
    server.server_close()


@needs_libreoffice
def test_the_printer_presents_the_key_the_api_was_given(
    snapshot_api: SnapshotApi,
) -> None:
    """As Electron does: the snapshot routes refuse a caller without the API's key."""
    with WordPrinter(snapshot_api.url, snapshot_api.key) as printer:
        assert snapshot_api.polled()

    assert set(snapshot_api.presented) == {f"Bearer {snapshot_api.key}"}
    assert printer.summary()["failures"] == []


@needs_libreoffice
def test_a_refused_poll_is_kept_once_for_the_run_folder(
    snapshot_api: SnapshotApi,
) -> None:
    """Otherwise every Word preview says the desktop app is not running, and nothing says why."""
    with WordPrinter(snapshot_api.url, "a-wrong-key") as printer:
        assert snapshot_api.polled()
        time.sleep(1.2)

    assert printer.summary()["failures"] == [
        "the API answered 401 to /agent/previews/docx-snapshots/next"
    ]
