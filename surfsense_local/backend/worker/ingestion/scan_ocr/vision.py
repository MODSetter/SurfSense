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
from collections import deque
from collections.abc import Iterable, Iterator
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

import psutil

from worker.ingestion.scan_ocr.frames import Frame
from worker.ingestion.scan_ocr.page import OcrPage
from worker.ingestion.scan_ocr.reading_order import Box, lines_in_order

log = logging.getLogger(__name__)

# Throughput stops growing past the performance cores; leave room for chat.
MAX_IN_FLIGHT = 4
# Vision takes far larger images than a 216 dpi page; this only bounds memory.
MAX_SIDE = 10_000


class VisionOcr:
    name = "Vision"
    language = "auto"
    max_side = MAX_SIDE

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
        """Each frame's page, in order. PyObjC lets go of the GIL inside every
        Objective-C call, so pages in flight do overlap."""
        in_flight = max(
            1, min(MAX_IN_FLIGHT, (psutil.cpu_count(logical=False) or 2) // 2)
        )
        with ThreadPoolExecutor(in_flight, thread_name_prefix="vision-ocr") as pool:
            pending: deque[tuple[Frame, Future[OcrPage]]] = deque()
            for frame in frames:
                if len(pending) >= in_flight:
                    done, future = pending.popleft()
                    yield done, future.result()
                pending.append((frame, pool.submit(_recognise, frame)))
            while pending:
                done, future = pending.popleft()
                yield done, future.result()


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
    return OcrPage(width, height, lines_in_order(boxes), frame.ink, "auto")


def _box(observation: Any, width: int, height: int) -> Box | None:
    """Vision's box is normalised with its origin bottom left."""
    text = str(observation.topCandidates_(1)[0].string()).strip()
    if not text:
        return None
    box = observation.boundingBox()
    x, y = box.origin.x * width, (1 - box.origin.y - box.size.height) * height
    return Box(x, y, x + box.size.width * width, y + box.size.height * height, text)
