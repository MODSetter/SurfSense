"""
Webcrawler connector indexer.

Implements 2-phase document status updates for real-time UI feedback:
- Phase 1: Create all documents with 'pending' status (visible in UI immediately)
- Phase 2: Process each document: pending → processing → ready/failed
"""

import time
from collections.abc import Awaitable, Callable
from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import Document, DocumentStatus, DocumentType, SearchSourceConnectorType
from app.proprietary.web_crawler import (
    CrawlOutcomeStatus,
    WebCrawlerConnector,
)
from app.services.etl_credit_service import InsufficientCreditsError
from app.services.task_logging_service import TaskLoggingService
from app.services.token_tracking_service import record_token_usage
from app.services.web_crawl_credit_service import WebCrawlCreditService
from app.utils.captcha import captcha_enabled
from app.utils.document_converters import (
    create_document_chunks,
    embed_text,
    generate_content_hash,
    generate_unique_identifier_hash,
)
from app.utils.webcrawler_utils import parse_webcrawler_urls

from .base import (
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


async def _resolve_workspace_owner(session: AsyncSession, workspace_id: int):
    """Return the ``user_id`` that owns ``workspace_id`` (the crawl payer).

    Phase 3c bills the **workspace owner**, not the triggering user (which for
    periodic/scheduled runs may differ). Returns ``None`` if the workspace is
    gone, letting the caller fall back to the triggering user.
    """
    from sqlalchemy import select

    from app.db import Workspace

    result = await session.execute(
        select(Workspace.user_id).where(Workspace.id == workspace_id)
    )
    return result.scalar_one_or_none()


async def index_crawled_urls(
    session: AsyncSession,
    connector_id: int,
    workspace_id: int,
    user_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    update_last_indexed: bool = True,
    on_heartbeat_callback: HeartbeatCallbackType | None = None,
) -> tuple[int, str | None]:
    """
    Index web page URLs with real-time document status updates.

    Implements 2-phase approach for real-time UI feedback:
    - Phase 1: Create all documents with 'pending' status (visible in UI immediately)
    - Phase 2: Process each document: pending → processing → ready/failed

    Args:
        session: Database session
        connector_id: ID of the webcrawler connector
        workspace_id: ID of the workspace to store documents in
        user_id: User ID
        start_date: Start date for filtering (YYYY-MM-DD format) - optional
        end_date: End date for filtering (YYYY-MM-DD format) - optional
        update_last_indexed: Whether to update the last_indexed_at timestamp (default: True)
        on_heartbeat_callback: Optional callback to update notification during long-running indexing.

    Returns:
        Tuple containing (number of documents indexed, error message or None)
    """
    task_logger = TaskLoggingService(session, workspace_id)

    # Log task start
    log_entry = await task_logger.log_task_start(
        task_name="crawled_url_indexing",
        source="connector_indexing_task",
        message=f"Starting web page URL indexing for connector {connector_id}",
        metadata={
            "connector_id": connector_id,
            "user_id": str(user_id),
            "start_date": start_date,
            "end_date": end_date,
        },
    )

    try:
        # Get the connector
        await task_logger.log_task_progress(
            log_entry,
            f"Retrieving webcrawler connector {connector_id} from database",
            {"stage": "connector_retrieval"},
        )

        # Get the connector from the database
        connector = await get_connector_by_id(
            session, connector_id, SearchSourceConnectorType.WEBCRAWLER_CONNECTOR
        )

        if not connector:
            await task_logger.log_task_failure(
                log_entry,
                f"Connector with ID {connector_id} not found or is not a webcrawler connector",
                "Connector not found",
                {"error_type": "ConnectorNotFound"},
            )
            return (
                0,
                f"Connector with ID {connector_id} not found or is not a webcrawler connector",
            )

        # Get URLs from connector config
        raw_initial_urls = connector.config.get("INITIAL_URLS")
        urls = parse_webcrawler_urls(raw_initial_urls)

        # DEBUG: Log connector config details for troubleshooting empty URL issues
        logger.info(
            f"Starting crawled web page indexing for connector {connector_id} with {len(urls)} URLs. "
            f"Connector name: {connector.name}, "
            f"INITIAL_URLS type: {type(raw_initial_urls).__name__}, "
            f"INITIAL_URLS value: {repr(raw_initial_urls)[:200] if raw_initial_urls else 'None'}"
        )

        # Initialize webcrawler client
        await task_logger.log_task_progress(
            log_entry,
            f"Initializing webcrawler client for connector {connector_id}",
            {
                "stage": "client_initialization",
            },
        )

        crawler = WebCrawlerConnector()

        # Validate URLs
        if not urls:
            # DEBUG: Log detailed connector config for troubleshooting
            logger.error(
                f"No URLs provided for indexing. Connector ID: {connector_id}, "
                f"Connector name: {connector.name}, "
                f"Config keys: {list(connector.config.keys()) if connector.config else 'None'}, "
                f"INITIAL_URLS raw value: {raw_initial_urls!r}"
            )
            await task_logger.log_task_failure(
                log_entry,
                "No URLs provided for indexing",
                f"Empty URL list. INITIAL_URLS value: {repr(raw_initial_urls)[:100]}",
                {"error_type": "ValidationError", "connector_name": connector.name},
            )
            return 0, "No URLs provided for indexing"

        # =======================================================================
        # Phase 3c/3d: crawl-credit pre-flight. Bill the workspace OWNER. The
        # estimate is a safe UPPER BOUND so the wallet can't strand mid-batch:
        #   crawl   = len(urls) successes        (3c; actual successes are <=)
        #   captcha = len(urls) * MAX_ATTEMPTS   (3d; per-attempt, worst case)
        # No-op (and no owner lookup) when both billers are disabled.
        # =======================================================================
        credit_service = WebCrawlCreditService(session)
        owner_user_id = user_id
        if credit_service.billing_enabled() or credit_service.captcha_billing_enabled():
            owner_user_id = (
                await _resolve_workspace_owner(session, workspace_id) or user_id
            )
            required_micros = 0
            if credit_service.billing_enabled():
                required_micros += credit_service.successes_to_micros(len(urls))
            # Only reserve captcha budget when solving is actually enabled;
            # with solving off, attempts can never happen, so reserving would
            # wrongly block runs for captcha that will never be attempted.
            if credit_service.captcha_billing_enabled() and captcha_enabled():
                worst_case_attempts = len(urls) * config.CAPTCHA_MAX_ATTEMPTS_PER_URL
                required_micros += credit_service.captcha_solves_to_micros(
                    worst_case_attempts
                )
            try:
                await credit_service.check_balance(owner_user_id, required_micros)
            except InsufficientCreditsError as credit_error:
                await task_logger.log_task_failure(
                    log_entry,
                    f"Insufficient crawl credit for connector {connector_id}",
                    str(credit_error),
                    {"error_type": "InsufficientCreditsError"},
                )
                logger.warning(
                    f"Skipping crawl for connector {connector_id}: {credit_error!s}"
                )
                return 0, f"Insufficient crawl credit: {credit_error!s}"

        await task_logger.log_task_progress(
            log_entry,
            f"Starting to process {len(urls)} URLs",
            {
                "stage": "processing",
                "total_urls": len(urls),
            },
        )

        documents_indexed = 0
        documents_updated = 0
        documents_skipped = 0
        documents_failed = 0
        duplicate_content_count = 0
        # Explicit "crawl succeeded" count: one per URL that yielded usable
        # extracted content, independent of downstream KB dedupe/unchanged
        # bucketing. This is the billable unit Phase 3c meters on.
        crawls_succeeded = 0
        # Phase 3d: per-attempt captcha telemetry summed across the batch. Only
        # accumulated when captcha billing is on (avoids touching the outcome
        # field otherwise — and keeps MagicMock outcomes in tests arithmetic-safe).
        total_captcha_attempts = 0
        total_captcha_solved = 0

        # Heartbeat tracking - update notification periodically to prevent appearing stuck
        last_heartbeat_time = time.time()

        # =======================================================================
        # PHASE 1: Analyze all URLs, create pending documents for new ones
        # This makes ALL new documents visible in the UI immediately with pending status
        # =======================================================================
        urls_to_process = []  # List of dicts with document and URL data
        new_documents_created = False

        for url in urls:
            try:
                # Generate unique identifier hash for this URL
                unique_identifier_hash = generate_unique_identifier_hash(
                    DocumentType.CRAWLED_URL, url, workspace_id
                )

                # Check if document with this unique identifier already exists
                existing_document = await check_document_by_unique_identifier(
                    session, unique_identifier_hash
                )

                if existing_document:
                    # Document exists - check if it's already being processed
                    if DocumentStatus.is_state(
                        existing_document.status, DocumentStatus.PENDING
                    ):
                        logger.info(f"URL {url} already pending. Skipping.")
                        documents_skipped += 1
                        continue
                    if DocumentStatus.is_state(
                        existing_document.status, DocumentStatus.PROCESSING
                    ):
                        logger.info(f"URL {url} already processing. Skipping.")
                        documents_skipped += 1
                        continue

                    # Queue existing document for potential update check
                    urls_to_process.append(
                        {
                            "document": existing_document,
                            "is_new": False,
                            "url": url,
                            "unique_identifier_hash": unique_identifier_hash,
                        }
                    )
                    continue

                # Create new document with PENDING status (visible in UI immediately)
                document = Document(
                    workspace_id=workspace_id,
                    title=url[:100],  # Placeholder - URL as title (truncated)
                    document_type=DocumentType.CRAWLED_URL,
                    document_metadata={
                        "url": url,
                        "connector_id": connector_id,
                    },
                    content="Pending crawl...",  # Placeholder content
                    content_hash=unique_identifier_hash,  # Temporary unique value
                    unique_identifier_hash=unique_identifier_hash,
                    embedding=None,
                    chunks=[],  # Empty at creation - safe for async
                    status=DocumentStatus.pending(),  # PENDING status - visible in UI
                    updated_at=get_current_timestamp(),
                    created_by_id=user_id,
                    connector_id=connector_id,
                )
                session.add(document)
                new_documents_created = True

                urls_to_process.append(
                    {
                        "document": document,
                        "is_new": True,
                        "url": url,
                        "unique_identifier_hash": unique_identifier_hash,
                    }
                )

            except Exception as e:
                logger.error(f"Error in Phase 1 for URL {url}: {e!s}", exc_info=True)
                documents_failed += 1
                continue

        # Commit all pending documents - they all appear in UI now
        if new_documents_created:
            logger.info(
                f"Phase 1: Committing {len([u for u in urls_to_process if u['is_new']])} pending documents"
            )
            await session.commit()

        # =======================================================================
        # PHASE 2: Process each URL one by one
        # Each document transitions: pending → processing → ready/failed
        # =======================================================================
        logger.info(f"Phase 2: Processing {len(urls_to_process)} URLs")

        for item in urls_to_process:
            # Send heartbeat periodically
            if on_heartbeat_callback:
                current_time = time.time()
                if current_time - last_heartbeat_time >= HEARTBEAT_INTERVAL_SECONDS:
                    await on_heartbeat_callback(documents_indexed + documents_updated)
                    last_heartbeat_time = current_time

            document = item["document"]
            url = item["url"]
            is_new = item["is_new"]

            try:
                # Set to PROCESSING and commit - shows "processing" in UI for THIS document only
                document.status = DocumentStatus.processing()
                await session.commit()

                await task_logger.log_task_progress(
                    log_entry,
                    f"Crawling URL: {url}",
                    {
                        "stage": "crawling_url",
                        "url": url,
                    },
                )

                # Crawl the URL
                outcome = await crawler.crawl_url(url)

                # Phase 3d: count captcha attempts BEFORE the success branch — a
                # failed solve still cost real solver money and must bill.
                if credit_service.captcha_billing_enabled():
                    total_captcha_attempts += outcome.captcha_attempts
                    if outcome.captcha_solved:
                        total_captcha_solved += 1

                if (
                    outcome.status is not CrawlOutcomeStatus.SUCCESS
                    or not outcome.result
                ):
                    logger.warning(f"Failed to crawl URL {url}: {outcome.error}")
                    document.status = DocumentStatus.failed(
                        outcome.error or "Crawl failed"
                    )
                    document.updated_at = get_current_timestamp()
                    await session.commit()
                    documents_failed += 1
                    continue

                # A tier extracted usable content: count the successful crawl now,
                # before the dedupe/unchanged branches (those still represent a
                # successful crawl and must bill — see 03c).
                crawls_succeeded += 1
                crawl_result = outcome.result

                # Extract content and metadata
                content = crawl_result.get("content", "")
                metadata = crawl_result.get("metadata", {})
                crawler_type = crawl_result.get("crawler_type", "unknown")

                if not content.strip():
                    logger.warning(f"Skipping URL with no content: {url}")
                    document.status = DocumentStatus.failed("No content extracted")
                    document.updated_at = get_current_timestamp()
                    await session.commit()
                    documents_failed += 1
                    continue

                # Format content as structured document for summary generation
                crawler.format_to_structured_document(crawl_result)

                # Generate content hash using a version WITHOUT metadata
                structured_document_for_hash = crawler.format_to_structured_document(
                    crawl_result, exclude_metadata=True
                )
                content_hash = generate_content_hash(
                    structured_document_for_hash, workspace_id
                )

                # Extract useful metadata
                title = metadata.get("title", url)
                metadata.get("description", "")
                metadata.get("language", "")

                # Update title immediately for better UX
                document.title = title
                await session.commit()

                # For existing documents, check if content has changed
                if not is_new and document.content_hash == content_hash:
                    logger.info(f"Document for URL {url} unchanged. Marking as ready.")
                    # Ensure status is ready (might have been stuck)
                    document.status = DocumentStatus.ready()
                    await session.commit()
                    documents_skipped += 1
                    continue

                # For new documents, check if duplicate content exists elsewhere
                if is_new:
                    with session.no_autoflush:
                        duplicate_by_content = await check_duplicate_document_by_hash(
                            session, content_hash
                        )

                    if duplicate_by_content:
                        logger.info(
                            f"URL {url} already indexed by another connector "
                            f"(existing document ID: {duplicate_by_content.id}). "
                            f"Marking as failed."
                        )
                        document.status = DocumentStatus.failed(
                            "Duplicate content exists"
                        )
                        document.updated_at = get_current_timestamp()
                        await session.commit()
                        duplicate_content_count += 1
                        documents_skipped += 1
                        continue

                # Select deterministic document content

                summary_content = f"Crawled URL: {title}\n\nURL: {url}\n\n{content}"
                summary_embedding = embed_text(summary_content)

                # Process chunks
                chunks = await create_document_chunks(content)

                # Update document to READY with actual content
                document.title = title
                document.content = summary_content
                document.content_hash = content_hash
                document.embedding = summary_embedding
                document.document_metadata = {
                    **metadata,
                    "crawler_type": crawler_type,
                    "indexed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "connector_id": connector_id,
                }
                await safe_set_chunks(session, document, chunks)
                document.status = DocumentStatus.ready()  # READY status
                document.updated_at = get_current_timestamp()

                if is_new:
                    documents_indexed += 1
                else:
                    documents_updated += 1

                logger.info(f"Successfully processed URL {url}")

                # Batch commit every 10 documents (for ready status updates)
                if (documents_indexed + documents_updated) % 10 == 0:
                    logger.info(
                        f"Committing batch: {documents_indexed + documents_updated} URLs processed so far"
                    )
                    await session.commit()

            except Exception as e:
                logger.error(f"Error processing URL {url}: {e!s}", exc_info=True)
                # Mark document as failed with reason (visible in UI)
                try:
                    document.status = DocumentStatus.failed(str(e)[:200])
                    document.updated_at = get_current_timestamp()
                    await session.commit()
                except Exception as status_error:
                    logger.error(
                        f"Failed to update document status to failed: {status_error}"
                    )
                documents_failed += 1
                continue

        total_processed = documents_indexed + documents_updated

        # CRITICAL: Always update timestamp (even if 0 documents indexed) so Zero syncs
        await update_connector_last_indexed(session, connector, update_last_indexed)

        # Final commit for any remaining documents not yet committed in batches
        logger.info(
            f"Final commit: Total {documents_indexed} new, {documents_updated} updated URLs processed"
        )
        try:
            await session.commit()
            logger.info(
                "Successfully committed all webcrawler document changes to database"
            )
        except Exception as e:
            # Handle any remaining integrity errors gracefully
            if "duplicate key value violates unique constraint" in str(e).lower():
                logger.warning(
                    f"Duplicate content_hash detected during final commit. "
                    f"Rolling back and continuing. Error: {e!s}"
                )
                await session.rollback()
            else:
                raise

        # =======================================================================
        # Phase 3c: charge the workspace owner for successful crawls. Audit row
        # is staged first (add only); charge_credits' commit flushes both the
        # ``web_crawl`` TokenUsage row and the balance debit in one transaction.
        # Skipped when billing is disabled or nothing crawled successfully.
        # =======================================================================
        if credit_service.billing_enabled() and crawls_succeeded > 0:
            await record_token_usage(
                session,
                usage_type="web_crawl",
                workspace_id=workspace_id,
                user_id=owner_user_id,
                cost_micros=credit_service.successes_to_micros(crawls_succeeded),
                call_details={
                    "urls": len(urls),
                    "successes": crawls_succeeded,
                    "connector_id": connector_id,
                },
                message_id=None,
            )
            await credit_service.charge_credits(owner_user_id, crawls_succeeded)

        # =======================================================================
        # Phase 3d: charge the workspace owner per captcha *attempt* (separate
        # unit; charged even when the crawl ultimately failed). Same stage +
        # owner as the crawl charge above.
        # =======================================================================
        if credit_service.captcha_billing_enabled() and total_captcha_attempts > 0:
            await record_token_usage(
                session,
                usage_type="web_crawl_captcha",
                workspace_id=workspace_id,
                user_id=owner_user_id,
                cost_micros=credit_service.captcha_solves_to_micros(
                    total_captcha_attempts
                ),
                call_details={
                    "attempts": total_captcha_attempts,
                    "solved": total_captcha_solved,
                    "connector_id": connector_id,
                },
                message_id=None,
            )
            await credit_service.charge_captcha(owner_user_id, total_captcha_attempts)

        # Build warning message if there were issues
        warning_parts = []
        if duplicate_content_count > 0:
            warning_parts.append(f"{duplicate_content_count} duplicate")
        if documents_failed > 0:
            warning_parts.append(f"{documents_failed} failed")
        warning_message = ", ".join(warning_parts) if warning_parts else None

        await task_logger.log_task_success(
            log_entry,
            f"Successfully completed crawled web page indexing for connector {connector_id}",
            {
                "urls_processed": total_processed,
                "crawls_succeeded": crawls_succeeded,
                "documents_indexed": documents_indexed,
                "documents_updated": documents_updated,
                "documents_skipped": documents_skipped,
                "documents_failed": documents_failed,
                "duplicate_content_count": duplicate_content_count,
            },
        )

        logger.info(
            f"Web page indexing completed: {documents_indexed} new, "
            f"{documents_updated} updated, {documents_skipped} skipped, "
            f"{documents_failed} failed"
        )

        if warning_message:
            return total_processed, f"Completed with issues: {warning_message}"

        return total_processed, None

    except SQLAlchemyError as db_error:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Database error during web page indexing for connector {connector_id}",
            str(db_error),
            {"error_type": "SQLAlchemyError"},
        )
        logger.error(f"Database error: {db_error!s}", exc_info=True)
        return 0, f"Database error: {db_error!s}"
    except Exception as e:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Failed to index web page URLs for connector {connector_id}",
            str(e),
            {"error_type": type(e).__name__},
        )
        logger.error(f"Failed to index web page URLs: {e!s}", exc_info=True)
        return 0, f"Failed to index web page URLs: {e!s}"


async def get_crawled_url_documents(
    session: AsyncSession,
    workspace_id: int,
    connector_id: int | None = None,
) -> list[Document]:
    """
    Get all crawled URL documents for a workspace.

    Args:
        session: Database session
        workspace_id: ID of the workspace
        connector_id: Optional connector ID to filter by

    Returns:
        List of Document objects
    """
    from sqlalchemy import select

    query = select(Document).filter(
        Document.workspace_id == workspace_id,
        Document.document_type == DocumentType.CRAWLED_URL,
    )

    if connector_id:
        query = query.filter(Document.connector_id == connector_id)

    result = await session.execute(query)
    documents = result.scalars().all()
    return list(documents)
