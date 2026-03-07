"""
Obsidian connector indexer.

Indexes markdown notes from a local Obsidian vault.
This connector is only available in self-hosted mode.

Implements 2-phase document status updates for real-time UI feedback:
- Phase 1: Create all documents with 'pending' status (visible in UI immediately)
- Phase 2: Process each document: pending → processing → ready/failed
"""

import os
import re
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path

import yaml
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
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
    build_document_metadata_string,
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


def parse_frontmatter(content: str) -> tuple[dict | None, str]:
    """
    Parse YAML frontmatter from markdown content.

    Args:
        content: The full markdown content

    Returns:
        Tuple of (frontmatter dict or None, content without frontmatter)
    """
    if not content.startswith("---"):
        return None, content

    # Find the closing ---
    end_match = re.search(r"\n---\n", content[3:])
    if not end_match:
        return None, content

    frontmatter_str = content[3 : end_match.start() + 3]
    remaining_content = content[end_match.end() + 3 :]

    try:
        frontmatter = yaml.safe_load(frontmatter_str)
        return frontmatter, remaining_content.strip()
    except yaml.YAMLError:
        return None, content


def extract_wiki_links(content: str) -> list[str]:
    """
    Extract [[wiki-style links]] from content.

    Args:
        content: Markdown content

    Returns:
        List of linked note names
    """
    # Match [[link]] or [[link|alias]]
    pattern = r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]"
    matches = re.findall(pattern, content)
    return list(set(matches))


def extract_tags(content: str) -> list[str]:
    """
    Extract #tags from content (both inline and frontmatter).

    Args:
        content: Markdown content

    Returns:
        List of tags (without # prefix)
    """
    # Match #tag but not ## headers
    pattern = r"(?<!\S)#([a-zA-Z][a-zA-Z0-9_/-]*)"
    matches = re.findall(pattern, content)
    return list(set(matches))


def scan_vault(
    vault_path: str,
    exclude_folders: list[str] | None = None,
) -> list[dict]:
    """
    Scan an Obsidian vault for markdown files.

    Args:
        vault_path: Path to the Obsidian vault
        exclude_folders: List of folder names to exclude

    Returns:
        List of file info dicts with path, name, modified time
    """
    if exclude_folders is None:
        exclude_folders = [".trash", ".obsidian", "templates"]

    vault = Path(vault_path)
    if not vault.exists():
        raise ValueError(f"Vault path does not exist: {vault_path}")

    files = []
    for md_file in vault.rglob("*.md"):
        # Check if file is in an excluded folder
        relative_path = md_file.relative_to(vault)
        parts = relative_path.parts

        if any(excluded in parts for excluded in exclude_folders):
            continue

        try:
            stat = md_file.stat()
            files.append(
                {
                    "path": str(md_file),
                    "relative_path": str(relative_path),
                    "name": md_file.stem,
                    "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=UTC),
                    "created_at": datetime.fromtimestamp(stat.st_ctime, tz=UTC),
                    "size": stat.st_size,
                }
            )
        except OSError as e:
            logger.warning(f"Could not stat file {md_file}: {e}")

    return files


async def index_obsidian_vault(
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
    Index notes from a local Obsidian vault.

    This indexer is only available in self-hosted mode as it requires
    direct file system access to the user's Obsidian vault.

    Args:
        session: Database session
        connector_id: ID of the Obsidian connector
        search_space_id: ID of the search space to store documents in
        user_id: ID of the user
        start_date: Start date for filtering (YYYY-MM-DD format) - optional
        end_date: End date for filtering (YYYY-MM-DD format) - optional
        update_last_indexed: Whether to update the last_indexed_at timestamp
        on_heartbeat_callback: Optional callback to update notification during long-running indexing.

    Returns:
        Tuple containing (number of documents indexed, error message or None)
    """
    task_logger = TaskLoggingService(session, search_space_id)

    # Check if self-hosted mode
    if not config.is_self_hosted():
        return 0, "Obsidian connector is only available in self-hosted mode"

    # Log task start
    log_entry = await task_logger.log_task_start(
        task_name="obsidian_vault_indexing",
        source="connector_indexing_task",
        message=f"Starting Obsidian vault indexing for connector {connector_id}",
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
            f"Retrieving Obsidian connector {connector_id} from database",
            {"stage": "connector_retrieval"},
        )

        connector = await get_connector_by_id(
            session, connector_id, SearchSourceConnectorType.OBSIDIAN_CONNECTOR
        )

        if not connector:
            await task_logger.log_task_failure(
                log_entry,
                f"Connector with ID {connector_id} not found or is not an Obsidian connector",
                "Connector not found",
                {"error_type": "ConnectorNotFound"},
            )
            return (
                0,
                f"Connector with ID {connector_id} not found or is not an Obsidian connector",
            )

        # Get vault path from connector config
        vault_path = connector.config.get("vault_path")
        if not vault_path:
            await task_logger.log_task_failure(
                log_entry,
                "Vault path not configured for this connector",
                "Missing vault path",
                {"error_type": "MissingVaultPath"},
            )
            return 0, "Vault path not configured for this connector"

        # Validate vault path exists
        if not os.path.exists(vault_path):
            await task_logger.log_task_failure(
                log_entry,
                f"Vault path does not exist: {vault_path}",
                "Vault path not found",
                {"error_type": "VaultNotFound", "vault_path": vault_path},
            )
            return 0, f"Vault path does not exist: {vault_path}"

        # Get configuration options
        exclude_folders = connector.config.get(
            "exclude_folders", [".trash", ".obsidian", "templates"]
        )
        vault_name = connector.config.get("vault_name") or os.path.basename(vault_path)

        await task_logger.log_task_progress(
            log_entry,
            f"Scanning Obsidian vault: {vault_name}",
            {"stage": "vault_scan", "vault_path": vault_path},
        )

        # Scan vault for markdown files
        try:
            files = scan_vault(vault_path, exclude_folders)
        except Exception as e:
            await task_logger.log_task_failure(
                log_entry,
                f"Failed to scan vault: {e}",
                "Vault scan error",
                {"error_type": "VaultScanError"},
            )
            return 0, f"Failed to scan vault: {e}"

        logger.info(f"Found {len(files)} markdown files in vault")

        await task_logger.log_task_progress(
            log_entry,
            f"Found {len(files)} markdown files to process",
            {"stage": "files_discovered", "file_count": len(files)},
        )

        # Filter by date if provided (handle "undefined" string from frontend)
        # Also handle inverted dates (start > end) by skipping filtering
        start_dt = None
        end_dt = None

        if start_date and start_date != "undefined":
            start_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=UTC)

        if end_date and end_date != "undefined":
            # Make end_date inclusive (end of day)
            end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=UTC)
            end_dt = end_dt.replace(hour=23, minute=59, second=59)

        # Only apply date filtering if dates are valid and in correct order
        if start_dt and end_dt and start_dt > end_dt:
            logger.warning(
                f"start_date ({start_date}) is after end_date ({end_date}), skipping date filter"
            )
        else:
            if start_dt:
                files = [f for f in files if f["modified_at"] >= start_dt]
                logger.info(
                    f"After start_date filter ({start_date}): {len(files)} files"
                )
            if end_dt:
                files = [f for f in files if f["modified_at"] <= end_dt]
                logger.info(f"After end_date filter ({end_date}): {len(files)} files")

        logger.info(f"Processing {len(files)} files after date filtering")

        indexed_count = 0
        skipped_count = 0
        failed_count = 0
        duplicate_content_count = 0

        # Heartbeat tracking - update notification periodically to prevent appearing stuck
        last_heartbeat_time = time.time()

        # =======================================================================
        # PHASE 1: Analyze all files, create pending documents
        # This makes ALL documents visible in the UI immediately with pending status
        # =======================================================================
        files_to_process = []  # List of dicts with document and file data
        new_documents_created = False

        for file_info in files:
            try:
                file_path = file_info["path"]
                relative_path = file_info["relative_path"]

                # Read file content
                try:
                    with open(file_path, encoding="utf-8") as f:
                        content = f.read()
                except UnicodeDecodeError:
                    logger.warning(f"Could not decode file {file_path}, skipping")
                    skipped_count += 1
                    continue

                if not content.strip():
                    logger.debug(f"Empty file {file_path}, skipping")
                    skipped_count += 1
                    continue

                # Parse frontmatter and extract metadata
                frontmatter, body_content = parse_frontmatter(content)
                wiki_links = extract_wiki_links(content)
                tags = extract_tags(content)

                # Get title from frontmatter or filename
                title = file_info["name"]
                if frontmatter:
                    title = frontmatter.get("title", title)
                    # Also extract tags from frontmatter
                    fm_tags = frontmatter.get("tags", [])
                    if isinstance(fm_tags, list):
                        tags = list({*tags, *fm_tags})
                    elif isinstance(fm_tags, str):
                        tags = list({*tags, fm_tags})

                # Generate unique identifier using vault name and relative path
                unique_identifier = f"{vault_name}:{relative_path}"
                unique_identifier_hash = generate_unique_identifier_hash(
                    DocumentType.OBSIDIAN_CONNECTOR,
                    unique_identifier,
                    search_space_id,
                )

                # Generate content hash
                content_hash = generate_content_hash(content, search_space_id)

                # Check for existing document
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
                        logger.debug(f"Note {title} unchanged, skipping")
                        skipped_count += 1
                        continue

                    # Queue existing document for update (will be set to processing in Phase 2)
                    files_to_process.append(
                        {
                            "document": existing_document,
                            "is_new": False,
                            "file_info": file_info,
                            "content": content,
                            "body_content": body_content,
                            "frontmatter": frontmatter,
                            "wiki_links": wiki_links,
                            "tags": tags,
                            "title": title,
                            "relative_path": relative_path,
                            "content_hash": content_hash,
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
                        f"Obsidian note {title} already indexed by another connector "
                        f"(existing document ID: {duplicate_by_content.id}, "
                        f"type: {duplicate_by_content.document_type}). Skipping."
                    )
                    duplicate_content_count += 1
                    skipped_count += 1
                    continue

                # Create new document with PENDING status (visible in UI immediately)
                document = Document(
                    search_space_id=search_space_id,
                    title=title,
                    document_type=DocumentType.OBSIDIAN_CONNECTOR,
                    document_metadata={
                        "vault_name": vault_name,
                        "file_path": relative_path,
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

                files_to_process.append(
                    {
                        "document": document,
                        "is_new": True,
                        "file_info": file_info,
                        "content": content,
                        "body_content": body_content,
                        "frontmatter": frontmatter,
                        "wiki_links": wiki_links,
                        "tags": tags,
                        "title": title,
                        "relative_path": relative_path,
                        "content_hash": content_hash,
                        "unique_identifier_hash": unique_identifier_hash,
                    }
                )

            except Exception as e:
                logger.exception(
                    f"Error in Phase 1 for file {file_info.get('path', 'unknown')}: {e}"
                )
                failed_count += 1
                continue

        # Commit all pending documents - they all appear in UI now
        if new_documents_created:
            logger.info(
                f"Phase 1: Committing {len([f for f in files_to_process if f['is_new']])} pending documents"
            )
            await session.commit()

        # =======================================================================
        # PHASE 2: Process each document one by one
        # Each document transitions: pending → processing → ready/failed
        # =======================================================================
        logger.info(f"Phase 2: Processing {len(files_to_process)} documents")

        # Get LLM for summarization
        long_context_llm = await get_user_long_context_llm(
            session, user_id, search_space_id
        )

        for item in files_to_process:
            # Send heartbeat periodically
            if on_heartbeat_callback:
                current_time = time.time()
                if current_time - last_heartbeat_time >= HEARTBEAT_INTERVAL_SECONDS:
                    await on_heartbeat_callback(indexed_count)
                    last_heartbeat_time = current_time

            document = item["document"]
            try:
                # Set to PROCESSING and commit - shows "processing" in UI for THIS document only
                document.status = DocumentStatus.processing()
                await session.commit()

                # Extract data from item
                title = item["title"]
                relative_path = item["relative_path"]
                content = item["content"]
                body_content = item["body_content"]
                frontmatter = item["frontmatter"]
                wiki_links = item["wiki_links"]
                tags = item["tags"]
                content_hash = item["content_hash"]
                file_info = item["file_info"]

                # Build metadata
                document_metadata = {
                    "vault_name": vault_name,
                    "file_path": relative_path,
                    "tags": tags,
                    "outgoing_links": wiki_links,
                    "frontmatter": frontmatter,
                    "modified_at": file_info["modified_at"].isoformat(),
                    "created_at": file_info["created_at"].isoformat(),
                    "word_count": len(body_content.split()),
                }

                # Build document content with metadata
                metadata_sections = [
                    (
                        "METADATA",
                        [
                            f"Title: {title}",
                            f"Vault: {vault_name}",
                            f"Path: {relative_path}",
                            f"Tags: {', '.join(tags) if tags else 'None'}",
                            f"Links to: {', '.join(wiki_links) if wiki_links else 'None'}",
                        ],
                    ),
                    ("CONTENT", [body_content]),
                ]
                document_string = build_document_metadata_string(metadata_sections)

                # Generate summary
                summary_content = ""
                if long_context_llm and connector.enable_summary:
                    summary_content, _ = await generate_document_summary(
                        document_string,
                        long_context_llm,
                        document_metadata,
                    )

                # Generate embedding
                embedding = embed_text(document_string)

                # Add URL and summary to metadata
                document_metadata["url"] = f"obsidian://{vault_name}/{relative_path}"
                document_metadata["summary"] = summary_content
                document_metadata["connector_id"] = connector_id

                # Create chunks
                chunks = await create_document_chunks(document_string)

                # Update document to READY with actual content
                document.title = title
                document.content = document_string
                document.content_hash = content_hash
                document.embedding = embedding
                document.document_metadata = document_metadata
                safe_set_chunks(document, chunks)
                document.updated_at = get_current_timestamp()
                document.status = DocumentStatus.ready()

                indexed_count += 1

                # Batch commit every 10 documents (for ready status updates)
                if indexed_count % 10 == 0:
                    logger.info(
                        f"Committing batch: {indexed_count} Obsidian notes processed so far"
                    )
                    await session.commit()

            except Exception as e:
                logger.exception(
                    f"Error processing file {item.get('file_info', {}).get('path', 'unknown')}: {e}"
                )
                # Mark document as failed with reason (visible in UI)
                try:
                    document.status = DocumentStatus.failed(str(e))
                    document.updated_at = get_current_timestamp()
                except Exception as status_error:
                    logger.error(
                        f"Failed to update document status to failed: {status_error}"
                    )
                failed_count += 1
                continue

        # CRITICAL: Always update timestamp (even if 0 documents indexed) so Electric SQL syncs
        await update_connector_last_indexed(session, connector, update_last_indexed)

        # Final commit for any remaining documents not yet committed in batches
        logger.info(f"Final commit: Total {indexed_count} Obsidian notes processed")
        try:
            await session.commit()
            logger.info(
                "Successfully committed all Obsidian document changes to database"
            )
        except Exception as e:
            # Handle any remaining integrity errors gracefully (race conditions, etc.)
            if (
                "duplicate key value violates unique constraint" in str(e).lower()
                or "uniqueviolationerror" in str(e).lower()
            ):
                logger.warning(
                    f"Duplicate content_hash detected during final commit. "
                    f"This may occur if the same note was indexed by multiple connectors. "
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
        if failed_count > 0:
            warning_parts.append(f"{failed_count} failed")
        warning_message = ", ".join(warning_parts) if warning_parts else None

        total_processed = indexed_count

        await task_logger.log_task_success(
            log_entry,
            f"Successfully completed Obsidian vault indexing for connector {connector_id}",
            {
                "notes_processed": total_processed,
                "documents_indexed": indexed_count,
                "documents_skipped": skipped_count,
                "documents_failed": failed_count,
                "duplicate_content_count": duplicate_content_count,
            },
        )

        logger.info(
            f"Obsidian vault indexing completed: {indexed_count} ready, "
            f"{skipped_count} skipped, {failed_count} failed "
            f"({duplicate_content_count} duplicate content)"
        )
        return total_processed, warning_message

    except SQLAlchemyError as e:
        logger.exception(f"Database error during Obsidian indexing: {e}")
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Database error during Obsidian indexing: {e}",
            "Database error",
            {"error_type": "SQLAlchemyError"},
        )
        return 0, f"Database error: {e}"

    except Exception as e:
        logger.exception(f"Error during Obsidian indexing: {e}")
        await task_logger.log_task_failure(
            log_entry,
            f"Error during Obsidian indexing: {e}",
            "Unexpected error",
            {"error_type": type(e).__name__},
        )
        return 0, str(e)
