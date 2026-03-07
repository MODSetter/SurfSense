"""
Airtable connector indexer.

Implements real-time document status updates using a two-phase approach:
- Phase 1: Create all documents with PENDING status (visible in UI immediately)
- Phase 2: Process each document one by one (pending → processing → ready/failed)
"""

import time
from collections.abc import Awaitable, Callable

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.airtable_history import AirtableHistoryConnector
from app.db import Document, DocumentStatus, DocumentType, SearchSourceConnectorType
from app.services.llm_service import get_user_long_context_llm
from app.services.task_logging_service import TaskLoggingService
from app.utils.document_converters import (
    create_document_chunks,
    embed_text,
    generate_content_hash,
    generate_document_summary,
    generate_unique_identifier_hash,
)

from .base import (
    calculate_date_range,
    check_document_by_unique_identifier,
    check_duplicate_document_by_hash,
    get_connector_by_id,
    get_current_timestamp,
    logger,
    safe_set_chunks,
    update_connector_last_indexed,
)

# Type hint for heartbeat callback
HeartbeatCallbackType = Callable[[int], Awaitable[None]]

# Heartbeat interval in seconds
HEARTBEAT_INTERVAL_SECONDS = 30


async def index_airtable_records(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    max_records: int = 2500,
    update_last_indexed: bool = True,
    on_heartbeat_callback: HeartbeatCallbackType | None = None,
) -> tuple[int, str | None]:
    """
    Index Airtable records for a given connector.

    Args:
        session: Database session
        connector_id: ID of the Airtable connector
        search_space_id: ID of the search space to store documents in
        user_id: ID of the user
        start_date: Start date for filtering records (YYYY-MM-DD)
        end_date: End date for filtering records (YYYY-MM-DD)
        max_records: Maximum number of records to fetch per table
        update_last_indexed: Whether to update the last_indexed_at timestamp
        on_heartbeat_callback: Optional callback to update notification during long-running indexing.

    Returns:
        Tuple of (number_of_documents_processed, error_message)
    """
    task_logger = TaskLoggingService(session, search_space_id)
    log_entry = await task_logger.log_task_start(
        task_name="airtable_indexing",
        source="connector_indexing_task",
        message=f"Starting Airtable indexing for connector {connector_id}",
        metadata={
            "connector_id": connector_id,
            "user_id": str(user_id),
            "start_date": start_date,
            "end_date": end_date,
            "max_records": max_records,
        },
    )

    try:
        # Get the connector from the database
        connector = await get_connector_by_id(
            session, connector_id, SearchSourceConnectorType.AIRTABLE_CONNECTOR
        )

        if not connector:
            await task_logger.log_task_failure(
                log_entry,
                f"Connector with ID {connector_id} not found",
                "Connector not found",
                {"error_type": "ConnectorNotFound"},
            )
            return 0, f"Connector with ID {connector_id} not found"

        # Normalize "undefined" strings to None (from frontend)
        if start_date == "undefined" or start_date == "":
            start_date = None
        if end_date == "undefined" or end_date == "":
            end_date = None

        # Calculate date range for indexing
        start_date_str, end_date_str = calculate_date_range(
            connector, start_date, end_date, default_days_back=365
        )

        logger.info(
            f"Starting Airtable indexing for connector {connector_id} "
            f"from {start_date_str} to {end_date_str}"
        )

        # Initialize Airtable history connector with auto-refresh capability
        airtable_history = AirtableHistoryConnector(session, connector_id)
        airtable_connector = await airtable_history._get_connector()
        total_processed = 0

        try:
            # Get accessible bases
            logger.info(f"Fetching Airtable bases for connector {connector_id}")
            bases, error = airtable_connector.get_bases()

            if error:
                await task_logger.log_task_failure(
                    log_entry,
                    f"Failed to fetch Airtable bases: {error}",
                    "API Error",
                    {"error_type": "APIError"},
                )
                return 0, f"Failed to fetch Airtable bases: {error}"

            if not bases:
                success_msg = "No Airtable bases found or accessible"
                await task_logger.log_task_success(
                    log_entry, success_msg, {"bases_count": 0}
                )
                # CRITICAL: Update timestamp even when no bases found so Electric SQL syncs
                await update_connector_last_indexed(
                    session, connector, update_last_indexed
                )
                await session.commit()
                return 0, None  # Return None (not error) when no items found

            logger.info(f"Found {len(bases)} Airtable bases to process")

            # Heartbeat tracking - update notification periodically to prevent appearing stuck
            last_heartbeat_time = time.time()

            # Track overall statistics
            documents_indexed = 0
            documents_skipped = 0
            documents_failed = 0
            duplicate_content_count = 0

            # =======================================================================
            # PHASE 1: Collect all records and create pending documents
            # This makes ALL documents visible in the UI immediately with pending status
            # =======================================================================
            records_to_process = []  # List of dicts with document and record data
            new_documents_created = False

            for base in bases:
                base_id = base.get("id")
                base_name = base.get("name", "Unknown Base")

                if not base_id:
                    logger.warning(f"Skipping base without ID: {base}")
                    continue

                logger.info(f"Processing base: {base_name} ({base_id})")

                # Get base schema to find tables
                schema_data, schema_error = airtable_connector.get_base_schema(base_id)

                if schema_error:
                    logger.warning(
                        f"Failed to get schema for base {base_id}: {schema_error}"
                    )
                    continue

                if not schema_data or "tables" not in schema_data:
                    logger.warning(f"No tables found in base {base_id}")
                    continue

                tables = schema_data["tables"]
                logger.info(f"Found {len(tables)} tables in base {base_name}")

                # Process each table
                for table in tables:
                    table_id = table.get("id")
                    table_name = table.get("name", "Unknown Table")

                    if not table_id:
                        logger.warning(f"Skipping table without ID: {table}")
                        continue

                    logger.info(f"Processing table: {table_name} ({table_id})")

                    # Fetch records
                    if start_date_str and end_date_str:
                        # Use date filtering if available
                        records, records_error = (
                            airtable_connector.get_records_by_date_range(
                                base_id=base_id,
                                table_id=table_id,
                                date_field="CREATED_TIME()",
                                start_date=start_date_str,
                                end_date=end_date_str,
                                max_records=max_records,
                            )
                        )
                    else:
                        # Fetch all records
                        records, records_error = airtable_connector.get_all_records(
                            base_id=base_id,
                            table_id=table_id,
                            max_records=max_records,
                        )

                    if records_error:
                        logger.warning(
                            f"Failed to fetch records from table {table_name}: {records_error}"
                        )
                        continue

                    if not records:
                        logger.info(f"No records found in table {table_name}")
                        continue

                    logger.info(f"Found {len(records)} records in table {table_name}")

                    # Phase 1: Analyze each record and create pending documents
                    for record in records:
                        try:
                            record_id = record.get("id", "")
                            if not record_id:
                                documents_skipped += 1
                                continue

                            # Generate markdown content
                            markdown_content = (
                                airtable_connector.format_record_to_markdown(
                                    record, f"{base_name} - {table_name}"
                                )
                            )

                            if not markdown_content.strip():
                                logger.warning(
                                    f"Skipping record with no content: {record_id}"
                                )
                                documents_skipped += 1
                                continue

                            # Generate unique identifier hash for this Airtable record
                            unique_identifier_hash = generate_unique_identifier_hash(
                                DocumentType.AIRTABLE_CONNECTOR,
                                record_id,
                                search_space_id,
                            )

                            # Generate content hash
                            content_hash = generate_content_hash(
                                markdown_content, search_space_id
                            )

                            # Check if document with this unique identifier already exists
                            existing_document = (
                                await check_document_by_unique_identifier(
                                    session, unique_identifier_hash
                                )
                            )

                            if existing_document:
                                # Document exists - check if content has changed
                                if existing_document.content_hash == content_hash:
                                    # Ensure status is ready (might have been stuck in processing/pending)
                                    if not DocumentStatus.is_state(
                                        existing_document.status, DocumentStatus.READY
                                    ):
                                        existing_document.status = (
                                            DocumentStatus.ready()
                                        )
                                    documents_skipped += 1
                                    continue

                                # Queue existing document for update (will be set to processing in Phase 2)
                                records_to_process.append(
                                    {
                                        "document": existing_document,
                                        "is_new": False,
                                        "markdown_content": markdown_content,
                                        "content_hash": content_hash,
                                        "record_id": record_id,
                                        "record": record,
                                        "base_name": base_name,
                                        "table_name": table_name,
                                    }
                                )
                                continue

                            # Document doesn't exist by unique_identifier_hash
                            # Check if a document with the same content_hash exists (from another connector)
                            with session.no_autoflush:
                                duplicate_by_content = (
                                    await check_duplicate_document_by_hash(
                                        session, content_hash
                                    )
                                )

                            if duplicate_by_content:
                                logger.info(
                                    f"Airtable record {record_id} already indexed by another connector "
                                    f"(existing document ID: {duplicate_by_content.id}, "
                                    f"type: {duplicate_by_content.document_type}). Skipping."
                                )
                                duplicate_content_count += 1
                                documents_skipped += 1
                                continue

                            # Create new document with PENDING status (visible in UI immediately)
                            document = Document(
                                search_space_id=search_space_id,
                                title=record_id,
                                document_type=DocumentType.AIRTABLE_CONNECTOR,
                                document_metadata={
                                    "record_id": record_id,
                                    "created_time": record.get("CREATED_TIME()", ""),
                                    "base_name": base_name,
                                    "table_name": table_name,
                                    "connector_id": connector_id,
                                },
                                content="Pending...",  # Placeholder until processed
                                content_hash=unique_identifier_hash,  # Temporary unique value - updated when ready
                                unique_identifier_hash=unique_identifier_hash,
                                embedding=None,
                                chunks=[],  # Empty at creation - safe for async
                                status=DocumentStatus.pending(),  # Pending until processing starts
                                updated_at=get_current_timestamp(),
                                created_by_id=user_id,
                                connector_id=connector_id,
                            )
                            session.add(document)
                            new_documents_created = True

                            records_to_process.append(
                                {
                                    "document": document,
                                    "is_new": True,
                                    "markdown_content": markdown_content,
                                    "content_hash": content_hash,
                                    "record_id": record_id,
                                    "record": record,
                                    "base_name": base_name,
                                    "table_name": table_name,
                                }
                            )

                        except Exception as e:
                            logger.error(
                                f"Error in Phase 1 for record: {e!s}", exc_info=True
                            )
                            documents_failed += 1
                            continue

            # Commit all pending documents - they all appear in UI now
            if new_documents_created:
                logger.info(
                    f"Phase 1: Committing {len([r for r in records_to_process if r['is_new']])} pending documents"
                )
                await session.commit()

            # =======================================================================
            # PHASE 2: Process each document one by one
            # Each document transitions: pending → processing → ready/failed
            # =======================================================================
            logger.info(f"Phase 2: Processing {len(records_to_process)} documents")

            for item in records_to_process:
                # Send heartbeat periodically
                if on_heartbeat_callback:
                    current_time = time.time()
                    if current_time - last_heartbeat_time >= HEARTBEAT_INTERVAL_SECONDS:
                        await on_heartbeat_callback(documents_indexed)
                        last_heartbeat_time = current_time

                document = item["document"]
                try:
                    # Set to PROCESSING and commit - shows "processing" in UI for THIS document only
                    document.status = DocumentStatus.processing()
                    await session.commit()

                    # Heavy processing (LLM, embeddings, chunks)
                    user_llm = await get_user_long_context_llm(
                        session, user_id, search_space_id
                    )

                    if user_llm and connector.enable_summary:
                        document_metadata_for_summary = {
                            "record_id": item["record_id"],
                            "created_time": item["record"].get("CREATED_TIME()", ""),
                            "document_type": "Airtable Record",
                            "connector_type": "Airtable",
                        }
                        (
                            summary_content,
                            summary_embedding,
                        ) = await generate_document_summary(
                            item["markdown_content"],
                            user_llm,
                            document_metadata_for_summary,
                        )
                    else:
                        summary_content = f"Airtable Record: {item['record_id']}\n\n{item['markdown_content']}"
                        summary_embedding = embed_text(summary_content)

                    chunks = await create_document_chunks(item["markdown_content"])

                    # Update document to READY with actual content
                    document.title = item["record_id"]
                    document.content = summary_content
                    document.content_hash = item["content_hash"]
                    document.embedding = summary_embedding
                    document.document_metadata = {
                        "record_id": item["record_id"],
                        "created_time": item["record"].get("CREATED_TIME()", ""),
                        "base_name": item["base_name"],
                        "table_name": item["table_name"],
                        "connector_id": connector_id,
                    }
                    safe_set_chunks(document, chunks)
                    document.updated_at = get_current_timestamp()
                    document.status = DocumentStatus.ready()

                    documents_indexed += 1

                    # Batch commit every 10 documents (for ready status updates)
                    if documents_indexed % 10 == 0:
                        logger.info(
                            f"Committing batch: {documents_indexed} Airtable records processed so far"
                        )
                        await session.commit()

                except Exception as e:
                    logger.error(
                        f"Error processing Airtable record: {e!s}", exc_info=True
                    )
                    # Mark document as failed with reason (visible in UI)
                    try:
                        document.status = DocumentStatus.failed(str(e))
                        document.updated_at = get_current_timestamp()
                    except Exception as status_error:
                        logger.error(
                            f"Failed to update document status to failed: {status_error}"
                        )
                    documents_failed += 1
                    continue

            # CRITICAL: Always update timestamp (even if 0 documents indexed) so Electric SQL syncs
            await update_connector_last_indexed(session, connector, update_last_indexed)

            total_processed = documents_indexed

            # Final commit to ensure all documents are persisted (safety net)
            logger.info(
                f"Final commit: Total {documents_indexed} Airtable records processed"
            )
            try:
                await session.commit()
                logger.info(
                    "Successfully committed all Airtable document changes to database"
                )
            except Exception as e:
                # Handle any remaining integrity errors gracefully (race conditions, etc.)
                if (
                    "duplicate key value violates unique constraint" in str(e).lower()
                    or "uniqueviolationerror" in str(e).lower()
                ):
                    logger.warning(
                        f"Duplicate content_hash detected during final commit. "
                        f"This may occur if the same record was indexed by multiple connectors. "
                        f"Rolling back and continuing. Error: {e!s}"
                    )
                    await session.rollback()
                    # Don't fail the entire task - some documents may have been successfully indexed
                else:
                    raise

            # Build warning message if there were issues
            warning_parts = []
            if duplicate_content_count > 0:
                warning_parts.append(f"{duplicate_content_count} duplicate")
            if documents_failed > 0:
                warning_parts.append(f"{documents_failed} failed")
            warning_message = ", ".join(warning_parts) if warning_parts else None

            # Log success after processing all bases and tables
            await task_logger.log_task_success(
                log_entry,
                f"Successfully completed Airtable indexing for connector {connector_id}",
                {
                    "documents_indexed": documents_indexed,
                    "documents_skipped": documents_skipped,
                    "documents_failed": documents_failed,
                    "duplicate_content_count": duplicate_content_count,
                },
            )

            logger.info(
                f"Airtable indexing completed: {documents_indexed} ready, "
                f"{documents_skipped} skipped, {documents_failed} failed "
                f"({duplicate_content_count} duplicate content)"
            )
            return (
                total_processed,
                warning_message,
            )

        except Exception as e:
            logger.error(
                f"Fetching Airtable bases for connector {connector_id} failed: {e!s}",
                exc_info=True,
            )
            await task_logger.log_task_failure(
                log_entry,
                f"Failed to fetch Airtable bases for connector {connector_id}",
                str(e),
                {"error_type": type(e).__name__},
            )
            return 0, f"Failed to fetch Airtable bases: {e!s}"

    except SQLAlchemyError as db_error:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Database error during Airtable indexing for connector {connector_id}",
            str(db_error),
            {"error_type": "SQLAlchemyError"},
        )
        logger.error(
            f"Database error during Airtable indexing: {db_error!s}", exc_info=True
        )
        return 0, f"Database error: {db_error!s}"
    except Exception as e:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Failed to index Airtable records for connector {connector_id}",
            str(e),
            {"error_type": type(e).__name__},
        )
        logger.error(f"Error during Airtable indexing: {e!s}", exc_info=True)
        return 0, f"Failed to index Airtable records: {e!s}"
