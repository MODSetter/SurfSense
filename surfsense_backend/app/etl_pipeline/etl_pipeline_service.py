import logging

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


class EtlPipelineService:
    """Single pipeline for extracting markdown from files. All callers use this."""

    def __init__(self, *, vision_llm=None):
        self._vision_llm = vision_llm

    async def extract(self, request: EtlRequest) -> EtlResult:
        category = classify_file(request.filename)

        if category == FileCategory.UNSUPPORTED:
            raise EtlUnsupportedFileError(
                f"File type not supported for parsing: {request.filename}"
            )

        if category == FileCategory.PLAINTEXT:
            content = read_plaintext(request.file_path)
            return EtlResult(
                markdown_content=content,
                etl_service="PLAINTEXT",
                content_type="plaintext",
            )

        if category == FileCategory.DIRECT_CONVERT:
            content = convert_file_directly(request.file_path, request.filename)
            return EtlResult(
                markdown_content=content,
                etl_service="DIRECT_CONVERT",
                content_type="direct_convert",
            )

        if category == FileCategory.AUDIO:
            content = await transcribe_audio(request.file_path, request.filename)
            return EtlResult(
                markdown_content=content,
                etl_service="AUDIO",
                content_type="audio",
            )

        if category == FileCategory.IMAGE:
            return await self._extract_image(request)

        return await self._extract_document(request)

    async def _extract_image(self, request: EtlRequest) -> EtlResult:
        if self._vision_llm:
            try:
                from app.etl_pipeline.parsers.vision_llm import parse_with_vision_llm

                content = await parse_with_vision_llm(
                    request.file_path, request.filename, self._vision_llm
                )
                return EtlResult(
                    markdown_content=content,
                    etl_service="VISION_LLM",
                    content_type="image",
                )
            except Exception:
                logging.warning(
                    "Vision LLM failed for %s, falling back to document parser",
                    request.filename,
                    exc_info=True,
                )

        logging.info(
            "No vision LLM provided, falling back to document parser for %s",
            request.filename,
        )
        return await self._extract_document(request)

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

        if etl_service == "DOCLING":
            from app.etl_pipeline.parsers.docling import parse_with_docling

            content = await parse_with_docling(request.file_path, request.filename)
        elif etl_service == "UNSTRUCTURED":
            from app.etl_pipeline.parsers.unstructured import parse_with_unstructured

            content = await parse_with_unstructured(request.file_path)
        elif etl_service == "LLAMACLOUD":
            content = await self._extract_with_llamacloud(request)
        else:
            raise EtlServiceUnavailableError(f"Unknown ETL_SERVICE: {etl_service}")

        return EtlResult(
            markdown_content=content,
            etl_service=etl_service,
            content_type="document",
        )

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

        if azure_configured and ext in AZURE_DI_DOCUMENT_EXTENSIONS:
            try:
                from app.etl_pipeline.parsers.azure_doc_intelligence import (
                    parse_with_azure_doc_intelligence,
                )

                return await parse_with_azure_doc_intelligence(request.file_path)
            except Exception:
                logging.warning(
                    "Azure Document Intelligence failed for %s, "
                    "falling back to LlamaCloud",
                    request.filename,
                    exc_info=True,
                )

        from app.etl_pipeline.parsers.llamacloud import parse_with_llamacloud

        return await parse_with_llamacloud(request.file_path, request.estimated_pages)
