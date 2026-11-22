"""The pages of a layout-only reading with a caption only OCR could read.

Drawn as outlines or pixels, such a caption has no characters in the text
layer, so layout alone drops it and the full reading's OCR keeps it. The rule
is Docling's own for the regions OCR reads: a layout cluster over a shape or
bitmap, or with no text (base_ocr_model.py, PDF-aware layout regions).

Imports docling: import it only after parsing._converter() has set the
environment docling reads as it is imported.
"""

import logging
from collections.abc import Iterable, Iterator

from docling.backend.pdf_backend import PdfPageBackend
from docling.datamodel.base_models import Page
from docling.datamodel.document import ConversionResult
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.models.base_model import BasePageModel
from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline
from docling.utils.layout_postprocessor import LayoutPostprocessor
from docling_core.types.doc import BoundingBox, DocItemLabel

logger = logging.getLogger(__name__)

# Below it, the layout's post-processing drops the caption with or without OCR.
_CAPTION_CONFIDENCE = LayoutPostprocessor.CONFIDENCE_THRESHOLDS[DocItemLabel.CAPTION]


class CaptionsForOcr(BasePageModel):
    """Notes, rather than reads, the pages whose captions OCR would read."""

    def __init__(self) -> None:
        self.pages: set[int] = set()

    def __call__(
        self, conv_res: ConversionResult, page_batch: Iterable[Page]
    ) -> Iterator[Page]:
        for page in page_batch:
            if _has_caption_for_ocr(page):
                self.pages.add(page.page_no)
            yield page


def layout_only_pipeline(captions: CaptionsForOcr) -> type[StandardPdfPipeline]:
    """Docling's PDF pipeline with `captions` in its OCR stage."""

    class LayoutOnlyPipeline(StandardPdfPipeline):
        def __init__(self, pipeline_options: PdfPipelineOptions) -> None:
            super().__init__(pipeline_options)
            # Runs after layout, before post-processing drops the empty clusters.
            self.ocr_model = captions

    return LayoutOnlyPipeline


def _has_caption_for_ocr(page: Page) -> bool:
    backend = page._backend
    if backend is None or not backend.is_valid():
        return False  # OCR skips such a page too
    if page.predictions.layout is None:
        return True  # Docling moved its stages: let the full reading decide
    try:
        return any(
            _read_by_ocr(backend, cluster.bbox)
            for cluster in page.predictions.layout.clusters
            if cluster.label == DocItemLabel.CAPTION
            and cluster.confidence >= _CAPTION_CONFIDENCE
        )
    except Exception:
        # A failure here would cost the page its pictures, as Docling drops it.
        logger.warning(
            "checked page %s's captions for OCR", page.page_no, exc_info=True
        )
        return True


def _read_by_ocr(backend: PdfPageBackend, region: BoundingBox) -> bool:
    # None: the backend cannot tell, so OCR may well read it.
    drawn = backend.has_content_in(bbox=region, chars=False, shapes=True, bitmaps=True)
    if drawn is None or drawn:
        return True
    text = backend.has_content_in(bbox=region, chars=True, shapes=False, bitmaps=False)
    return not text
