"""
Jira connector indexer.

Provides real-time document status updates during indexing using a two-phase approach:
- Phase 1: Create all documents with PENDING status (visible in UI immediately)
- Phase 2: Process each document one by one (PENDING → PROCESSING → READY/FAILED)
"""

import contextlib
import time
from collections.abc import Awaitable, Callable
from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.jira_history import JiraHistoryConnector
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

# Heartbeat interval in seconds - update notification every 30 seconds
HEARTBEAT_INTERVAL_SECONDS = 30


async def index_jira_issues(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    update_last_indexed: bool = True,
    on_heartbeat_callback: HeartbeatCallbackType | None = None,
) -> tuple[int, str | None]:
    """
    Index Jira issues and comments.

    Args:
        session: Database session
        connector_id: ID of the Jira connector
        search_space_id: ID of the search space to store documents in
        user_id: User ID
        start_date: Start date for indexing (YYYY-MM-DD format)
        end_date: End date for indexing (YYYY-MM-DD format)
        update_last_indexed: Whether to update the last_indexed_at timestamp (default: True)
        on_heartbeat_callback: Optional callback to update notification during long-running indexing.

    Returns:
        Tuple containing (number of documents indexed, error message or None)
    """
    task_logger = TaskLoggingService(session, search_space_id)

    # Log task start
    log_entry = await task_logger.log_task_start(
        task_name="jira_issues_indexing",
        source="connector_indexing_task",
        message=f"Starting Jira issues indexing for connector {connector_id}",
        metadata={
            "connector_id": connector_id,
            "user_id": str(user_id),
            "start_date": start_date,
            "end_date": end_date,
        },
    )

    try:
        # Get the connector from the database
        connector = await get_connector_by_id(
            session, connector_id, SearchSourceConnectorType.JIRA_CONNECTOR
        )

        if not connector:
            await task_logger.log_task_failure(
                log_entry,
                f"Connector with ID {connector_id} not found",
                "Connector not found",
                {"error_type": "ConnectorNotFound"},
            )
            return 0, f"Connector with ID {connector_id} not found"

        # Initialize Jira client with internal refresh capability
        # Token refresh will happen automatically when needed
        await task_logger.log_task_progress(
            log_entry,
            f"Initializing Jira client for connector {connector_id}",
            {"stage": "client_initialization"},
        )

        logger.info(f"Initializing Jira client for connector {connector_id}")

        # Create connector with session and connector_id for internal refresh
        # Token refresh will happen automatically when needed
        jira_client = JiraHistoryConnector(session=session, connector_id=connector_id)

        # Calculate date range
        # Handle "undefined" strings from frontend
        if start_date == "undefined" or start_date == "":
            start_date = None
        if end_date == "undefined" or end_date == "":
            end_date = None

        start_date_str, end_date_str = calculate_date_range(
            connector, start_date, end_date, default_days_back=365
        )

        await task_logger.log_task_progress(
            log_entry,
            f"Fetching Jira issues from {start_date_str} to {end_date_str}",
            {
                "stage": "fetching_issues",
                "start_date": start_date_str,
                "end_date": end_date_str,
            },
        )

        # Get issues within date range
        try:
            issues, error = await jira_client.get_issues_by_date_range(
                start_date=start_date_str, end_date=end_date_str, include_comments=True
            )

            if error:
                # Don't treat "No issues found" as an error that should stop indexing
                if "No issues found" in error:
                    logger.info(f"No Jira issues found: {error}")
                    logger.info(
                        "No issues found is not a critical error, continuing with update"
                    )
                    if update_last_indexed:
                        await update_connector_last_indexed(
                            session, connector, update_last_indexed
                        )
                        await session.commit()
                        logger.info(
                            f"Updated last_indexed_at to {connector.last_indexed_at} despite no issues found"
                        )

                    await task_logger.log_task_success(
                        log_entry,
                        f"No Jira issues found in date range {start_date_str} to {end_date_str}",
                        {"issues_found": 0},
                    )
                    return 0, None
                else:
                    logger.error(f"Failed to get Jira issues: {error}")
                    await task_logger.log_task_failure(
                        log_entry,
                        f"Failed to get Jira issues: {error}",
                        "API Error",
                        {"error_type": "APIError"},
                    )
                    return 0, f"Failed to get Jira issues: {error}"

            logger.info(f"Retrieved {len(issues)} issues from Jira API")

        except Exception as e:
            logger.error(f"Error fetching Jira issues: {e!s}", exc_info=True)
            return 0, f"Error fetching Jira issues: {e!s}"

        # =======================================================================
        # PHASE 1: Analyze all issues, create pending documents
        # This makes ALL documents visible in the UI immediately with pending status
        # =======================================================================
        documents_indexed = 0
        documents_skipped = 0
        documents_failed = 0
        duplicate_content_count = 0

        # Heartbeat tracking - update notification periodically to prevent appearing stuck
        last_heartbeat_time = time.time()

        issues_to_process = []  # List of dicts with document and issue data
        new_documents_created = False

        for issue in issues:
            try:
                issue_id = issue.get("key")
                issue_identifier = issue.get("key", "")
                issue_title = issue.get("id", "")

                if not issue_id or not issue_title:
                    logger.warning(
                        f"Skipping issue with missing ID or title: {issue_id or 'Unknown'}"
                    )
                    documents_skipped += 1
                    continue

                # Format the issue for better readability
                formatted_issue = jira_client.format_issue(issue)

                # Convert to markdown
                issue_content = jira_client.format_issue_to_markdown(formatted_issue)

                if not issue_content:
                    logger.warning(
                        f"Skipping issue with no content: {issue_identifier} - {issue_title}"
                    )
                    documents_skipped += 1
                    continue

                # Generate unique identifier hash for this Jira issue
                unique_identifier_hash = generate_unique_identifier_hash(
                    DocumentType.JIRA_CONNECTOR, issue_id, search_space_id
                )

                # Generate content hash
                content_hash = generate_content_hash(issue_content, search_space_id)

                # Check if document with this unique identifier already exists
                existing_document = await check_document_by_unique_identifier(
                    session, unique_identifier_hash
                )

                comment_count = len(formatted_issue.get("comments", []))

                if existing_document:
                    # Document exists - check if content has changed
                    if existing_document.content_hash == content_hash:
                        # Ensure status is ready (might have been stuck in processing/pending)
                        if not DocumentStatus.is_state(
                            existing_document.status, DocumentStatus.READY
                        ):
                            existing_document.status = DocumentStatus.ready()
                        documents_skipped += 1
                        continue

                    # Queue existing document for update (will be set to processing in Phase 2)
                    issues_to_process.append(
                        {
                            "document": existing_document,
                            "is_new": False,
                            "issue_content": issue_content,
                            "content_hash": content_hash,
                            "issue_id": issue_id,
                            "issue_identifier": issue_identifier,
                            "issue_title": issue_title,
                            "formatted_issue": formatted_issue,
                            "comment_count": comment_count,
                        }
                    )
                    continue

                # Document doesn't exist by unique_identifier_hash
                # Check if a document with the same content_hash exists (from another connector)
                with session.no_autoflush:
                    duplicate_by_content = await check_duplicate_document_by_hash(
                        session, content_hash
                    )

                if duplicate_by_content:
                    logger.info(
                        f"Jira issue {issue_identifier} already indexed by another connector "
                        f"(existing document ID: {duplicate_by_content.id}, "
                        f"type: {duplicate_by_content.document_type}). Skipping."
                    )
                    duplicate_content_count += 1
                    documents_skipped += 1
                    continue

                # Create new document with PENDING status (visible in UI immediately)
                document = Document(
                    search_space_id=search_space_id,
                    title=f"{issue_identifier}: {issue_title}",
                    document_type=DocumentType.JIRA_CONNECTOR,
                    document_metadata={
                        "issue_id": issue_id,
                        "issue_identifier": issue_identifier,
                        "issue_title": issue_title,
                        "state": formatted_issue.get("status", "Unknown"),
                        "comment_count": comment_count,
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

                issues_to_process.append(
                    {
                        "document": document,
                        "is_new": True,
                        "issue_content": issue_content,
                        "content_hash": content_hash,
                        "issue_id": issue_id,
                        "issue_identifier": issue_identifier,
                        "issue_title": issue_title,
                        "formatted_issue": formatted_issue,
                        "comment_count": comment_count,
                    }
                )

            except Exception as e:
                logger.error(f"Error in Phase 1 for issue: {e!s}", exc_info=True)
                documents_failed += 1
                continue

        # Commit all pending documents - they all appear in UI now
        if new_documents_created:
            logger.info(
                f"Phase 1: Committing {len([i for i in issues_to_process if i['is_new']])} pending documents"
            )
            await session.commit()

        # =======================================================================
        # PHASE 2: Process each document one by one
        # Each document transitions: pending → processing → ready/failed
        # =======================================================================
        logger.info(f"Phase 2: Processing {len(issues_to_process)} documents")

        for item in issues_to_process:
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
                    document_metadata = {
                        "issue_key": item["issue_identifier"],
                        "issue_title": item["issue_title"],
                        "status": item["formatted_issue"].get("status", "Unknown"),
                        "priority": item["formatted_issue"].get("priority", "Unknown"),
                        "comment_count": item["comment_count"],
                        "document_type": "Jira Issue",
                        "connector_type": "Jira",
                    }
                    (
                        summary_content,
                        summary_embedding,
                    ) = await generate_document_summary(
                        item["issue_content"], user_llm, document_metadata
                    )
                else:
                    summary_content = f"Jira Issue {item['issue_identifier']}: {item['issue_title']}\n\n{item['issue_content']}"
                    summary_embedding = embed_text(summary_content)

                # Process chunks - using the full issue content with comments
                chunks = await create_document_chunks(item["issue_content"])

                # Update document to READY with actual content
                document.title = f"{item['issue_identifier']}: {item['issue_title']}"
                document.content = summary_content
                document.content_hash = item["content_hash"]
                document.embedding = summary_embedding
                document.document_metadata = {
                    "issue_id": item["issue_id"],
                    "issue_identifier": item["issue_identifier"],
                    "issue_title": item["issue_title"],
                    "state": item["formatted_issue"].get("status", "Unknown"),
                    "comment_count": item["comment_count"],
                    "indexed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "connector_id": connector_id,
                }
                safe_set_chunks(document, chunks)
                document.updated_at = get_current_timestamp()
                document.status = DocumentStatus.ready()

                documents_indexed += 1

                # Batch commit every 10 documents (for ready status updates)
                if documents_indexed % 10 == 0:
                    logger.info(
                        f"Committing batch: {documents_indexed} Jira issues processed so far"
                    )
                    await session.commit()

            except Exception as e:
                logger.error(
                    f"Error processing issue {item.get('issue_identifier', 'Unknown')}: {e!s}",
                    exc_info=True,
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
                continue  # Skip this issue and continue with others

        # CRITICAL: Always update timestamp (even if 0 documents indexed) so Electric SQL syncs
        # This ensures the UI shows "Last indexed" instead of "Never indexed"
        await update_connector_last_indexed(session, connector, update_last_indexed)

        # Final commit to ensure all documents are persisted (safety net)
        logger.info(f"Final commit: Total {documents_indexed} Jira issues processed")
        try:
            await session.commit()
            logger.info("Successfully committed all JIRA document changes to database")
        except Exception as e:
            # Handle any remaining integrity errors gracefully (race conditions, etc.)
            if (
                "duplicate key value violates unique constraint" in str(e).lower()
                or "uniqueviolationerror" in str(e).lower()
            ):
                logger.warning(
                    f"Duplicate content_hash detected during final commit. "
                    f"This may occur if the same issue was indexed by multiple connectors. "
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

        # Log success
        await task_logger.log_task_success(
            log_entry,
            f"Successfully completed JIRA indexing for connector {connector_id}",
            {
                "documents_indexed": documents_indexed,
                "documents_skipped": documents_skipped,
                "documents_failed": documents_failed,
                "duplicate_content_count": duplicate_content_count,
            },
        )

        logger.info(
            f"JIRA indexing completed: {documents_indexed} ready, "
            f"{documents_skipped} skipped, {documents_failed} failed "
            f"({duplicate_content_count} duplicate content)"
        )

        # Clean up the connector
        await jira_client.close()

        return documents_indexed, warning_message

    except SQLAlchemyError as db_error:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Database error during JIRA indexing for connector {connector_id}",
            str(db_error),
            {"error_type": "SQLAlchemyError"},
        )
        logger.error(f"Database error: {db_error!s}", exc_info=True)
        # Clean up the connector in case of error
        if "jira_client" in locals():
            with contextlib.suppress(Exception):
                await jira_client.close()
        return 0, f"Database error: {db_error!s}"
    except Exception as e:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Failed to index JIRA issues for connector {connector_id}",
            str(e),
            {"error_type": type(e).__name__},
        )
        logger.error(f"Failed to index JIRA issues: {e!s}", exc_info=True)
        # Clean up the connector in case of error
        if "jira_client" in locals():
            with contextlib.suppress(Exception):
                await jira_client.close()
        return 0, f"Failed to index JIRA issues: {e!s}"
