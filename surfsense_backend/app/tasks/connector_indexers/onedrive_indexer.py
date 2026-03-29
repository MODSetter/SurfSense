"""OneDrive indexer using the shared IndexingPipelineService.

File-level pre-filter (_should_skip_file) handles hash/modifiedDateTime
checks and rename-only detection.  download_and_extract_content()
returns markdown which is fed into ConnectorDocument -> pipeline.
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
from app.connectors.onedrive import (
    OneDriveClient,
    download_and_extract_content,
    get_file_by_id,
    get_files_in_folder,
)
from app.connectors.onedrive.file_types import should_skip_file as skip_item
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _should_skip_file(
    session: AsyncSession,
    file: dict,
    search_space_id: int,
) -> tuple[bool, str | None]:
    """Pre-filter: detect unchanged / rename-only files."""
    file_id = file.get("id")
    file_name = file.get("name", "Unknown")

    if skip_item(file):
        return True, "folder/onenote/remote"
    if not file_id:
        return True, "missing file_id"

    primary_hash = compute_identifier_hash(
        DocumentType.ONEDRIVE_FILE.value, file_id, search_space_id
    )
    existing = await check_document_by_unique_identifier(session, primary_hash)

    if not existing:
        result = await session.execute(
            select(Document).where(
                Document.search_space_id == search_space_id,
                Document.document_type == DocumentType.ONEDRIVE_FILE,
                cast(Document.document_metadata["onedrive_file_id"], String) == file_id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.unique_identifier_hash = primary_hash
            logger.debug(f"Found OneDrive doc by metadata for file_id: {file_id}")

    if not existing:
        return False, None

    incoming_mtime = file.get("lastModifiedDateTime")
    meta = existing.document_metadata or {}
    stored_mtime = meta.get("modified_time")

    file_info = file.get("file", {})
    file_hashes = file_info.get("hashes", {})
    incoming_hash = file_hashes.get("sha256Hash") or file_hashes.get("quickXorHash")
    stored_hash = meta.get("sha256_hash") or meta.get("quick_xor_hash")

    content_unchanged = False
    if incoming_hash and stored_hash:
        content_unchanged = incoming_hash == stored_hash
    elif incoming_hash and not stored_hash:
        return False, None
    elif not incoming_hash and incoming_mtime and stored_mtime:
        content_unchanged = incoming_mtime == stored_mtime
    elif not incoming_hash:
        return False, None

    if not content_unchanged:
        return False, None

    old_name = meta.get("onedrive_file_name")
    if old_name and old_name != file_name:
        existing.title = file_name
        if not existing.document_metadata:
            existing.document_metadata = {}
        existing.document_metadata["onedrive_file_name"] = file_name
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
    onedrive_metadata: dict,
    *,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    enable_summary: bool,
) -> ConnectorDocument:
    file_id = file.get("id", "")
    file_name = file.get("name", "Unknown")

    metadata = {
        **onedrive_metadata,
        "connector_id": connector_id,
        "document_type": "OneDrive File",
        "connector_type": "OneDrive",
    }

    fallback_summary = f"File: {file_name}\n\n{markdown[:4000]}"

    return ConnectorDocument(
        title=file_name,
        source_markdown=markdown,
        unique_id=file_id,
        document_type=DocumentType.ONEDRIVE_FILE,
        search_space_id=search_space_id,
        connector_id=connector_id,
        created_by_id=user_id,
        should_summarize=enable_summary,
        fallback_summary=fallback_summary,
        metadata=metadata,
    )


async def _download_files_parallel(
    onedrive_client: OneDriveClient,
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
            markdown, od_metadata, error = await download_and_extract_content(
                onedrive_client, file
            )
            if error or not markdown:
                file_name = file.get("name", "Unknown")
                reason = error or "empty content"
                logger.warning(f"Download/ETL failed for {file_name}: {reason}")
                return None
            doc = _build_connector_doc(
                file, markdown, od_metadata,
                connector_id=connector_id, search_space_id=search_space_id,
                user_id=user_id, enable_summary=enable_summary,
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
        if isinstance(outcome, Exception):
            failed += 1
        elif outcome is None:
            failed += 1
        else:
            results.append(outcome)

    return results, failed


async def _download_and_index(
    onedrive_client: OneDriveClient,
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
        onedrive_client, files,
        connector_id=connector_id, search_space_id=search_space_id,
        user_id=user_id, enable_summary=enable_summary,
        on_heartbeat=on_heartbeat,
    )

    batch_indexed = 0
    batch_failed = 0
    if connector_docs:
        pipeline = IndexingPipelineService(session)

        async def _get_llm(s):
            return await get_user_long_context_llm(s, user_id, search_space_id)

        _, batch_indexed, batch_failed = await pipeline.index_batch_parallel(
            connector_docs, _get_llm, max_concurrency=3,
            on_heartbeat=on_heartbeat,
        )

    return batch_indexed, download_failed + batch_failed


async def _remove_document(session: AsyncSession, file_id: str, search_space_id: int):
    """Remove a document that was deleted in OneDrive."""
    primary_hash = compute_identifier_hash(
        DocumentType.ONEDRIVE_FILE.value, file_id, search_space_id
    )
    existing = await check_document_by_unique_identifier(session, primary_hash)

    if not existing:
        result = await session.execute(
            select(Document).where(
                Document.search_space_id == search_space_id,
                Document.document_type == DocumentType.ONEDRIVE_FILE,
                cast(Document.document_metadata["onedrive_file_id"], String) == file_id,
            )
        )
        existing = result.scalar_one_or_none()

    if existing:
        await session.delete(existing)
        logger.info(f"Removed deleted OneDrive file document: {file_id}")


async def _index_selected_files(
    onedrive_client: OneDriveClient,
    session: AsyncSession,
    file_ids: list[tuple[str, str | None]],
    *,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    enable_summary: bool,
    on_heartbeat: HeartbeatCallbackType | None = None,
) -> tuple[int, int, list[str]]:
    """Index user-selected files using the parallel pipeline."""
    files_to_download: list[dict] = []
    errors: list[str] = []
    renamed_count = 0
    skipped = 0

    for file_id, file_name in file_ids:
        file, error = await get_file_by_id(onedrive_client, file_id)
        if error or not file:
            display = file_name or file_id
            errors.append(f"File '{display}': {error or 'File not found'}")
            continue

        skip, msg = await _should_skip_file(session, file, search_space_id)
        if skip:
            if msg and "renamed" in msg.lower():
                renamed_count += 1
            else:
                skipped += 1
            continue

        files_to_download.append(file)

    batch_indexed, failed = await _download_and_index(
        onedrive_client, session, files_to_download,
        connector_id=connector_id, search_space_id=search_space_id,
        user_id=user_id, enable_summary=enable_summary,
        on_heartbeat=on_heartbeat,
    )

    return renamed_count + batch_indexed, skipped, errors


# ---------------------------------------------------------------------------
# Scan strategies
# ---------------------------------------------------------------------------

async def _index_full_scan(
    onedrive_client: OneDriveClient,
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    folder_id: str,
    folder_name: str,
    task_logger: TaskLoggingService,
    log_entry: object,
    max_files: int,
    include_subfolders: bool = True,
    on_heartbeat_callback: HeartbeatCallbackType | None = None,
    enable_summary: bool = True,
) -> tuple[int, int]:
    """Full scan indexing of a folder."""
    await task_logger.log_task_progress(
        log_entry,
        f"Starting full scan of folder: {folder_name}",
        {"stage": "full_scan", "folder_id": folder_id, "include_subfolders": include_subfolders},
    )

    renamed_count = 0
    skipped = 0
    files_to_download: list[dict] = []

    all_files, error = await get_files_in_folder(
        onedrive_client, folder_id, include_subfolders=include_subfolders,
    )
    if error:
        err_lower = error.lower()
        if "401" in error or "authentication expired" in err_lower:
            raise Exception(f"OneDrive authentication failed. Please re-authenticate. (Error: {error})")
        raise Exception(f"Failed to list OneDrive files: {error}")

    for file in all_files[:max_files]:
        skip, msg = await _should_skip_file(session, file, search_space_id)
        if skip:
            if msg and "renamed" in msg.lower():
                renamed_count += 1
            else:
                skipped += 1
            continue
        files_to_download.append(file)

    batch_indexed, failed = await _download_and_index(
        onedrive_client, session, files_to_download,
        connector_id=connector_id, search_space_id=search_space_id,
        user_id=user_id, enable_summary=enable_summary,
        on_heartbeat=on_heartbeat_callback,
    )

    indexed = renamed_count + batch_indexed
    logger.info(f"Full scan complete: {indexed} indexed, {skipped} skipped, {failed} failed")
    return indexed, skipped


async def _index_with_delta_sync(
    onedrive_client: OneDriveClient,
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    folder_id: str | None,
    delta_link: str,
    task_logger: TaskLoggingService,
    log_entry: object,
    max_files: int,
    on_heartbeat_callback: HeartbeatCallbackType | None = None,
    enable_summary: bool = True,
) -> tuple[int, int, str | None]:
    """Delta sync using OneDrive change tracking. Returns (indexed, skipped, new_delta_link)."""
    await task_logger.log_task_progress(
        log_entry, "Starting delta sync",
        {"stage": "delta_sync"},
    )

    changes, new_delta_link, error = await onedrive_client.get_delta(
        folder_id=folder_id, delta_link=delta_link
    )
    if error:
        err_lower = error.lower()
        if "401" in error or "authentication expired" in err_lower:
            raise Exception(f"OneDrive authentication failed. Please re-authenticate. (Error: {error})")
        raise Exception(f"Failed to fetch OneDrive changes: {error}")

    if not changes:
        logger.info("No changes detected since last sync")
        return 0, 0, new_delta_link

    logger.info(f"Processing {len(changes)} delta changes")

    renamed_count = 0
    skipped = 0
    files_to_download: list[dict] = []
    files_processed = 0

    for change in changes:
        if files_processed >= max_files:
            break
        files_processed += 1

        if change.get("deleted"):
            fid = change.get("id")
            if fid:
                await _remove_document(session, fid, search_space_id)
            continue

        if "folder" in change:
            continue

        if not change.get("file"):
            continue

        skip, msg = await _should_skip_file(session, change, search_space_id)
        if skip:
            if msg and "renamed" in msg.lower():
                renamed_count += 1
            else:
                skipped += 1
            continue

        files_to_download.append(change)

    batch_indexed, failed = await _download_and_index(
        onedrive_client, session, files_to_download,
        connector_id=connector_id, search_space_id=search_space_id,
        user_id=user_id, enable_summary=enable_summary,
        on_heartbeat=on_heartbeat_callback,
    )

    indexed = renamed_count + batch_indexed
    logger.info(f"Delta sync complete: {indexed} indexed, {skipped} skipped, {failed} failed")
    return indexed, skipped, new_delta_link


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def index_onedrive_files(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    items_dict: dict,
) -> tuple[int, int, str | None]:
    """Index OneDrive files for a specific connector.

    items_dict format:
        {
            "folders": [{"id": "...", "name": "..."}, ...],
            "files": [{"id": "...", "name": "..."}, ...],
            "indexing_options": {"max_files": 500, "include_subfolders": true, "use_delta_sync": true}
        }
    """
    task_logger = TaskLoggingService(session, search_space_id)
    log_entry = await task_logger.log_task_start(
        task_name="onedrive_files_indexing",
        source="connector_indexing_task",
        message=f"Starting OneDrive indexing for connector {connector_id}",
        metadata={"connector_id": connector_id, "user_id": str(user_id)},
    )

    try:
        connector = await get_connector_by_id(
            session, connector_id, SearchSourceConnectorType.ONEDRIVE_CONNECTOR
        )
        if not connector:
            error_msg = f"OneDrive connector with ID {connector_id} not found"
            await task_logger.log_task_failure(log_entry, error_msg, None, {"error_type": "ConnectorNotFound"})
            return 0, 0, error_msg

        token_encrypted = connector.config.get("_token_encrypted", False)
        if token_encrypted and not config.SECRET_KEY:
            error_msg = "SECRET_KEY not configured but credentials are encrypted"
            await task_logger.log_task_failure(log_entry, error_msg, "Missing SECRET_KEY", {"error_type": "MissingSecretKey"})
            return 0, 0, error_msg

        connector_enable_summary = getattr(connector, "enable_summary", True)
        onedrive_client = OneDriveClient(session, connector_id)

        indexing_options = items_dict.get("indexing_options", {})
        max_files = indexing_options.get("max_files", 500)
        include_subfolders = indexing_options.get("include_subfolders", True)
        use_delta_sync = indexing_options.get("use_delta_sync", True)

        total_indexed = 0
        total_skipped = 0

        # Index selected individual files
        selected_files = items_dict.get("files", [])
        if selected_files:
            file_tuples = [(f["id"], f.get("name")) for f in selected_files]
            indexed, skipped, errors = await _index_selected_files(
                onedrive_client, session, file_tuples,
                connector_id=connector_id, search_space_id=search_space_id,
                user_id=user_id, enable_summary=connector_enable_summary,
            )
            total_indexed += indexed
            total_skipped += skipped

        # Index selected folders
        folders = items_dict.get("folders", [])
        for folder in folders:
            folder_id = folder.get("id", "root")
            folder_name = folder.get("name", "Root")

            folder_delta_links = connector.config.get("folder_delta_links", {})
            delta_link = folder_delta_links.get(folder_id)
            can_use_delta = use_delta_sync and delta_link and connector.last_indexed_at

            if can_use_delta:
                logger.info(f"Using delta sync for folder {folder_name}")
                indexed, skipped, new_delta_link = await _index_with_delta_sync(
                    onedrive_client, session, connector_id, search_space_id, user_id,
                    folder_id, delta_link, task_logger, log_entry, max_files,
                    enable_summary=connector_enable_summary,
                )
                total_indexed += indexed
                total_skipped += skipped

                if new_delta_link:
                    await session.refresh(connector)
                    if "folder_delta_links" not in connector.config:
                        connector.config["folder_delta_links"] = {}
                    connector.config["folder_delta_links"][folder_id] = new_delta_link
                    flag_modified(connector, "config")

                # Reconciliation full scan
                ri, rs = await _index_full_scan(
                    onedrive_client, session, connector_id, search_space_id, user_id,
                    folder_id, folder_name, task_logger, log_entry, max_files,
                    include_subfolders, enable_summary=connector_enable_summary,
                )
                total_indexed += ri
                total_skipped += rs
            else:
                logger.info(f"Using full scan for folder {folder_name}")
                indexed, skipped = await _index_full_scan(
                    onedrive_client, session, connector_id, search_space_id, user_id,
                    folder_id, folder_name, task_logger, log_entry, max_files,
                    include_subfolders, enable_summary=connector_enable_summary,
                )
                total_indexed += indexed
                total_skipped += skipped

            # Store new delta link for this folder
            _, new_delta_link, _ = await onedrive_client.get_delta(folder_id=folder_id)
            if new_delta_link:
                await session.refresh(connector)
                if "folder_delta_links" not in connector.config:
                    connector.config["folder_delta_links"] = {}
                connector.config["folder_delta_links"][folder_id] = new_delta_link
                flag_modified(connector, "config")

        if total_indexed > 0 or folders:
            await update_connector_last_indexed(session, connector, True)

        await session.commit()

        await task_logger.log_task_success(
            log_entry,
            f"Successfully completed OneDrive indexing for connector {connector_id}",
            {"files_processed": total_indexed, "files_skipped": total_skipped},
        )
        logger.info(f"OneDrive indexing completed: {total_indexed} indexed, {total_skipped} skipped")
        return total_indexed, total_skipped, None

    except SQLAlchemyError as db_error:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry, f"Database error during OneDrive indexing for connector {connector_id}",
            str(db_error), {"error_type": "SQLAlchemyError"},
        )
        logger.error(f"Database error: {db_error!s}", exc_info=True)
        return 0, 0, f"Database error: {db_error!s}"
    except Exception as e:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry, f"Failed to index OneDrive files for connector {connector_id}",
            str(e), {"error_type": type(e).__name__},
        )
        logger.error(f"Failed to index OneDrive files: {e!s}", exc_info=True)
        return 0, 0, f"Failed to index OneDrive files: {e!s}"
