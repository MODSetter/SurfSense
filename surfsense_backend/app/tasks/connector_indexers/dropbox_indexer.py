"""Dropbox indexer using the shared IndexingPipelineService.

File-level pre-filter (_should_skip_file) handles content_hash and
server_modified checks.  download_and_extract_content() returns
markdown which is fed into ConnectorDocument -> pipeline.
"""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable

from sqlalchemy import String, cast, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.config import config
from app.connectors.dropbox import (
    DropboxClient,
    download_and_extract_content,
    get_file_by_path,
    get_files_in_folder,
)
from app.connectors.dropbox.file_types import should_skip_file as skip_item
from app.db import Document, DocumentStatus, DocumentType, SearchSourceConnectorType
from app.indexing_pipeline.connector_document import ConnectorDocument
from app.indexing_pipeline.document_hashing import compute_identifier_hash
from app.indexing_pipeline.indexing_pipeline_service import IndexingPipelineService
from app.services.llm_service import get_user_long_context_llm
from app.services.task_logging_service import TaskLoggingService
from app.tasks.connector_indexers.base import (
    check_document_by_unique_identifier,
    get_connector_by_id,
    update_connector_last_indexed,
)

HeartbeatCallbackType = Callable[[int], Awaitable[None]]
HEARTBEAT_INTERVAL_SECONDS = 30

logger = logging.getLogger(__name__)


async def _should_skip_file(
    session: AsyncSession,
    file: dict,
    search_space_id: int,
) -> tuple[bool, str | None]:
    """Pre-filter: detect unchanged / rename-only files."""
    file_id = file.get("id", "")
    file_name = file.get("name", "Unknown")

    if skip_item(file):
        return True, "folder/non-downloadable"
    if not file_id:
        return True, "missing file_id"

    primary_hash = compute_identifier_hash(
        DocumentType.DROPBOX_FILE.value, file_id, search_space_id
    )
    existing = await check_document_by_unique_identifier(session, primary_hash)

    if not existing:
        result = await session.execute(
            select(Document).where(
                Document.search_space_id == search_space_id,
                Document.document_type == DocumentType.DROPBOX_FILE,
                cast(Document.document_metadata["dropbox_file_id"], String) == file_id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.unique_identifier_hash = primary_hash
            logger.debug(f"Found Dropbox doc by metadata for file_id: {file_id}")

    if not existing:
        return False, None

    incoming_content_hash = file.get("content_hash")
    meta = existing.document_metadata or {}
    stored_content_hash = meta.get("content_hash")

    incoming_mtime = file.get("server_modified")
    stored_mtime = meta.get("modified_time")

    content_unchanged = False
    if incoming_content_hash and stored_content_hash:
        content_unchanged = incoming_content_hash == stored_content_hash
    elif incoming_content_hash and not stored_content_hash:
        return False, None
    elif not incoming_content_hash and incoming_mtime and stored_mtime:
        content_unchanged = incoming_mtime == stored_mtime
    elif not incoming_content_hash:
        return False, None

    if not content_unchanged:
        return False, None

    old_name = meta.get("dropbox_file_name")
    if old_name and old_name != file_name:
        existing.title = file_name
        if not existing.document_metadata:
            existing.document_metadata = {}
        existing.document_metadata["dropbox_file_name"] = file_name
        if incoming_mtime:
            existing.document_metadata["modified_time"] = incoming_mtime
        flag_modified(existing, "document_metadata")
        await session.commit()
        logger.info(f"Rename-only update: '{old_name}' -> '{file_name}'")
        return True, f"File renamed: '{old_name}' -> '{file_name}'"

    if not DocumentStatus.is_state(existing.status, DocumentStatus.READY):
        return True, "skipped (previously failed)"
    return True, "unchanged"


def _build_connector_doc(
    file: dict,
    markdown: str,
    dropbox_metadata: dict,
    *,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    enable_summary: bool,
) -> ConnectorDocument:
    file_id = file.get("id", "")
    file_name = file.get("name", "Unknown")

    metadata = {
        **dropbox_metadata,
        "connector_id": connector_id,
        "document_type": "Dropbox File",
        "connector_type": "Dropbox",
    }

    fallback_summary = f"File: {file_name}\n\n{markdown[:4000]}"

    return ConnectorDocument(
        title=file_name,
        source_markdown=markdown,
        unique_id=file_id,
        document_type=DocumentType.DROPBOX_FILE,
        search_space_id=search_space_id,
        connector_id=connector_id,
        created_by_id=user_id,
        should_summarize=enable_summary,
        fallback_summary=fallback_summary,
        metadata=metadata,
    )


async def _download_files_parallel(
    dropbox_client: DropboxClient,
    files: list[dict],
    *,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    enable_summary: bool,
    max_concurrency: int = 3,
    on_heartbeat: HeartbeatCallbackType | None = None,
) -> tuple[list[ConnectorDocument], int]:
    """Download and ETL files in parallel. Returns (docs, failed_count)."""
    results: list[ConnectorDocument] = []
    sem = asyncio.Semaphore(max_concurrency)
    last_heartbeat = time.time()
    completed_count = 0
    hb_lock = asyncio.Lock()

    async def _download_one(file: dict) -> ConnectorDocument | None:
        nonlocal last_heartbeat, completed_count
        async with sem:
            markdown, db_metadata, error = await download_and_extract_content(
                dropbox_client, file
            )
            if error or not markdown:
                file_name = file.get("name", "Unknown")
                reason = error or "empty content"
                logger.warning(f"Download/ETL failed for {file_name}: {reason}")
                return None
            doc = _build_connector_doc(
                file,
                markdown,
                db_metadata,
                connector_id=connector_id,
                search_space_id=search_space_id,
                user_id=user_id,
                enable_summary=enable_summary,
            )
            async with hb_lock:
                completed_count += 1
                if on_heartbeat:
                    now = time.time()
                    if now - last_heartbeat >= HEARTBEAT_INTERVAL_SECONDS:
                        await on_heartbeat(completed_count)
                        last_heartbeat = now
            return doc

    tasks = [_download_one(f) for f in files]
    outcomes = await asyncio.gather(*tasks, return_exceptions=True)

    failed = 0
    for outcome in outcomes:
        if isinstance(outcome, Exception) or outcome is None:
            failed += 1
        else:
            results.append(outcome)

    return results, failed


async def _download_and_index(
    dropbox_client: DropboxClient,
    session: AsyncSession,
    files: list[dict],
    *,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    enable_summary: bool,
    on_heartbeat: HeartbeatCallbackType | None = None,
) -> tuple[int, int]:
    """Parallel download then parallel indexing. Returns (batch_indexed, total_failed)."""
    connector_docs, download_failed = await _download_files_parallel(
        dropbox_client,
        files,
        connector_id=connector_id,
        search_space_id=search_space_id,
        user_id=user_id,
        enable_summary=enable_summary,
        on_heartbeat=on_heartbeat,
    )

    batch_indexed = 0
    batch_failed = 0
    if connector_docs:
        pipeline = IndexingPipelineService(session)

        async def _get_llm(s):
            return await get_user_long_context_llm(s, user_id, search_space_id)

        _, batch_indexed, batch_failed = await pipeline.index_batch_parallel(
            connector_docs,
            _get_llm,
            max_concurrency=3,
            on_heartbeat=on_heartbeat,
        )

    return batch_indexed, download_failed + batch_failed


async def _index_full_scan(
    dropbox_client: DropboxClient,
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    folder_path: str,
    folder_name: str,
    task_logger: TaskLoggingService,
    log_entry: object,
    max_files: int,
    include_subfolders: bool = True,
    incremental_sync: bool = True,
    on_heartbeat_callback: HeartbeatCallbackType | None = None,
    enable_summary: bool = True,
) -> tuple[int, int]:
    """Full scan indexing of a folder."""
    await task_logger.log_task_progress(
        log_entry,
        f"Starting full scan of folder: {folder_name}",
        {
            "stage": "full_scan",
            "folder_path": folder_path,
            "include_subfolders": include_subfolders,
            "incremental_sync": incremental_sync,
        },
    )

    renamed_count = 0
    skipped = 0
    files_to_download: list[dict] = []

    all_files, error = await get_files_in_folder(
        dropbox_client,
        folder_path,
        include_subfolders=include_subfolders,
    )
    if error:
        err_lower = error.lower()
        if "401" in error or "authentication expired" in err_lower:
            raise Exception(
                f"Dropbox authentication failed. Please re-authenticate. (Error: {error})"
            )
        raise Exception(f"Failed to list Dropbox files: {error}")

    for file in all_files[:max_files]:
        if incremental_sync:
            skip, msg = await _should_skip_file(session, file, search_space_id)
            if skip:
                if msg and "renamed" in msg.lower():
                    renamed_count += 1
                else:
                    skipped += 1
                continue
        elif skip_item(file):
            skipped += 1
            continue
        files_to_download.append(file)

    batch_indexed, failed = await _download_and_index(
        dropbox_client,
        session,
        files_to_download,
        connector_id=connector_id,
        search_space_id=search_space_id,
        user_id=user_id,
        enable_summary=enable_summary,
        on_heartbeat=on_heartbeat_callback,
    )

    indexed = renamed_count + batch_indexed
    logger.info(
        f"Full scan complete: {indexed} indexed, {skipped} skipped, {failed} failed"
    )
    return indexed, skipped


async def _index_selected_files(
    dropbox_client: DropboxClient,
    session: AsyncSession,
    file_paths: list[tuple[str, str | None]],
    *,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    enable_summary: bool,
    incremental_sync: bool = True,
    on_heartbeat: HeartbeatCallbackType | None = None,
) -> tuple[int, int, list[str]]:
    """Index user-selected files using the parallel pipeline."""
    files_to_download: list[dict] = []
    errors: list[str] = []
    renamed_count = 0
    skipped = 0

    for file_path, file_name in file_paths:
        file, error = await get_file_by_path(dropbox_client, file_path)
        if error or not file:
            display = file_name or file_path
            errors.append(f"File '{display}': {error or 'File not found'}")
            continue

        if incremental_sync:
            skip, msg = await _should_skip_file(session, file, search_space_id)
            if skip:
                if msg and "renamed" in msg.lower():
                    renamed_count += 1
                else:
                    skipped += 1
                continue
        elif skip_item(file):
            skipped += 1
            continue

        files_to_download.append(file)

    batch_indexed, _failed = await _download_and_index(
        dropbox_client,
        session,
        files_to_download,
        connector_id=connector_id,
        search_space_id=search_space_id,
        user_id=user_id,
        enable_summary=enable_summary,
        on_heartbeat=on_heartbeat,
    )

    return renamed_count + batch_indexed, skipped, errors


async def index_dropbox_files(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    items_dict: dict,
) -> tuple[int, int, str | None]:
    """Index Dropbox files for a specific connector.

    items_dict format:
        {
            "folders": [{"path": "...", "name": "..."}, ...],
            "files": [{"path": "...", "name": "..."}, ...],
            "indexing_options": {
                "max_files": 500,
                "incremental_sync": true,
                "include_subfolders": true,
            }
        }
    """
    task_logger = TaskLoggingService(session, search_space_id)
    log_entry = await task_logger.log_task_start(
        task_name="dropbox_files_indexing",
        source="connector_indexing_task",
        message=f"Starting Dropbox indexing for connector {connector_id}",
        metadata={"connector_id": connector_id, "user_id": str(user_id)},
    )

    try:
        connector = await get_connector_by_id(
            session, connector_id, SearchSourceConnectorType.DROPBOX_CONNECTOR
        )
        if not connector:
            error_msg = f"Dropbox connector with ID {connector_id} not found"
            await task_logger.log_task_failure(
                log_entry, error_msg, None, {"error_type": "ConnectorNotFound"}
            )
            return 0, 0, error_msg

        token_encrypted = connector.config.get("_token_encrypted", False)
        if token_encrypted and not config.SECRET_KEY:
            error_msg = "SECRET_KEY not configured but credentials are encrypted"
            await task_logger.log_task_failure(
                log_entry,
                error_msg,
                "Missing SECRET_KEY",
                {"error_type": "MissingSecretKey"},
            )
            return 0, 0, error_msg

        connector_enable_summary = getattr(connector, "enable_summary", True)
        dropbox_client = DropboxClient(session, connector_id)

        indexing_options = items_dict.get("indexing_options", {})
        max_files = indexing_options.get("max_files", 500)
        incremental_sync = indexing_options.get("incremental_sync", True)
        include_subfolders = indexing_options.get("include_subfolders", True)

        total_indexed = 0
        total_skipped = 0

        selected_files = items_dict.get("files", [])
        if selected_files:
            file_tuples = [
                (f.get("path", f.get("path_lower", "")), f.get("name"))
                for f in selected_files
            ]
            indexed, skipped, _errors = await _index_selected_files(
                dropbox_client,
                session,
                file_tuples,
                connector_id=connector_id,
                search_space_id=search_space_id,
                user_id=user_id,
                enable_summary=connector_enable_summary,
                incremental_sync=incremental_sync,
            )
            total_indexed += indexed
            total_skipped += skipped

        folders = items_dict.get("folders", [])
        for folder in folders:
            folder_path = folder.get("path", folder.get("path_lower", ""))
            folder_name = folder.get("name", "Root")

            logger.info(f"Using full scan for folder {folder_name}")
            indexed, skipped = await _index_full_scan(
                dropbox_client,
                session,
                connector_id,
                search_space_id,
                user_id,
                folder_path,
                folder_name,
                task_logger,
                log_entry,
                max_files,
                include_subfolders,
                incremental_sync=incremental_sync,
                enable_summary=connector_enable_summary,
            )
            total_indexed += indexed
            total_skipped += skipped

        if total_indexed > 0 or folders:
            await update_connector_last_indexed(session, connector, True)

        await session.commit()

        await task_logger.log_task_success(
            log_entry,
            f"Successfully completed Dropbox indexing for connector {connector_id}",
            {"files_processed": total_indexed, "files_skipped": total_skipped},
        )
        logger.info(
            f"Dropbox indexing completed: {total_indexed} indexed, {total_skipped} skipped"
        )
        return total_indexed, total_skipped, None

    except SQLAlchemyError as db_error:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Database error during Dropbox indexing for connector {connector_id}",
            str(db_error),
            {"error_type": "SQLAlchemyError"},
        )
        logger.error(f"Database error: {db_error!s}", exc_info=True)
        return 0, 0, f"Database error: {db_error!s}"
    except Exception as e:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Failed to index Dropbox files for connector {connector_id}",
            str(e),
            {"error_type": type(e).__name__},
        )
        logger.error(f"Failed to index Dropbox files: {e!s}", exc_info=True)
        return 0, 0, f"Failed to index Dropbox files: {e!s}"
