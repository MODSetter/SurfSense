import asyncio
import logging
import os
import random

import httpx

from app.config import config as app_config
from app.etl_pipeline.constants import (
    LLAMACLOUD_BASE_DELAY,
    LLAMACLOUD_MAX_DELAY,
    LLAMACLOUD_MAX_RETRIES,
    LLAMACLOUD_RETRYABLE_EXCEPTIONS,
    PER_PAGE_JOB_TIMEOUT,
    calculate_job_timeout,
    calculate_upload_timeout,
)

LLAMA_TIER_BY_MODE = {
    "basic": "cost_effective",
    "premium": "agentic_plus",
}


async def parse_with_llamacloud(
    file_path: str, estimated_pages: int, processing_mode: str = "basic"
) -> str:
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

    tier = LLAMA_TIER_BY_MODE.get(processing_mode, "cost_effective")

    logging.info(
        f"LlamaCloud upload configured: file_size={file_size_mb:.1f}MB, "
        f"pages={estimated_pages}, upload_timeout={upload_timeout:.0f}s, "
        f"job_timeout={job_timeout:.0f}s, tier={tier} (mode={processing_mode})"
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
                    tier=tier,
                )
                result = await parser.aparse(file_path)

                if attempt > 1:
                    logging.info(
                        f"LlamaCloud upload succeeded on attempt {attempt} after "
                        f"{len(attempt_errors)} failures"
                    )

                if hasattr(result, "get_markdown_documents"):
                    markdown_docs = result.get_markdown_documents(split_by_page=False)
                    if markdown_docs and hasattr(markdown_docs[0], "text"):
                        return markdown_docs[0].text
                    if hasattr(result, "pages") and result.pages:
                        return "\n\n".join(
                            p.md for p in result.pages if hasattr(p, "md") and p.md
                        )
                    return str(result)

                if isinstance(result, list):
                    if result and hasattr(result[0], "text"):
                        return result[0].text
                    return "\n\n".join(
                        doc.page_content if hasattr(doc, "page_content") else str(doc)
                        for doc in result
                    )

                return str(result)

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
