"""
Composio Google Drive Connector Module.

Provides Google Drive specific methods for data retrieval and indexing via Composio.
"""

import contextlib
import hashlib
import json
import logging
import os
import tempfile
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.config import config
from app.connectors.composio_connector import ComposioConnector
from app.db import Document, DocumentType, Log
from app.services.composio_service import TOOLKIT_TO_DOCUMENT_TYPE
from app.services.llm_service import get_user_long_context_llm
from app.services.task_logging_service import TaskLoggingService
from app.utils.document_converters import (
    create_document_chunks,
    generate_content_hash,
    generate_document_summary,
    generate_unique_identifier_hash,
)

# Heartbeat configuration
HeartbeatCallbackType = Callable[[int], Awaitable[None]]
HEARTBEAT_INTERVAL_SECONDS = 30

logger = logging.getLogger(__name__)


# Binary file extensions that need file processor
BINARY_FILE_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".tiff",
    ".webp",
    ".zip",
    ".tar",
    ".gz",
    ".rar",
    ".7z",
    ".mp3",
    ".mp4",
    ".wav",
    ".avi",
    ".mov",
    ".exe",
    ".dll",
    ".so",
    ".bin",
}

# Text file extensions that can be decoded as UTF-8
TEXT_FILE_EXTENSIONS = {
    ".txt",
    ".md",
    ".markdown",
    ".json",
    ".xml",
    ".html",
    ".htm",
    ".css",
    ".js",
    ".ts",
    ".py",
    ".java",
    ".c",
    ".cpp",
    ".h",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    ".sh",
    ".bash",
    ".zsh",
    ".fish",
    ".sql",
    ".csv",
    ".tsv",
    ".rst",
    ".tex",
    ".log",
}


def get_current_timestamp() -> datetime:
    """Get the current timestamp with timezone for updated_at field."""
    return datetime.now(UTC)


def _is_binary_file(file_name: str, mime_type: str) -> bool:
    """Check if a file is binary based on extension or mime type."""
    extension = Path(file_name).suffix.lower()

    # Check extension first
    if extension in BINARY_FILE_EXTENSIONS:
        return True
    if extension in TEXT_FILE_EXTENSIONS:
        return False

    # Check mime type
    if mime_type:
        if mime_type.startswith(("image/", "audio/", "video/", "application/pdf")):
            return True
        if mime_type.startswith(("text/", "application/json", "application/xml")):
            return False
        # Office documents
        if (
            "spreadsheet" in mime_type
            or "document" in mime_type
            or "presentation" in mime_type
        ):
            return True

    # Default to text for unknown types
    return False


class ComposioGoogleDriveConnector(ComposioConnector):
    """
    Google Drive specific Composio connector.

    Provides methods for listing files, downloading content, and tracking changes
    from Google Drive via Composio.
    """

    async def list_drive_files(
        self,
        folder_id: str | None = None,
        page_token: str | None = None,
        page_size: int = 100,
    ) -> tuple[list[dict[str, Any]], str | None, str | None]:
        """
        List files from Google Drive via Composio.

        Args:
            folder_id: Optional folder ID to list contents of.
            page_token: Pagination token.
            page_size: Number of files per page.

        Returns:
            Tuple of (files list, next_page_token, error message).
        """
        connected_account_id = await self.get_connected_account_id()
        if not connected_account_id:
            return [], None, "No connected account ID found"

        entity_id = await self.get_entity_id()
        service = await self._get_service()
        return await service.get_drive_files(
            connected_account_id=connected_account_id,
            entity_id=entity_id,
            folder_id=folder_id,
            page_token=page_token,
            page_size=page_size,
        )

    async def get_drive_file_content(
        self, file_id: str, original_mime_type: str | None = None
    ) -> tuple[bytes | None, str | None]:
        """
        Download file content from Google Drive via Composio.

        Args:
            file_id: Google Drive file ID.
            original_mime_type: Original MIME type (used to detect Google Workspace files for export).

        Returns:
            Tuple of (file content bytes, error message).
        """
        connected_account_id = await self.get_connected_account_id()
        if not connected_account_id:
            return None, "No connected account ID found"

        entity_id = await self.get_entity_id()
        service = await self._get_service()
        return await service.get_drive_file_content(
            connected_account_id=connected_account_id,
            entity_id=entity_id,
            file_id=file_id,
            original_mime_type=original_mime_type,
        )

    async def get_file_metadata(
        self, file_id: str
    ) -> tuple[dict[str, Any] | None, str | None]:
        """
        Get metadata for a specific file from Google Drive.

        Args:
            file_id: The ID of the file to get metadata for.

        Returns:
            Tuple of (metadata dict, error message).
        """
        connected_account_id = await self.get_connected_account_id()
        if not connected_account_id:
            return None, "No connected account ID found"

        entity_id = await self.get_entity_id()
        service = await self._get_service()
        return await service.get_file_metadata(
            connected_account_id=connected_account_id,
            entity_id=entity_id,
            file_id=file_id,
        )

    async def get_drive_start_page_token(self) -> tuple[str | None, str | None]:
        """
        Get the starting page token for Google Drive change tracking.

        Returns:
            Tuple of (start_page_token, error message).
        """
        connected_account_id = await self.get_connected_account_id()
        if not connected_account_id:
            return None, "No connected account ID found"

        entity_id = await self.get_entity_id()
        service = await self._get_service()
        return await service.get_drive_start_page_token(
            connected_account_id=connected_account_id,
            entity_id=entity_id,
        )

    async def list_drive_changes(
        self,
        page_token: str | None = None,
        page_size: int = 100,
        include_removed: bool = True,
    ) -> tuple[list[dict[str, Any]], str | None, str | None]:
        """
        List changes in Google Drive since the given page token.

        Args:
            page_token: Page token from previous sync (optional).
            page_size: Number of changes per page.
            include_removed: Whether to include removed items.

        Returns:
            Tuple of (changes list, new_start_page_token, error message).
        """
        connected_account_id = await self.get_connected_account_id()
        if not connected_account_id:
            return [], None, "No connected account ID found"

        entity_id = await self.get_entity_id()
        service = await self._get_service()
        return await service.list_drive_changes(
            connected_account_id=connected_account_id,
            entity_id=entity_id,
            page_token=page_token,
            page_size=page_size,
            include_removed=include_removed,
        )


# ============ File Processing Utilities ============


async def _process_file_content(
    content: bytes | str,
    file_name: str,
    file_id: str,
    mime_type: str,
    search_space_id: int,
    user_id: str,
    session: AsyncSession,
    task_logger: TaskLoggingService,
    log_entry: Log,
    processing_errors: list[str],
) -> str:
    """
    Process file content and return markdown text.

    For binary files (PDFs, images, etc.), uses Surfsense's ETL service.
    For text files, decodes as UTF-8.

    Args:
        content: File content as bytes or string
        file_name: Name of the file
        file_id: Google Drive file ID
        mime_type: MIME type of the file
        search_space_id: Search space ID
        user_id: User ID
        session: Database session
        task_logger: Task logging service
        log_entry: Log entry for tracking
        processing_errors: List to append errors to

    Returns:
        Markdown content string
    """
    # Ensure content is bytes
    if isinstance(content, str):
        content = content.encode("utf-8")

    # Check if this is a binary file based on extension or MIME type
    is_binary = _is_binary_file(file_name, mime_type)

    if is_binary:
        # Use ETL service for binary files (PDF, Office docs, etc.)
        temp_file_path = None
        try:
            # Get file extension
            extension = Path(file_name).suffix or ".bin"

            # Write to temp file
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=extension
            ) as tmp_file:
                tmp_file.write(content)
                temp_file_path = tmp_file.name

            # Use the configured ETL service to extract text
            extracted_text = await _extract_text_with_etl(
                temp_file_path, file_name, task_logger, log_entry
            )

            if extracted_text:
                return extracted_text
            else:
                # Fallback if extraction fails
                logger.warning(f"ETL returned empty for binary file {file_name}")
                return f"# {file_name}\n\n[Binary file - text extraction failed]\n\n**File ID:** {file_id}\n**Type:** {mime_type}\n"

        except Exception as e:
            error_msg = f"Error processing binary file {file_name}: {e!s}"
            logger.error(error_msg)
            processing_errors.append(error_msg)
            return f"# {file_name}\n\n[Binary file - processing error]\n\n**File ID:** {file_id}\n**Type:** {mime_type}\n"
        finally:
            # Cleanup temp file
            if temp_file_path and os.path.exists(temp_file_path):
                with contextlib.suppress(Exception):
                    os.unlink(temp_file_path)
    else:
        # Text file - try to decode as UTF-8
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            # Try other encodings
            for encoding in ["latin-1", "cp1252", "iso-8859-1"]:
                try:
                    return content.decode(encoding)
                except UnicodeDecodeError:
                    continue

            # If all encodings fail, treat as binary
            error_msg = f"Could not decode text file {file_name} with any encoding"
            logger.warning(error_msg)
            processing_errors.append(error_msg)
            return f"# {file_name}\n\n[File content could not be decoded]\n\n**File ID:** {file_id}\n**Type:** {mime_type}\n"


async def _extract_text_with_etl(
    file_path: str,
    file_name: str,
    task_logger: TaskLoggingService,
    log_entry: Log,
) -> str | None:
    """
    Extract text from a file using the configured ETL service.

    Args:
        file_path: Path to the file
        file_name: Name of the file
        task_logger: Task logging service
        log_entry: Log entry for tracking

    Returns:
        Extracted text as markdown, or None if extraction fails
    """
    import warnings
    from logging import ERROR, getLogger

    etl_service = config.ETL_SERVICE
    logger.debug(
        f"[_extract_text_with_etl] START - file_path={file_path}, file_name={file_name}, etl_service={etl_service}"
    )

    try:
        if etl_service == "UNSTRUCTURED":
            logger.debug("[_extract_text_with_etl] Using UNSTRUCTURED ETL")
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
            logger.debug(
                f"[_extract_text_with_etl] UNSTRUCTURED loaded {len(docs) if docs else 0} docs"
            )
            if docs:
                result = await convert_document_to_markdown(docs)
                logger.debug(
                    f"[_extract_text_with_etl] UNSTRUCTURED result: {len(result) if result else 0} chars"
                )
                return result
            logger.debug("[_extract_text_with_etl] UNSTRUCTURED returned no docs")
            return None

        elif etl_service == "LLAMACLOUD":
            logger.debug("[_extract_text_with_etl] Using LLAMACLOUD ETL")
            from app.tasks.document_processors.file_processors import (
                parse_with_llamacloud_retry,
            )

            # Estimate pages (rough estimate based on file size)
            file_size = os.path.getsize(file_path)
            estimated_pages = max(1, file_size // (80 * 1024))

            result = await parse_with_llamacloud_retry(
                file_path=file_path,
                estimated_pages=estimated_pages,
                task_logger=task_logger,
                log_entry=log_entry,
            )

            markdown_documents = await result.aget_markdown_documents(
                split_by_page=False
            )
            logger.debug(
                f"[_extract_text_with_etl] LLAMACLOUD got {len(markdown_documents) if markdown_documents else 0} markdown docs"
            )
            if markdown_documents:
                text = markdown_documents[0].text
                logger.debug(
                    f"[_extract_text_with_etl] LLAMACLOUD result: {len(text) if text else 0} chars"
                )
                return text
            logger.debug(
                "[_extract_text_with_etl] LLAMACLOUD returned no markdown docs"
            )
            return None

        elif etl_service == "DOCLING":
            logger.debug("[_extract_text_with_etl] Using DOCLING ETL")
            from app.services.docling_service import create_docling_service

            docling_service = create_docling_service()

            # Suppress pdfminer warnings
            pdfminer_logger = getLogger("pdfminer")
            original_level = pdfminer_logger.level

            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore", category=UserWarning, module="pdfminer"
                )
                warnings.filterwarnings(
                    "ignore", message=".*Cannot set gray non-stroke color.*"
                )
                warnings.filterwarnings("ignore", message=".*invalid float value.*")

                pdfminer_logger.setLevel(ERROR)

                try:
                    result = await docling_service.process_document(
                        file_path, file_name
                    )
                    logger.debug(
                        f"[_extract_text_with_etl] DOCLING result keys: {list(result.keys()) if result else 'None'}"
                    )
                finally:
                    pdfminer_logger.setLevel(original_level)

            content = result.get("content")
            logger.debug(
                f"[_extract_text_with_etl] DOCLING content: {len(content) if content else 0} chars"
            )
            return content
        else:
            logger.warning(
                f"[_extract_text_with_etl] Unknown ETL service: {etl_service}"
            )
            return None

    except Exception as e:
        logger.error(
            f"[_extract_text_with_etl] ETL extraction EXCEPTION for {file_name}: {e!s}"
        )
        import traceback

        logger.error(f"[_extract_text_with_etl] Traceback: {traceback.format_exc()}")
        return None


# ============ Indexer Functions ============


async def check_document_by_unique_identifier(
    session: AsyncSession, unique_identifier_hash: str
) -> Document | None:
    """Check if a document with the given unique identifier hash already exists."""
    from sqlalchemy.future import select
    from sqlalchemy.orm import selectinload

    existing_doc_result = await session.execute(
        select(Document)
        .options(selectinload(Document.chunks))
        .where(Document.unique_identifier_hash == unique_identifier_hash)
    )
    return existing_doc_result.scalars().first()


async def check_document_by_content_hash(
    session: AsyncSession, content_hash: str
) -> Document | None:
    """Check if a document with the given content hash already exists.

    This is used to prevent duplicate content from being indexed, regardless
    of which connector originally indexed it.
    """
    from sqlalchemy.future import select

    existing_doc_result = await session.execute(
        select(Document).where(Document.content_hash == content_hash)
    )
    return existing_doc_result.scalars().first()


async def check_document_by_google_drive_file_id(
    session: AsyncSession, file_id: str, search_space_id: int
) -> Document | None:
    """Check if a document with this Google Drive file ID exists (from any connector).

    This checks both metadata key formats:
    - 'google_drive_file_id' (normal Google Drive connector)
    - 'file_id' (Composio Google Drive connector)

    This allows detecting duplicates BEFORE downloading/ETL, saving expensive API calls.
    """
    from sqlalchemy import String, cast, or_
    from sqlalchemy.future import select

    # When casting JSON to String, the result includes quotes: "value" instead of value
    # So we need to compare with the quoted version
    quoted_file_id = f'"{file_id}"'

    existing_doc_result = await session.execute(
        select(Document).where(
            Document.search_space_id == search_space_id,
            or_(
                # Normal Google Drive connector format
                cast(Document.document_metadata["google_drive_file_id"], String)
                == quoted_file_id,
                # Composio Google Drive connector format
                cast(Document.document_metadata["file_id"], String) == quoted_file_id,
            ),
        )
    )
    return existing_doc_result.scalars().first()


async def update_connector_last_indexed(
    session: AsyncSession,
    connector,
    update_last_indexed: bool = True,
) -> None:
    """Update the last_indexed_at timestamp for a connector."""
    if update_last_indexed:
        connector.last_indexed_at = datetime.now(
            UTC
        )  # Use UTC for timezone consistency
        logger.info(f"Updated last_indexed_at to {connector.last_indexed_at}")


def generate_indexing_settings_hash(
    selected_folders: list[dict],
    selected_files: list[dict],
    indexing_options: dict,
) -> str:
    """Generate a hash of indexing settings to detect configuration changes.

    This hash is used to determine if indexing settings have changed since
    the last index, which would require a full re-scan instead of delta sync.

    Args:
        selected_folders: List of {id, name} for folders to index
        selected_files: List of {id, name} for individual files to index
        indexing_options: Dict with max_files_per_folder, include_subfolders, etc.

    Returns:
        MD5 hash string of the settings
    """
    settings = {
        "folders": sorted([f.get("id", "") for f in selected_folders]),
        "files": sorted([f.get("id", "") for f in selected_files]),
        "include_subfolders": indexing_options.get("include_subfolders", True),
        "max_files_per_folder": indexing_options.get("max_files_per_folder", 100),
    }
    return hashlib.md5(
        json.dumps(settings, sort_keys=True).encode(), usedforsecurity=False
    ).hexdigest()


async def index_composio_google_drive(
    session: AsyncSession,
    connector,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    task_logger: TaskLoggingService,
    log_entry,
    update_last_indexed: bool = True,
    max_items: int = 1000,
    on_heartbeat_callback: HeartbeatCallbackType | None = None,
) -> tuple[int, int, str | None]:
    """Index Google Drive files via Composio with delta sync support.

    Returns:
        Tuple of (documents_indexed, documents_skipped, error_message or None)

    Delta Sync Flow:
    1. First sync: Full scan + get initial page token
    2. Subsequent syncs: Use LIST_CHANGES to process only changed files
       (unless settings changed or incremental_sync is disabled)

    Supports folder/file selection via connector config:
    - selected_folders: List of {id, name} for folders to index
    - selected_files: List of {id, name} for individual files to index
    - indexing_options: {max_files_per_folder, incremental_sync, include_subfolders}
    """
    try:
        composio_connector = ComposioGoogleDriveConnector(session, connector_id)
        connector_config = await composio_connector.get_config()

        # Get folder/file selection configuration
        selected_folders = connector_config.get("selected_folders", [])
        selected_files = connector_config.get("selected_files", [])
        indexing_options = connector_config.get("indexing_options", {})

        max_files_per_folder = indexing_options.get("max_files_per_folder", 100)
        include_subfolders = indexing_options.get("include_subfolders", True)
        incremental_sync = indexing_options.get("incremental_sync", True)

        # Generate current settings hash to detect configuration changes
        current_settings_hash = generate_indexing_settings_hash(
            selected_folders, selected_files, indexing_options
        )
        last_settings_hash = connector_config.get("last_indexed_settings_hash")

        # Detect if settings changed since last index
        settings_changed = (
            last_settings_hash is not None
            and current_settings_hash != last_settings_hash
        )

        if settings_changed:
            logger.info(
                f"Indexing settings changed for connector {connector_id}. "
                f"Will perform full re-scan to apply new configuration."
            )

        # Check for stored page token for delta sync
        stored_page_token = connector_config.get("drive_page_token")

        # Determine whether to use delta sync:
        # - Must have a stored page token
        # - Must have been indexed before (last_indexed_at exists)
        # - User must have incremental_sync enabled
        # - Settings must not have changed (folder/subfolder config)
        use_delta_sync = (
            incremental_sync
            and stored_page_token
            and connector.last_indexed_at
            and not settings_changed
        )

        # Route to delta sync or full scan
        if use_delta_sync:
            logger.info(
                f"Using delta sync for Composio Google Drive connector {connector_id}"
            )
            await task_logger.log_task_progress(
                log_entry,
                f"Starting delta sync for Google Drive via Composio (connector {connector_id})",
                {"stage": "delta_sync", "token": stored_page_token[:20] + "..."},
            )

            (
                documents_indexed,
                documents_skipped,
                processing_errors,
            ) = await _index_composio_drive_delta_sync(
                session=session,
                composio_connector=composio_connector,
                connector_id=connector_id,
                search_space_id=search_space_id,
                user_id=user_id,
                page_token=stored_page_token,
                max_items=max_items,
                task_logger=task_logger,
                log_entry=log_entry,
                on_heartbeat_callback=on_heartbeat_callback,
            )
        else:
            logger.info(
                f"Using full scan for Composio Google Drive connector {connector_id} (first sync or no token)"
            )
            await task_logger.log_task_progress(
                log_entry,
                f"Fetching Google Drive files via Composio for connector {connector_id}",
                {
                    "stage": "full_scan",
                    "selected_folders": len(selected_folders),
                    "selected_files": len(selected_files),
                },
            )

            (
                documents_indexed,
                documents_skipped,
                processing_errors,
            ) = await _index_composio_drive_full_scan(
                session=session,
                composio_connector=composio_connector,
                connector_id=connector_id,
                search_space_id=search_space_id,
                user_id=user_id,
                selected_folders=selected_folders,
                selected_files=selected_files,
                max_files_per_folder=max_files_per_folder,
                include_subfolders=include_subfolders,
                max_items=max_items,
                task_logger=task_logger,
                log_entry=log_entry,
                on_heartbeat_callback=on_heartbeat_callback,
            )

        # Get new page token for next sync (always update after successful sync)
        new_token, token_error = await composio_connector.get_drive_start_page_token()
        if new_token and not token_error:
            # Refresh connector to avoid stale state
            await session.refresh(connector)

            if not connector.config:
                connector.config = {}
            connector.config["drive_page_token"] = new_token
            flag_modified(connector, "config")
            logger.info(f"Updated drive_page_token for connector {connector_id}")
        elif token_error:
            logger.warning(f"Failed to get new page token: {token_error}")

        # Save current settings hash for future change detection
        # This allows detecting when folder/subfolder settings change
        if not connector.config:
            connector.config = {}
        connector.config["last_indexed_settings_hash"] = current_settings_hash
        flag_modified(connector, "config")
        logger.info(f"Saved indexing settings hash for connector {connector_id}")

        # CRITICAL: Always update timestamp so Electric SQL syncs and UI shows indexed status
        await update_connector_last_indexed(session, connector, update_last_indexed)

        # Final commit
        logger.info(
            f"Final commit: Total {documents_indexed} Google Drive files processed"
        )
        await session.commit()
        logger.info(
            "Successfully committed all Composio Google Drive document changes to database"
        )

        # Handle processing errors
        error_message = None
        if processing_errors:
            if len(processing_errors) == 1:
                error_message = processing_errors[0]
            else:
                error_message = f"Failed to process {len(processing_errors)} file(s). First error: {processing_errors[0]}"
            await task_logger.log_task_failure(
                log_entry,
                f"Completed Google Drive indexing with {len(processing_errors)} error(s) for connector {connector_id}",
                {
                    "documents_indexed": documents_indexed,
                    "documents_skipped": documents_skipped,
                    "sync_type": "delta" if use_delta_sync else "full",
                    "errors": processing_errors,
                },
            )
        else:
            await task_logger.log_task_success(
                log_entry,
                f"Successfully completed Google Drive indexing via Composio for connector {connector_id}",
                {
                    "documents_indexed": documents_indexed,
                    "documents_skipped": documents_skipped,
                    "sync_type": "delta" if use_delta_sync else "full",
                },
            )

        return documents_indexed, documents_skipped, error_message

    except Exception as e:
        logger.error(f"Failed to index Google Drive via Composio: {e!s}", exc_info=True)
        return 0, 0, f"Failed to index Google Drive via Composio: {e!s}"


async def _index_composio_drive_delta_sync(
    session: AsyncSession,
    composio_connector: ComposioGoogleDriveConnector,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    page_token: str,
    max_items: int,
    task_logger: TaskLoggingService,
    log_entry,
    on_heartbeat_callback: HeartbeatCallbackType | None = None,
) -> tuple[int, int, list[str]]:
    """Index Google Drive files using delta sync (only changed files).

    Uses GOOGLEDRIVE_LIST_CHANGES to fetch only files that changed since last sync.
    Handles: new files, modified files, and deleted files.
    """
    documents_indexed = 0
    documents_skipped = 0
    processing_errors = []
    last_heartbeat_time = time.time()

    # Fetch all changes with pagination
    all_changes = []
    current_token = page_token

    while len(all_changes) < max_items:
        changes, next_token, error = await composio_connector.list_drive_changes(
            page_token=current_token,
            page_size=100,
            include_removed=True,
        )

        if error:
            logger.error(f"Error fetching Drive changes: {error}")
            processing_errors.append(f"Failed to fetch changes: {error}")
            break

        all_changes.extend(changes)

        if not next_token or next_token == current_token:
            break
        current_token = next_token

    if not all_changes:
        logger.info("No changes detected since last sync")
        return 0, 0, []

    logger.info(f"Processing {len(all_changes)} changes from delta sync")

    for change in all_changes[:max_items]:
        # Send heartbeat periodically to indicate task is still alive
        if on_heartbeat_callback:
            current_time = time.time()
            if current_time - last_heartbeat_time >= HEARTBEAT_INTERVAL_SECONDS:
                await on_heartbeat_callback(documents_indexed)
                last_heartbeat_time = current_time

        try:
            # Handle removed files
            is_removed = change.get("removed", False)
            file_info = change.get("file", {})
            file_id = change.get("fileId") or file_info.get("id", "")

            if not file_id:
                documents_skipped += 1
                continue

            # Check if file was trashed or removed
            if is_removed or file_info.get("trashed", False):
                # Remove document from database
                document_type = DocumentType(TOOLKIT_TO_DOCUMENT_TYPE["googledrive"])
                unique_identifier_hash = generate_unique_identifier_hash(
                    document_type, f"drive_{file_id}", search_space_id
                )
                existing_document = await check_document_by_unique_identifier(
                    session, unique_identifier_hash
                )
                if existing_document:
                    await session.delete(existing_document)
                    documents_indexed += 1
                    logger.info(f"Deleted document for removed/trashed file: {file_id}")
                continue

            # Process changed file
            file_name = file_info.get("name", "") or "Untitled"
            mime_type = file_info.get("mimeType", "") or file_info.get("mime_type", "")

            # Skip folders
            if mime_type == "application/vnd.google-apps.folder":
                continue

            # Process the file
            indexed, skipped, errors = await _process_single_drive_file(
                session=session,
                composio_connector=composio_connector,
                file_id=file_id,
                file_name=file_name,
                mime_type=mime_type,
                connector_id=connector_id,
                search_space_id=search_space_id,
                user_id=user_id,
                task_logger=task_logger,
                log_entry=log_entry,
            )

            documents_indexed += indexed
            documents_skipped += skipped
            processing_errors.extend(errors)

            # Batch commit every 10 documents
            if documents_indexed > 0 and documents_indexed % 10 == 0:
                await session.commit()
                logger.info(f"Committed batch: {documents_indexed} changes processed")

        except Exception as e:
            error_msg = f"Error processing change for file {file_id}: {e!s}"
            logger.error(error_msg, exc_info=True)
            processing_errors.append(error_msg)
            documents_skipped += 1

    logger.info(
        f"Delta sync complete: {documents_indexed} indexed, {documents_skipped} skipped"
    )
    return documents_indexed, documents_skipped, processing_errors


async def _index_composio_drive_full_scan(
    session: AsyncSession,
    composio_connector: ComposioGoogleDriveConnector,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    selected_folders: list[dict],
    selected_files: list[dict],
    max_files_per_folder: int,
    include_subfolders: bool,
    max_items: int,
    task_logger: TaskLoggingService,
    log_entry,
    on_heartbeat_callback: HeartbeatCallbackType | None = None,
) -> tuple[int, int, list[str]]:
    """Index Google Drive files using full scan (first sync or when no delta token)."""
    documents_indexed = 0
    documents_skipped = 0
    processing_errors = []
    last_heartbeat_time = time.time()

    all_files = []

    # If specific folders/files are selected, fetch from those
    if selected_folders or selected_files:
        # Fetch files from selected folders
        for folder in selected_folders:
            folder_id = folder.get("id")
            folder_name = folder.get("name", "Unknown")

            if not folder_id:
                continue

            # Handle special case for "root" folder
            actual_folder_id = None if folder_id == "root" else folder_id

            logger.info(f"Fetching files from folder: {folder_name} ({folder_id})")

            # Fetch files from this folder
            folder_files = []
            page_token = None

            while len(folder_files) < max_files_per_folder:
                (
                    files,
                    next_token,
                    error,
                ) = await composio_connector.list_drive_files(
                    folder_id=actual_folder_id,
                    page_token=page_token,
                    page_size=min(100, max_files_per_folder - len(folder_files)),
                )

                if error:
                    logger.warning(
                        f"Failed to fetch files from folder {folder_name}: {error}"
                    )
                    break

                # Process files
                for file_info in files:
                    mime_type = file_info.get("mimeType", "") or file_info.get(
                        "mime_type", ""
                    )

                    # If it's a folder and include_subfolders is enabled, recursively fetch
                    if mime_type == "application/vnd.google-apps.folder":
                        if include_subfolders:
                            # Add subfolder files recursively
                            subfolder_files = await _fetch_folder_files_recursively(
                                composio_connector,
                                file_info.get("id"),
                                max_files=max_files_per_folder,
                                current_count=len(folder_files),
                            )
                            folder_files.extend(subfolder_files)
                    else:
                        folder_files.append(file_info)

                if not next_token:
                    break
                page_token = next_token

            all_files.extend(folder_files[:max_files_per_folder])
            logger.info(f"Found {len(folder_files)} files in folder {folder_name}")

        # Add specifically selected files - fetch metadata to get mimeType
        for selected_file in selected_files:
            file_id = selected_file.get("id")
            file_name = selected_file.get("name", "Unknown")

            if not file_id:
                continue

            # Fetch file metadata to get proper mimeType
            metadata, meta_error = await composio_connector.get_file_metadata(file_id)
            if metadata and not meta_error:
                all_files.append(
                    {
                        "id": file_id,
                        "name": metadata.get("name") or file_name,
                        "mimeType": metadata.get("mimeType", ""),
                        "modifiedTime": metadata.get("modifiedTime", ""),
                        "createdTime": metadata.get("createdTime", ""),
                    }
                )
                logger.info(
                    f"Fetched metadata for UI-selected file: {file_name} "
                    f"(mimeType={metadata.get('mimeType', 'unknown')})"
                )
            else:
                # Fallback if metadata fetch fails - content-based detection will handle it
                logger.warning(
                    f"Could not fetch metadata for file {file_name}: {meta_error}. "
                    f"Falling back to content-based detection."
                )
                all_files.append(
                    {
                        "id": file_id,
                        "name": file_name,
                        "mimeType": "",  # Content-based detection will handle this
                    }
                )
    else:
        # No selection specified - fetch all files (original behavior)
        page_token = None

        while len(all_files) < max_items:
            files, next_token, error = await composio_connector.list_drive_files(
                page_token=page_token,
                page_size=min(100, max_items - len(all_files)),
            )

            if error:
                return 0, 0, [f"Failed to fetch Drive files: {error}"]

            all_files.extend(files)

            if not next_token:
                break
            page_token = next_token

    if not all_files:
        logger.info("No Google Drive files found")
        return 0, 0, []

    logger.info(
        f"Found {len(all_files)} Google Drive files to index via Composio (full scan)"
    )

    for file_info in all_files:
        # Send heartbeat periodically to indicate task is still alive
        if on_heartbeat_callback:
            current_time = time.time()
            if current_time - last_heartbeat_time >= HEARTBEAT_INTERVAL_SECONDS:
                await on_heartbeat_callback(documents_indexed)
                last_heartbeat_time = current_time

        try:
            # Handle both standard Google API and potential Composio variations
            file_id = file_info.get("id", "") or file_info.get("fileId", "")
            file_name = (
                file_info.get("name", "") or file_info.get("fileName", "") or "Untitled"
            )
            mime_type = file_info.get("mimeType", "") or file_info.get("mime_type", "")

            if not file_id:
                documents_skipped += 1
                continue

            # Skip folders
            if mime_type == "application/vnd.google-apps.folder":
                continue

            # Process the file
            indexed, skipped, errors = await _process_single_drive_file(
                session=session,
                composio_connector=composio_connector,
                file_id=file_id,
                file_name=file_name,
                mime_type=mime_type,
                connector_id=connector_id,
                search_space_id=search_space_id,
                user_id=user_id,
                task_logger=task_logger,
                log_entry=log_entry,
            )

            documents_indexed += indexed
            documents_skipped += skipped
            processing_errors.extend(errors)

            # Batch commit every 10 documents
            if documents_indexed > 0 and documents_indexed % 10 == 0:
                logger.info(
                    f"Committing batch: {documents_indexed} Google Drive files processed so far"
                )
                await session.commit()

        except Exception as e:
            error_msg = f"Error processing Drive file {file_name or 'unknown'}: {e!s}"
            logger.error(error_msg, exc_info=True)
            processing_errors.append(error_msg)
            documents_skipped += 1

    logger.info(
        f"Full scan complete: {documents_indexed} indexed, {documents_skipped} skipped"
    )
    return documents_indexed, documents_skipped, processing_errors


async def _process_single_drive_file(
    session: AsyncSession,
    composio_connector: ComposioGoogleDriveConnector,
    file_id: str,
    file_name: str,
    mime_type: str,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    task_logger: TaskLoggingService,
    log_entry,
) -> tuple[int, int, list[str]]:
    """Process a single Google Drive file for indexing.

    Returns:
        Tuple of (documents_indexed, documents_skipped, processing_errors)
    """
    processing_errors = []

    # ========== EARLY DUPLICATE CHECK BY FILE ID ==========
    # Check if this Google Drive file was already indexed by ANY connector
    # This happens BEFORE download/ETL to save expensive API calls
    existing_by_file_id = await check_document_by_google_drive_file_id(
        session, file_id, search_space_id
    )
    if existing_by_file_id:
        logger.info(
            f"Skipping file {file_name} (file_id={file_id}): already indexed "
            f"by {existing_by_file_id.document_type.value} as '{existing_by_file_id.title}' "
            f"(saved download & ETL cost)"
        )
        return 0, 1, processing_errors  # Skip - NO download, NO ETL!
    # ======================================================

    # Generate unique identifier hash
    document_type = DocumentType(TOOLKIT_TO_DOCUMENT_TYPE["googledrive"])
    unique_identifier_hash = generate_unique_identifier_hash(
        document_type, f"drive_{file_id}", search_space_id
    )

    # Check if document exists by unique identifier (same connector, same file)
    existing_document = await check_document_by_unique_identifier(
        session, unique_identifier_hash
    )

    # Get file content (pass mime_type for Google Workspace export handling)
    content, content_error = await composio_connector.get_drive_file_content(
        file_id, original_mime_type=mime_type
    )

    if content_error or not content:
        logger.warning(f"Could not get content for file {file_name}: {content_error}")
        # Use metadata as content fallback
        markdown_content = f"# {file_name}\n\n"
        markdown_content += f"**File ID:** {file_id}\n"
        markdown_content += f"**Type:** {mime_type}\n"
    elif isinstance(content, dict):
        # Safety check: if content is still a dict, log error and use fallback
        error_msg = f"Unexpected dict content format for file {file_name}: {list(content.keys())}"
        logger.error(error_msg)
        processing_errors.append(error_msg)
        markdown_content = f"# {file_name}\n\n"
        markdown_content += f"**File ID:** {file_id}\n"
        markdown_content += f"**Type:** {mime_type}\n"
    else:
        # Process content based on file type
        markdown_content = await _process_file_content(
            content=content,
            file_name=file_name,
            file_id=file_id,
            mime_type=mime_type,
            search_space_id=search_space_id,
            user_id=user_id,
            session=session,
            task_logger=task_logger,
            log_entry=log_entry,
            processing_errors=processing_errors,
        )

    content_hash = generate_content_hash(markdown_content, search_space_id)

    if existing_document:
        if existing_document.content_hash == content_hash:
            return 0, 1, processing_errors  # Skipped - unchanged

        # Update existing document
        user_llm = await get_user_long_context_llm(session, user_id, search_space_id)

        if user_llm:
            document_metadata = {
                "file_id": file_id,
                "file_name": file_name,
                "mime_type": mime_type,
                "document_type": "Google Drive File (Composio)",
            }
            (
                summary_content,
                summary_embedding,
            ) = await generate_document_summary(
                markdown_content, user_llm, document_metadata
            )
        else:
            summary_content = f"Google Drive File: {file_name}\n\nType: {mime_type}"
            summary_embedding = config.embedding_model_instance.embed(summary_content)

        chunks = await create_document_chunks(markdown_content)

        existing_document.title = f"Drive: {file_name}"
        existing_document.content = summary_content
        existing_document.content_hash = content_hash
        existing_document.embedding = summary_embedding
        existing_document.document_metadata = {
            "file_id": file_id,
            "file_name": file_name,
            "FILE_NAME": file_name,  # For compatibility
            "mime_type": mime_type,
            "connector_id": connector_id,
            "source": "composio",
        }
        existing_document.chunks = chunks
        existing_document.updated_at = get_current_timestamp()

        return 1, 0, processing_errors  # Indexed - updated

    # Check if content_hash already exists (from any connector)
    # This prevents duplicate content and avoids IntegrityError on unique constraint
    existing_by_content_hash = await check_document_by_content_hash(
        session, content_hash
    )
    if existing_by_content_hash:
        logger.info(
            f"Skipping file {file_name} (file_id={file_id}): identical content "
            f"already indexed as '{existing_by_content_hash.title}'"
        )
        return 0, 1, processing_errors  # Skipped - duplicate content

    # Create new document
    user_llm = await get_user_long_context_llm(session, user_id, search_space_id)

    if user_llm:
        document_metadata = {
            "file_id": file_id,
            "file_name": file_name,
            "mime_type": mime_type,
            "document_type": "Google Drive File (Composio)",
        }
        (
            summary_content,
            summary_embedding,
        ) = await generate_document_summary(
            markdown_content, user_llm, document_metadata
        )
    else:
        summary_content = f"Google Drive File: {file_name}\n\nType: {mime_type}"
        summary_embedding = config.embedding_model_instance.embed(summary_content)

    chunks = await create_document_chunks(markdown_content)

    document = Document(
        search_space_id=search_space_id,
        title=f"Drive: {file_name}",
        document_type=DocumentType(TOOLKIT_TO_DOCUMENT_TYPE["googledrive"]),
        document_metadata={
            "file_id": file_id,
            "file_name": file_name,
            "FILE_NAME": file_name,  # For compatibility
            "mime_type": mime_type,
            "toolkit_id": "googledrive",
            "source": "composio",
        },
        content=summary_content,
        content_hash=content_hash,
        unique_identifier_hash=unique_identifier_hash,
        embedding=summary_embedding,
        chunks=chunks,
        updated_at=get_current_timestamp(),
        created_by_id=user_id,
        connector_id=connector_id,
    )
    session.add(document)

    return 1, 0, processing_errors  # Indexed - new


async def _fetch_folder_files_recursively(
    composio_connector: ComposioGoogleDriveConnector,
    folder_id: str,
    max_files: int = 100,
    current_count: int = 0,
    depth: int = 0,
    max_depth: int = 10,
) -> list[dict[str, Any]]:
    """
    Recursively fetch files from a Google Drive folder via Composio.

    Args:
        composio_connector: The Composio connector instance
        folder_id: Google Drive folder ID
        max_files: Maximum number of files to fetch
        current_count: Current number of files already fetched
        depth: Current recursion depth
        max_depth: Maximum recursion depth to prevent infinite loops

    Returns:
        List of file info dictionaries
    """
    if depth >= max_depth:
        logger.warning(f"Max recursion depth reached for folder {folder_id}")
        return []

    if current_count >= max_files:
        return []

    all_files = []
    page_token = None

    try:
        while len(all_files) + current_count < max_files:
            files, next_token, error = await composio_connector.list_drive_files(
                folder_id=folder_id,
                page_token=page_token,
                page_size=min(100, max_files - len(all_files) - current_count),
            )

            if error:
                logger.warning(
                    f"Error fetching files from subfolder {folder_id}: {error}"
                )
                break

            for file_info in files:
                mime_type = file_info.get("mimeType", "") or file_info.get(
                    "mime_type", ""
                )

                if mime_type == "application/vnd.google-apps.folder":
                    # Recursively fetch from subfolders
                    subfolder_files = await _fetch_folder_files_recursively(
                        composio_connector,
                        file_info.get("id"),
                        max_files=max_files,
                        current_count=current_count + len(all_files),
                        depth=depth + 1,
                        max_depth=max_depth,
                    )
                    all_files.extend(subfolder_files)
                else:
                    all_files.append(file_info)

                if len(all_files) + current_count >= max_files:
                    break

            if not next_token:
                break
            page_token = next_token

        return all_files[: max_files - current_count]

    except Exception as e:
        logger.error(f"Error in recursive folder fetch: {e!s}")
        return all_files
