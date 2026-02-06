"""
Elasticsearch indexer for SurfSense

Implements 2-phase document status updates for real-time UI feedback:
- Phase 1: Collect all documents and create pending documents (visible in UI immediately)
- Phase 2: Process each document: pending → processing → ready/failed
"""

import json
import logging
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.connectors.elasticsearch_connector import ElasticsearchConnector
from app.db import Document, DocumentStatus, DocumentType, SearchSourceConnector
from app.services.task_logging_service import TaskLoggingService
from app.utils.document_converters import (
    create_document_chunks,
    generate_content_hash,
    generate_unique_identifier_hash,
)

from .base import (
    check_document_by_unique_identifier,
    check_duplicate_document_by_hash,
    get_current_timestamp,
    safe_set_chunks,
)

# Type hint for heartbeat callback
HeartbeatCallbackType = Callable[[int], Awaitable[None]]

# Heartbeat interval in seconds
HEARTBEAT_INTERVAL_SECONDS = 30

logger = logging.getLogger(__name__)


async def index_elasticsearch_documents(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str,
    end_date: str,
    update_last_indexed: bool = True,
    on_heartbeat_callback: HeartbeatCallbackType | None = None,
) -> tuple[int, str | None]:
    """
    Index documents from Elasticsearch into SurfSense

    Args:
        session: Database session
        connector_id: Elasticsearch connector ID
        search_space_id: Search space ID
        user_id: User ID
        start_date: Start date for indexing (not used for Elasticsearch, kept for compatibility)
        end_date: End date for indexing (not used for Elasticsearch, kept for compatibility)
        update_last_indexed: Whether to update the last indexed timestamp
        on_heartbeat_callback: Optional callback to update notification during long-running indexing.

    Returns:
        Tuple of (number of documents processed, error message if any)
    """
    task_logger = TaskLoggingService(session, search_space_id)
    log_entry = await task_logger.log_task_start(
        task_name="elasticsearch_indexing",
        source="connector_indexing_task",
        message=f"Starting Elasticsearch indexing for connector {connector_id}",
        metadata={
            "connector_id": connector_id,
            "user_id": str(user_id),
            "index": None,
            "start_date": start_date,
            "end_date": end_date,
        },
    )
    es_connector = None
    try:
        # Get the connector configuration
        result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.id == connector_id
            )
        )
        connector = result.scalars().first()

        if not connector:
            error_msg = f"Elasticsearch connector with ID {connector_id} not found"
            logger.error(error_msg)
            await task_logger.log_task_failure(
                log_entry,
                "Connector not found",
                error_msg,
                {"connector_id": connector_id},
            )
            return 0, error_msg

        # Get connector configuration
        config = connector.config

        # Validate required fields - now only URL and INDEX are required
        # Authentication can be either API key OR username/password
        if "ELASTICSEARCH_URL" not in config:
            error_msg = "Missing required field in connector config: ELASTICSEARCH_URL"
            logger.error(error_msg)
            return 0, error_msg

        # Allow missing/empty index: default to searching all indices ("*" or "_all")
        index_name = config.get("ELASTICSEARCH_INDEX")
        if not index_name:
            index_name = "*"
            logger.info(
                "ELASTICSEARCH_INDEX missing or empty in connector config; defaulting to '*' (search all indices)"
            )
            await task_logger.log_task_progress(
                log_entry,
                "Using default index",
                {"index": index_name, "stage": "index_defaulted"},
            )

        # Check authentication - must have either API key or username+password
        has_api_key = (
            "ELASTICSEARCH_API_KEY" in config and config["ELASTICSEARCH_API_KEY"]
        )
        has_basic_auth = (
            "ELASTICSEARCH_USERNAME" in config
            and config["ELASTICSEARCH_USERNAME"]
            and "ELASTICSEARCH_PASSWORD" in config
            and config["ELASTICSEARCH_PASSWORD"]
        )

        if not has_api_key and not has_basic_auth:
            error_msg = "Missing authentication: provide either ELASTICSEARCH_API_KEY or ELASTICSEARCH_USERNAME + ELASTICSEARCH_PASSWORD"
            logger.error(error_msg)
            return 0, error_msg

        # Initialize document service
        # document_service = _DocumentService(session)

        # Initialize Elasticsearch connector
        es_connector = ElasticsearchConnector(
            url=config["ELASTICSEARCH_URL"],
            api_key=config.get("ELASTICSEARCH_API_KEY"),
            username=config.get("ELASTICSEARCH_USERNAME"),
            password=config.get("ELASTICSEARCH_PASSWORD"),
            verify_certs=config.get("ELASTICSEARCH_VERIFY_CERTS", True),
            ca_certs=config.get("ELASTICSEARCH_CA_CERTS"),
        )
        await task_logger.log_task_progress(
            log_entry,
            "Initialized Elasticsearch connector",
            {"index": index_name, "stage": "connector_initialized"},
        )

        # Build query based on configuration
        query = _build_elasticsearch_query(config)

        # Get max documents to index
        max_documents = config.get("ELASTICSEARCH_MAX_DOCUMENTS", 1000)

        logger.info(
            f"Starting Elasticsearch indexing for index '{index_name}' with max {max_documents} documents"
        )

        documents_processed = 0
        documents_skipped = 0
        documents_failed = 0

        # Heartbeat tracking - update notification periodically to prevent appearing stuck
        last_heartbeat_time = time.time()

        try:
            await task_logger.log_task_progress(
                log_entry,
                "Starting scroll search",
                {
                    "index": index_name,
                    "stage": "scroll_start",
                    "max_documents": max_documents,
                },
            )

            # =======================================================================
            # PHASE 1: Collect all documents from Elasticsearch and create pending documents
            # This makes ALL documents visible in the UI immediately with pending status
            # =======================================================================
            docs_to_process = []  # List of dicts with document and ES data
            new_documents_created = False
            hits_collected = 0

            async for hit in es_connector.scroll_search(
                index=index_name,
                query=query,
                size=min(max_documents, 100),  # Scroll in batches
                fields=config.get("ELASTICSEARCH_FIELDS"),
            ):
                if hits_collected >= max_documents:
                    break

                try:
                    # Extract document data
                    doc_id = hit["_id"]
                    source = hit.get("_source", {})

                    # Build document title
                    title_field = config.get("ELASTICSEARCH_TITLE_FIELD")
                    if not title_field:
                        for candidate in ("title", "name", "subject"):
                            if candidate in source:
                                title_field = candidate
                                break
                    title = (
                        str(source.get(title_field, doc_id))
                        if title_field is not None
                        else str(doc_id)
                    )

                    # Build document content
                    content = _build_document_content(source, config)

                    if not content.strip():
                        logger.warning(f"Skipping document {doc_id} - no content found")
                        documents_skipped += 1
                        continue

                    # Create content hash
                    content_hash = generate_content_hash(content, search_space_id)

                    # Build source-unique identifier and hash (prefer source id dedupe)
                    source_identifier = f"{hit.get('_index', index_name)}:{doc_id}"
                    unique_identifier_hash = generate_unique_identifier_hash(
                        DocumentType.ELASTICSEARCH_CONNECTOR,
                        source_identifier,
                        search_space_id,
                    )

                    # Two-step duplicate detection: first by source-unique id, then by content hash
                    existing_doc = await check_document_by_unique_identifier(
                        session, unique_identifier_hash
                    )
                    if not existing_doc:
                        existing_doc = await check_duplicate_document_by_hash(
                            session, content_hash
                        )

                    if existing_doc:
                        # If content is unchanged, skip. Otherwise queue for update.
                        if existing_doc.content_hash == content_hash:
                            # Ensure status is ready (might have been stuck in processing/pending)
                            if not DocumentStatus.is_state(
                                existing_doc.status, DocumentStatus.READY
                            ):
                                existing_doc.status = DocumentStatus.ready()
                            logger.info(
                                f"Skipping ES doc {doc_id} — already indexed (doc id {existing_doc.id})"
                            )
                            documents_skipped += 1
                            continue

                        # Queue existing document for update (will be set to processing in Phase 2)
                        docs_to_process.append(
                            {
                                "document": existing_doc,
                                "is_new": False,
                                "doc_id": doc_id,
                                "title": title,
                                "content": content,
                                "content_hash": content_hash,
                                "unique_identifier_hash": unique_identifier_hash,
                                "hit": hit,
                                "source": source,
                            }
                        )
                        hits_collected += 1
                        continue

                    # Build metadata for new document
                    metadata = {
                        "elasticsearch_id": doc_id,
                        "elasticsearch_index": hit.get("_index", index_name),
                        "elasticsearch_score": hit.get("_score"),
                        "source": "ELASTICSEARCH_CONNECTOR",
                        "connector_id": connector_id,
                    }

                    # Add any additional metadata fields specified in config
                    if "ELASTICSEARCH_METADATA_FIELDS" in config:
                        for field in config["ELASTICSEARCH_METADATA_FIELDS"]:
                            if field in source:
                                metadata[f"es_{field}"] = source[field]

                    # Create new document with PENDING status (visible in UI immediately)
                    document = Document(
                        title=title,
                        content="Pending...",  # Placeholder until processed
                        content_hash=unique_identifier_hash,  # Temporary unique value - updated when ready
                        unique_identifier_hash=unique_identifier_hash,
                        document_type=DocumentType.ELASTICSEARCH_CONNECTOR,
                        document_metadata=metadata,
                        search_space_id=search_space_id,
                        embedding=None,
                        chunks=[],  # Empty at creation - safe for async
                        status=DocumentStatus.pending(),  # Pending until processing starts
                        updated_at=get_current_timestamp(),
                        created_by_id=user_id,
                        connector_id=connector_id,
                    )
                    session.add(document)
                    new_documents_created = True

                    docs_to_process.append(
                        {
                            "document": document,
                            "is_new": True,
                            "doc_id": doc_id,
                            "title": title,
                            "content": content,
                            "content_hash": content_hash,
                            "unique_identifier_hash": unique_identifier_hash,
                            "hit": hit,
                            "source": source,
                        }
                    )
                    hits_collected += 1

                except Exception as e:
                    logger.error(f"Error in Phase 1 for ES doc: {e!s}", exc_info=True)
                    documents_failed += 1
                    continue

            # Commit all pending documents - they all appear in UI now
            if new_documents_created:
                logger.info(
                    f"Phase 1: Committing {len([d for d in docs_to_process if d['is_new']])} pending documents"
                )
                await session.commit()

            # =======================================================================
            # PHASE 2: Process each document one by one
            # Each document transitions: pending → processing → ready/failed
            # =======================================================================
            logger.info(f"Phase 2: Processing {len(docs_to_process)} documents")

            for item in docs_to_process:
                # Send heartbeat periodically
                if on_heartbeat_callback:
                    current_time = time.time()
                    if current_time - last_heartbeat_time >= HEARTBEAT_INTERVAL_SECONDS:
                        await on_heartbeat_callback(documents_processed)
                        last_heartbeat_time = current_time

                document = item["document"]
                try:
                    # Set to PROCESSING and commit - shows "processing" in UI for THIS document only
                    document.status = DocumentStatus.processing()
                    await session.commit()

                    # Build metadata
                    metadata = {
                        "elasticsearch_id": item["doc_id"],
                        "elasticsearch_index": item["hit"].get("_index", index_name),
                        "elasticsearch_score": item["hit"].get("_score"),
                        "indexed_at": datetime.now().isoformat(),
                        "source": "ELASTICSEARCH_CONNECTOR",
                        "connector_id": connector_id,
                    }

                    # Add any additional metadata fields specified in config
                    if "ELASTICSEARCH_METADATA_FIELDS" in config:
                        for field in config["ELASTICSEARCH_METADATA_FIELDS"]:
                            if field in item["source"]:
                                metadata[f"es_{field}"] = item["source"][field]

                    # Create chunks
                    chunks = await create_document_chunks(item["content"])

                    # Update document to READY with actual content
                    document.title = item["title"]
                    document.content = item["content"]
                    document.content_hash = item["content_hash"]
                    document.unique_identifier_hash = item["unique_identifier_hash"]
                    document.document_metadata = metadata
                    safe_set_chunks(document, chunks)
                    document.updated_at = get_current_timestamp()
                    document.status = DocumentStatus.ready()

                    documents_processed += 1

                    # Batch commit every 10 documents (for ready status updates)
                    if documents_processed % 10 == 0:
                        logger.info(
                            f"Committing batch: {documents_processed} Elasticsearch documents processed so far"
                        )
                        await session.commit()

                except Exception as e:
                    msg = f"Error processing Elasticsearch document {item.get('doc_id', 'unknown')}: {e}"
                    logger.error(msg)
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
            # This ensures the UI shows "Last indexed" instead of "Never indexed"
            if update_last_indexed:
                connector.last_indexed_at = (
                    datetime.now(UTC).isoformat().replace("+00:00", "Z")
                )

            # Final commit for any remaining documents not yet committed in batches
            logger.info(
                f"Final commit: Total {documents_processed} Elasticsearch documents processed"
            )
            try:
                await session.commit()
                logger.info(
                    "Successfully committed all Elasticsearch document changes to database"
                )
            except Exception as e:
                # Handle any remaining integrity errors gracefully (race conditions, etc.)
                if (
                    "duplicate key value violates unique constraint" in str(e).lower()
                    or "uniqueviolationerror" in str(e).lower()
                ):
                    logger.warning(
                        f"Duplicate content_hash detected during final commit. "
                        f"This may occur if the same document was indexed by multiple connectors. "
                        f"Rolling back and continuing. Error: {e!s}"
                    )
                    await session.rollback()
                    # Don't fail the entire task - some documents may have been successfully indexed
                else:
                    raise

            # Build warning message if there were issues
            warning_parts = []
            if documents_failed > 0:
                warning_parts.append(f"{documents_failed} failed")
            warning_message = ", ".join(warning_parts) if warning_parts else None

            await task_logger.log_task_success(
                log_entry,
                f"Successfully indexed {documents_processed} documents from Elasticsearch",
                {
                    "documents_indexed": documents_processed,
                    "documents_skipped": documents_skipped,
                    "documents_failed": documents_failed,
                    "index": index_name,
                },
            )
            logger.info(
                f"Elasticsearch indexing completed: {documents_processed} ready, "
                f"{documents_skipped} skipped, {documents_failed} failed"
            )

            return documents_processed, warning_message

        finally:
            # Clean up Elasticsearch connection
            if es_connector:
                await es_connector.close()

    except Exception as e:
        error_msg = f"Error indexing Elasticsearch documents: {e}"
        logger.error(error_msg, exc_info=True)
        await task_logger.log_task_failure(
            log_entry, "Indexing failed", error_msg, {"error_type": type(e).__name__}
        )
        await session.rollback()
        if es_connector:
            await es_connector.close()
        return 0, error_msg


def _build_elasticsearch_query(config: dict[str, Any]) -> dict[str, Any]:
    """
    Build Elasticsearch query from connector configuration

    Args:
        config: Connector configuration

    Returns:
        Elasticsearch query DSL
    """
    # Check if custom query is provided
    if config.get("ELASTICSEARCH_QUERY"):
        try:
            if isinstance(config["ELASTICSEARCH_QUERY"], str):
                return json.loads(config["ELASTICSEARCH_QUERY"])
            else:
                return config["ELASTICSEARCH_QUERY"]
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Invalid custom query, using match_all: {e}")

    # Default to match all documents
    return {"match_all": {}}


def _build_document_content(source: dict[str, Any], config: dict[str, Any]) -> str:
    """
    Build document content from Elasticsearch document source

    Args:
        source: Elasticsearch document source
        config: Connector configuration

    Returns:
        Formatted document content
    """
    content_parts = []

    # Get content fields from config
    content_fields = config.get("ELASTICSEARCH_CONTENT_FIELDS", [])

    if content_fields:
        # Use specified content fields
        for field in content_fields:
            if field in source:
                field_value = source[field]
                if isinstance(field_value, str | int | float):
                    content_parts.append(f"{field}: {field_value}")
                elif isinstance(field_value, list | dict):
                    content_parts.append(f"{field}: {json.dumps(field_value)}")
    else:
        # Use all fields if no specific content fields specified
        for key, value in source.items():
            if isinstance(value, str | int | float):
                content_parts.append(f"{key}: {value}")
            elif isinstance(value, list | dict):
                content_parts.append(f"{key}: {json.dumps(value)}")

    return "\n".join(content_parts)
