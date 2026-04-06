from app.config import config as app_config
from app.etl_pipeline.etl_document import EtlRequest, EtlResult
from app.etl_pipeline.exceptions import EtlServiceUnavailableError, EtlUnsupportedFileError
from app.etl_pipeline.file_classifier import FileCategory, classify_file
from app.etl_pipeline.parsers.audio import transcribe_audio
from app.etl_pipeline.parsers.direct_convert import convert_file_directly
from app.etl_pipeline.parsers.plaintext import read_plaintext


class EtlPipelineService:
    """Single pipeline for extracting markdown from files. All callers use this."""

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

        return await self._extract_document(request)

    async def _extract_document(self, request: EtlRequest) -> EtlResult:
        etl_service = app_config.ETL_SERVICE
        if not etl_service:
            raise EtlServiceUnavailableError(
                "No ETL_SERVICE configured. "
                "Set ETL_SERVICE to UNSTRUCTURED, LLAMACLOUD, or DOCLING in your .env"
            )

        if etl_service == "DOCLING":
            from app.etl_pipeline.parsers.docling import parse_with_docling

            content = await parse_with_docling(request.file_path, request.filename)
        elif etl_service == "UNSTRUCTURED":
            from app.etl_pipeline.parsers.unstructured import parse_with_unstructured

            content = await parse_with_unstructured(request.file_path)
        elif etl_service == "LLAMACLOUD":
            from app.etl_pipeline.parsers.llamacloud import parse_with_llamacloud

            content = await parse_with_llamacloud(
                request.file_path, request.estimated_pages
            )
        else:
            raise EtlServiceUnavailableError(
                f"Unknown ETL_SERVICE: {etl_service}"
            )

        return EtlResult(
            markdown_content=content,
            etl_service=etl_service,
            content_type="document",
        )
