"""The Word snapshots the API asks Electron for, and what the waiter gets back."""

import threading
from pathlib import Path

import pytest

from modules.agent.previews.docx_snapshots import (
    DocxSnapshots,
    SnapshotRequest,
    SnapshotUnavailableError,
)

pytestmark = pytest.mark.unit


class Clock:
    """A monotonic clock the test moves by hand."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _served_by(snapshots: DocxSnapshots, answer) -> threading.Thread:
    """Electron's side: poll until a request arrives, then answer it once."""

    def serve() -> None:
        while (request := snapshots.next_request()) is None:
            threading.Event().wait(0.01)
        answer(request)

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    return thread


def test_without_electron_polling_a_snapshot_is_refused_at_once() -> None:
    """With no Electron polling, the tool does not wait 30 s for nothing."""
    snapshots = DocxSnapshots()

    with pytest.raises(SnapshotUnavailableError, match="desktop app"):
        snapshots.snapshot(format="docx", artifact_id=7, timeout=5)

    assert snapshots.next_request() is None


def test_electron_gets_the_request_once_and_its_pdf_reaches_the_waiter() -> None:
    """A request is handed out once, and its PDF goes to the one who asked."""
    snapshots = DocxSnapshots()
    snapshots.next_request()  # Electron is polling.
    handed: list[SnapshotRequest] = []

    def answer(request: SnapshotRequest) -> None:
        handed.append(request)
        assert snapshots.next_request() is None  # claimed, so not handed out twice
        assert snapshots.deliver(request.id, b"%PDF-1.7 pages")

    thread = _served_by(snapshots, answer)
    pdf = snapshots.snapshot(format="docx", artifact_id=7, timeout=5)
    thread.join(timeout=5)

    assert pdf == b"%PDF-1.7 pages"
    assert [(r.artifact_id, r.format, r.pages) for r in handed] == [(7, "docx", "1-4")]


def test_a_failure_electron_reports_reaches_the_waiter_as_its_reason() -> None:
    """Electron's reason for failing is what the waiter is told."""
    snapshots = DocxSnapshots()
    snapshots.next_request()

    thread = _served_by(
        snapshots, lambda request: snapshots.fail(request.id, "docx-preview threw")
    )
    with pytest.raises(SnapshotUnavailableError, match="docx-preview threw"):
        snapshots.snapshot(format="docx", artifact_id=7, timeout=5)
    thread.join(timeout=5)


def test_an_unanswered_request_times_out_and_a_late_answer_is_refused() -> None:
    """A waiter stops at its time box and leaves no request behind."""
    snapshots = DocxSnapshots()
    snapshots.next_request()
    claimed: list[SnapshotRequest] = []

    thread = _served_by(snapshots, claimed.append)
    with pytest.raises(SnapshotUnavailableError, match="did not finish within"):
        snapshots.snapshot(format="docx", artifact_id=7, timeout=0.2)
    thread.join(timeout=5)

    assert not snapshots.deliver(claimed[0].id, b"%PDF-1.7 late")
    assert snapshots.next_request() is None


def test_electron_counts_as_gone_a_minute_after_its_last_poll() -> None:
    """An Electron that stopped polling is not waited for."""
    clock = Clock()
    snapshots = DocxSnapshots(clock=clock)
    snapshots.next_request()

    clock.now += 61

    with pytest.raises(SnapshotUnavailableError, match="desktop app"):
        snapshots.snapshot(format="docx", artifact_id=7, timeout=5)


def test_an_unknown_request_cannot_be_answered() -> None:
    """Nothing can be answered that was never asked."""
    snapshots = DocxSnapshots()

    assert not snapshots.deliver("no-such-request", b"%PDF-1.7")
    assert not snapshots.fail("no-such-request", "nothing")


def test_a_sources_file_is_handed_out_only_while_its_request_is_being_printed(
    tmp_path: Path,
) -> None:
    """The file route serves a source's original by request id, and only until it is answered."""
    snapshots = DocxSnapshots()
    snapshots.next_request()
    original = tmp_path / "Brand.pptx"
    served: list[Path | None] = []

    def answer(request: SnapshotRequest) -> None:
        served.append(snapshots.source_file(request.id))
        snapshots.deliver(request.id, b"%PDF-1.7 slides")

    thread = _served_by(snapshots, answer)
    snapshots.snapshot(format="pptx", source_file=original, pages="2,5", timeout=5)
    thread.join(timeout=5)

    assert served == [original]
    assert snapshots.source_file("no-such-request") is None


def test_an_artifacts_request_hands_out_no_source_file() -> None:
    """An artifact is printed from its own route; the source-file route has nothing for it."""
    snapshots = DocxSnapshots()
    snapshots.next_request()
    seen: list[Path | None] = []

    def answer(request: SnapshotRequest) -> None:
        seen.append(snapshots.source_file(request.id))
        snapshots.deliver(request.id, b"%PDF-1.7")

    thread = _served_by(snapshots, answer)
    snapshots.snapshot(format="pptx", artifact_id=7, timeout=5)
    thread.join(timeout=5)

    assert seen == [None]


def test_a_pptx_failure_names_powerpoint() -> None:
    """The model reads which kind of file did not print."""
    snapshots = DocxSnapshots()

    with pytest.raises(SnapshotUnavailableError, match="PowerPoint slides are drawn"):
        snapshots.snapshot(format="pptx", artifact_id=7, timeout=5)
