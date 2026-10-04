"""The Word snapshots the API asks Electron for, and what the waiter gets back."""

import threading

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
        snapshots.snapshot(artifact_id=7, timeout=5)

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
    pdf = snapshots.snapshot(artifact_id=7, timeout=5)
    thread.join(timeout=5)

    assert pdf == b"%PDF-1.7 pages"
    assert [request.artifact_id for request in handed] == [7]


def test_a_failure_electron_reports_reaches_the_waiter_as_its_reason() -> None:
    """Electron's reason for failing is what the waiter is told."""
    snapshots = DocxSnapshots()
    snapshots.next_request()

    thread = _served_by(
        snapshots, lambda request: snapshots.fail(request.id, "docx-preview threw")
    )
    with pytest.raises(SnapshotUnavailableError, match="docx-preview threw"):
        snapshots.snapshot(artifact_id=7, timeout=5)
    thread.join(timeout=5)


def test_an_unanswered_request_times_out_and_a_late_answer_is_refused() -> None:
    """A waiter stops at its time box and leaves no request behind."""
    snapshots = DocxSnapshots()
    snapshots.next_request()
    claimed: list[SnapshotRequest] = []

    thread = _served_by(snapshots, claimed.append)
    with pytest.raises(SnapshotUnavailableError, match="did not finish within"):
        snapshots.snapshot(artifact_id=7, timeout=0.2)
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
        snapshots.snapshot(artifact_id=7, timeout=5)


def test_an_unknown_request_cannot_be_answered() -> None:
    """Nothing can be answered that was never asked."""
    snapshots = DocxSnapshots()

    assert not snapshots.deliver("no-such-request", b"%PDF-1.7")
    assert not snapshots.fail("no-such-request", "nothing")
