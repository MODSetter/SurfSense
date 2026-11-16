"""macOS's own OCR (Vision's VNRecognizeTextRequest, accurate), through PyObjC.

On a GitHub macOS runner (a 3-core M1 virtual machine, no Neural Engine) it read
the corpus's 499 real pages at 2.4 s a page, as well as RapidOCR on books,
receipts and DocVQA but for forms (0.71 of their words against 0.80), and read
the camera photos neither RapidOCR nor Docling could (0.94 against 0.05). Its
fast level found 0.27 of all words: not used.

Called directly rather than through ocrmac: installing ocrmac would switch
Docling's own OCR on a Mac with no parser pack.
"""

import logging
import threading
from collections.abc import Iterable, Iterator
from concurrent.futures import Future
from typing import Any

from PIL import Image

from worker.ingestion.scan_ocr.frames import Frame
from worker.ingestion.scan_ocr.page import OcrPage
from worker.ingestion.scan_ocr.pages_at_once import PagesAtOnce
from worker.ingestion.scan_ocr.reading_order import Box, lines_in_order, vertical_share

log = logging.getLogger(__name__)

# Vision takes far larger images than a 216 dpi page; this only bounds memory.
MAX_SIDE = 10_000
_BLANK_PAGE = (64, 64)
# Fifty times the 2.4 s a page of the slowest Mac measured, above; a read past it
# is stuck inside Apple's call, as one was once on macOS 27.
READ_SECONDS = 120.0
# The first read of a blank page, 0.35 s where measured: long enough for a slow Mac to
# load Vision's models, and it holds up only the document that starts the reader.
START_SECONDS = 60.0


class VisionOcr:
    name = "Vision"
    language = "auto"
    max_side = MAX_SIDE

    def __init__(self) -> None:
        # PyObjC lets go of the GIL inside every Objective-C call, so pages in
        # flight do overlap.
        self._pages = PagesAtOnce(self._read_within_limit, "vision-ocr")
        self.stuck = False

    @classmethod
    def create(cls) -> "VisionOcr | None":
        try:
            # A real read: on macOS 27 a request could be made while every page failed.
            _within_limit(
                Frame(1, Image.new("L", _BLANK_PAGE, 255), 0.0), START_SECONDS
            )
        except Exception:
            log.info("Vision is not available", exc_info=True)
            return None
        return cls()

    def read(self, frames: Iterable[Frame]) -> Iterator[tuple[Frame, OcrPage]]:
        return self._pages.read(frames)

    def _read_within_limit(self, frame: Frame) -> OcrPage:
        # A page queued behind a stuck one would leave another thread behind.
        if self.stuck:
            raise TimeoutError("an earlier Vision read is stuck")
        try:
            return _within_limit(frame, READ_SECONDS)
        except TimeoutError:
            self.stuck = True
            raise


def _within_limit(frame: Frame, seconds: float) -> OcrPage:
    """On a thread of its own: a stuck native call cannot be killed, and a pool's
    thread would hold its pool open. Left behind, it ends with the process."""
    outcome: Future[OcrPage] = Future()

    def read() -> None:
        try:
            outcome.set_result(_recognise(frame))
        except BaseException as error:
            outcome.set_exception(error)

    threading.Thread(target=read, name="vision-read", daemon=True).start()
    return outcome.result(timeout=seconds)


def _recognise(frame: Frame) -> OcrPage:
    import Foundation
    import objc
    import Quartz
    import Vision

    image = frame.image
    width, height = image.size
    with objc.autorelease_pool():
        pixels = image.tobytes()
        data = Foundation.NSData.dataWithBytes_length_(pixels, len(pixels))
        provider = Quartz.CGDataProviderCreateWithCFData(data)
        picture = Quartz.CGImageCreate(
            width,
            height,
            8,
            8,
            width,
            Quartz.CGColorSpaceCreateDeviceGray(),
            Quartz.kCGImageAlphaNone,
            provider,
            None,
            False,
            Quartz.kCGRenderingIntentDefault,
        )
        # macOS 27 refuses a Python dict here, even with PyObjC 13; Apple declares
        # this argument non-null, so None is not promised to work either.
        handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(
            picture, Foundation.NSDictionary.dictionary()
        )
        request = Vision.VNRecognizeTextRequest.alloc().init()
        request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
        request.setUsesLanguageCorrection_(True)
        # macOS 13, the app's own minimum: Vision picks the language.
        if hasattr(request, "setAutomaticallyDetectsLanguage_"):
            request.setAutomaticallyDetectsLanguage_(True)
        outcome = handler.performRequests_error_([request], None)
        ok, error = outcome if isinstance(outcome, tuple) else (outcome, None)
        if not ok:
            raise RuntimeError(f"Vision could not read the page: {error}")
        boxes = [
            box
            for observation in request.results() or ()
            if (box := _box(observation, width, height)) is not None
        ]
    # No confidence: Vision's was never measured against the corpus, and the
    # page verdict's threshold is RapidOCR's.
    return OcrPage(
        width,
        height,
        lines_in_order(boxes),
        frame.ink,
        "auto",
        vertical=vertical_share(boxes),
    )


def _box(observation: Any, width: int, height: int) -> Box | None:
    """Vision's box is normalised with its origin bottom left."""
    text = str(observation.topCandidates_(1)[0].string()).strip()
    if not text:
        return None
    box = observation.boundingBox()
    x, y = box.origin.x * width, (1 - box.origin.y - box.size.height) * height
    return Box(x, y, x + box.size.width * width, y + box.size.height * height, text)
