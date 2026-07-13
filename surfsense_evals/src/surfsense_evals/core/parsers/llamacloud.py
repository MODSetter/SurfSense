"""LlamaParse (LlamaCloud) parser — eval-side mirror of the backend.

Calls ``LlamaParse.aparse`` with one of two ``parse_mode`` slugs
depending on ``processing_mode``:

* ``basic``   → ``parse_page_with_llm``   (cheap, single-LLM-call/page)
* ``premium`` → ``parse_page_with_agent`` (multi-step agent per page;
                                            handles tables / figures
                                            substantially better)

These are the exact mappings from production
``surfsense_backend/app/etl_pipeline/parsers/llamacloud.py``. We keep
``num_workers=1`` and language=``"en"`` to match production.

The result is materialised via ``get_markdown_documents(split_by_page=False)``
which concatenates every page into a single markdown string, exactly
the shape we need for long-context stuffing.
"""

from __future__ import annotations

import asyncio
import logging
import os
import random

import httpx

logger = logging.getLogger(__name__)

_LLAMA_PARSE_MODE_MAP = {
    "basic": "parse_page_with_llm",
    "premium": "parse_page_with_agent",
}

_MAX_RETRIES = 3
_BASE_DELAY = 10.0
_MAX_DELAY = 90.0


class LlamaCloudError(RuntimeError):
    """Raised when LlamaCloud parse fails after all retries."""


def _extract_markdown(result) -> str:
    """Pull markdown out of whatever object LlamaParse.aparse returns.

    Mirrors backend's tolerant extraction: the SDK has gone through
    several response shapes; we accept all of them so a minor SDK bump
    doesn't silently zero the eval.
    """

    if hasattr(result, "get_markdown_documents"):
        docs = result.get_markdown_documents(split_by_page=False)
        if docs and hasattr(docs[0], "text"):
            return docs[0].text
        if hasattr(result, "pages") and result.pages:
            return "\n\n".join(p.md for p in result.pages if hasattr(p, "md") and p.md)

    if isinstance(result, list):
        if result and hasattr(result[0], "text"):
            return result[0].text
        return "\n\n".join(
            doc.page_content if hasattr(doc, "page_content") else str(doc)
            for doc in result
        )

    return str(result)


async def parse_with_llamacloud(
    file_path: str | os.PathLike,
    *,
    processing_mode: str = "basic",
    estimated_pages: int = 50,
    api_key: str | None = None,
) -> str:
    """Run LlamaParse on ``file_path`` and return the markdown content.

    ``api_key`` defaults to the ``LLAMA_CLOUD_API_KEY`` env var (set
    in ``surfsense_evals/.env``).

    Raises ``LlamaCloudError`` after exhausting retries; ``ValueError``
    if the API key is missing.
    """

    api_key = api_key or os.environ.get("LLAMA_CLOUD_API_KEY")
    if not api_key:
        raise ValueError(
            "LLAMA_CLOUD_API_KEY must be set (see surfsense_evals/.env)."
        )

    parse_mode = _LLAMA_PARSE_MODE_MAP.get(processing_mode, "parse_page_with_llm")

    # Lazy import: llama-cloud pulls llama-index-core (~50 MB) on first
    # touch; defer until the parser actually runs.
    from llama_cloud_services import LlamaParse
    from llama_cloud_services.parse.base import JobFailedException
    from llama_cloud_services.parse.utils import ResultType

    file_size_mb = await asyncio.to_thread(os.path.getsize, file_path) / (1024 * 1024)
    # Match backend's per-page timeout heuristic so big PDFs don't drop
    # mid-job: 60s baseline + 30s/page (premium agent runs longer than
    # basic; both fit comfortably here).
    job_timeout = max(180.0, 60.0 + 30.0 * estimated_pages)
    upload_timeout = max(120.0, 30.0 * file_size_mb)

    logger.info(
        "LlamaCloud parsing %s (mode=%s, parse_mode=%s, %.1fMB, "
        "job_timeout=%.0fs)",
        file_path, processing_mode, parse_mode, file_size_mb, job_timeout,
    )

    custom_timeout = httpx.Timeout(
        connect=120.0, read=upload_timeout, write=upload_timeout, pool=120.0,
    )

    last_exc: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=custom_timeout) as client:
                parser = LlamaParse(
                    api_key=api_key,
                    num_workers=1,
                    verbose=False,
                    language="en",
                    result_type=ResultType.MD,
                    parse_mode=parse_mode,
                    ignore_errors=False,
                    max_timeout=int(max(2000.0, job_timeout + upload_timeout)),
                    job_timeout_in_seconds=job_timeout,
                    job_timeout_extra_time_per_page_in_seconds=60,
                    custom_client=client,
                )
                result = await parser.aparse(str(file_path))
            content = _extract_markdown(result).strip()
            if not content:
                raise LlamaCloudError(
                    f"LlamaCloud returned empty content for {file_path}"
                )
            logger.info(
                "LlamaCloud OK: %s (%s) -> %d chars",
                file_path, parse_mode, len(content),
            )
            return content

        except (
            httpx.HTTPError,
            JobFailedException,
            RuntimeError,
        ) as exc:
            last_exc = exc
            if attempt < _MAX_RETRIES:
                delay = min(_BASE_DELAY * (2 ** (attempt - 1)), _MAX_DELAY)
                jitter = delay * 0.25 * (2 * random.random() - 1)
                sleep_for = delay + jitter
                logger.warning(
                    "LlamaCloud attempt %d/%d failed (%s); retrying in %.1fs",
                    attempt, _MAX_RETRIES, type(last_exc).__name__, sleep_for,
                )
                await asyncio.sleep(sleep_for)

    raise LlamaCloudError(
        f"LlamaCloud failed after {_MAX_RETRIES} attempts on {file_path}"
    ) from last_exc


__all__ = ["LlamaCloudError", "parse_with_llamacloud"]
