"""A page OCR read sideways, read again turned upright.

The readers read upright text only. A phone photo with no EXIF turn, or a scan
fed in sideways, comes back as letters' strokes, as text the engine is unsure
of, or as lines standing on end: all 20 real camera captures in the corpus did.
Turning costs a reading or three, and only on such pages.
"""

from collections.abc import Iterable, Iterator

from worker.ingestion.scan_ocr.frames import Frame
from worker.ingestion.scan_ocr.page import OcrPage, PageVerdict
from worker.ingestion.scan_ocr.reader import PageReader

# A quarter turn first: sideways is far commoner than upside down.
TURNS = (90, 270, 180)


def read_upright(
    reader: PageReader, frames: Iterable[Frame]
) -> Iterator[tuple[Frame, OcrPage]]:
    """Each frame's page; one that looks sideways turned the first way that reads
    as upright text, or as it was when none does, for its verdict to decide."""
    for frame, page in reader.read(frames):
        yield _upright(reader, frame, page) if page.looks_sideways() else (frame, page)


def _upright(reader: PageReader, frame: Frame, page: OcrPage) -> tuple[Frame, OcrPage]:
    for angle in TURNS:
        turned = Frame(frame.number, frame.image.rotate(angle, expand=True), frame.ink)
        # One turn at a time: each is read within the reader's own cap.
        [(_, read)] = list(reader.read([turned]))
        if read.verdict() is PageVerdict.TEXT and not read.looks_sideways():
            return turned, read
    return frame, page
