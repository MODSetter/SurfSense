"""Several pages read at once, in order, within one cap per reader.

At most 4, and half the physical cores, as chat may need the rest. The cap is a
semaphore every reading of the reader shares, a sideways page's turned reads
included, so no mix of pages and turns goes past it.
"""

import threading
from collections import deque
from collections.abc import Callable, Iterable, Iterator
from concurrent.futures import Future, ThreadPoolExecutor

import psutil

from worker.ingestion.scan_ocr.frames import Frame
from worker.ingestion.scan_ocr.page import OcrPage

MAX_AT_ONCE = 4


def at_once() -> int:
    return max(1, min(MAX_AT_ONCE, (psutil.cpu_count(logical=False) or 2) // 2))


class PagesAtOnce:
    def __init__(self, recognise: Callable[[Frame], OcrPage], name: str) -> None:
        self._recognise = recognise
        self._name = name
        self._slots = threading.BoundedSemaphore(at_once())

    def read(self, frames: Iterable[Frame]) -> Iterator[tuple[Frame, OcrPage]]:
        """Each frame's page in order; the next frame renders while earlier ones
        are read."""
        width = at_once()
        with ThreadPoolExecutor(width, thread_name_prefix=self._name) as pool:
            pending: deque[tuple[Frame, Future[OcrPage]]] = deque()
            try:
                for frame in frames:
                    if len(pending) >= width:
                        done, future = pending.popleft()
                        yield done, future.result()
                    pending.append((frame, pool.submit(self._within_cap, frame)))
                while pending:
                    done, future = pending.popleft()
                    yield done, future.result()
            finally:
                # Pages not yet started are not read once the caller stops.
                for _, future in pending:
                    future.cancel()

    def _within_cap(self, frame: Frame) -> OcrPage:
        with self._slots:
            return self._recognise(frame)
