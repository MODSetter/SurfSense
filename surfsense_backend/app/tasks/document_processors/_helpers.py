"""
Document helper functions for deduplication, migration, and connector updates.

Provides reusable logic shared across file processors and ETL strategies.
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Document, DocumentStatus, DocumentType
from app.utils.document_converters import generate_unique_identifier_hash

from .base import (
    check_document_by_unique_identifier,
    check_duplicate_document,
)

# ---------------------------------------------------------------------------
# Unique identifier helpers
# ---------------------------------------------------------------------------


def get_google_drive_unique_identifier(
    connector: dict | None,
    filename: str,
    search_space_id: int,
) -> tuple[str, str | None]:
    """
    Get unique identifier hash, using file_id for Google Drive (stable across renames).

    Returns:
        Tuple of (primary_hash, legacy_hash or None).
        For Google Drive: (file_id-based hash, filename-based hash for migration).
        For other sources: (filename-based hash, None).
    """
    if connector and connector.get("type") == DocumentType.GOOGLE_DRIVE_FILE:
        metadata = connector.get("metadata", {})
        file_id = metadata.get("google_drive_file_id")

        if file_id:
            primary_hash = generate_unique_identifier_hash(
                DocumentType.GOOGLE_DRIVE_FILE, file_id, search_space_id
            )
            legacy_hash = generate_unique_identifier_hash(
                DocumentType.GOOGLE_DRIVE_FILE, filename, search_space_id
            )
            return primary_hash, legacy_hash

    primary_hash = generate_unique_identifier_hash(
        DocumentType.FILE, filename, search_space_id
    )
    return primary_hash, None


# ---------------------------------------------------------------------------
# Document deduplication and migration
# ---------------------------------------------------------------------------


async def handle_existing_document_update(
    session: AsyncSession,
    existing_document: Document,
    content_hash: str,
    connector: dict | None,
    filename: str,
    primary_hash: str,
) -> tuple[bool, Document | None]:
    """
    Handle update logic for an existing document.

    Returns:
        Tuple of (should_skip_processing, document_to_return):
        - (True, document): Content unchanged, return existing document
        - (False, None): Content changed, needs re-processing
    """
    if existing_document.unique_identifier_hash != primary_hash:
        existing_document.unique_identifier_hash = primary_hash
        logging.info(f"Migrated document to file_id-based identifier: {filename}")

    if existing_document.content_hash == content_hash:
        if connector and connector.get("type") == DocumentType.GOOGLE_DRIVE_FILE:
            connector_metadata = connector.get("metadata", {})
            new_name = connector_metadata.get("google_drive_file_name")
            doc_metadata = existing_document.document_metadata or {}
            old_name = doc_metadata.get("FILE_NAME") or doc_metadata.get(
                "google_drive_file_name"
            )

            if new_name and old_name and old_name != new_name:
                from sqlalchemy.orm.attributes import flag_modified

                existing_document.title = new_name
                if not existing_document.document_metadata:
                    existing_document.document_metadata = {}
                existing_document.document_metadata["FILE_NAME"] = new_name
                existing_document.document_metadata["google_drive_file_name"] = new_name
                flag_modified(existing_document, "document_metadata")
                await session.commit()
                logging.info(
                    f"File renamed in Google Drive: '{old_name}' → '{new_name}' "
                    f"(no re-processing needed)"
                )

        logging.info(f"Document for file {filename} unchanged. Skipping.")
        return True, existing_document

    # Content has changed — guard against content_hash collision before
    # expensive ETL processing.
    collision_doc = await check_duplicate_document(session, content_hash)
    if collision_doc and collision_doc.id != existing_document.id:
        logging.warning(
            "Content-hash collision for %s: identical content exists in "
            "document #%s (%s). Skipping re-processing.",
            filename,
            collision_doc.id,
            collision_doc.document_type,
        )
        if DocumentStatus.is_state(
            existing_document.status, DocumentStatus.PENDING
        ) or DocumentStatus.is_state(
            existing_document.status, DocumentStatus.PROCESSING
        ):
            await session.delete(existing_document)
            await session.commit()
            return True, None

        return True, existing_document

    logging.info(f"Content changed for file {filename}. Updating document.")
    return False, None


async def find_existing_document_with_migration(
    session: AsyncSession,
    primary_hash: str,
    legacy_hash: str | None,
    content_hash: str | None = None,
) -> Document | None:
    """
    Find existing document, checking primary hash, legacy hash, and content_hash.

    Supports migration from filename-based to file_id-based hashing for
    Google Drive files, with content_hash fallback for cross-source dedup.
    """
    existing_document = await check_document_by_unique_identifier(session, primary_hash)

    if not existing_document and legacy_hash:
        existing_document = await check_document_by_unique_identifier(
            session, legacy_hash
        )
        if existing_document:
            logging.info(
                "Found legacy document (filename-based hash), "
                "will migrate to file_id-based hash"
            )

    if not existing_document and content_hash:
        existing_document = await check_duplicate_document(session, content_hash)
        if existing_document:
            logging.info(
                f"Found duplicate content from different source (content_hash match). "
                f"Original document ID: {existing_document.id}, "
                f"type: {existing_document.document_type}"
            )

    return existing_document


# ---------------------------------------------------------------------------
# Connector helpers
# ---------------------------------------------------------------------------


async def update_document_from_connector(
    document: Document | None,
    connector: dict | None,
    session: AsyncSession,
) -> None:
    """Update document type, metadata, and connector_id from connector info."""
    if not document or not connector:
        return
    if "type" in connector:
        document.document_type = connector["type"]
    if "metadata" in connector:
        if not document.document_metadata:
            document.document_metadata = connector["metadata"]
        else:
            merged = {**document.document_metadata, **connector["metadata"]}
            document.document_metadata = merged
    if "connector_id" in connector:
        document.connector_id = connector["connector_id"]
    await session.commit()
