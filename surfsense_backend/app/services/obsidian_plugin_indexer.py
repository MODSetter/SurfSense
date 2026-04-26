"""
Obsidian plugin indexer service.

Bridges the SurfSense Obsidian plugin's HTTP payloads
(see ``app/schemas/obsidian_plugin.py``) into the shared
``IndexingPipelineService``.

Responsibilities:

- ``upsert_note``  — push one note through the indexing pipeline; respects
  unchanged content (skip) and version-snapshots existing rows before
  rewrite.
- ``rename_note``  — rewrite path-derived fields (path metadata,
  ``unique_identifier_hash``, ``source_url``) without re-indexing content.
- ``delete_note``  — soft delete with a tombstone in ``document_metadata``
  so reconciliation can distinguish "user explicitly killed this in the UI"
  from "plugin hasn't synced yet".
- ``get_manifest`` — return ``{path: {hash, mtime, size}}`` for every
  non-deleted note belonging to a vault, used by the plugin's reconcile
  pass on ``onload``.

Design notes
------------

The plugin's content hash and the backend's ``content_hash`` are computed
differently (plugin uses raw SHA-256 of the markdown body; backend salts
with ``search_space_id``). We persist the plugin's hash in
``document_metadata['plugin_content_hash']`` so the manifest endpoint can
return what the plugin sent — that's the only number the plugin can
compare without re-downloading content.
"""

from __future__ import annotations

import base64
import contextlib
import logging
import os
import tempfile
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import (
    Document,
    DocumentStatus,
    DocumentType,
    SearchSourceConnector,
)
from app.indexing_pipeline.connector_document import ConnectorDocument
from app.indexing_pipeline.indexing_pipeline_service import IndexingPipelineService
from app.schemas.obsidian_plugin import (
    ManifestEntry,
    ManifestResponse,
    NotePayload,
)
from app.utils.document_converters import generate_unique_identifier_hash
from app.utils.document_versioning import create_version_snapshot

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _vault_path_unique_id(vault_id: str, path: str) -> str:
    """Stable identifier for a note. Vault-scoped so the same path under two
    different vaults doesn't collide."""
    return f"{vault_id}:{path}"


def _build_source_url(vault_name: str, path: str) -> str:
    """Build the ``obsidian://`` deep link for the web UI's "Open in Obsidian"
    button. Both segments are URL-encoded because vault names and paths can
    contain spaces, ``#``, ``?``, etc.
    """
    return (
        "obsidian://open"
        f"?vault={quote(vault_name, safe='')}"
        f"&file={quote(path, safe='')}"
    )


def _build_metadata(
    payload: NotePayload,
    *,
    vault_name: str,
    connector_id: int,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Flatten the rich plugin payload into the JSONB ``document_metadata``
    column. Keys here are what the chat UI / search UI surface to users.
    """
    meta: dict[str, Any] = {
        "source": "plugin",
        "vault_id": payload.vault_id,
        "vault_name": vault_name,
        "file_path": payload.path,
        "file_name": payload.name,
        "extension": payload.extension,
        "frontmatter": payload.frontmatter,
        "tags": payload.tags,
        "headings": [h.model_dump() for h in payload.headings],
        "outgoing_links": payload.resolved_links,
        "unresolved_links": payload.unresolved_links,
        "embeds": payload.embeds,
        "aliases": payload.aliases,
        "plugin_content_hash": payload.content_hash,
        "plugin_file_size": payload.size,
        "mtime": payload.mtime.isoformat(),
        "ctime": payload.ctime.isoformat(),
        "connector_id": connector_id,
        "url": _build_source_url(vault_name, payload.path),
    }
    if payload.is_binary:
        meta["is_binary"] = True
        meta["mime_type"] = payload.mime_type
    if extra:
        meta.update(extra)
    return meta


def _build_document_string(
    payload: NotePayload, vault_name: str, *, content_override: str | None = None
) -> str:
    """Compose the indexable string the pipeline embeds and chunks.

    Mirrors the legacy obsidian indexer's METADATA + CONTENT framing so
    existing search relevance heuristics keep working unchanged.
    """
    tags_line = ", ".join(payload.tags) if payload.tags else "None"
    links_line = ", ".join(payload.resolved_links) if payload.resolved_links else "None"
    body = payload.content if content_override is None else content_override
    return (
        "<METADATA>\n"
        f"Title: {payload.name}\n"
        f"Vault: {vault_name}\n"
        f"Path: {payload.path}\n"
        f"Tags: {tags_line}\n"
        f"Links to: {links_line}\n"
        "</METADATA>\n\n"
        "<CONTENT>\n"
        f"{body}\n"
        "</CONTENT>\n"
    )


async def _extract_binary_attachment_markdown(
    payload: NotePayload, *, vision_llm
) -> tuple[str, dict[str, Any]]:
    try:
        raw_bytes = base64.b64decode(payload.binary_base64, validate=True)
    except Exception:
        logger.warning("obsidian attachment payload had invalid base64: %s", payload.path)
        return "", {"attachment_extraction_status": "invalid_binary_payload"}

    suffix = f".{payload.extension.lstrip('.')}"
    temp_path: str | None = None
    filename = payload.path.rsplit("/", 1)[-1] or payload.name
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(raw_bytes)
            temp_path = tmp.name

        result = await _run_etl_extract(
            file_path=temp_path,
            filename=filename,
            vision_llm=vision_llm,
        )
        metadata: dict[str, Any] = {
            "attachment_extraction_status": "ok",
            "attachment_etl_service": result.etl_service,
            "attachment_content_type": result.content_type,
        }
        return result.markdown_content, metadata
    except Exception as exc:
        logger.warning(
            "obsidian attachment ETL failed for %s: %s", payload.path, exc, exc_info=True
        )
        return "", {
            "attachment_extraction_status": "etl_failed",
            "attachment_extraction_error": str(exc)[:300],
        }
    finally:
        if temp_path and os.path.exists(temp_path):
            with contextlib.suppress(Exception):
                os.unlink(temp_path)


async def _run_etl_extract(*, file_path: str, filename: str, vision_llm):
    """Lazy-load ETL dependencies to avoid module-import cycles."""
    from app.etl_pipeline.etl_document import EtlRequest
    from app.etl_pipeline.etl_pipeline_service import EtlPipelineService

    return await EtlPipelineService(vision_llm=vision_llm).extract(
        EtlRequest(file_path=file_path, filename=filename)
    )


def _is_image_attachment(payload: NotePayload) -> bool:
    ext = payload.extension.lower().lstrip(".")
    return ext in {"png", "jpg", "jpeg", "gif", "webp", "svg"}


async def _resolve_attachment_vision_llm(
    session: AsyncSession,
    *,
    connector: SearchSourceConnector,
    search_space_id: int,
    payload: NotePayload,
):
    """Match connector indexers: only fetch vision LLM for image attachments
    when the connector has vision indexing enabled."""
    if not payload.is_binary:
        return None
    if not _is_image_attachment(payload):
        return None
    if not getattr(connector, "enable_vision_llm", False):
        return None

    from app.services.llm_service import get_vision_llm

    return await get_vision_llm(session, search_space_id)


async def _resolve_summary_llm(
    session: AsyncSession, *, user_id: str, search_space_id: int, should_summarize: bool
):
    """Fetch summary LLM only when indexing summary is enabled."""
    if not should_summarize:
        return None

    from app.services.llm_service import get_user_long_context_llm

    return await get_user_long_context_llm(session, user_id, search_space_id)


def _require_extracted_attachment_content(
    *, content: str, etl_meta: dict[str, Any], path: str
) -> str:
    extracted = content.strip()
    if extracted:
        return extracted

    status = etl_meta.get("attachment_extraction_status", "unknown")
    reason = etl_meta.get("attachment_extraction_error")
    if reason:
        raise RuntimeError(
            f"Attachment extraction failed for {path} ({status}): {reason}"
        )
    raise RuntimeError(f"Attachment extraction failed for {path} ({status})")


async def _find_existing_document(
    session: AsyncSession,
    *,
    search_space_id: int,
    vault_id: str,
    path: str,
) -> Document | None:
    unique_id = _vault_path_unique_id(vault_id, path)
    uid_hash = generate_unique_identifier_hash(
        DocumentType.OBSIDIAN_CONNECTOR,
        unique_id,
        search_space_id,
    )
    result = await session.execute(
        select(Document).where(Document.unique_identifier_hash == uid_hash)
    )
    return result.scalars().first()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def upsert_note(
    session: AsyncSession,
    *,
    connector: SearchSourceConnector,
    payload: NotePayload,
    user_id: str,
) -> Document:
    """Index or refresh a single note pushed by the plugin.

    Returns the resulting ``Document`` (whether newly created, updated, or
    a skip-because-unchanged hit).
    """
    vault_name: str = (connector.config or {}).get("vault_name") or "Vault"
    search_space_id = connector.search_space_id

    existing = await _find_existing_document(
        session,
        search_space_id=search_space_id,
        vault_id=payload.vault_id,
        path=payload.path,
    )

    plugin_hash = payload.content_hash
    if existing is not None:
        existing_meta = existing.document_metadata or {}
        was_tombstoned = bool(existing_meta.get("deleted_at"))

        if (
            not was_tombstoned
            and existing_meta.get("plugin_content_hash") == plugin_hash
            and DocumentStatus.is_state(existing.status, DocumentStatus.READY)
        ):
            return existing

        try:
            await create_version_snapshot(session, existing)
        except Exception:
            logger.debug(
                "version snapshot failed for obsidian doc %s",
                existing.id,
                exc_info=True,
            )

    content_for_index = payload.content
    extra_meta: dict[str, Any] = {}
    vision_llm = None
    if payload.is_binary:
        vision_llm = await _resolve_attachment_vision_llm(
            session,
            connector=connector,
            search_space_id=search_space_id,
            payload=payload,
        )
        content_for_index, etl_meta = await _extract_binary_attachment_markdown(
            payload, vision_llm=vision_llm
        )
        extra_meta.update(etl_meta)
        # Strict KB behavior: do not index metadata-only attachments.
        content_for_index = _require_extracted_attachment_content(
            content=content_for_index,
            etl_meta=etl_meta,
            path=payload.path,
        )

    llm = await _resolve_summary_llm(
        session,
        user_id=str(user_id),
        search_space_id=search_space_id,
        should_summarize=connector.enable_summary,
    )

    document_string = _build_document_string(
        payload, vault_name, content_override=content_for_index
    )
    metadata = _build_metadata(
        payload,
        vault_name=vault_name,
        connector_id=connector.id,
        extra=extra_meta,
    )

    connector_doc = ConnectorDocument(
        title=payload.name,
        source_markdown=document_string,
        unique_id=_vault_path_unique_id(payload.vault_id, payload.path),
        document_type=DocumentType.OBSIDIAN_CONNECTOR,
        search_space_id=search_space_id,
        connector_id=connector.id,
        created_by_id=str(user_id),
        should_summarize=connector.enable_summary,
        fallback_summary=f"Obsidian Note: {payload.name}\n\n{content_for_index}",
        metadata=metadata,
    )

    pipeline = IndexingPipelineService(session)
    prepared = await pipeline.prepare_for_indexing([connector_doc])
    if not prepared:
        if existing is not None:
            return existing
        raise RuntimeError(f"Indexing pipeline rejected obsidian note {payload.path}")

    document = prepared[0]

    return await pipeline.index(document, connector_doc, llm)


async def rename_note(
    session: AsyncSession,
    *,
    connector: SearchSourceConnector,
    old_path: str,
    new_path: str,
    vault_id: str,
) -> Document | None:
    """Rewrite path-derived columns without re-indexing content.

    Returns the updated document, or ``None`` if no row matched the
    ``old_path`` (this happens when the plugin is renaming a file that was
    never synced — safe to ignore, the next ``sync`` will create it under
    the new path).
    """
    vault_name: str = (connector.config or {}).get("vault_name") or "Vault"
    search_space_id = connector.search_space_id

    existing = await _find_existing_document(
        session,
        search_space_id=search_space_id,
        vault_id=vault_id,
        path=old_path,
    )
    if existing is None:
        return None

    new_unique_id = _vault_path_unique_id(vault_id, new_path)
    new_uid_hash = generate_unique_identifier_hash(
        DocumentType.OBSIDIAN_CONNECTOR,
        new_unique_id,
        search_space_id,
    )

    collision = await session.execute(
        select(Document).where(
            and_(
                Document.unique_identifier_hash == new_uid_hash,
                Document.id != existing.id,
            )
        )
    )
    collision_row = collision.scalars().first()
    if collision_row is not None:
        logger.warning(
            "obsidian rename target already exists "
            "(vault=%s old=%s new=%s); skipping rename so the next /sync "
            "can resolve the conflict via content_hash",
            vault_id,
            old_path,
            new_path,
        )
        return existing

    new_filename = new_path.rsplit("/", 1)[-1]
    new_stem = new_filename.rsplit(".", 1)[0] if "." in new_filename else new_filename

    existing.unique_identifier_hash = new_uid_hash
    existing.title = new_stem

    meta = dict(existing.document_metadata or {})
    meta["file_path"] = new_path
    meta["file_name"] = new_stem
    meta["url"] = _build_source_url(vault_name, new_path)
    existing.document_metadata = meta
    existing.updated_at = datetime.now(UTC)

    await session.commit()
    return existing


async def delete_note(
    session: AsyncSession,
    *,
    connector: SearchSourceConnector,
    vault_id: str,
    path: str,
) -> bool:
    """Soft-delete via tombstone in ``document_metadata``.

    The row is *not* removed and chunks are *not* dropped, so existing
    citations in chat threads remain resolvable. The manifest endpoint
    filters tombstoned rows out, so the plugin's reconcile pass will not
    see this path and won't try to "resurrect" a note the user deleted in
    the SurfSense UI.

    Returns True if a row was tombstoned, False if no matching row existed.
    """
    existing = await _find_existing_document(
        session,
        search_space_id=connector.search_space_id,
        vault_id=vault_id,
        path=path,
    )
    if existing is None:
        return False

    meta = dict(existing.document_metadata or {})
    if meta.get("deleted_at"):
        return True

    meta["deleted_at"] = datetime.now(UTC).isoformat()
    meta["deleted_by_source"] = "plugin"
    existing.document_metadata = meta
    existing.updated_at = datetime.now(UTC)

    await session.commit()
    return True


async def merge_obsidian_connectors(
    session: AsyncSession,
    *,
    source: SearchSourceConnector,
    target: SearchSourceConnector,
) -> None:
    """Fold ``source``'s documents into ``target`` and delete ``source``.

    Triggered when the fingerprint dedup detects two plugin connectors
    pointing at the same vault (e.g. a mobile install raced with iCloud
    hydration and got a partial fingerprint, then caught up). Path
    collisions resolve in favour of ``target`` (the surviving row);
    ``source``'s duplicate documents are hard-deleted along with their
    chunks via the ``cascade='all, delete-orphan'`` on ``Document.chunks``.
    """
    if source.id == target.id:
        return

    target_vault_id = (target.config or {}).get("vault_id")
    target_search_space_id = target.search_space_id
    if not target_vault_id:
        raise RuntimeError("merge target is missing vault_id")

    target_paths_result = await session.execute(
        select(Document).where(
            and_(
                Document.connector_id == target.id,
                Document.document_type == DocumentType.OBSIDIAN_CONNECTOR,
            )
        )
    )
    target_paths: set[str] = set()
    for doc in target_paths_result.scalars().all():
        meta = doc.document_metadata or {}
        path = meta.get("file_path")
        if path:
            target_paths.add(path)

    source_docs_result = await session.execute(
        select(Document).where(
            and_(
                Document.connector_id == source.id,
                Document.document_type == DocumentType.OBSIDIAN_CONNECTOR,
            )
        )
    )

    for doc in source_docs_result.scalars().all():
        meta = dict(doc.document_metadata or {})
        path = meta.get("file_path")
        if not path or path in target_paths:
            await session.delete(doc)
            continue

        new_unique_id = _vault_path_unique_id(target_vault_id, path)
        new_uid_hash = generate_unique_identifier_hash(
            DocumentType.OBSIDIAN_CONNECTOR,
            new_unique_id,
            target_search_space_id,
        )
        meta["vault_id"] = target_vault_id
        meta["connector_id"] = target.id
        doc.document_metadata = meta
        doc.connector_id = target.id
        doc.search_space_id = target_search_space_id
        doc.unique_identifier_hash = new_uid_hash
        target_paths.add(path)

    await session.flush()
    await session.delete(source)


async def get_manifest(
    session: AsyncSession,
    *,
    connector: SearchSourceConnector,
    vault_id: str,
) -> ManifestResponse:
    """Return ``{path: {hash, mtime, size}}`` for every non-deleted note in
    this vault.

    The plugin compares this against its local vault on every ``onload`` to
    catch up edits made while offline. Rows missing ``plugin_content_hash``
    (e.g. tombstoned, or somehow indexed without going through this
    service) are excluded so the plugin doesn't get confused by partial
    data.
    """
    result = await session.execute(
        select(Document).where(
            and_(
                Document.search_space_id == connector.search_space_id,
                Document.connector_id == connector.id,
                Document.document_type == DocumentType.OBSIDIAN_CONNECTOR,
            )
        )
    )

    items: dict[str, ManifestEntry] = {}
    for doc in result.scalars().all():
        meta = doc.document_metadata or {}
        if meta.get("deleted_at"):
            continue
        if meta.get("vault_id") != vault_id:
            continue
        path = meta.get("file_path")
        plugin_hash = meta.get("plugin_content_hash")
        mtime_raw = meta.get("mtime")
        if not path or not plugin_hash or not mtime_raw:
            continue
        try:
            mtime = datetime.fromisoformat(mtime_raw)
        except ValueError:
            continue
        size_raw = meta.get("plugin_file_size")
        size = int(size_raw) if isinstance(size_raw, int) else None
        items[path] = ManifestEntry(hash=plugin_hash, mtime=mtime, size=size)

    return ManifestResponse(vault_id=vault_id, items=items)
