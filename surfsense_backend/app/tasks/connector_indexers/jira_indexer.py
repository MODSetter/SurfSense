"""Jira connector indexer using the unified parallel indexing pipeline."""

import contextlib
from collections.abc import Awaitable, Callable

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.jira_history import JiraHistoryConnector
from app.db import DocumentType, SearchSourceConnectorType
from app.indexing_pipeline.connector_document import ConnectorDocument
from app.indexing_pipeline.document_hashing import compute_content_hash
from app.indexing_pipeline.indexing_pipeline_service import IndexingPipelineService
from app.services.llm_service import get_user_long_context_llm
from app.services.task_logging_service import TaskLoggingService

from .base import (
    calculate_date_range,
    check_duplicate_document_by_hash,
    get_connector_by_id,
    logger,
    update_connector_last_indexed,
)

HeartbeatCallbackType = Callable[[int], Awaitable[None]]
HEARTBEAT_INTERVAL_SECONDS = 30


def _build_connector_doc(
    issue: dict,
    formatted_issue: dict,
    issue_content: str,
    *,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    enable_summary: bool,
) -> ConnectorDocument:
    """Map a raw Jira issue dict to a ConnectorDocument."""
    issue_id = issue.get("key", "")
    issue_identifier = issue.get("key", "")
    issue_title = issue.get("id", "")
    state = formatted_issue.get("status", "Unknown")
    priority = formatted_issue.get("priority", "Unknown")
    comment_count = len(formatted_issue.get("comments", []))

    metadata = {
        "issue_id": issue_id,
        "issue_identifier": issue_identifier,
        "issue_title": issue_title,
        "state": state,
        "priority": priority,
        "comment_count": comment_count,
        "connector_id": connector_id,
        "document_type": "Jira Issue",
        "connector_type": "Jira",
    }

    fallback_summary = (
        f"Jira Issue {issue_identifier}: {issue_title}\n\n"
        f"Status: {state}\n\n{issue_content}"
    )

    return ConnectorDocument(
        title=f"{issue_identifier}: {issue_title}",
        source_markdown=issue_content,
        unique_id=issue_id,
        document_type=DocumentType.JIRA_CONNECTOR,
        search_space_id=search_space_id,
        connector_id=connector_id,
        created_by_id=user_id,
        should_summarize=enable_summary,
        fallback_summary=fallback_summary,
        metadata=metadata,
    )


async def index_jira_issues(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    update_last_indexed: bool = True,
    on_heartbeat_callback: HeartbeatCallbackType | None = None,
) -> tuple[int, int, str | None]:
    """Index Jira issues and comments."""
    task_logger = TaskLoggingService(session, search_space_id)
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
            return 0, 0, f"Connector with ID {connector_id} not found"

        await task_logger.log_task_progress(
            log_entry,
            f"Initializing Jira client for connector {connector_id}",
            {"stage": "client_initialization"},
        )
        jira_client = JiraHistoryConnector(session=session, connector_id=connector_id)

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

        try:
            issues, error = await jira_client.get_issues_by_date_range(
                start_date=start_date_str, end_date=end_date_str, include_comments=True
            )

            if error:
                if "No issues found" in error:
                    logger.info(f"No Jira issues found: {error}")
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
                    await jira_client.close()
                    return 0, 0, None
                else:
                    logger.error(f"Failed to get Jira issues: {error}")
                    await task_logger.log_task_failure(
                        log_entry,
                        f"Failed to get Jira issues: {error}",
                        "API Error",
                        {"error_type": "APIError"},
                    )
                    await jira_client.close()
                    return 0, 0, f"Failed to get Jira issues: {error}"

            logger.info(f"Retrieved {len(issues)} issues from Jira API")

        except Exception as e:
            logger.error(f"Error fetching Jira issues: {e!s}", exc_info=True)
            await jira_client.close()
            return 0, 0, f"Error fetching Jira issues: {e!s}"

        if not issues:
            logger.info("No Jira issues found for the specified date range")
            if update_last_indexed:
                await update_connector_last_indexed(
                    session, connector, update_last_indexed
                )
                await session.commit()
            await jira_client.close()
            return 0, 0, None

        connector_docs: list[ConnectorDocument] = []
        documents_skipped = 0
        duplicate_content_count = 0

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

                formatted_issue = jira_client.format_issue(issue)
                issue_content = jira_client.format_issue_to_markdown(formatted_issue)

                if not issue_content:
                    logger.warning(
                        f"Skipping issue with no content: {issue_identifier} - {issue_title}"
                    )
                    documents_skipped += 1
                    continue

                doc = _build_connector_doc(
                    issue,
                    formatted_issue,
                    issue_content,
                    connector_id=connector_id,
                    search_space_id=search_space_id,
                    user_id=user_id,
                    enable_summary=connector.enable_summary,
                )

                with session.no_autoflush:
                    duplicate_by_content = await check_duplicate_document_by_hash(
                        session, compute_content_hash(doc)
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

                connector_docs.append(doc)

            except Exception as e:
                logger.error(
                    f"Error building ConnectorDocument for issue {issue_identifier}: {e!s}",
                    exc_info=True,
                )
                documents_skipped += 1
                continue

        pipeline = IndexingPipelineService(session)
        await pipeline.migrate_legacy_docs(connector_docs)

        async def _get_llm(s: AsyncSession):
            return await get_user_long_context_llm(s, user_id, search_space_id)

        _, documents_indexed, documents_failed = await pipeline.index_batch_parallel(
            connector_docs,
            _get_llm,
            max_concurrency=3,
            on_heartbeat=on_heartbeat_callback,
            heartbeat_interval=HEARTBEAT_INTERVAL_SECONDS,
        )

        await update_connector_last_indexed(session, connector, update_last_indexed)

        logger.info(f"Final commit: Total {documents_indexed} Jira issues processed")
        try:
            await session.commit()
            logger.info("Successfully committed all JIRA document changes to database")
        except Exception as e:
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

        warning_parts = []
        if duplicate_content_count > 0:
            warning_parts.append(f"{duplicate_content_count} duplicate")
        if documents_failed > 0:
            warning_parts.append(f"{documents_failed} failed")
        warning_message = ", ".join(warning_parts) if warning_parts else None

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
        await jira_client.close()
        return documents_indexed, documents_skipped, warning_message

    except SQLAlchemyError as db_error:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Database error during JIRA indexing for connector {connector_id}",
            str(db_error),
            {"error_type": "SQLAlchemyError"},
        )
        logger.error(f"Database error: {db_error!s}", exc_info=True)
        if "jira_client" in locals():
            with contextlib.suppress(Exception):
                await jira_client.close()
        return 0, 0, f"Database error: {db_error!s}"
    except Exception as e:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Failed to index JIRA issues for connector {connector_id}",
            str(e),
            {"error_type": type(e).__name__},
        )
        logger.error(f"Failed to index JIRA issues: {e!s}", exc_info=True)
        if "jira_client" in locals():
            with contextlib.suppress(Exception):
                await jira_client.close()
        return 0, 0, f"Failed to index JIRA issues: {e!s}"
