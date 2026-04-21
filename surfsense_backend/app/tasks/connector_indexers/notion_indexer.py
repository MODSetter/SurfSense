"""
Notion connector indexer.

Uses the shared IndexingPipelineService for document deduplication,
summarization, chunking, and embedding with bounded parallel indexing.
"""

from collections.abc import Awaitable, Callable
from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.notion_history import NotionHistoryConnector
from app.db import DocumentType, SearchSourceConnectorType
from app.indexing_pipeline.connector_document import ConnectorDocument
from app.indexing_pipeline.document_hashing import compute_content_hash
from app.indexing_pipeline.indexing_pipeline_service import (
    IndexingPipelineService,
    PlaceholderInfo,
)
from app.services.llm_service import get_user_long_context_llm
from app.services.task_logging_service import TaskLoggingService
from app.utils.notion_utils import process_blocks

from .base import (
    calculate_date_range,
    check_duplicate_document_by_hash,
    get_connector_by_id,
    logger,
    update_connector_last_indexed,
)

RetryCallbackType = Callable[[str, int, int, float], Awaitable[None]]
HeartbeatCallbackType = Callable[[int], Awaitable[None]]
HEARTBEAT_INTERVAL_SECONDS = 30


def _build_connector_doc(
    page: dict,
    markdown_content: str,
    *,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    enable_summary: bool,
) -> ConnectorDocument:
    """Map a raw Notion page dict to a ConnectorDocument."""
    page_id = page.get("page_id", "")
    page_title = page.get("title", f"Untitled page ({page_id})")

    metadata = {
        "page_title": page_title,
        "page_id": page_id,
        "connector_id": connector_id,
        "document_type": "Notion Page",
        "connector_type": "Notion",
    }

    fallback_summary = f"Notion Page: {page_title}\n\n{markdown_content}"

    return ConnectorDocument(
        title=page_title,
        source_markdown=markdown_content,
        unique_id=page_id,
        document_type=DocumentType.NOTION_CONNECTOR,
        search_space_id=search_space_id,
        connector_id=connector_id,
        created_by_id=user_id,
        should_summarize=enable_summary,
        fallback_summary=fallback_summary,
        metadata=metadata,
    )


async def index_notion_pages(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    update_last_indexed: bool = True,
    on_retry_callback: RetryCallbackType | None = None,
    on_heartbeat_callback: HeartbeatCallbackType | None = None,
) -> tuple[int, int, str | None]:
    """
    Index Notion pages from all accessible pages.

    Returns:
        Tuple of (indexed_count, skipped_count, warning_or_error_message)
    """
    task_logger = TaskLoggingService(session, search_space_id)

    log_entry = await task_logger.log_task_start(
        task_name="notion_pages_indexing",
        source="connector_indexing_task",
        message=f"Starting Notion pages indexing for connector {connector_id}",
        metadata={
            "connector_id": connector_id,
            "user_id": str(user_id),
            "start_date": start_date,
            "end_date": end_date,
        },
    )

    try:
        # ── Connector lookup ──────────────────────────────────────────
        await task_logger.log_task_progress(
            log_entry,
            f"Retrieving Notion connector {connector_id} from database",
            {"stage": "connector_retrieval"},
        )

        connector = await get_connector_by_id(
            session, connector_id, SearchSourceConnectorType.NOTION_CONNECTOR
        )

        if not connector:
            await task_logger.log_task_failure(
                log_entry,
                f"Connector with ID {connector_id} not found or is not a Notion connector",
                "Connector not found",
                {"error_type": "ConnectorNotFound"},
            )
            return (
                0,
                0,
                f"Connector with ID {connector_id} not found or is not a Notion connector",
            )

        if not connector.config.get("access_token") and not connector.config.get(
            "NOTION_INTEGRATION_TOKEN"
        ):
            await task_logger.log_task_failure(
                log_entry,
                f"Notion access token not found in connector config for connector {connector_id}",
                "Missing Notion access token",
                {"error_type": "MissingToken"},
            )
            return 0, 0, "Notion access token not found in connector config"

        # ── Client init ───────────────────────────────────────────────
        await task_logger.log_task_progress(
            log_entry,
            f"Initializing Notion client for connector {connector_id}",
            {"stage": "client_initialization"},
        )

        logger.info(f"Initializing Notion client for connector {connector_id}")

        if start_date == "undefined" or start_date == "":
            start_date = None
        if end_date == "undefined" or end_date == "":
            end_date = None

        start_date_str, end_date_str = calculate_date_range(
            connector, start_date, end_date, default_days_back=365
        )

        start_date_iso = datetime.strptime(start_date_str, "%Y-%m-%d").strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        end_date_iso = datetime.strptime(end_date_str, "%Y-%m-%d").strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

        notion_client = NotionHistoryConnector(
            session=session, connector_id=connector_id
        )

        if on_retry_callback:
            notion_client.set_retry_callback(on_retry_callback)

        logger.info(f"Fetching Notion pages from {start_date_iso} to {end_date_iso}")

        await task_logger.log_task_progress(
            log_entry,
            f"Fetching Notion pages from {start_date_iso} to {end_date_iso}",
            {
                "stage": "fetch_pages",
                "start_date": start_date_iso,
                "end_date": end_date_iso,
            },
        )

        # ── Fetch pages ───────────────────────────────────────────────
        try:
            pages = await notion_client.get_all_pages(
                start_date=start_date_iso, end_date=end_date_iso
            )
            logger.info(f"Found {len(pages)} Notion pages")

            pages_with_skipped_content = notion_client.get_skipped_content_count()
            if pages_with_skipped_content > 0:
                logger.info(
                    f"{pages_with_skipped_content} pages had Notion AI content skipped (not available via API)"
                )

            if notion_client.is_using_legacy_token():
                logger.warning(
                    f"Connector {connector_id} is using legacy integration token. "
                    "Recommend reconnecting with OAuth."
                )
        except Exception as e:
            error_str = str(e)
            unsupported_block_errors = [
                "transcription is not supported",
                "ai_block is not supported",
                "is not supported via the API",
            ]
            is_unsupported_block_error = any(
                err in error_str.lower() for err in unsupported_block_errors
            )

            if is_unsupported_block_error:
                logger.warning(
                    f"Notion API limitation for connector {connector_id}: {error_str}. "
                    "This is a known issue with Notion AI blocks (transcription, ai_block) "
                    "that are not accessible via the Notion API."
                )
                await task_logger.log_task_failure(
                    log_entry,
                    "Failed to get Notion pages: Notion API limitation",
                    f"{error_str} - This page contains Notion AI content (transcription/ai_block) that cannot be accessed via the API.",
                    {"error_type": "UnsupportedBlockType", "is_known_limitation": True},
                )
            else:
                logger.error(
                    f"Error fetching Notion pages for connector {connector_id}: {error_str}",
                    exc_info=True,
                )
                await task_logger.log_task_failure(
                    log_entry,
                    f"Failed to get Notion pages for connector {connector_id}",
                    str(e),
                    {"error_type": "PageFetchError"},
                )

            await notion_client.close()
            return 0, 0, f"Failed to get Notion pages: {e!s}"

        if not pages:
            await task_logger.log_task_success(
                log_entry,
                f"No Notion pages found for connector {connector_id}. "
                "Ensure pages are shared with the Notion integration.",
                {"pages_found": 0},
            )
            logger.info("No Notion pages found to index")
            await update_connector_last_indexed(session, connector, update_last_indexed)
            await session.commit()
            await notion_client.close()
            return 0, 0, None

        # ── Create placeholders for instant UI feedback ───────────────
        pipeline = IndexingPipelineService(session)
        placeholders = [
            PlaceholderInfo(
                title=page.get("title", f"Untitled page ({page.get('page_id', '')})"),
                document_type=DocumentType.NOTION_CONNECTOR,
                unique_id=page.get("page_id", ""),
                search_space_id=search_space_id,
                connector_id=connector_id,
                created_by_id=user_id,
                metadata={
                    "page_id": page.get("page_id", ""),
                    "connector_id": connector_id,
                    "connector_type": "Notion",
                },
            )
            for page in pages
            if page.get("page_id")
        ]
        await pipeline.create_placeholder_documents(placeholders)

        # ── Build ConnectorDocuments ──────────────────────────────────
        connector_docs: list[ConnectorDocument] = []
        documents_skipped = 0
        duplicate_content_count = 0

        await task_logger.log_task_progress(
            log_entry,
            f"Starting to process {len(pages)} Notion pages",
            {"stage": "process_pages", "total_pages": len(pages)},
        )

        for page in pages:
            try:
                page_id = page.get("page_id")
                page_title = page.get("title", f"Untitled page ({page_id})")
                page_content = page.get("content", [])

                if not page_id:
                    documents_skipped += 1
                    continue

                if not page_content:
                    logger.info(f"No content found in page {page_title}. Skipping.")
                    documents_skipped += 1
                    continue

                markdown_content = f"# Notion Page: {page_title}\n\n"
                markdown_content += process_blocks(page_content)

                if not markdown_content.strip():
                    logger.warning(f"Skipping page with empty markdown: {page_title}")
                    documents_skipped += 1
                    continue

                doc = _build_connector_doc(
                    page,
                    markdown_content,
                    connector_id=connector_id,
                    search_space_id=search_space_id,
                    user_id=user_id,
                    enable_summary=connector.enable_summary,
                )

                with session.no_autoflush:
                    duplicate = await check_duplicate_document_by_hash(
                        session, compute_content_hash(doc)
                    )
                if duplicate:
                    logger.info(
                        f"Notion page {doc.title} already indexed by another connector "
                        f"(existing document ID: {duplicate.id}, "
                        f"type: {duplicate.document_type}). Skipping."
                    )
                    duplicate_content_count += 1
                    documents_skipped += 1
                    continue

                connector_docs.append(doc)

            except Exception as e:
                logger.error(
                    f"Error building ConnectorDocument for page: {e!s}",
                    exc_info=True,
                )
                documents_skipped += 1
                continue

        # ── Pipeline: migrate legacy docs + parallel index ────────────
        await pipeline.migrate_legacy_docs(connector_docs)

        async def _get_llm(s):
            return await get_user_long_context_llm(s, user_id, search_space_id)

        _, documents_indexed, documents_failed = await pipeline.index_batch_parallel(
            connector_docs,
            _get_llm,
            max_concurrency=3,
            on_heartbeat=on_heartbeat_callback,
            heartbeat_interval=HEARTBEAT_INTERVAL_SECONDS,
        )

        # ── Finalize ──────────────────────────────────────────────────
        await update_connector_last_indexed(session, connector, update_last_indexed)

        logger.info(f"Final commit: Total {documents_indexed} documents processed")
        try:
            await session.commit()
            logger.info(
                "Successfully committed all Notion document changes to database"
            )
        except Exception as e:
            if (
                "duplicate key value violates unique constraint" in str(e).lower()
                or "uniqueviolationerror" in str(e).lower()
            ):
                logger.warning(
                    f"Duplicate content_hash detected during final commit. "
                    f"Rolling back and continuing. Error: {e!s}"
                )
                await session.rollback()
            else:
                raise

        # ── Build warning / notification message ──────────────────────
        pages_with_skipped_ai_content = notion_client.get_skipped_content_count()

        warning_parts: list[str] = []
        if duplicate_content_count > 0:
            warning_parts.append(f"{duplicate_content_count} duplicate")
        if documents_failed > 0:
            warning_parts.append(f"{documents_failed} failed")

        notification_parts: list[str] = []
        if pages_with_skipped_ai_content > 0:
            notification_parts.append(
                "Some Notion AI content couldn't be synced (API limitation)"
            )
        if notion_client.is_using_legacy_token():
            notification_parts.append(
                "Using legacy token. Reconnect with OAuth for better reliability."
            )
        if warning_parts:
            notification_parts.append(", ".join(warning_parts))

        user_notification_message = (
            " ".join(notification_parts) if notification_parts else None
        )

        await task_logger.log_task_success(
            log_entry,
            f"Successfully completed Notion indexing for connector {connector_id}",
            {
                "pages_processed": documents_indexed,
                "documents_indexed": documents_indexed,
                "documents_skipped": documents_skipped,
                "documents_failed": documents_failed,
                "duplicate_content_count": duplicate_content_count,
                "pages_with_skipped_ai_content": pages_with_skipped_ai_content,
            },
        )

        logger.info(
            f"Notion indexing completed: {documents_indexed} ready, "
            f"{documents_skipped} skipped, {documents_failed} failed "
            f"({duplicate_content_count} duplicate content)"
        )

        await notion_client.close()

        return documents_indexed, documents_skipped, user_notification_message

    except SQLAlchemyError as db_error:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Database error during Notion indexing for connector {connector_id}",
            str(db_error),
            {"error_type": "SQLAlchemyError"},
        )
        logger.error(
            f"Database error during Notion indexing: {db_error!s}", exc_info=True
        )
        if "notion_client" in locals():
            await notion_client.close()
        return 0, 0, f"Database error: {db_error!s}"
    except Exception as e:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Failed to index Notion pages for connector {connector_id}",
            str(e),
            {"error_type": type(e).__name__},
        )
        logger.error(f"Failed to index Notion pages: {e!s}", exc_info=True)
        if "notion_client" in locals():
            await notion_client.close()
        return 0, 0, f"Failed to index Notion pages: {e!s}"
