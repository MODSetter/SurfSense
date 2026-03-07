"""
GitHub connector indexer using gitingest.

This indexer processes entire repository digests in one pass, dramatically
reducing LLM API calls compared to the previous file-by-file approach.

Implements 2-phase document status updates for real-time UI feedback:
- Phase 1: Create all documents with 'pending' status (visible in UI immediately)
- Phase 2: Process each document: pending → processing → ready/failed
"""

import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.github_connector import GitHubConnector
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

# Maximum tokens for a single digest before splitting
# Most LLMs can handle 128k+ tokens now, but we'll be conservative
MAX_DIGEST_CHARS = 500_000  # ~125k tokens


async def index_github_repos(
    session: AsyncSession,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str | None = None,  # Ignored - GitHub indexes full repo snapshots
    end_date: str | None = None,  # Ignored - GitHub indexes full repo snapshots
    update_last_indexed: bool = True,
    on_heartbeat_callback: HeartbeatCallbackType | None = None,
) -> tuple[int, str | None]:
    """
    Index GitHub repositories using gitingest for efficient processing.

    This function ingests entire repositories as digests, generates a single
    summary per repository, and chunks the content for vector storage.

    Note: The start_date and end_date parameters are accepted for API compatibility
    but are IGNORED. GitHub repositories are indexed as complete snapshots since
    gitingest captures the current state of the entire codebase.

    Args:
        session: Database session
        connector_id: ID of the GitHub connector
        search_space_id: ID of the search space to store documents in
        user_id: ID of the user
        start_date: Ignored - kept for API compatibility
        end_date: Ignored - kept for API compatibility
        update_last_indexed: Whether to update the last_indexed_at timestamp (default: True)
        on_heartbeat_callback: Optional callback to update notification during long-running indexing.

    Returns:
        Tuple containing (number of documents indexed, error message or None)
    """
    # Note: start_date and end_date are intentionally unused
    _ = start_date, end_date
    task_logger = TaskLoggingService(session, search_space_id)

    # Log task start
    log_entry = await task_logger.log_task_start(
        task_name="github_repos_indexing",
        source="connector_indexing_task",
        message=f"Starting GitHub repositories indexing for connector {connector_id} (using gitingest)",
        metadata={
            "connector_id": connector_id,
            "user_id": str(user_id),
            "method": "gitingest",
        },
    )

    documents_processed = 0
    errors = []

    try:
        # 1. Get the GitHub connector from the database
        await task_logger.log_task_progress(
            log_entry,
            f"Retrieving GitHub connector {connector_id} from database",
            {"stage": "connector_retrieval"},
        )

        connector = await get_connector_by_id(
            session, connector_id, SearchSourceConnectorType.GITHUB_CONNECTOR
        )

        if not connector:
            await task_logger.log_task_failure(
                log_entry,
                f"Connector with ID {connector_id} not found or is not a GitHub connector",
                "Connector not found",
                {"error_type": "ConnectorNotFound"},
            )
            return (
                0,
                f"Connector with ID {connector_id} not found or is not a GitHub connector",
            )

        # 2. Get the GitHub PAT (optional) and selected repositories from the connector config
        # PAT is only required for private repositories - public repos work without it
        github_pat = connector.config.get("GITHUB_PAT")  # Can be None or empty
        repo_full_names_to_index = connector.config.get("repo_full_names")

        if not repo_full_names_to_index or not isinstance(
            repo_full_names_to_index, list
        ):
            await task_logger.log_task_failure(
                log_entry,
                f"'repo_full_names' not found or is not a list in connector config for connector {connector_id}",
                "Invalid repo configuration",
                {"error_type": "InvalidConfiguration"},
            )
            return 0, "'repo_full_names' not found or is not a list in connector config"

        # Log whether we're using authentication
        if github_pat:
            logger.info("Using GitHub PAT for authentication (private repos supported)")
        else:
            logger.info(
                "No GitHub PAT provided - only public repositories can be indexed"
            )

        # 3. Initialize GitHub connector with gitingest backend
        await task_logger.log_task_progress(
            log_entry,
            f"Initializing gitingest-based GitHub client for connector {connector_id}",
            {
                "stage": "client_initialization",
                "repo_count": len(repo_full_names_to_index),
            },
        )

        try:
            github_client = GitHubConnector(token=github_pat)
        except ValueError as e:
            await task_logger.log_task_failure(
                log_entry,
                f"Failed to initialize GitHub client for connector {connector_id}",
                str(e),
                {"error_type": "ClientInitializationError"},
            )
            return 0, f"Failed to initialize GitHub client: {e!s}"

        # 4. Process each repository with gitingest using 2-phase approach
        await task_logger.log_task_progress(
            log_entry,
            f"Starting gitingest processing for {len(repo_full_names_to_index)} repositories",
            {
                "stage": "repo_processing",
                "repo_count": len(repo_full_names_to_index),
            },
        )

        logger.info(
            f"Starting gitingest indexing for {len(repo_full_names_to_index)} repositories."
        )

        # Heartbeat tracking - update notification periodically to prevent appearing stuck
        last_heartbeat_time = time.time()
        documents_indexed = 0
        documents_skipped = 0
        documents_failed = 0

        # =======================================================================
        # PHASE 1: Analyze all repos and create pending documents
        # This makes ALL documents visible in the UI immediately with pending status
        # =======================================================================
        repos_to_process = []  # List of dicts with document and digest data
        new_documents_created = False

        for repo_full_name in repo_full_names_to_index:
            if not repo_full_name or not isinstance(repo_full_name, str):
                logger.warning(f"Skipping invalid repository entry: {repo_full_name}")
                continue

            try:
                logger.info(f"Phase 1: Analyzing repository: {repo_full_name}")

                # Run gitingest via subprocess (isolated from event loop)
                import asyncio

                digest = await asyncio.to_thread(
                    github_client.ingest_repository, repo_full_name
                )

                if not digest:
                    logger.warning(
                        f"No digest returned for repository: {repo_full_name}"
                    )
                    errors.append(f"No digest for {repo_full_name}")
                    continue

                # Generate unique identifier based on repo name
                unique_identifier_hash = generate_unique_identifier_hash(
                    DocumentType.GITHUB_CONNECTOR, repo_full_name, search_space_id
                )

                # Generate content hash from digest
                full_content = digest.full_digest
                content_hash = generate_content_hash(full_content, search_space_id)

                # Check if document with this unique identifier already exists
                existing_document = await check_document_by_unique_identifier(
                    session, unique_identifier_hash
                )

                if existing_document:
                    # Document exists - check if content has changed
                    if existing_document.content_hash == content_hash:
                        # Ensure status is ready (might have been stuck in processing/pending)
                        if not DocumentStatus.is_state(
                            existing_document.status, DocumentStatus.READY
                        ):
                            existing_document.status = DocumentStatus.ready()
                        logger.info(f"Repository {repo_full_name} unchanged. Skipping.")
                        documents_skipped += 1
                        continue

                    # Queue existing document for update (will be set to processing in Phase 2)
                    logger.info(
                        f"Content changed for repository {repo_full_name}. Queuing for update."
                    )
                    repos_to_process.append(
                        {
                            "document": existing_document,
                            "is_new": False,
                            "digest": digest,
                            "content_hash": content_hash,
                            "repo_full_name": repo_full_name,
                            "unique_identifier_hash": unique_identifier_hash,
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
                        f"Repository {repo_full_name} already indexed by another connector "
                        f"(existing document ID: {duplicate_by_content.id}, "
                        f"type: {duplicate_by_content.document_type}). Skipping."
                    )
                    documents_skipped += 1
                    continue

                # Create new document with PENDING status (visible in UI immediately)
                document = Document(
                    search_space_id=search_space_id,
                    title=repo_full_name,
                    document_type=DocumentType.GITHUB_CONNECTOR,
                    document_metadata={
                        "repository_full_name": repo_full_name,
                        "url": f"https://github.com/{repo_full_name}",
                        "branch": digest.branch,
                        "ingestion_method": "gitingest",
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

                repos_to_process.append(
                    {
                        "document": document,
                        "is_new": True,
                        "digest": digest,
                        "content_hash": content_hash,
                        "repo_full_name": repo_full_name,
                        "unique_identifier_hash": unique_identifier_hash,
                    }
                )

            except Exception as repo_err:
                logger.error(
                    f"Error in Phase 1 for repository {repo_full_name}: {repo_err}",
                    exc_info=True,
                )
                errors.append(f"Phase 1 error for {repo_full_name}: {repo_err}")
                documents_failed += 1

        # Commit all pending documents - they all appear in UI now
        if new_documents_created:
            logger.info(
                f"Phase 1: Committing {len([r for r in repos_to_process if r['is_new']])} pending documents"
            )
            await session.commit()

        # =======================================================================
        # PHASE 2: Process each document one by one
        # Each document transitions: pending → processing → ready/failed
        # =======================================================================
        logger.info(f"Phase 2: Processing {len(repos_to_process)} documents")

        for item in repos_to_process:
            # Send heartbeat periodically
            if on_heartbeat_callback:
                current_time = time.time()
                if current_time - last_heartbeat_time >= HEARTBEAT_INTERVAL_SECONDS:
                    await on_heartbeat_callback(documents_indexed)
                    last_heartbeat_time = current_time

            document = item["document"]
            digest = item["digest"]
            repo_full_name = item["repo_full_name"]

            try:
                # Set to PROCESSING and commit - shows "processing" in UI for THIS document only
                document.status = DocumentStatus.processing()
                await session.commit()

                # Heavy processing (LLM, embeddings, chunks)
                user_llm = await get_user_long_context_llm(
                    session, user_id, search_space_id
                )

                document_metadata_for_summary = {
                    "repository": repo_full_name,
                    "document_type": "GitHub Repository",
                    "connector_type": "GitHub",
                    "ingestion_method": "gitingest",
                    "file_tree": digest.tree[:2000]
                    if len(digest.tree) > 2000
                    else digest.tree,
                    "estimated_tokens": digest.estimated_tokens,
                }

                if user_llm and connector.enable_summary:
                    # Prepare content for summarization
                    summary_content = digest.full_digest
                    if len(summary_content) > MAX_DIGEST_CHARS:
                        summary_content = (
                            f"# Repository: {repo_full_name}\n\n"
                            f"## File Structure\n\n{digest.tree}\n\n"
                            f"## File Contents (truncated)\n\n{digest.content[: MAX_DIGEST_CHARS - len(digest.tree) - 200]}..."
                        )

                    summary_text, summary_embedding = await generate_document_summary(
                        summary_content, user_llm, document_metadata_for_summary
                    )
                else:
                    summary_text = (
                        f"# GitHub Repository: {repo_full_name}\n\n"
                        f"## Summary\n{digest.summary}\n\n"
                        f"## File Structure\n{digest.tree}"
                    )
                    summary_embedding = embed_text(summary_text)

                # Chunk the full digest content for granular search
                try:
                    chunks_data = await create_document_chunks(digest.content)
                except Exception as chunk_err:
                    logger.error(
                        f"Failed to chunk repository {repo_full_name}: {chunk_err}"
                    )
                    chunks_data = await _simple_chunk_content(digest.content)

                # Update document to READY with actual content
                doc_metadata = {
                    "repository_full_name": repo_full_name,
                    "url": f"https://github.com/{repo_full_name}",
                    "branch": digest.branch,
                    "ingestion_method": "gitingest",
                    "file_tree": digest.tree,
                    "gitingest_summary": digest.summary,
                    "estimated_tokens": digest.estimated_tokens,
                    "connector_id": connector_id,
                    "indexed_at": datetime.now(UTC).isoformat(),
                }

                document.title = repo_full_name
                document.content = summary_text
                document.content_hash = item["content_hash"]
                document.embedding = summary_embedding
                document.document_metadata = doc_metadata
                safe_set_chunks(document, chunks_data)
                document.updated_at = get_current_timestamp()
                document.status = DocumentStatus.ready()

                documents_processed += 1
                documents_indexed += 1

                logger.info(
                    f"Created document for repository {repo_full_name} "
                    f"with {len(chunks_data)} chunks"
                )

                # Batch commit every 5 documents (repositories are large)
                if documents_indexed % 5 == 0:
                    logger.info(
                        f"Committing batch: {documents_indexed} GitHub repos processed so far"
                    )
                    await session.commit()

            except Exception as repo_err:
                logger.error(
                    f"Error processing repository {repo_full_name}: {repo_err}",
                    exc_info=True,
                )
                # Mark document as failed with reason (visible in UI)
                try:
                    document.status = DocumentStatus.failed(str(repo_err))
                    document.updated_at = get_current_timestamp()
                except Exception as status_error:
                    logger.error(
                        f"Failed to update document status to failed: {status_error}"
                    )
                errors.append(f"Failed processing {repo_full_name}: {repo_err}")
                documents_failed += 1
                continue

        # CRITICAL: Always update timestamp (even if 0 documents indexed) so Electric SQL syncs
        await update_connector_last_indexed(session, connector, update_last_indexed)

        # Final commit
        logger.info(
            f"Final commit: Total {documents_processed} GitHub repositories processed"
        )
        try:
            await session.commit()
            logger.info(
                "Successfully committed all GitHub document changes to database"
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

        logger.info(
            f"Finished GitHub indexing for connector {connector_id}. "
            f"Created {documents_processed} documents."
        )

        # Log success
        await task_logger.log_task_success(
            log_entry,
            f"Successfully completed GitHub indexing for connector {connector_id}",
            {
                "documents_processed": documents_processed,
                "documents_skipped": documents_skipped,
                "documents_failed": documents_failed,
                "errors_count": len(errors),
                "repo_count": len(repo_full_names_to_index),
                "method": "gitingest",
            },
        )

    except SQLAlchemyError as db_err:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Database error during GitHub indexing for connector {connector_id}",
            str(db_err),
            {"error_type": "SQLAlchemyError"},
        )
        logger.error(
            f"Database error during GitHub indexing for connector {connector_id}: {db_err}"
        )
        errors.append(f"Database error: {db_err}")
        return documents_processed, "; ".join(errors) if errors else str(db_err)

    except Exception as e:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Unexpected error during GitHub indexing for connector {connector_id}",
            str(e),
            {"error_type": type(e).__name__},
        )
        logger.error(
            f"Unexpected error during GitHub indexing for connector {connector_id}: {e}",
            exc_info=True,
        )
        errors.append(f"Unexpected error: {e}")
        return documents_processed, "; ".join(errors) if errors else str(e)

    error_message = "; ".join(errors) if errors else None
    return documents_processed, error_message


async def _simple_chunk_content(content: str, chunk_size: int = 4000) -> list:
    """
    Simple fallback chunking when the regular chunker fails.

    Args:
        content: The content to chunk
        chunk_size: Size of each chunk in characters

    Returns:
        List of chunk dictionaries with content and embedding
    """
    from app.db import Chunk

    chunks = []
    for i in range(0, len(content), chunk_size):
        chunk_text = content[i : i + chunk_size]
        if chunk_text.strip():
            chunks.append(
                Chunk(
                    content=chunk_text,
                    embedding=embed_text(chunk_text),
                )
            )

    return chunks
