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
from collections.abc import Iterable, Iterator
from typing import Any

from worker.ingestion.scan_ocr.frames import Frame
from worker.ingestion.scan_ocr.page import OcrPage
from worker.ingestion.scan_ocr.pages_at_once import PagesAtOnce
from worker.ingestion.scan_ocr.reading_order import Box, lines_in_order, vertical_share

log = logging.getLogger(__name__)

# Vision takes far larger images than a 216 dpi page; this only bounds memory.
MAX_SIDE = 10_000


class VisionOcr:
    name = "Vision"
    language = "auto"
    max_side = MAX_SIDE

    def __init__(self) -> None:
        # PyObjC lets go of the GIL inside every Objective-C call, so pages in
        # flight do overlap.
        self._pages = PagesAtOnce(_recognise, "vision-ocr")

    @classmethod
    def create(cls) -> "VisionOcr | None":
        try:
            import Vision

            Vision.VNRecognizeTextRequest.alloc().init()
        except Exception:
            log.info("Vision is not available", exc_info=True)
            return None
        return cls()

    def read(self, frames: Iterable[Frame]) -> Iterator[tuple[Frame, OcrPage]]:
        return self._pages.read(frames)


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
        handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(
            picture, {}
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
