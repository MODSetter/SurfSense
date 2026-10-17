"""RapidOCR on its own: the OCR inside Docling, without Docling's layout model,
TableFormer or torch.

The same PP-OCRv6 files Docling reads, and more of the page: on 499 real pages it
found 0.80 of a form's words where Docling found 0.72, and the answer to 0.88 of
374 DocVQA questions where Docling's text held 0.70. A page took about 2 s and
8 CPU-s on a Ryzen 5800X, where Docling took 4.9 s and 39 CPU-s.
"""

import logging
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from worker.ingestion.parser_pack import parser_dir
from worker.ingestion.scan_ocr.frames import Frame
from worker.ingestion.scan_ocr.page import OcrPage
from worker.ingestion.scan_ocr.pages_at_once import PagesAtOnce
from worker.ingestion.scan_ocr.reading_order import Box, lines_in_order, vertical_share

log = logging.getLogger(__name__)

DET = "PP-OCRv6_det_small.onnx"
REC = "PP-OCRv6_rec_small.onnx"
CLS = "ch_ppocr_mobile_v2.0_cls_mobile.onnx"
# RapidOCR shrinks anything longer to this before reading; rendering larger only
# costs time.
MAX_SIDE = 2000
# One onnxruntime thread a page, several pages at once: a page costs about 8 CPU-s
# however it is split, and one thread a page spends the least (824 CPU-s for 100
# pages against 1,016 at 8 threads a page, at about the same wall time).
THREADS_A_PAGE = 1


class RapidOcr:
    name = "RapidOCR"
    language = "multi"
    max_side = MAX_SIDE

    def __init__(self, engine: Any) -> None:
        self._engine = engine
        # One engine, several pages at once: its only per-call state is harmless
        # (rapidocr 3.9.2).
        self._pages = PagesAtOnce(self._recognise, "rapidocr")

    @classmethod
    def create(cls) -> "RapidOcr | None":
        models = _models()
        if models is None:
            log.info("RapidOCR's models are not here")
            return None
        try:
            from rapidocr import RapidOCR

            engine = RapidOCR(
                params={
                    # What Docling passes for the app: RapidOcrOptions(use_cls=False).
                    "Global.text_score": 0.5,
                    "Global.use_cls": False,
                    "Global.log_level": "error",
                    "EngineConfig.onnxruntime.intra_op_num_threads": THREADS_A_PAGE,
                    "Det.model_path": str(models / DET),
                    "Rec.model_path": str(models / REC),
                    # Built even when off; pointed at the pack so nothing downloads.
                    "Cls.model_path": str(models / CLS),
                }
            )
        except Exception:
            log.info("RapidOCR could not start", exc_info=True)
            return None
        return cls(engine)

    def read(self, frames: Iterable[Frame]) -> Iterator[tuple[Frame, OcrPage]]:
        return self._pages.read(frames)

    def _recognise(self, frame: Frame) -> OcrPage:
        import numpy

        image = frame.image
        result = self._engine(numpy.asarray(image))
        boxes: list[Box] = []
        weighed = chars = 0.0
        if getattr(result, "boxes", None) is not None and result.txts:
            scores = list(result.scores or [])
            for index, (corners, text) in enumerate(
                zip(result.boxes.tolist(), result.txts, strict=False)
            ):
                text = (text or "").strip()
                if text:
                    xs = [point[0] for point in corners]
                    ys = [point[1] for point in corners]
                    boxes.append(Box(min(xs), min(ys), max(xs), max(ys), text))
                    if index < len(scores):
                        weighed += float(scores[index]) * len(text)
                        chars += len(text)
        return OcrPage(
            image.width,
            image.height,
            lines_in_order(boxes),
            frame.ink,
            self.language,
            confidence=weighed / chars if chars else None,
            vertical=vertical_share(boxes),
        )


def _models() -> Path | None:
    """The parser pack's RapidOcr folder, else the identical files the rapidocr
    wheel carries."""
    candidates = [parser_dir() / "RapidOcr"]
    try:
        import rapidocr

        candidates.append(Path(rapidocr.__file__).parent / "models")
    except ImportError:
        return None
    for folder in candidates:
        if all((folder / name).is_file() for name in (DET, REC, CLS)):
            return folder
    return None
