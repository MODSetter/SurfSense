import contextlib
import logging
import time
from pathlib import PurePosixPath

from app.config import config as app_config
from app.etl_pipeline.etl_document import EtlRequest, EtlResult
from app.etl_pipeline.exceptions import (
    EtlServiceUnavailableError,
    EtlUnsupportedFileError,
)
from app.etl_pipeline.file_classifier import FileCategory, classify_file
from app.etl_pipeline.parsers.audio import transcribe_audio
from app.etl_pipeline.parsers.direct_convert import convert_file_directly
from app.etl_pipeline.parsers.plaintext import read_plaintext
from app.observability import metrics as ot_metrics, otel as ot


def _file_extension(filename: str) -> str:
    return PurePosixPath(filename).suffix.lower() or "none"


class EtlPipelineService:
    """Single pipeline for extracting markdown from files. All callers use this."""

    def __init__(self, *, vision_llm=None):
        self._vision_llm = vision_llm

    async def extract(self, request: EtlRequest) -> EtlResult:
        category = classify_file(request.filename)
        start = time.perf_counter()
        status = "success"
        result: EtlResult | None = None
        with ot.etl_extract_span(
            content_type=category.value,
            file_extension=_file_extension(request.filename),
            processing_mode=request.processing_mode.value,
        ) as sp:
            try:
                if category == FileCategory.UNSUPPORTED:
                    raise EtlUnsupportedFileError(
                        f"File type not supported for parsing: {request.filename}"
                    )

                if category == FileCategory.PLAINTEXT:
                    content = read_plaintext(request.file_path)
                    result = EtlResult(
                        markdown_content=content,
                        etl_service="PLAINTEXT",
                        content_type="plaintext",
                    )
                    return result

                if category == FileCategory.DIRECT_CONVERT:
                    content = convert_file_directly(request.file_path, request.filename)
                    result = EtlResult(
                        markdown_content=content,
                        etl_service="DIRECT_CONVERT",
                        content_type="direct_convert",
                    )
                    return result

                if category == FileCategory.AUDIO:
                    content = await transcribe_audio(request.file_path, request.filename)
                    result = EtlResult(
                        markdown_content=content,
                        etl_service="AUDIO",
                        content_type="audio",
                    )
                    return result

                if category == FileCategory.IMAGE:
                    result = await self._extract_image(request)
                    return result

                result = await self._extract_document(request)
                return result
            except Exception:
                status = "error"
                raise
            finally:
                with contextlib.suppress(Exception):
                    if result is not None:
                        sp.set_attribute("etl.service", result.etl_service)
                        sp.set_attribute("content.type", result.content_type)
                    sp.set_attribute("etl.status", status)
                    ot_metrics.record_etl_extract_duration(
                        time.perf_counter() - start,
                        etl_service=result.etl_service if result else None,
                        content_type=result.content_type if result else category.value,
                        status=status,
                    )
                    ot_metrics.record_etl_extract_outcome(
                        etl_service=result.etl_service if result else None,
                        content_type=result.content_type if result else category.value,
                        status=status,
                    )

    async def _extract_image(self, request: EtlRequest) -> EtlResult:
        if self._vision_llm:
            try:
                from app.etl_pipeline.parsers.vision_llm import parse_with_vision_llm

                with ot.etl_parse_span(
                    etl_service="VISION_LLM",
                    content_type="image",
                    file_extension=_file_extension(request.filename),
                ) as sp:
                    content = await parse_with_vision_llm(
                        request.file_path, request.filename, self._vision_llm
                    )
                    sp.set_attribute("etl.status", "success")
                return EtlResult(
                    markdown_content=content,
                    etl_service="VISION_LLM",
                    content_type="image",
                )
            except Exception as exc:
                # Special-case quota exhaustion so we log a clearer message
                # — the vision LLM didn't "fail", the user just ran out of
                # premium credit. Falling through to the document parser
                # is a graceful degradation: OCR/Unstructured still
                # extracts text from the image without burning credit.
                from app.services.billable_calls import QuotaInsufficientError

                if isinstance(exc, QuotaInsufficientError):
                    logging.info(
                        "Vision LLM quota exhausted for %s; falling back to document parser",
                        request.filename,
                    )
                else:
                    logging.warning(
                        "Vision LLM failed for %s, falling back to document parser",
                        request.filename,
                        exc_info=True,
                    )
        else:
            logging.info(
                "No vision LLM provided, falling back to document parser for %s",
                request.filename,
            )

        try:
            with ot.etl_ocr_span(
                etl_service=app_config.ETL_SERVICE,
                file_extension=_file_extension(request.filename),
            ):
                return await self._extract_document(request)
        except (EtlUnsupportedFileError, EtlServiceUnavailableError):
            raise EtlUnsupportedFileError(
                f"Cannot process image {request.filename}: vision LLM "
                f"{'failed' if self._vision_llm else 'not configured'} and "
                f"document parser does not support this format"
            ) from None

    async def _extract_document(self, request: EtlRequest) -> EtlResult:
        from pathlib import PurePosixPath

        from app.utils.file_extensions import get_document_extensions_for_service

        etl_service = app_config.ETL_SERVICE
        if not etl_service:
            raise EtlServiceUnavailableError(
                "No ETL_SERVICE configured. "
                "Set ETL_SERVICE to UNSTRUCTURED, LLAMACLOUD, or DOCLING in your .env"
            )

        ext = PurePosixPath(request.filename).suffix.lower()
        supported = get_document_extensions_for_service(etl_service)
        if ext not in supported:
            raise EtlUnsupportedFileError(
                f"File type {ext} is not supported by {etl_service}"
            )

        with ot.etl_parse_span(
            etl_service=etl_service,
            content_type="document",
            file_extension=ext,
            processing_mode=request.processing_mode.value,
        ) as sp:
            if etl_service == "DOCLING":
                from app.etl_pipeline.parsers.docling import parse_with_docling

                content = await parse_with_docling(request.file_path, request.filename)
            elif etl_service == "UNSTRUCTURED":
                from app.etl_pipeline.parsers.unstructured import (
                    parse_with_unstructured,
                )

                content = await parse_with_unstructured(request.file_path)
            elif etl_service == "LLAMACLOUD":
                content = await self._extract_with_llamacloud(request)
            else:
                raise EtlServiceUnavailableError(f"Unknown ETL_SERVICE: {etl_service}")
            sp.set_attribute("etl.status", "success")

        # When the operator opts into vision-LLM at ingest, walk the
        # original file's embedded images and append a structured
        # "Image Content" section. The parser's own OCR (Docling
        # do_ocr=True, Azure DI prebuilt-read, etc.) handles text-in-
        # image; this side handles the *visual* description which the
        # parsers all drop today.
        content = await self._maybe_append_picture_descriptions(request, content)

        return EtlResult(
            markdown_content=content,
            etl_service=etl_service,
            content_type="document",
        )

    async def _maybe_append_picture_descriptions(
        self, request: EtlRequest, markdown: str
    ) -> str:
        if self._vision_llm is None:
            return markdown

        from app.etl_pipeline.picture_describer import (
            describe_pictures,
            merge_descriptions_into_markdown,
        )

        # Per-image OCR runner: re-feed each extracted image through
        # the ETL pipeline *as a standalone image* (no vision LLM, so
        # the IMAGE branch falls through to the document parser, which
        # OCRs the image with the configured backend -- Docling /
        # Azure DI / LlamaCloud). This gives us per-image OCR text
        # attached to the inline image block, in addition to the
        # page-level OCR that the parser already merges into the main
        # markdown stream. The fresh sub-service gets vision_llm=None
        # so this call cannot recurse back into picture_describer.
        async def _ocr_image(image_path: str, image_name: str) -> str:
            try:
                sub = EtlPipelineService(vision_llm=None)
                with ot.etl_picture_ocr_span(
                    file_extension=_file_extension(image_name)
                ) as sp:
                    ocr_result = await sub.extract(
                        EtlRequest(file_path=image_path, filename=image_name)
                    )
                    sp.set_attribute("etl.service", ocr_result.etl_service)
                    sp.set_attribute("etl.status", "success")
            except (
                EtlUnsupportedFileError,
                EtlServiceUnavailableError,
            ) as exc:
                # Common case: the configured ETL service can't OCR
                # this image format (or no service is configured at
                # all). Don't spam warnings -- just no OCR for it.
                logging.debug("Skipping per-image OCR for %s: %s", image_name, exc)
                return ""
            return ocr_result.markdown_content

        try:
            with ot.etl_picture_describe_span() as sp:
                result = await describe_pictures(
                    request.file_path,
                    request.filename,
                    self._vision_llm,
                    ocr_runner=_ocr_image,
                )
                sp.set_attribute("image.described.count", len(result.descriptions))
                sp.set_attribute("image.failed.count", result.failed)
                sp.set_attribute("image.skipped.too_small", result.skipped_too_small)
                sp.set_attribute("image.skipped.too_large", result.skipped_too_large)
                sp.set_attribute("image.skipped.duplicate", result.skipped_duplicate)
                sp.set_attribute("etl.status", "success")
        except Exception:
            # Picture description is additive; never let it fail an
            # otherwise-successful document extraction.
            logging.warning(
                "Picture description failed for %s, returning parser output unchanged",
                request.filename,
                exc_info=True,
            )
            return markdown

        if not result.descriptions:
            return markdown

        merged = merge_descriptions_into_markdown(markdown, result)
        logging.info(
            "Vision LLM described %d image(s) in %s "
            "(skipped: %d small / %d large / %d duplicate, %d failed)",
            len(result.descriptions),
            request.filename,
            result.skipped_too_small,
            result.skipped_too_large,
            result.skipped_duplicate,
            result.failed,
        )
        return merged

    async def _extract_with_llamacloud(self, request: EtlRequest) -> str:
        """Try Azure Document Intelligence first (when configured) then LlamaCloud.

        Azure DI is an internal accelerator: cheaper and faster for its supported
        file types.  If it is not configured, or the file extension is not in
        Azure DI's supported set, LlamaCloud is used directly.  If Azure DI
        fails for any reason, LlamaCloud is used as a fallback.
        """
        from pathlib import PurePosixPath

        from app.utils.file_extensions import AZURE_DI_DOCUMENT_EXTENSIONS

        ext = PurePosixPath(request.filename).suffix.lower()
        azure_configured = bool(
            getattr(app_config, "AZURE_DI_ENDPOINT", None)
            and getattr(app_config, "AZURE_DI_KEY", None)
        )

        mode_value = request.processing_mode.value

        if azure_configured and ext in AZURE_DI_DOCUMENT_EXTENSIONS:
            try:
                from app.etl_pipeline.parsers.azure_doc_intelligence import (
                    parse_with_azure_doc_intelligence,
                )

                return await parse_with_azure_doc_intelligence(
                    request.file_path, processing_mode=mode_value
                )
            except Exception:
                logging.warning(
                    "Azure Document Intelligence failed for %s, "
                    "falling back to LlamaCloud",
                    request.filename,
                    exc_info=True,
                )

        from app.etl_pipeline.parsers.llamacloud import parse_with_llamacloud

        return await parse_with_llamacloud(
            request.file_path, request.estimated_pages, processing_mode=mode_value
        )
