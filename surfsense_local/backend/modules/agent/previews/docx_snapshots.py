"""Word documents waiting for Electron to print them to PDF.

The app has no Word converter. Electron renders the file with docx-preview, the
in-app viewer's library, and prints it; it polls for requests as it polls for
the image runtime, so the API needs no way to reach it.
"""

import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field

# Electron polls every 2 s but not while it prints, which takes seconds; a
# minute of silence means it is gone (or never ran: the Docker stack, tests).
PRESENCE_SECONDS = 60


class SnapshotUnavailableError(Exception):
    """No PDF came back, said in a sentence the model can read."""


@dataclass(frozen=True)
class SnapshotRequest:
    """What Electron is handed: which artifact's primary file to print."""

    id: str
    artifact_id: int


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

    def snapshot(self, artifact_id: int, timeout: float) -> bytes:
        """Block until Electron sends the artifact's pages as a PDF."""
        with self._lock:
            if not self._electron_polling():
                raise SnapshotUnavailableError(
                    "Word pages are drawn by the SurfSense desktop app, which is "
                    "not running beside this server."
                )
            pending = _Pending(SnapshotRequest(uuid.uuid4().hex, artifact_id))
            self._pending[pending.request.id] = pending
        try:
            answered = pending.answered.wait(timeout)
        finally:
            with self._lock:
                self._pending.pop(pending.request.id, None)
        if not answered:
            raise SnapshotUnavailableError(
                f"The Word preview did not finish within {timeout:g} s."
            )
        if pending.pdf is None:
            raise SnapshotUnavailableError(
                f"The Word preview failed: {pending.failure}"
            )
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
