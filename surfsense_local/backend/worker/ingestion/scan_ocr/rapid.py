"""RapidOCR on its own: the OCR inside Docling, without Docling's layout model,
TableFormer or torch.

The same PP-OCRv6 files Docling reads, and more of the page: on 499 real pages it
found 0.80 of a form's words where Docling found 0.72, and the answer to 0.88 of
374 DocVQA questions where Docling's text held 0.70. A page took about 2 s and
8 CPU-s on a Ryzen 5800X, where Docling took 4.9 s and 39 CPU-s.
"""

import logging
from collections import deque
from collections.abc import Iterable, Iterator
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Any

import psutil

from worker.ingestion.parser_pack import parser_dir
from worker.ingestion.scan_ocr.frames import Frame
from worker.ingestion.scan_ocr.page import OcrPage
from worker.ingestion.scan_ocr.reading_order import Box, lines_in_order

log = logging.getLogger(__name__)

DET = "PP-OCRv6_det_small.onnx"
REC = "PP-OCRv6_rec_small.onnx"
CLS = "ch_ppocr_mobile_v2.0_cls_mobile.onnx"
# RapidOCR shrinks anything longer to this before reading; rendering larger only
# costs time.
MAX_SIDE = 2000
# Pages read at once, one onnxruntime thread each: its CPU-s a page grow with its
# threads (14.9 at 1, 36.6 at 8), so several pages at one thread read more pages
# a CPU-second. At most 4, and half the physical cores, as chat may need the rest.
MAX_IN_FLIGHT = 4


class RapidOcr:
    name = "RapidOCR"
    language = "multi"
    max_side = MAX_SIDE

    def __init__(self, engine: Any) -> None:
        self._engine = engine

    @classmethod
    def create(cls) -> "RapidOcr | None":
        models = _models()
        if models is None:
            log.info("RapidOCR's models are not here")
            return None
        try:
            from rapidocr import RapidOCR

            _no_spinning()
            engine = RapidOCR(
                params={
                    # What Docling passes for the app: RapidOcrOptions(use_cls=False).
                    "Global.text_score": 0.5,
                    "Global.use_cls": False,
                    "Global.log_level": "error",
                    "EngineConfig.onnxruntime.intra_op_num_threads": 1,
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
        """Each frame's page, in order, several read at once on one engine: its
        only per-call state is harmless (rapidocr 3.9.2)."""
        in_flight = max(
            1, min(MAX_IN_FLIGHT, (psutil.cpu_count(logical=False) or 2) // 2)
        )
        with ThreadPoolExecutor(in_flight, thread_name_prefix="rapidocr") as pool:
            pending: deque[tuple[Frame, Future[OcrPage]]] = deque()
            for frame in frames:
                if len(pending) >= in_flight:
                    done, future = pending.popleft()
                    yield done, future.result()
                pending.append((frame, pool.submit(self._recognise, frame)))
            while pending:
                done, future = pending.popleft()
                yield done, future.result()

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


def _no_spinning() -> None:
    """onnxruntime's idle threads spin, burning CPU-seconds a page never used:
    13 CPU-s a page at 8 threads in the corpus run. RapidOCR has no switch for it."""
    try:
        from rapidocr.inference_engine.onnxruntime import main as ort_main

        build = ort_main.OrtInferSession._init_sess_opts
        if getattr(build, "_no_spin", False):
            return

        def quiet(config: Any) -> Any:
            options = build(config)
            options.add_session_config_entry("session.intra_op.allow_spinning", "0")
            options.add_session_config_entry("session.inter_op.allow_spinning", "0")
            return options

        quiet._no_spin = True  # type: ignore[attr-defined]
        ort_main.OrtInferSession._init_sess_opts = staticmethod(quiet)
    except Exception:
        log.debug("onnxruntime's threads keep spinning", exc_info=True)
