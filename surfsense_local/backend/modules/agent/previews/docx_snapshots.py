"""Word documents and PowerPoint decks waiting for Electron to print them to PDF.

The app has no Office converter. Electron lays the file out with the in-app
viewer's library (docx-preview, or pptx-renderer for a deck) and prints it; it
polls for requests as it polls for the image runtime, so the API needs no way
to reach it. The name is the routes', kept from when only Word was printed.
"""

import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

# Electron polls every 2 s but not while it prints, which takes seconds; a
# minute of silence means it is gone (or never ran: the Docker stack, tests).
PRESENCE_SECONDS = 60
# printToPDF's pageRanges: a version's previews are its first four pages.
FIRST_PAGES = "1-4"

SnapshotFormat = Literal["docx", "pptx"]

# What the model is told failed to print.
_PRINTED: dict[str, tuple[str, str]] = {
    "docx": ("Word pages", "Word preview"),
    "pptx": ("PowerPoint slides", "PowerPoint preview"),
}


class SnapshotUnavailableError(Exception):
    """No PDF came back, said in a sentence the model can read."""


@dataclass(frozen=True)
class SnapshotRequest:
    """What Electron is handed: which file to print, laid out as which format, which pages.

    The file is an artifact's primary file, or a source's original, which the
    route serves only while this request is being printed.
    """

    id: str
    format: SnapshotFormat
    pages: str
    artifact_id: int | None = None
    source_file: Path | None = None


@dataclass
class _Pending:
    request: SnapshotRequest
    claimed: bool = False
    answered: threading.Event = field(default_factory=threading.Event)
    pdf: bytes | None = None
    failure: str | None = None


class DocxSnapshots:
    """The requests between the tool that waits and the routes Electron calls."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._pending: dict[str, _Pending] = {}
        self._last_poll: float | None = None

    def snapshot(
        self,
        *,
        format: SnapshotFormat,
        timeout: float,
        artifact_id: int | None = None,
        source_file: Path | None = None,
        pages: str = FIRST_PAGES,
    ) -> bytes:
        """Block until Electron sends those pages of the file as a PDF, in page order."""
        if (artifact_id is None) == (source_file is None):
            raise ValueError("print either an artifact or a source's file")
        printed, preview = _PRINTED[format]
        with self._lock:
            if not self._electron_polling():
                raise SnapshotUnavailableError(
                    f"{printed} are drawn by the SurfSense desktop app, which is "
                    "not running beside this server."
                )
            request = SnapshotRequest(
                uuid.uuid4().hex, format, pages, artifact_id, source_file
            )
            pending = _Pending(request)
            self._pending[request.id] = pending
        try:
            answered = pending.answered.wait(timeout)
        finally:
            with self._lock:
                self._pending.pop(request.id, None)
        if not answered:
            raise SnapshotUnavailableError(
                f"The {preview} did not finish within {timeout:g} s."
            )
        if pending.pdf is None:
            raise SnapshotUnavailableError(f"The {preview} failed: {pending.failure}")
        return pending.pdf

    def next_request(self) -> SnapshotRequest | None:
        """Electron's poll: the oldest request no one has taken, now taken."""
        with self._lock:
            self._last_poll = self._clock()
            for pending in self._pending.values():
                if not pending.claimed:
                    pending.claimed = True
                    return pending.request
        return None

    def source_file(self, request_id: str) -> Path | None:
        """The source's file a taken, unanswered request prints; None for anything else."""
        with self._lock:
            pending = self._pending.get(request_id)
            if pending is None or not pending.claimed or pending.answered.is_set():
                return None
            return pending.request.source_file

    def deliver(self, request_id: str, pdf: bytes) -> bool:
        """Hand the waiter its PDF; False when no one waits for it any more."""
        return self._answer(request_id, pdf=pdf)

    def fail(self, request_id: str, reason: str) -> bool:
        """Tell the waiter why there is no PDF; False when no one waits any more."""
        return self._answer(request_id, failure=reason)

    def _answer(
        self, request_id: str, *, pdf: bytes | None = None, failure: str | None = None
    ) -> bool:
        with self._lock:
            pending = self._pending.get(request_id)
            if pending is None or pending.answered.is_set():
                return False
            pending.pdf, pending.failure = pdf, failure
            pending.answered.set()
            return True

    def _electron_polling(self) -> bool:
        return (
            self._last_poll is not None
            and self._clock() - self._last_poll <= PRESENCE_SECONDS
        )


# One per API process: the tool that waits and the routes Electron calls run in it.
snapshots = DocxSnapshots()
