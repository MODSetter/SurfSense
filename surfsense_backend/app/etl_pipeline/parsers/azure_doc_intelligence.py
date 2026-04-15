import asyncio
import logging
import os
import random

from app.config import config as app_config

MAX_RETRIES = 5
BASE_DELAY = 10
MAX_DELAY = 120


AZURE_MODEL_BY_MODE = {
    "basic": "prebuilt-read",
    "premium": "prebuilt-layout",
}


async def parse_with_azure_doc_intelligence(
    file_path: str, processing_mode: str = "basic"
) -> str:
    from azure.ai.documentintelligence.aio import DocumentIntelligenceClient
    from azure.ai.documentintelligence.models import DocumentContentFormat
    from azure.core.credentials import AzureKeyCredential
    from azure.core.exceptions import (
        ClientAuthenticationError,
        HttpResponseError,
        ServiceRequestError,
        ServiceResponseError,
    )

    model_id = AZURE_MODEL_BY_MODE.get(processing_mode, "prebuilt-read")
    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    retryable_exceptions = (ServiceRequestError, ServiceResponseError)

    logging.info(
        f"Azure Document Intelligence using model={model_id} "
        f"(mode={processing_mode}, file={file_size_mb:.1f}MB)"
    )

    last_exception = None
    attempt_errors: list[str] = []

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            client = DocumentIntelligenceClient(
                endpoint=app_config.AZURE_DI_ENDPOINT,
                credential=AzureKeyCredential(app_config.AZURE_DI_KEY),
            )
            async with client:
                with open(file_path, "rb") as f:
                    poller = await client.begin_analyze_document(
                        model_id,
                        body=f,
                        output_content_format=DocumentContentFormat.MARKDOWN,
                    )
                result = await poller.result()

            if attempt > 1:
                logging.info(
                    f"Azure Document Intelligence succeeded on attempt {attempt} "
                    f"after {len(attempt_errors)} failures"
                )

            if not result.content:
                return ""

            return result.content

        except ClientAuthenticationError:
            raise
        except HttpResponseError as e:
            if e.status_code and 400 <= e.status_code < 500:
                raise
            last_exception = e
            error_type = type(e).__name__
            error_msg = str(e)[:200]
            attempt_errors.append(f"Attempt {attempt}: {error_type} - {error_msg}")
        except retryable_exceptions as e:
            last_exception = e
            error_type = type(e).__name__
            error_msg = str(e)[:200]
            attempt_errors.append(f"Attempt {attempt}: {error_type} - {error_msg}")

        if attempt < MAX_RETRIES:
            base_delay = min(BASE_DELAY * (2 ** (attempt - 1)), MAX_DELAY)
            jitter = base_delay * 0.25 * (2 * random.random() - 1)
            delay = base_delay + jitter

            logging.warning(
                f"Azure Document Intelligence failed "
                f"(attempt {attempt}/{MAX_RETRIES}): "
                f"{attempt_errors[-1]}. File: {file_size_mb:.1f}MB. "
                f"Retrying in {delay:.0f}s..."
            )
            await asyncio.sleep(delay)
        else:
            logging.error(
                f"Azure Document Intelligence failed after {MAX_RETRIES} "
                f"attempts. File size: {file_size_mb:.1f}MB. "
                f"Errors: {'; '.join(attempt_errors)}"
            )

    raise last_exception or RuntimeError(
        f"Azure Document Intelligence parsing failed after {MAX_RETRIES} retries. "
        f"File size: {file_size_mb:.1f}MB"
    )
