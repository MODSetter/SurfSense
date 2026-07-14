"""Azure Document Intelligence parser — eval-side mirror of the backend.

Calls ``DocumentIntelligenceClient.begin_analyze_document`` with one
of two ``model_id`` slugs depending on ``processing_mode``:

* ``basic``   → ``prebuilt-read``   (text OCR only, cheaper, faster)
* ``premium`` → ``prebuilt-layout`` (text + tables + structure;
                                     produces real markdown headings,
                                     pipe-tables, etc.)

These are the same model selections the production
``surfsense_backend/app/etl_pipeline/parsers/azure_doc_intelligence.py``
makes per ``processing_mode``. Output format is forced to Markdown
(``DocumentContentFormat.MARKDOWN``) so the long-context arm can stuff
it into a prompt verbatim.

Retry policy is intentionally light here (the eval harness re-runs
the whole batch on top-level failure); we do one synchronous attempt
plus exponential backoff on transient transport errors.
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
from pathlib import Path

logger = logging.getLogger(__name__)


_AZURE_MODEL_BY_MODE = {
    "basic": "prebuilt-read",
    "premium": "prebuilt-layout",
}

_MAX_RETRIES = 4
_BASE_DELAY = 5.0
_MAX_DELAY = 60.0


class AzureDIError(RuntimeError):
    """Raised when Azure DI fails after all retries."""


async def parse_with_azure_di(
    file_path: str | os.PathLike,
    *,
    processing_mode: str = "basic",
    endpoint: str | None = None,
    api_key: str | None = None,
) -> str:
    """Run Azure DI on ``file_path`` and return the markdown content.

    ``endpoint`` / ``api_key`` default to ``AZURE_DI_ENDPOINT`` and
    ``AZURE_DI_KEY`` env vars (set in ``surfsense_evals/.env``).

    Raises ``AzureDIError`` after exhausting retries; ``ValueError`` if
    credentials are missing.
    """

    endpoint = endpoint or os.environ.get("AZURE_DI_ENDPOINT")
    api_key = api_key or os.environ.get("AZURE_DI_KEY")
    if not endpoint or not api_key:
        raise ValueError(
            "AZURE_DI_ENDPOINT and AZURE_DI_KEY must be set (see surfsense_evals/.env)."
        )

    model_id = _AZURE_MODEL_BY_MODE.get(processing_mode, "prebuilt-read")

    # Lazy imports — surfsense_evals shouldn't pay the azure-sdk
    # import cost on every CLI invocation that doesn't touch
    # parser_compare.
    from azure.ai.documentintelligence.aio import DocumentIntelligenceClient
    from azure.ai.documentintelligence.models import DocumentContentFormat
    from azure.core.credentials import AzureKeyCredential
    from azure.core.exceptions import (
        ClientAuthenticationError,
        HttpResponseError,
        ServiceRequestError,
        ServiceResponseError,
    )

    file_size_mb = await asyncio.to_thread(os.path.getsize, file_path) / (1024 * 1024)
    logger.info(
        "Azure DI parsing %s (mode=%s, model=%s, size=%.1fMB)",
        file_path,
        processing_mode,
        model_id,
        file_size_mb,
    )

    last_exc: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            client = DocumentIntelligenceClient(
                endpoint=endpoint,
                credential=AzureKeyCredential(api_key),
            )
            async with client:
                body = await asyncio.to_thread(Path(file_path).read_bytes)
                poller = await client.begin_analyze_document(
                    model_id,
                    body=body,
                    output_content_format=DocumentContentFormat.MARKDOWN,
                )
                result = await poller.result()
            content = (result.content or "").strip()
            if not content:
                raise AzureDIError(f"Azure DI returned empty content for {file_path}")
            logger.info(
                "Azure DI OK: %s (%s) -> %d chars",
                file_path,
                model_id,
                len(content),
            )
            return content

        except ClientAuthenticationError:
            raise
        except HttpResponseError as exc:
            # 4xx that's not auth: don't retry, the request itself is broken.
            if exc.status_code and 400 <= exc.status_code < 500:
                raise AzureDIError(f"Azure DI {exc.status_code} on {file_path}: {exc}") from exc
            last_exc = exc
        except (ServiceRequestError, ServiceResponseError) as exc:
            last_exc = exc

        if attempt < _MAX_RETRIES:
            delay = min(_BASE_DELAY * (2 ** (attempt - 1)), _MAX_DELAY)
            jitter = delay * 0.25 * (2 * random.random() - 1)
            sleep_for = delay + jitter
            logger.warning(
                "Azure DI attempt %d/%d failed (%s); retrying in %.1fs",
                attempt,
                _MAX_RETRIES,
                type(last_exc).__name__,
                sleep_for,
            )
            await asyncio.sleep(sleep_for)

    raise AzureDIError(
        f"Azure DI failed after {_MAX_RETRIES} attempts on {file_path}"
    ) from last_exc


__all__ = ["AzureDIError", "parse_with_azure_di"]
