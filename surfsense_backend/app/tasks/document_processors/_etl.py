"""
ETL parsing strategies for different document processing services.

Provides parse functions for Unstructured, LlamaCloud, and Docling, along with
LlamaCloud retry logic and dynamic timeout calculations.
"""

import asyncio
import logging
import os
import random
import warnings
from logging import ERROR, getLogger

import httpx

from app.config import config as app_config
from app.db import Log
from app.services.task_logging_service import TaskLoggingService

from ._constants import (
    LLAMACLOUD_BASE_DELAY,
    LLAMACLOUD_MAX_DELAY,
    LLAMACLOUD_MAX_RETRIES,
    LLAMACLOUD_RETRYABLE_EXCEPTIONS,
    PER_PAGE_JOB_TIMEOUT,
)
from ._helpers import calculate_job_timeout, calculate_upload_timeout

# ---------------------------------------------------------------------------
# LlamaCloud parsing with retry
# ---------------------------------------------------------------------------


async def parse_with_llamacloud_retry(
    file_path: str,
    estimated_pages: int,
    task_logger: TaskLoggingService | None = None,
    log_entry: Log | None = None,
):
    """
    Parse a file with LlamaCloud with retry logic for transient SSL/connection errors.

    Uses dynamic timeout calculations based on file size and page count to handle
    very large files reliably.

    Returns:
        LlamaParse result object

    Raises:
        Exception: If all retries fail
    """
    from llama_cloud_services import LlamaParse
    from llama_cloud_services.parse.utils import ResultType

    file_size_bytes = os.path.getsize(file_path)
    file_size_mb = file_size_bytes / (1024 * 1024)

    upload_timeout = calculate_upload_timeout(file_size_bytes)
    job_timeout = calculate_job_timeout(estimated_pages, file_size_bytes)

    custom_timeout = httpx.Timeout(
        connect=120.0,
        read=upload_timeout,
        write=upload_timeout,
        pool=120.0,
    )

    logging.info(
        f"LlamaCloud upload configured: file_size={file_size_mb:.1f}MB, "
        f"pages={estimated_pages}, upload_timeout={upload_timeout:.0f}s, "
        f"job_timeout={job_timeout:.0f}s"
    )

    last_exception = None
    attempt_errors: list[str] = []

    for attempt in range(1, LLAMACLOUD_MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=custom_timeout) as custom_client:
                parser = LlamaParse(
                    api_key=app_config.LLAMA_CLOUD_API_KEY,
                    num_workers=1,
                    verbose=True,
                    language="en",
                    result_type=ResultType.MD,
                    max_timeout=int(max(2000, job_timeout + upload_timeout)),
                    job_timeout_in_seconds=job_timeout,
                    job_timeout_extra_time_per_page_in_seconds=PER_PAGE_JOB_TIMEOUT,
                    custom_client=custom_client,
                )
                result = await parser.aparse(file_path)

                if attempt > 1:
                    logging.info(
                        f"LlamaCloud upload succeeded on attempt {attempt} after "
                        f"{len(attempt_errors)} failures"
                    )
                return result

        except LLAMACLOUD_RETRYABLE_EXCEPTIONS as e:
            last_exception = e
            error_type = type(e).__name__
            error_msg = str(e)[:200]
            attempt_errors.append(f"Attempt {attempt}: {error_type} - {error_msg}")

            if attempt < LLAMACLOUD_MAX_RETRIES:
                base_delay = min(
                    LLAMACLOUD_BASE_DELAY * (2 ** (attempt - 1)),
                    LLAMACLOUD_MAX_DELAY,
                )
                jitter = base_delay * 0.25 * (2 * random.random() - 1)
                delay = base_delay + jitter

                if task_logger and log_entry:
                    await task_logger.log_task_progress(
                        log_entry,
                        f"LlamaCloud upload failed "
                        f"(attempt {attempt}/{LLAMACLOUD_MAX_RETRIES}), "
                        f"retrying in {delay:.0f}s",
                        {
                            "error_type": error_type,
                            "error_message": error_msg,
                            "attempt": attempt,
                            "retry_delay": delay,
                            "file_size_mb": round(file_size_mb, 1),
                            "upload_timeout": upload_timeout,
                        },
                    )
                else:
                    logging.warning(
                        f"LlamaCloud upload failed "
                        f"(attempt {attempt}/{LLAMACLOUD_MAX_RETRIES}): "
                        f"{error_type}. File: {file_size_mb:.1f}MB. "
                        f"Retrying in {delay:.0f}s..."
                    )

                await asyncio.sleep(delay)
            else:
                logging.error(
                    f"LlamaCloud upload failed after {LLAMACLOUD_MAX_RETRIES} "
                    f"attempts. File size: {file_size_mb:.1f}MB, "
                    f"Pages: {estimated_pages}. "
                    f"Errors: {'; '.join(attempt_errors)}"
                )

        except Exception:
            raise

    raise last_exception or RuntimeError(
        f"LlamaCloud parsing failed after {LLAMACLOUD_MAX_RETRIES} retries. "
        f"File size: {file_size_mb:.1f}MB"
    )


# ---------------------------------------------------------------------------
# Per-service parse functions
# ---------------------------------------------------------------------------


async def parse_with_unstructured(file_path: str):
    """
    Parse a file using the Unstructured ETL service.

    Returns:
        List of LangChain Document elements.
    """
    from langchain_unstructured import UnstructuredLoader

    loader = UnstructuredLoader(
        file_path,
        mode="elements",
        post_processors=[],
        languages=["eng"],
        include_orig_elements=False,
        include_metadata=False,
        strategy="auto",
    )
    return await loader.aload()


async def parse_with_docling(file_path: str, filename: str) -> str:
    """
    Parse a file using the Docling ETL service (via the Docling service wrapper).

    Returns:
        Markdown content string.
    """
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
