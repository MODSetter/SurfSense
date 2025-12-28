"""
Google Drive Indexer - Delegates all processing to Surfsense's file processors.

Handles:
- Folder-specific indexing (user selects folder)
- Delta sync (only index changed files)
- Delegates file processing to process_file_in_background
"""

import logging
from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.google_drive import (
    GoogleDriveClient,
    categorize_change,
    download_and_process_file,
    fetch_all_changes,
    get_files_in_folder,
    get_start_page_token,
)
from app.db import DocumentType, SearchSourceConnectorType
from app.services.task_logging_service import TaskLoggingService
from app.tasks.connector_indexers.base import (
    check_document_by_unique_identifier,
    get_connector_by_id,
    update_connector_last_indexed,
)
from app.utils.document_converters import generate_unique_identifier_hash

logger = logging.getLogger(__name__)


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
) -> tuple[int, str | None]:
    """
    Index Google Drive files for a specific connector.

    Args:
        session: Database session
        connector_id: ID of the Drive connector
        search_space_id: ID of the search space
        user_id: ID of the user
        folder_id: Specific folder to index (from UI/request, takes precedence)
        folder_name: Folder name for display (from UI/request)
        use_delta_sync: Whether to use change tracking for incremental sync
        update_last_indexed: Whether to update last_indexed_at timestamp
        max_files: Maximum number of files to index

    Returns:
        Tuple of (number_of_indexed_files, error_message)
    """
    task_logger = TaskLoggingService(session, search_space_id)

    # Log task start
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
        # Get connector from database
        connector = await get_connector_by_id(
            session, connector_id, SearchSourceConnectorType.GOOGLE_DRIVE_CONNECTOR
        )

        if not connector:
            error_msg = f"Google Drive connector with ID {connector_id} not found"
            await task_logger.log_task_failure(
                log_entry, error_msg, {"error_type": "ConnectorNotFound"}
            )
            return 0, error_msg

        # Initialize Drive client
        await task_logger.log_task_progress(
            log_entry,
            f"Initializing Google Drive client for connector {connector_id}",
            {"stage": "client_initialization"},
        )

        drive_client = GoogleDriveClient(session, connector_id)

        # Use folder from request params (required for Google Drive)
        if not folder_id:
            error_msg = "folder_id is required for Google Drive indexing"
            await task_logger.log_task_failure(
                log_entry, error_msg, {"error_type": "MissingParameter"}
            )
            return 0, error_msg

        target_folder_id = folder_id
        target_folder_name = folder_name or "Selected Folder"

        logger.info(f"Indexing Google Drive folder: {target_folder_name} ({target_folder_id})")

        # Decide sync strategy
        start_page_token = connector.config.get("start_page_token")
        can_use_delta_sync = use_delta_sync and start_page_token and connector.last_indexed_at

        if can_use_delta_sync:
            logger.info(f"Using delta sync for connector {connector_id}")
            result = await _index_with_delta_sync(
                drive_client=drive_client,
                session=session,
                connector=connector,
                connector_id=connector_id,
                search_space_id=search_space_id,
                user_id=user_id,
                folder_id=target_folder_id,
                start_page_token=start_page_token,
                task_logger=task_logger,
                log_entry=log_entry,
                max_files=max_files,
            )
        else:
            logger.info(f"Using full scan for connector {connector_id}")
            result = await _index_full_scan(
                drive_client=drive_client,
                session=session,
                connector=connector,
                connector_id=connector_id,
                search_space_id=search_space_id,
                user_id=user_id,
                folder_id=target_folder_id,
                folder_name=target_folder_name,
                task_logger=task_logger,
                log_entry=log_entry,
                max_files=max_files,
            )

        documents_indexed, documents_skipped = result

        # Update last indexed timestamp and get new start page token
        if documents_indexed > 0 or can_use_delta_sync:
            # Get new start page token for next sync
            new_token, token_error = await get_start_page_token(drive_client)
            if new_token and not token_error:
                from sqlalchemy.orm.attributes import flag_modified

                connector.config["start_page_token"] = new_token
                flag_modified(connector, "config")

            await update_connector_last_indexed(session, connector, update_last_indexed)

        # Final commit
        await session.commit()
        logger.info(
            f"Successfully committed Google Drive indexing changes to database"
        )

        # Log success
        await task_logger.log_task_success(
            log_entry,
            f"Successfully completed Google Drive indexing for connector {connector_id}",
            {
                "files_processed": documents_indexed,
                "files_skipped": documents_skipped,
                "sync_type": "delta" if can_use_delta_sync else "full",
                "folder": target_folder_name,
            },
        )

        logger.info(
            f"Google Drive indexing completed: {documents_indexed} files indexed, {documents_skipped} skipped"
        )
        return documents_indexed, None

    except SQLAlchemyError as db_error:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Database error during Google Drive indexing for connector {connector_id}",
            str(db_error),
            {"error_type": "SQLAlchemyError"},
        )
        logger.error(f"Database error: {db_error!s}", exc_info=True)
        return 0, f"Database error: {db_error!s}"
    except Exception as e:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Failed to index Google Drive files for connector {connector_id}",
            str(e),
            {"error_type": type(e).__name__},
        )
        logger.error(f"Failed to index Google Drive files: {e!s}", exc_info=True)
        return 0, f"Failed to index Google Drive files: {e!s}"


async def _index_full_scan(
    drive_client: GoogleDriveClient,
    session: AsyncSession,
    connector: any,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    folder_id: str | None,
    folder_name: str,
    task_logger: TaskLoggingService,
    log_entry: any,
    max_files: int,
) -> tuple[int, int]:
    """Perform full scan indexing of a folder."""
    await task_logger.log_task_progress(
        log_entry,
        f"Starting full scan of folder: {folder_name}",
        {"stage": "full_scan", "folder_id": folder_id},
    )

    documents_indexed = 0
    documents_skipped = 0
    page_token = None
    files_processed = 0

    # Paginate through all files in folder
    while files_processed < max_files:
        files, next_token, error = await get_files_in_folder(
            drive_client, folder_id, include_subfolders=False, page_token=page_token
        )

        if error:
            logger.error(f"Error listing files: {error}")
            break

        if not files:
            break

        for file in files:
            if files_processed >= max_files:
                break

            files_processed += 1

            # Process file
            indexed, skipped = await _process_single_file(
                drive_client=drive_client,
                session=session,
                file=file,
                connector_id=connector_id,
                search_space_id=search_space_id,
                user_id=user_id,
                task_logger=task_logger,
                log_entry=log_entry,
            )

            documents_indexed += indexed
            documents_skipped += skipped

            # Batch commit every 10 files
            if documents_indexed % 10 == 0 and documents_indexed > 0:
                await session.commit()
                logger.info(f"Committed batch: {documents_indexed} files indexed so far")

        page_token = next_token
        if not page_token:
            break

    logger.info(
        f"Full scan complete: {documents_indexed} indexed, {documents_skipped} skipped"
    )
    return documents_indexed, documents_skipped


async def _index_with_delta_sync(
    drive_client: GoogleDriveClient,
    session: AsyncSession,
    connector: any,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    folder_id: str | None,
    start_page_token: str,
    task_logger: TaskLoggingService,
    log_entry: any,
    max_files: int,
) -> tuple[int, int]:
    """Perform delta sync indexing using change tracking."""
    await task_logger.log_task_progress(
        log_entry,
        f"Starting delta sync from token: {start_page_token[:20]}...",
        {"stage": "delta_sync", "start_token": start_page_token},
    )

    # Fetch all changes since last sync
    changes, final_token, error = await fetch_all_changes(
        drive_client, start_page_token, folder_id
    )

    if error:
        logger.error(f"Error fetching changes: {error}")
        return 0, 0

    if not changes:
        logger.info("No changes detected since last sync")
        return 0, 0

    logger.info(f"Processing {len(changes)} changes")

    documents_indexed = 0
    documents_skipped = 0
    files_processed = 0

    for change in changes:
        if files_processed >= max_files:
            break

        files_processed += 1
        change_type = categorize_change(change)

        # Handle removed/trashed files
        if change_type in ["removed", "trashed"]:
            file_id = change.get("fileId")
            if file_id:
                await _remove_document(session, file_id, search_space_id)
            continue

        # Handle modified/new files
        file = change.get("file")
        if not file:
            continue

        indexed, skipped = await _process_single_file(
            drive_client=drive_client,
            session=session,
            file=file,
            connector_id=connector_id,
            search_space_id=search_space_id,
            user_id=user_id,
            task_logger=task_logger,
            log_entry=log_entry,
        )

        documents_indexed += indexed
        documents_skipped += skipped

        # Batch commit every 10 files
        if documents_indexed % 10 == 0 and documents_indexed > 0:
            await session.commit()
            logger.info(f"Committed batch: {documents_indexed} changes processed")

    logger.info(
        f"Delta sync complete: {documents_indexed} indexed, {documents_skipped} skipped"
    )
    return documents_indexed, documents_skipped


async def _process_single_file(
    drive_client: GoogleDriveClient,
    session: AsyncSession,
    file: dict,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    task_logger: TaskLoggingService,
    log_entry: any,
) -> tuple[int, int]:
    """
    Process a single file by downloading and using Surfsense's file processor.

    Returns:
        Tuple of (indexed_count, skipped_count)
    """
    file_name = file.get("name", "Unknown")
    mime_type = file.get("mimeType", "")

    try:
        logger.info(f"Processing file: {file_name} ({mime_type})")

        # Download and process using Surfsense's existing infrastructure
        # This handles: markdown, audio, PDFs, Office docs, images, etc.
        # It also handles: deduplication, chunking, summarization, embedding
        document, error, file_metadata = await download_and_process_file(
            client=drive_client,
            file=file,
            search_space_id=search_space_id,
            user_id=user_id,
            session=session,
            task_logger=task_logger,
            log_entry=log_entry,
        )

        if error:
            # Log and skip - not an error, just unsupported or empty
            await task_logger.log_task_progress(
                log_entry,
                f"Skipped {file_name}: {error}",
                {"status": "skipped", "reason": error},
            )
            return 0, 1

        if document and file_metadata:
            # Refresh document from database to ensure it's attached to session
            from app.db import Document
            from sqlalchemy import select
            
            # Get fresh document from database
            result = await session.execute(
                select(Document).where(Document.id == document.id)
            )
            document = result.scalar_one_or_none()
            
            if not document:
                logger.error(f"Could not find document {document.id} in database")
                return 0, 1
            
            # Update document type to GOOGLE_DRIVE_CONNECTOR and add metadata
            original_type = document.document_type
            document.document_type = DocumentType.GOOGLE_DRIVE_CONNECTOR
            
            # Add Google Drive specific metadata
            if not document.metadata:
                document.metadata = {}
            
            document.metadata.update({
                **file_metadata,
                "original_document_type": original_type,
                "source_connector": "google_drive",
            })
            
            # Commit the document type and metadata changes
            await session.commit()
            
            logger.info(
                f"Updated document {document.id} to GOOGLE_DRIVE_CONNECTOR type with metadata"
            )
            
            # Successfully indexed
            await task_logger.log_task_progress(
                log_entry,
                f"Successfully indexed: {file_name}",
                {
                    "status": "indexed",
                    "document_id": document.id,
                    "file_name": file_name,
                    "document_type": DocumentType.GOOGLE_DRIVE_CONNECTOR,
                },
            )
            return 1, 0
        else:
            # Likely a duplicate or unsupported type
            logger.info(f"No document created for {file_name} (duplicate or unsupported)")
            return 0, 1

    except Exception as e:
        logger.error(f"Error processing file {file_name}: {e!s}", exc_info=True)
        return 0, 1


async def _remove_document(
    session: AsyncSession, file_id: str, search_space_id: int
):
    """Remove a document that was deleted in Drive."""
    unique_identifier_hash = generate_unique_identifier_hash(
        DocumentType.GOOGLE_DRIVE_CONNECTOR, file_id, search_space_id
    )

    existing_document = await check_document_by_unique_identifier(
        session, unique_identifier_hash
    )

    if existing_document:
        await session.delete(existing_document)
        logger.info(f"Removed deleted file document: {file_id}")


