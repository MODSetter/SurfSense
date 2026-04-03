"""Google Drive indexer using the shared IndexingPipelineService.

File-level pre-filter (_should_skip_file) handles md5/modifiedTime
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
from app.connectors.google_drive import (
    GoogleDriveClient,
    categorize_change,
    download_and_extract_content,
    fetch_all_changes,
    get_file_by_id,
    get_files_in_folder,
    get_start_page_token,
)
from app.connectors.google_drive.file_types import should_skip_file as skip_mime
from app.db import Document, DocumentStatus, DocumentType, SearchSourceConnectorType
from app.indexing_pipeline.connector_document import ConnectorDocument
from app.indexing_pipeline.document_hashing import compute_identifier_hash
from app.indexing_pipeline.indexing_pipeline_service import (
    IndexingPipelineService,
    PlaceholderInfo,
)
from app.services.llm_service import get_user_long_context_llm
from app.services.page_limit_service import PageLimitService
from app.services.task_logging_service import TaskLoggingService
from app.tasks.connector_indexers.base import (
    check_document_by_unique_identifier,
    get_connector_by_id,
    update_connector_last_indexed,
)
from app.utils.google_credentials import (
    COMPOSIO_GOOGLE_CONNECTOR_TYPES,
    build_composio_credentials,
)

ACCEPTED_DRIVE_CONNECTOR_TYPES = {
    SearchSourceConnectorType.GOOGLE_DRIVE_CONNECTOR,
    SearchSourceConnectorType.COMPOSIO_GOOGLE_DRIVE_CONNECTOR,
}

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
    """Pre-filter: detect unchanged / rename-only files.

    Returns (should_skip, message).
    Side-effects: migrates legacy Composio hashes, updates renames in-place.
    """
    file_id = file.get("id")
    file_name = file.get("name", "Unknown")
    mime_type = file.get("mimeType", "")

    if skip_mime(mime_type):
        return True, "folder/shortcut"
    if not file_id:
        return True, "missing file_id"

    # --- locate existing document ---
    primary_hash = compute_identifier_hash(
        DocumentType.GOOGLE_DRIVE_FILE.value, file_id, search_space_id
    )
    existing = await check_document_by_unique_identifier(session, primary_hash)

    if not existing:
        legacy_hash = compute_identifier_hash(
            DocumentType.COMPOSIO_GOOGLE_DRIVE_CONNECTOR.value, file_id, search_space_id
        )
        existing = await check_document_by_unique_identifier(session, legacy_hash)
        if existing:
            existing.unique_identifier_hash = primary_hash
            if existing.document_type == DocumentType.COMPOSIO_GOOGLE_DRIVE_CONNECTOR:
                existing.document_type = DocumentType.GOOGLE_DRIVE_FILE
            logger.info(f"Migrated legacy Composio Drive document: {file_id}")

    if not existing:
        result = await session.execute(
            select(Document).where(
                Document.search_space_id == search_space_id,
                Document.document_type.in_(
                    [
                        DocumentType.GOOGLE_DRIVE_FILE,
                        DocumentType.COMPOSIO_GOOGLE_DRIVE_CONNECTOR,
                    ]
                ),
                cast(Document.document_metadata["google_drive_file_id"], String)
                == file_id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.unique_identifier_hash = primary_hash
            if existing.document_type == DocumentType.COMPOSIO_GOOGLE_DRIVE_CONNECTOR:
                existing.document_type = DocumentType.GOOGLE_DRIVE_FILE
            logger.debug(f"Found legacy doc by metadata for file_id: {file_id}")

    if not existing:
        return False, None

    # --- content-change check via md5 / modifiedTime ---
    incoming_md5 = file.get("md5Checksum")
    incoming_mtime = file.get("modifiedTime")
    meta = existing.document_metadata or {}
    stored_md5 = meta.get("md5_checksum")
    stored_mtime = meta.get("modified_time")

    content_unchanged = False
    if incoming_md5 and stored_md5:
        content_unchanged = incoming_md5 == stored_md5
    elif incoming_md5 and not stored_md5:
        return False, None
    elif not incoming_md5 and incoming_mtime and stored_mtime:
        content_unchanged = incoming_mtime == stored_mtime
    elif not incoming_md5:
        return False, None

    if not content_unchanged:
        return False, None

    # --- rename-only detection ---
    old_name = meta.get("FILE_NAME") or meta.get("google_drive_file_name")
    if old_name and old_name != file_name:
        existing.title = file_name
        if not existing.document_metadata:
            existing.document_metadata = {}
        existing.document_metadata["FILE_NAME"] = file_name
        existing.document_metadata["google_drive_file_name"] = file_name
        if incoming_mtime:
            existing.document_metadata["modified_time"] = incoming_mtime
        flag_modified(existing, "document_metadata")
        await session.commit()
        logger.info(f"Rename-only update: '{old_name}' → '{file_name}'")
        return True, f"File renamed: '{old_name}' → '{file_name}'"

    if not DocumentStatus.is_state(existing.status, DocumentStatus.READY):
        return True, "skipped (previously failed)"
    return True, "unchanged"


def _build_connector_doc(
    file: dict,
    markdown: str,
    drive_metadata: dict,
    *,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    enable_summary: bool,
) -> ConnectorDocument:
    """Build a ConnectorDocument from Drive file metadata + extracted markdown."""
    file_id = file.get("id", "")
    file_name = file.get("name", "Unknown")

    metadata = {
        **drive_metadata,
        "connector_id": connector_id,
        "document_type": "Google Drive File",
        "connector_type": "Google Drive",
    }

    fallback_summary = f"File: {file_name}\n\n{markdown[:4000]}"

    return ConnectorDocument(
        title=file_name,
        source_markdown=markdown,
        unique_id=file_id,
        document_type=DocumentType.GOOGLE_DRIVE_FILE,
        search_space_id=search_space_id,
        connector_id=connector_id,
        created_by_id=user_id,
        should_summarize=enable_summary,
        fallback_summary=fallback_summary,
        metadata=metadata,
    )


async def _create_drive_placeholders(
    session: AsyncSession,
    files: list[dict],
    *,
    connector_id: int,
    search_space_id: int,
    user_id: str,
) -> None:
    """Create placeholder document rows for discovered Drive files.

    Called immediately after file discovery (Phase 1) so documents appear
    in the UI via Zero sync before the slow download/ETL phase begins.
    """
    if not files:
        return

    placeholders = []
    for file in files:
        file_id = file.get("id")
        file_name = file.get("name", "Unknown")
        if not file_id:
            continue
        placeholders.append(
            PlaceholderInfo(
                title=file_name,
                document_type=DocumentType.GOOGLE_DRIVE_FILE,
                unique_id=file_id,
                search_space_id=search_space_id,
                connector_id=connector_id,
                created_by_id=user_id,
                metadata={
                    "google_drive_file_id": file_id,
                    "FILE_NAME": file_name,
                    "connector_id": connector_id,
                    "connector_type": "Google Drive",
                },
            )
        )

    if placeholders:
        pipeline = IndexingPipelineService(session)
        await pipeline.create_placeholder_documents(placeholders)


async def _download_files_parallel(
    drive_client: GoogleDriveClient,
    files: list[dict],
    *,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    enable_summary: bool,
    max_concurrency: int = 3,
    on_heartbeat: HeartbeatCallbackType | None = None,
) -> tuple[list[ConnectorDocument], int]:
    """Download and ETL files in parallel, returning ConnectorDocuments.

    Returns (connector_docs, download_failed_count).
    """
    results: list[ConnectorDocument] = []
    sem = asyncio.Semaphore(max_concurrency)
    last_heartbeat = time.time()
    completed_count = 0
    hb_lock = asyncio.Lock()

    async def _download_one(file: dict) -> ConnectorDocument | None:
        nonlocal last_heartbeat, completed_count
        async with sem:
            markdown, drive_metadata, error = await download_and_extract_content(
                drive_client, file
            )
            if error or not markdown:
                file_name = file.get("name", "Unknown")
                reason = error or "empty content"
                logger.warning(f"Download/ETL failed for {file_name}: {reason}")
                return None
            doc = _build_connector_doc(
                file,
                markdown,
                drive_metadata,
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


async def _process_single_file(
    drive_client: GoogleDriveClient,
    session: AsyncSession,
    file: dict,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    enable_summary: bool = True,
) -> tuple[int, int, int]:
    """Download, extract, and index a single Drive file via the pipeline.

    Returns (indexed, skipped, failed).
    """
    file_name = file.get("name", "Unknown")

    try:
        skip, msg = await _should_skip_file(session, file, search_space_id)
        if skip:
            if msg and "renamed" in msg.lower():
                return 1, 0, 0
            return 0, 1, 0

        page_limit_service = PageLimitService(session)
        estimated_pages = PageLimitService.estimate_pages_from_metadata(
            file_name, file.get("size")
        )
        await page_limit_service.check_page_limit(user_id, estimated_pages)

        markdown, drive_metadata, error = await download_and_extract_content(
            drive_client, file
        )
        if error or not markdown:
            logger.warning(f"ETL failed for {file_name}: {error}")
            return 0, 1, 0

        doc = _build_connector_doc(
            file,
            markdown,
            drive_metadata,
            connector_id=connector_id,
            search_space_id=search_space_id,
            user_id=user_id,
            enable_summary=enable_summary,
        )

        pipeline = IndexingPipelineService(session)
        documents = await pipeline.prepare_for_indexing([doc])
        if not documents:
            return 0, 1, 0

        from app.indexing_pipeline.document_hashing import (
            compute_unique_identifier_hash,
        )

        doc_map = {compute_unique_identifier_hash(doc): doc}
        for document in documents:
            connector_doc = doc_map.get(document.unique_identifier_hash)
            if not connector_doc:
                continue
            user_llm = await get_user_long_context_llm(
                session, user_id, search_space_id
            )
            await pipeline.index(document, connector_doc, user_llm)

        await page_limit_service.update_page_usage(
            user_id, estimated_pages, allow_exceed=True
        )
        logger.info(f"Successfully indexed Google Drive file: {file_name}")
        return 1, 0, 0

    except Exception as e:
        logger.error(f"Error processing file {file_name}: {e!s}", exc_info=True)
        return 0, 0, 1


async def _remove_document(session: AsyncSession, file_id: str, search_space_id: int):
    """Remove a document that was deleted in Drive."""
    primary_hash = compute_identifier_hash(
        DocumentType.GOOGLE_DRIVE_FILE.value, file_id, search_space_id
    )
    existing = await check_document_by_unique_identifier(session, primary_hash)

    if not existing:
        legacy_hash = compute_identifier_hash(
            DocumentType.COMPOSIO_GOOGLE_DRIVE_CONNECTOR.value, file_id, search_space_id
        )
        existing = await check_document_by_unique_identifier(session, legacy_hash)

    if not existing:
        result = await session.execute(
            select(Document).where(
                Document.search_space_id == search_space_id,
                Document.document_type.in_(
                    [
                        DocumentType.GOOGLE_DRIVE_FILE,
                        DocumentType.COMPOSIO_GOOGLE_DRIVE_CONNECTOR,
                    ]
                ),
                cast(Document.document_metadata["google_drive_file_id"], String)
                == file_id,
            )
        )
        existing = result.scalar_one_or_none()

    if existing:
        await session.delete(existing)
        logger.info(f"Removed deleted file document: {file_id}")


async def _download_and_index(
    drive_client: GoogleDriveClient,
    session: AsyncSession,
    files: list[dict],
    *,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    enable_summary: bool,
    on_heartbeat: HeartbeatCallbackType | None = None,
) -> tuple[int, int]:
    """Phase 2+3: parallel download then parallel indexing.

    Returns (batch_indexed, total_failed).
    """
    connector_docs, download_failed = await _download_files_parallel(
        drive_client,
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


async def _index_selected_files(
    drive_client: GoogleDriveClient,
    session: AsyncSession,
    file_ids: list[tuple[str, str | None]],
    *,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    enable_summary: bool,
    on_heartbeat: HeartbeatCallbackType | None = None,
) -> tuple[int, int, list[str]]:
    """Index user-selected files using the parallel pipeline.

    Phase 1 (serial): fetch metadata + skip checks.
    Phase 2+3 (parallel): download, ETL, index via _download_and_index.

    Returns (indexed_count, skipped_count, errors).
    """
    page_limit_service = PageLimitService(session)
    pages_used, pages_limit = await page_limit_service.get_page_usage(user_id)
    remaining_quota = pages_limit - pages_used
    batch_estimated_pages = 0

    files_to_download: list[dict] = []
    errors: list[str] = []
    renamed_count = 0
    skipped = 0

    for file_id, file_name in file_ids:
        file, error = await get_file_by_id(drive_client, file_id)
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

        file_pages = PageLimitService.estimate_pages_from_metadata(
            file.get("name", ""), file.get("size")
        )
        if batch_estimated_pages + file_pages > remaining_quota:
            display = file_name or file_id
            errors.append(f"File '{display}': page limit would be exceeded")
            continue

        batch_estimated_pages += file_pages
        files_to_download.append(file)

    await _create_drive_placeholders(
        session,
        files_to_download,
        connector_id=connector_id,
        search_space_id=search_space_id,
        user_id=user_id,
    )

    batch_indexed, _failed = await _download_and_index(
        drive_client,
        session,
        files_to_download,
        connector_id=connector_id,
        search_space_id=search_space_id,
        user_id=user_id,
        enable_summary=enable_summary,
        on_heartbeat=on_heartbeat,
    )

    if batch_indexed > 0 and files_to_download and batch_estimated_pages > 0:
        pages_to_deduct = max(
            1, batch_estimated_pages * batch_indexed // len(files_to_download)
        )
        await page_limit_service.update_page_usage(
            user_id, pages_to_deduct, allow_exceed=True
        )

    return renamed_count + batch_indexed, skipped, errors


# ---------------------------------------------------------------------------
# Scan strategies
# ---------------------------------------------------------------------------


async def _index_full_scan(
    drive_client: GoogleDriveClient,
    session: AsyncSession,
    connector: object,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    folder_id: str | None,
    folder_name: str,
    task_logger: TaskLoggingService,
    log_entry: object,
    max_files: int,
    include_subfolders: bool = False,
    on_heartbeat_callback: HeartbeatCallbackType | None = None,
    enable_summary: bool = True,
) -> tuple[int, int]:
    """Full scan indexing of a folder."""
    await task_logger.log_task_progress(
        log_entry,
        f"Starting full scan of folder: {folder_name} (include_subfolders={include_subfolders})",
        {
            "stage": "full_scan",
            "folder_id": folder_id,
            "include_subfolders": include_subfolders,
        },
    )

    # ------------------------------------------------------------------
    # Phase 1 (serial): collect files, run skip checks, track renames
    # ------------------------------------------------------------------
    page_limit_service = PageLimitService(session)
    pages_used, pages_limit = await page_limit_service.get_page_usage(user_id)
    remaining_quota = pages_limit - pages_used
    batch_estimated_pages = 0
    page_limit_reached = False

    renamed_count = 0
    skipped = 0
    files_processed = 0
    files_to_download: list[dict] = []
    folders_to_process = [(folder_id, folder_name)]
    first_error: str | None = None

    while folders_to_process and files_processed < max_files:
        cur_id, cur_name = folders_to_process.pop(0)
        page_token = None

        while files_processed < max_files:
            files, next_token, error = await get_files_in_folder(
                drive_client,
                cur_id,
                include_subfolders=True,
                page_token=page_token,
            )
            if error:
                logger.error(f"Error listing files in {cur_name}: {error}")
                if first_error is None:
                    first_error = error
                break
            if not files:
                break

            for file in files:
                if files_processed >= max_files:
                    break

                mime = file.get("mimeType", "")
                if mime == "application/vnd.google-apps.folder":
                    if include_subfolders:
                        folders_to_process.append(
                            (file["id"], file.get("name", "Unknown"))
                        )
                    continue

                files_processed += 1

                skip, msg = await _should_skip_file(session, file, search_space_id)
                if skip:
                    if msg and "renamed" in msg.lower():
                        renamed_count += 1
                    else:
                        skipped += 1
                    continue

                file_pages = PageLimitService.estimate_pages_from_metadata(
                    file.get("name", ""), file.get("size")
                )
                if batch_estimated_pages + file_pages > remaining_quota:
                    if not page_limit_reached:
                        logger.warning(
                            "Page limit reached during Google Drive full scan, "
                            "skipping remaining files"
                        )
                        page_limit_reached = True
                    skipped += 1
                    continue

                batch_estimated_pages += file_pages
                files_to_download.append(file)

            page_token = next_token
            if not page_token:
                break

    if not files_processed and first_error:
        err_lower = first_error.lower()
        if (
            "401" in first_error
            or "invalid credentials" in err_lower
            or "authError" in first_error
        ):
            raise Exception(
                f"Google Drive authentication failed. Please re-authenticate. (Error: {first_error})"
            )
        raise Exception(f"Failed to list Google Drive files: {first_error}")

    # ------------------------------------------------------------------
    # Phase 1.5: create placeholders for instant UI feedback
    # ------------------------------------------------------------------
    await _create_drive_placeholders(
        session,
        files_to_download,
        connector_id=connector_id,
        search_space_id=search_space_id,
        user_id=user_id,
    )

    # ------------------------------------------------------------------
    # Phase 2+3 (parallel): download, ETL, index
    # ------------------------------------------------------------------
    batch_indexed, failed = await _download_and_index(
        drive_client,
        session,
        files_to_download,
        connector_id=connector_id,
        search_space_id=search_space_id,
        user_id=user_id,
        enable_summary=enable_summary,
        on_heartbeat=on_heartbeat_callback,
    )

    if batch_indexed > 0 and files_to_download and batch_estimated_pages > 0:
        pages_to_deduct = max(
            1, batch_estimated_pages * batch_indexed // len(files_to_download)
        )
        await page_limit_service.update_page_usage(
            user_id, pages_to_deduct, allow_exceed=True
        )

    indexed = renamed_count + batch_indexed
    logger.info(
        f"Full scan complete: {indexed} indexed, {skipped} skipped, {failed} failed"
    )
    return indexed, skipped


async def _index_with_delta_sync(
    drive_client: GoogleDriveClient,
    session: AsyncSession,
    connector: object,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    folder_id: str | None,
    start_page_token: str,
    task_logger: TaskLoggingService,
    log_entry: object,
    max_files: int,
    include_subfolders: bool = False,
    on_heartbeat_callback: HeartbeatCallbackType | None = None,
    enable_summary: bool = True,
) -> tuple[int, int]:
    """Delta sync using change tracking."""
    await task_logger.log_task_progress(
        log_entry,
        f"Starting delta sync from token: {start_page_token[:20]}...",
        {"stage": "delta_sync", "start_token": start_page_token},
    )

    changes, _final_token, error = await fetch_all_changes(
        drive_client, start_page_token, folder_id
    )
    if error:
        err_lower = error.lower()
        if "401" in error or "invalid credentials" in err_lower or "authError" in error:
            raise Exception(
                f"Google Drive authentication failed. Please re-authenticate. (Error: {error})"
            )
        raise Exception(f"Failed to fetch Google Drive changes: {error}")

    if not changes:
        logger.info("No changes detected since last sync")
        return 0, 0

    logger.info(f"Processing {len(changes)} changes")

    # ------------------------------------------------------------------
    # Phase 1 (serial): handle removals, collect files for download
    # ------------------------------------------------------------------
    page_limit_service = PageLimitService(session)
    pages_used, pages_limit = await page_limit_service.get_page_usage(user_id)
    remaining_quota = pages_limit - pages_used
    batch_estimated_pages = 0
    page_limit_reached = False

    renamed_count = 0
    skipped = 0
    files_to_download: list[dict] = []
    files_processed = 0

    for change in changes:
        if files_processed >= max_files:
            break
        files_processed += 1
        change_type = categorize_change(change)

        if change_type in ["removed", "trashed"]:
            fid = change.get("fileId")
            if fid:
                await _remove_document(session, fid, search_space_id)
            continue

        file = change.get("file")
        if not file:
            continue

        skip, msg = await _should_skip_file(session, file, search_space_id)
        if skip:
            if msg and "renamed" in msg.lower():
                renamed_count += 1
            else:
                skipped += 1
            continue

        file_pages = PageLimitService.estimate_pages_from_metadata(
            file.get("name", ""), file.get("size")
        )
        if batch_estimated_pages + file_pages > remaining_quota:
            if not page_limit_reached:
                logger.warning(
                    "Page limit reached during Google Drive delta sync, "
                    "skipping remaining files"
                )
                page_limit_reached = True
            skipped += 1
            continue

        batch_estimated_pages += file_pages
        files_to_download.append(file)

    # ------------------------------------------------------------------
    # Phase 1.5: create placeholders for instant UI feedback
    # ------------------------------------------------------------------
    await _create_drive_placeholders(
        session,
        files_to_download,
        connector_id=connector_id,
        search_space_id=search_space_id,
        user_id=user_id,
    )

    # ------------------------------------------------------------------
    # Phase 2+3 (parallel): download, ETL, index
    # ------------------------------------------------------------------
    batch_indexed, failed = await _download_and_index(
        drive_client,
        session,
        files_to_download,
        connector_id=connector_id,
        search_space_id=search_space_id,
        user_id=user_id,
        enable_summary=enable_summary,
        on_heartbeat=on_heartbeat_callback,
    )

    if batch_indexed > 0 and files_to_download and batch_estimated_pages > 0:
        pages_to_deduct = max(
            1, batch_estimated_pages * batch_indexed // len(files_to_download)
        )
        await page_limit_service.update_page_usage(
            user_id, pages_to_deduct, allow_exceed=True
        )

    indexed = renamed_count + batch_indexed
    logger.info(
        f"Delta sync complete: {indexed} indexed, {skipped} skipped, {failed} failed"
    )
    return indexed, skipped


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


async def index_google_drive_files(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    folder_id: str | None = None,
    folder_name: str | None = None,
    use_delta_sync: bool = True,
    update_last_indexed: bool = True,
    max_files: int = 500,
    include_subfolders: bool = False,
    on_heartbeat_callback: HeartbeatCallbackType | None = None,
) -> tuple[int, int, str | None]:
    """Index Google Drive files for a specific connector."""
    task_logger = TaskLoggingService(session, search_space_id)
    log_entry = await task_logger.log_task_start(
        task_name="google_drive_files_indexing",
        source="connector_indexing_task",
        message=f"Starting Google Drive indexing for connector {connector_id}",
        metadata={
            "connector_id": connector_id,
            "user_id": str(user_id),
            "folder_id": folder_id,
            "use_delta_sync": use_delta_sync,
            "max_files": max_files,
        },
    )

    try:
        connector = None
        for ct in ACCEPTED_DRIVE_CONNECTOR_TYPES:
            connector = await get_connector_by_id(session, connector_id, ct)
            if connector:
                break
        if not connector:
            error_msg = f"Google Drive connector with ID {connector_id} not found"
            await task_logger.log_task_failure(
                log_entry, error_msg, None, {"error_type": "ConnectorNotFound"}
            )
            return 0, 0, error_msg

        await task_logger.log_task_progress(
            log_entry,
            f"Initializing Google Drive client for connector {connector_id}",
            {"stage": "client_initialization"},
        )

        pre_built_credentials = None
        if connector.connector_type in COMPOSIO_GOOGLE_CONNECTOR_TYPES:
            connected_account_id = connector.config.get("composio_connected_account_id")
            if not connected_account_id:
                error_msg = f"Composio connected_account_id not found for connector {connector_id}"
                await task_logger.log_task_failure(
                    log_entry,
                    error_msg,
                    "Missing Composio account",
                    {"error_type": "MissingComposioAccount"},
                )
                return 0, 0, error_msg
            pre_built_credentials = build_composio_credentials(connected_account_id)
        else:
            token_encrypted = connector.config.get("_token_encrypted", False)
            if token_encrypted and not config.SECRET_KEY:
                await task_logger.log_task_failure(
                    log_entry,
                    "SECRET_KEY not configured but credentials are encrypted",
                    "Missing SECRET_KEY",
                    {"error_type": "MissingSecretKey"},
                )
                return (
                    0,
                    0,
                    "SECRET_KEY not configured but credentials are marked as encrypted",
                )

        connector_enable_summary = getattr(connector, "enable_summary", True)
        drive_client = GoogleDriveClient(
            session, connector_id, credentials=pre_built_credentials
        )

        if not folder_id:
            error_msg = "folder_id is required for Google Drive indexing"
            await task_logger.log_task_failure(
                log_entry, error_msg, {"error_type": "MissingParameter"}
            )
            return 0, 0, error_msg

        target_folder_id = folder_id
        target_folder_name = folder_name or "Selected Folder"

        folder_tokens = connector.config.get("folder_tokens", {})
        start_page_token = folder_tokens.get(target_folder_id)
        can_use_delta = (
            use_delta_sync and start_page_token and connector.last_indexed_at
        )

        if can_use_delta:
            logger.info(f"Using delta sync for connector {connector_id}")
            documents_indexed, documents_skipped = await _index_with_delta_sync(
                drive_client,
                session,
                connector,
                connector_id,
                search_space_id,
                user_id,
                target_folder_id,
                start_page_token,
                task_logger,
                log_entry,
                max_files,
                include_subfolders,
                on_heartbeat_callback,
                connector_enable_summary,
            )
            logger.info("Running reconciliation scan after delta sync")
            ri, rs = await _index_full_scan(
                drive_client,
                session,
                connector,
                connector_id,
                search_space_id,
                user_id,
                target_folder_id,
                target_folder_name,
                task_logger,
                log_entry,
                max_files,
                include_subfolders,
                on_heartbeat_callback,
                connector_enable_summary,
            )
            documents_indexed += ri
            documents_skipped += rs
        else:
            logger.info(f"Using full scan for connector {connector_id}")
            documents_indexed, documents_skipped = await _index_full_scan(
                drive_client,
                session,
                connector,
                connector_id,
                search_space_id,
                user_id,
                target_folder_id,
                target_folder_name,
                task_logger,
                log_entry,
                max_files,
                include_subfolders,
                on_heartbeat_callback,
                connector_enable_summary,
            )

        if documents_indexed > 0 or can_use_delta:
            new_token, token_error = await get_start_page_token(drive_client)
            if new_token and not token_error:
                await session.refresh(connector)
                if "folder_tokens" not in connector.config:
                    connector.config["folder_tokens"] = {}
                connector.config["folder_tokens"][target_folder_id] = new_token
                flag_modified(connector, "config")
            await update_connector_last_indexed(session, connector, update_last_indexed)

        await session.commit()

        await task_logger.log_task_success(
            log_entry,
            f"Successfully completed Google Drive indexing for connector {connector_id}",
            {
                "files_processed": documents_indexed,
                "files_skipped": documents_skipped,
                "sync_type": "delta" if can_use_delta else "full",
                "folder": target_folder_name,
            },
        )
        logger.info(
            f"Google Drive indexing completed: {documents_indexed} indexed, {documents_skipped} skipped"
        )
        return documents_indexed, documents_skipped, None

    except SQLAlchemyError as db_error:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Database error during Google Drive indexing for connector {connector_id}",
            str(db_error),
            {"error_type": "SQLAlchemyError"},
        )
        logger.error(f"Database error: {db_error!s}", exc_info=True)
        return 0, 0, f"Database error: {db_error!s}"
    except Exception as e:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Failed to index Google Drive files for connector {connector_id}",
            str(e),
            {"error_type": type(e).__name__},
        )
        logger.error(f"Failed to index Google Drive files: {e!s}", exc_info=True)
        return 0, 0, f"Failed to index Google Drive files: {e!s}"


async def index_google_drive_single_file(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    file_id: str,
    file_name: str | None = None,
) -> tuple[int, str | None]:
    """Index a single Google Drive file by its ID."""
    task_logger = TaskLoggingService(session, search_space_id)
    log_entry = await task_logger.log_task_start(
        task_name="google_drive_single_file_indexing",
        source="connector_indexing_task",
        message=f"Starting Google Drive single file indexing for file {file_id}",
        metadata={
            "connector_id": connector_id,
            "user_id": str(user_id),
            "file_id": file_id,
            "file_name": file_name,
        },
    )

    try:
        connector = None
        for ct in ACCEPTED_DRIVE_CONNECTOR_TYPES:
            connector = await get_connector_by_id(session, connector_id, ct)
            if connector:
                break
        if not connector:
            error_msg = f"Google Drive connector with ID {connector_id} not found"
            await task_logger.log_task_failure(
                log_entry, error_msg, None, {"error_type": "ConnectorNotFound"}
            )
            return 0, error_msg

        pre_built_credentials = None
        if connector.connector_type in COMPOSIO_GOOGLE_CONNECTOR_TYPES:
            connected_account_id = connector.config.get("composio_connected_account_id")
            if not connected_account_id:
                error_msg = f"Composio connected_account_id not found for connector {connector_id}"
                await task_logger.log_task_failure(
                    log_entry,
                    error_msg,
                    "Missing Composio account",
                    {"error_type": "MissingComposioAccount"},
                )
                return 0, error_msg
            pre_built_credentials = build_composio_credentials(connected_account_id)
        else:
            token_encrypted = connector.config.get("_token_encrypted", False)
            if token_encrypted and not config.SECRET_KEY:
                await task_logger.log_task_failure(
                    log_entry,
                    "SECRET_KEY not configured but credentials are encrypted",
                    "Missing SECRET_KEY",
                    {"error_type": "MissingSecretKey"},
                )
                return (
                    0,
                    "SECRET_KEY not configured but credentials are marked as encrypted",
                )

        connector_enable_summary = getattr(connector, "enable_summary", True)
        drive_client = GoogleDriveClient(
            session, connector_id, credentials=pre_built_credentials
        )

        file, error = await get_file_by_id(drive_client, file_id)
        if error or not file:
            error_msg = f"Failed to fetch file {file_id}: {error or 'File not found'}"
            await task_logger.log_task_failure(
                log_entry, error_msg, {"error_type": "FileNotFound"}
            )
            return 0, error_msg

        display_name = file_name or file.get("name", "Unknown")

        indexed, _skipped, failed = await _process_single_file(
            drive_client,
            session,
            file,
            connector_id,
            search_space_id,
            user_id,
            connector_enable_summary,
        )
        await session.commit()

        if failed > 0:
            error_msg = f"Failed to index file {display_name}"
            await task_logger.log_task_failure(
                log_entry, error_msg, {"file_name": display_name, "file_id": file_id}
            )
            return 0, error_msg

        if indexed > 0:
            await task_logger.log_task_success(
                log_entry,
                f"Successfully indexed file {display_name}",
                {"file_name": display_name, "file_id": file_id},
            )
            return 1, None

        return 0, None

    except SQLAlchemyError as db_error:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            "Database error during file indexing",
            str(db_error),
            {"error_type": "SQLAlchemyError"},
        )
        logger.error(f"Database error: {db_error!s}", exc_info=True)
        return 0, f"Database error: {db_error!s}"
    except Exception as e:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            "Failed to index Google Drive file",
            str(e),
            {"error_type": type(e).__name__},
        )
        logger.error(f"Failed to index Google Drive file: {e!s}", exc_info=True)
        return 0, f"Failed to index Google Drive file: {e!s}"


async def index_google_drive_selected_files(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    files: list[tuple[str, str | None]],
    on_heartbeat_callback: HeartbeatCallbackType | None = None,
) -> tuple[int, int, list[str]]:
    """Index multiple user-selected Google Drive files in parallel.

    Sets up the connector/credentials once, then delegates to
    _index_selected_files for the three-phase parallel pipeline.

    Returns (indexed_count, skipped_count, errors).
    """
    task_logger = TaskLoggingService(session, search_space_id)
    log_entry = await task_logger.log_task_start(
        task_name="google_drive_selected_files_indexing",
        source="connector_indexing_task",
        message=f"Starting Google Drive batch file indexing for {len(files)} files",
        metadata={
            "connector_id": connector_id,
            "user_id": str(user_id),
            "file_count": len(files),
        },
    )

    try:
        connector = None
        for ct in ACCEPTED_DRIVE_CONNECTOR_TYPES:
            connector = await get_connector_by_id(session, connector_id, ct)
            if connector:
                break
        if not connector:
            error_msg = f"Google Drive connector with ID {connector_id} not found"
            await task_logger.log_task_failure(
                log_entry, error_msg, None, {"error_type": "ConnectorNotFound"}
            )
            return 0, 0, [error_msg]

        pre_built_credentials = None
        if connector.connector_type in COMPOSIO_GOOGLE_CONNECTOR_TYPES:
            connected_account_id = connector.config.get("composio_connected_account_id")
            if not connected_account_id:
                error_msg = f"Composio connected_account_id not found for connector {connector_id}"
                await task_logger.log_task_failure(
                    log_entry,
                    error_msg,
                    "Missing Composio account",
                    {"error_type": "MissingComposioAccount"},
                )
                return 0, 0, [error_msg]
            pre_built_credentials = build_composio_credentials(connected_account_id)
        else:
            token_encrypted = connector.config.get("_token_encrypted", False)
            if token_encrypted and not config.SECRET_KEY:
                error_msg = (
                    "SECRET_KEY not configured but credentials are marked as encrypted"
                )
                await task_logger.log_task_failure(
                    log_entry,
                    error_msg,
                    "Missing SECRET_KEY",
                    {"error_type": "MissingSecretKey"},
                )
                return 0, 0, [error_msg]

        connector_enable_summary = getattr(connector, "enable_summary", True)
        drive_client = GoogleDriveClient(
            session, connector_id, credentials=pre_built_credentials
        )

        indexed, skipped, errors = await _index_selected_files(
            drive_client,
            session,
            files,
            connector_id=connector_id,
            search_space_id=search_space_id,
            user_id=user_id,
            enable_summary=connector_enable_summary,
            on_heartbeat=on_heartbeat_callback,
        )

        await session.commit()

        if errors:
            await task_logger.log_task_failure(
                log_entry,
                f"Batch file indexing completed with {len(errors)} error(s)",
                "; ".join(errors),
                {"indexed": indexed, "skipped": skipped, "error_count": len(errors)},
            )
        else:
            await task_logger.log_task_success(
                log_entry,
                f"Successfully indexed {indexed} files ({skipped} skipped)",
                {"indexed": indexed, "skipped": skipped},
            )

        logger.info(
            f"Selected files indexing: {indexed} indexed, {skipped} skipped, {len(errors)} errors"
        )
        return indexed, skipped, errors

    except SQLAlchemyError as db_error:
        await session.rollback()
        error_msg = f"Database error: {db_error!s}"
        await task_logger.log_task_failure(
            log_entry, error_msg, str(db_error), {"error_type": "SQLAlchemyError"}
        )
        logger.error(error_msg, exc_info=True)
        return 0, 0, [error_msg]
    except Exception as e:
        await session.rollback()
        error_msg = f"Failed to index Google Drive files: {e!s}"
        await task_logger.log_task_failure(
            log_entry, error_msg, str(e), {"error_type": type(e).__name__}
        )
        logger.error(error_msg, exc_info=True)
        return 0, 0, [error_msg]
