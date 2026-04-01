"""Content extraction for OneDrive files.

Reuses the same ETL parsing logic as Google Drive since file parsing is
extension-based, not provider-specific.
"""

import asyncio
import contextlib
import logging
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

from .client import OneDriveClient
from .file_types import get_extension_from_mime, should_skip_file

logger = logging.getLogger(__name__)


async def download_and_extract_content(
    client: OneDriveClient,
    file: dict[str, Any],
) -> tuple[str | None, dict[str, Any], str | None]:
    """Download a OneDrive file and extract its content as markdown.

    Returns (markdown_content, onedrive_metadata, error_message).
    """
    item_id = file.get("id")
    file_name = file.get("name", "Unknown")

    if should_skip_file(file):
        return None, {}, "Skipping non-indexable item"

    file_info = file.get("file", {})
    mime_type = file_info.get("mimeType", "")

    logger.info(f"Downloading file for content extraction: {file_name} ({mime_type})")

    metadata: dict[str, Any] = {
        "onedrive_file_id": item_id,
        "onedrive_file_name": file_name,
        "onedrive_mime_type": mime_type,
        "source_connector": "onedrive",
    }
    if "lastModifiedDateTime" in file:
        metadata["modified_time"] = file["lastModifiedDateTime"]
    if "createdDateTime" in file:
        metadata["created_time"] = file["createdDateTime"]
    if "size" in file:
        metadata["file_size"] = file["size"]
    if "webUrl" in file:
        metadata["web_url"] = file["webUrl"]
    file_hashes = file_info.get("hashes", {})
    if file_hashes.get("sha256Hash"):
        metadata["sha256_hash"] = file_hashes["sha256Hash"]
    elif file_hashes.get("quickXorHash"):
        metadata["quick_xor_hash"] = file_hashes["quickXorHash"]

    temp_file_path = None
    try:
        extension = (
            Path(file_name).suffix or get_extension_from_mime(mime_type) or ".bin"
        )
        with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as tmp:
            temp_file_path = tmp.name

        error = await client.download_file_to_disk(item_id, temp_file_path)
        if error:
            return None, metadata, error

        markdown = await _parse_file_to_markdown(temp_file_path, file_name)
        return markdown, metadata, None

    except Exception as e:
        logger.warning(f"Failed to extract content from {file_name}: {e!s}")
        return None, metadata, str(e)
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            with contextlib.suppress(Exception):
                os.unlink(temp_file_path)


async def _parse_file_to_markdown(file_path: str, filename: str) -> str:
    """Parse a local file to markdown using the configured ETL service.

    Same logic as Google Drive -- file parsing is extension-based.
    """
    lower = filename.lower()

    if lower.endswith((".md", ".markdown", ".txt")):
        with open(file_path, encoding="utf-8") as f:
            return f.read()

    if lower.endswith((".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm")):
        from litellm import atranscription

        from app.config import config as app_config

        stt_service_type = (
            "local"
            if app_config.STT_SERVICE and app_config.STT_SERVICE.startswith("local/")
            else "external"
        )
        if stt_service_type == "local":
            from app.services.stt_service import stt_service

            t0 = time.monotonic()
            logger.info(
                f"[local-stt] START file={filename} thread={threading.current_thread().name}"
            )
            result = await asyncio.to_thread(stt_service.transcribe_file, file_path)
            logger.info(
                f"[local-stt] END file={filename} elapsed={time.monotonic() - t0:.2f}s"
            )
            text = result.get("text", "")
        else:
            with open(file_path, "rb") as audio_file:
                kwargs: dict[str, Any] = {
                    "model": app_config.STT_SERVICE,
                    "file": audio_file,
                    "api_key": app_config.STT_SERVICE_API_KEY,
                }
                if app_config.STT_SERVICE_API_BASE:
                    kwargs["api_base"] = app_config.STT_SERVICE_API_BASE
                resp = await atranscription(**kwargs)
                text = resp.get("text", "")

        if not text:
            raise ValueError("Transcription returned empty text")
        return f"# Transcription of {filename}\n\n{text}"

    from app.config import config as app_config

    if app_config.ETL_SERVICE == "UNSTRUCTURED":
        from langchain_unstructured import UnstructuredLoader

        from app.utils.document_converters import convert_document_to_markdown

        loader = UnstructuredLoader(
            file_path,
            mode="elements",
            post_processors=[],
            languages=["eng"],
            include_orig_elements=False,
            include_metadata=False,
            strategy="auto",
        )
        docs = await loader.aload()
        return await convert_document_to_markdown(docs)

    if app_config.ETL_SERVICE == "LLAMACLOUD":
        from app.tasks.document_processors.file_processors import (
            parse_with_llamacloud_retry,
        )

        result = await parse_with_llamacloud_retry(
            file_path=file_path, estimated_pages=50
        )
        markdown_documents = await result.aget_markdown_documents(split_by_page=False)
        if not markdown_documents:
            raise RuntimeError(f"LlamaCloud returned no documents for {filename}")
        return markdown_documents[0].text

    if app_config.ETL_SERVICE == "DOCLING":
        from docling.document_converter import DocumentConverter

        converter = DocumentConverter()
        t0 = time.monotonic()
        logger.info(
            f"[docling] START file={filename} thread={threading.current_thread().name}"
        )
        result = await asyncio.to_thread(converter.convert, file_path)
        logger.info(
            f"[docling] END file={filename} elapsed={time.monotonic() - t0:.2f}s"
        )
        return result.document.export_to_markdown()

    raise RuntimeError(f"Unknown ETL_SERVICE: {app_config.ETL_SERVICE}")
