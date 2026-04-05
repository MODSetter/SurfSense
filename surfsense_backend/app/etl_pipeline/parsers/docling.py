import warnings
from logging import ERROR, getLogger


async def parse_with_docling(file_path: str, filename: str) -> str:
    from app.services.docling_service import create_docling_service

    docling_service = create_docling_service()

    pdfminer_logger = getLogger("pdfminer")
    original_level = pdfminer_logger.level

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=UserWarning, module="pdfminer")
        warnings.filterwarnings(
            "ignore", message=".*Cannot set gray non-stroke color.*"
        )
        warnings.filterwarnings("ignore", message=".*invalid float value.*")
        pdfminer_logger.setLevel(ERROR)

        try:
            result = await docling_service.process_document(file_path, filename)
        finally:
            pdfminer_logger.setLevel(original_level)

    return result["content"]
