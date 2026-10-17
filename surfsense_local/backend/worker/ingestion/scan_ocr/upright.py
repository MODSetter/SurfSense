"""A page the system's OCR read sideways, read again turned upright.

The engines read upright text only. A phone photo with no EXIF turn, or a scan
fed in sideways, came back as "O 00 o c": all 20 real camera captures in the
corpus did. Turning costs a reading or three, and only on such pages.
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
    """Each frame's page, turned to whichever way reads best when it looks sideways."""
    for frame, page in reader.read(frames):
        if not page.looks_sideways():
            yield frame, page
            continue
        turned = [
            Frame(frame.number, frame.image.rotate(angle, expand=True), frame.ink)
            for angle in TURNS
        ]
        best = max(reader.read(turned), key=lambda read: read[1].word_share())
        if best[1].verdict() in (PageVerdict.GARBLED, PageVerdict.TOO_LITTLE):
            yield frame, page
        else:
            yield best
