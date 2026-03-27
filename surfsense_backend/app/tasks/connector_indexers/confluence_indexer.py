"""Confluence connector indexer using the unified parallel indexing pipeline."""

import contextlib
from collections.abc import Awaitable, Callable

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.confluence_history import ConfluenceHistoryConnector
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
    page: dict,
    full_content: str,
    *,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    enable_summary: bool,
) -> ConnectorDocument:
    """Map a raw Confluence page dict to a ConnectorDocument."""
    page_id = page.get("id", "")
    page_title = page.get("title", "")
    space_id = page.get("spaceId", "")
    comment_count = len(page.get("comments", []))

    metadata = {
        "page_id": page_id,
        "page_title": page_title,
        "space_id": space_id,
        "comment_count": comment_count,
        "connector_id": connector_id,
        "document_type": "Confluence Page",
        "connector_type": "Confluence",
    }

    fallback_summary = (
        f"Confluence Page: {page_title}\n\nSpace ID: {space_id}\n\n{full_content}"
    )

    return ConnectorDocument(
        title=page_title,
        source_markdown=full_content,
        unique_id=page_id,
        document_type=DocumentType.CONFLUENCE_CONNECTOR,
        search_space_id=search_space_id,
        connector_id=connector_id,
        created_by_id=user_id,
        should_summarize=enable_summary,
        fallback_summary=fallback_summary,
        metadata=metadata,
    )


async def index_confluence_pages(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    update_last_indexed: bool = True,
    on_heartbeat_callback: HeartbeatCallbackType | None = None,
) -> tuple[int, int, str | None]:
    """Index Confluence pages and comments."""
    task_logger = TaskLoggingService(session, search_space_id)
    log_entry = await task_logger.log_task_start(
        task_name="confluence_pages_indexing",
        source="connector_indexing_task",
        message=f"Starting Confluence pages indexing for connector {connector_id}",
        metadata={
            "connector_id": connector_id,
            "user_id": str(user_id),
            "start_date": start_date,
            "end_date": end_date,
        },
    )

    try:
        connector = await get_connector_by_id(
            session, connector_id, SearchSourceConnectorType.CONFLUENCE_CONNECTOR
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
            f"Initializing Confluence OAuth client for connector {connector_id}",
            {"stage": "client_initialization"},
        )

        confluence_client: ConfluenceHistoryConnector | None = (
            ConfluenceHistoryConnector(
                session=session,
                connector_id=connector_id,
            )
        )

        start_date_str, end_date_str = calculate_date_range(
            connector, start_date, end_date, default_days_back=365
        )

        await task_logger.log_task_progress(
            log_entry,
            f"Fetching Confluence pages from {start_date_str} to {end_date_str}",
            {
                "stage": "fetching_pages",
                "start_date": start_date_str,
                "end_date": end_date_str,
            },
        )

        try:
            pages, error = await confluence_client.get_pages_by_date_range(
                start_date=start_date_str, end_date=end_date_str, include_comments=True
            )

            if error:
                if "No pages found" in error:
                    logger.info(f"No Confluence pages found: {error}")
                    if update_last_indexed:
                        await update_connector_last_indexed(
                            session, connector, update_last_indexed
                        )
                        await session.commit()
                        logger.info(
                            f"Updated last_indexed_at to {connector.last_indexed_at} despite no pages found"
                        )

                    await task_logger.log_task_success(
                        log_entry,
                        f"No Confluence pages found in date range {start_date_str} to {end_date_str}",
                        {"pages_found": 0},
                    )
                    if confluence_client:
                        with contextlib.suppress(Exception):
                            await confluence_client.close()
                    return 0, 0, None
                else:
                    logger.error(f"Failed to get Confluence pages: {error}")
                    await task_logger.log_task_failure(
                        log_entry,
                        f"Failed to get Confluence pages: {error}",
                        "API Error",
                        {"error_type": "APIError"},
                    )
                    if confluence_client:
                        with contextlib.suppress(Exception):
                            await confluence_client.close()
                    return 0, 0, f"Failed to get Confluence pages: {error}"

            logger.info(f"Retrieved {len(pages)} pages from Confluence API")

        except Exception as e:
            logger.error(f"Error fetching Confluence pages: {e!s}", exc_info=True)
            if confluence_client:
                with contextlib.suppress(Exception):
                    await confluence_client.close()
            return 0, 0, f"Error fetching Confluence pages: {e!s}"

        if not pages:
            logger.info("No Confluence pages found for the specified date range")
            if update_last_indexed:
                await update_connector_last_indexed(
                    session, connector, update_last_indexed
                )
                await session.commit()
            if confluence_client:
                with contextlib.suppress(Exception):
                    await confluence_client.close()
            return 0, 0, None

        documents_skipped = 0
        duplicate_content_count = 0
        connector_docs: list[ConnectorDocument] = []

        for page in pages:
            try:
                page_id = page.get("id")
                page_title = page.get("title", "")
                space_id = page.get("spaceId", "")

                if not page_id or not page_title:
                    logger.warning(
                        f"Skipping page with missing ID or title: {page_id or 'Unknown'}"
                    )
                    documents_skipped += 1
                    continue

                page_content = ""
                if page.get("body") and page["body"].get("storage"):
                    page_content = page["body"]["storage"].get("value", "")

                comments = page.get("comments", [])
                comments_content = ""
                if comments:
                    comments_content = "\n\n## Comments\n\n"
                    for comment in comments:
                        comment_body = ""
                        if comment.get("body") and comment["body"].get("storage"):
                            comment_body = comment["body"]["storage"].get("value", "")

                        comment_author = comment.get("version", {}).get(
                            "authorId", "Unknown"
                        )
                        comment_date = comment.get("version", {}).get("createdAt", "")

                        comments_content += f"**Comment by {comment_author}** ({comment_date}):\n{comment_body}\n\n"

                full_content = f"# {page_title}\n\n{page_content}{comments_content}"

                if not page_content.strip() and not comments:
                    logger.warning(f"Skipping page with no content: {page_title}")
                    documents_skipped += 1
                    continue

                doc = _build_connector_doc(
                    page,
                    full_content,
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
                        f"Confluence page {page_title} already indexed by another connector "
                        f"(existing document ID: {duplicate_by_content.id}, "
                        f"type: {duplicate_by_content.document_type}). Skipping."
                    )
                    duplicate_content_count += 1
                    documents_skipped += 1
                    continue

                connector_docs.append(doc)

            except Exception as e:
                logger.error(f"Error building ConnectorDocument for page: {e!s}", exc_info=True)
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

        logger.info(
            f"Final commit: Total {documents_indexed} Confluence pages processed"
        )
        try:
            await session.commit()
            logger.info(
                "Successfully committed all Confluence document changes to database"
            )
        except Exception as e:
            if (
                "duplicate key value violates unique constraint" in str(e).lower()
                or "uniqueviolationerror" in str(e).lower()
            ):
                logger.warning(
                    f"Duplicate content_hash detected during final commit. "
                    f"This may occur if the same page was indexed by multiple connectors. "
                    f"Rolling back and continuing. Error: {e!s}"
                )
                await session.rollback()
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
            f"Successfully completed Confluence indexing for connector {connector_id}",
            {
                "documents_indexed": documents_indexed,
                "documents_skipped": documents_skipped,
                "documents_failed": documents_failed,
                "duplicate_content_count": duplicate_content_count,
            },
        )
        logger.info(
            f"Confluence indexing completed: {documents_indexed} ready, "
            f"{documents_skipped} skipped, {documents_failed} failed "
            f"({duplicate_content_count} duplicate content)"
        )

        if confluence_client:
            await confluence_client.close()

        return documents_indexed, documents_skipped, warning_message

    except SQLAlchemyError as db_error:
        await session.rollback()
        if confluence_client:
            with contextlib.suppress(Exception):
                await confluence_client.close()
        await task_logger.log_task_failure(
            log_entry,
            f"Database error during Confluence indexing for connector {connector_id}",
            str(db_error),
            {"error_type": "SQLAlchemyError"},
        )
        logger.error(f"Database error: {db_error!s}", exc_info=True)
        return 0, 0, f"Database error: {db_error!s}"
    except Exception as e:
        await session.rollback()
        if confluence_client:
            with contextlib.suppress(Exception):
                await confluence_client.close()
        await task_logger.log_task_failure(
            log_entry,
            f"Failed to index Confluence pages for connector {connector_id}",
            str(e),
            {"error_type": type(e).__name__},
        )
        logger.error(f"Failed to index Confluence pages: {e!s}", exc_info=True)
        return 0, 0, f"Failed to index Confluence pages: {e!s}"
