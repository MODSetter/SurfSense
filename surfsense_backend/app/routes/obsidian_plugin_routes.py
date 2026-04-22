"""Obsidian plugin ingestion routes (``/api/v1/obsidian/*``).

Wire surface for the ``surfsense_obsidian/`` plugin. Versioning anchor is
the ``/api/v1/`` URL prefix; additive feature detection rides the
``capabilities`` array on /health and /connect.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, case, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db import (
    Document,
    DocumentType,
    SearchSourceConnector,
    SearchSourceConnectorType,
    SearchSpace,
    User,
    get_async_session,
)
from app.schemas.obsidian_plugin import (
    ConnectRequest,
    ConnectResponse,
    DeleteAck,
    DeleteAckItem,
    DeleteBatchRequest,
    HealthResponse,
    ManifestResponse,
    RenameAck,
    RenameAckItem,
    RenameBatchRequest,
    StatsResponse,
    SyncAck,
    SyncAckItem,
    SyncBatchRequest,
)
from app.services.notification_service import NotificationService
from app.services.obsidian_plugin_indexer import (
    delete_note,
    get_manifest,
    merge_obsidian_connectors,
    rename_note,
    upsert_note,
)
from app.tasks.celery_tasks.obsidian_tasks import index_obsidian_attachment_task
from app.users import current_active_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/obsidian", tags=["obsidian-plugin"])


# Plugins feature-gate on these. Add entries, never rename or remove.
OBSIDIAN_CAPABILITIES: list[str] = ["sync", "rename", "delete", "manifest", "stats"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_handshake() -> dict[str, object]:
    return {"capabilities": list(OBSIDIAN_CAPABILITIES)}


def _connector_type_value(connector: SearchSourceConnector) -> str:
    connector_type = connector.connector_type
    if hasattr(connector_type, "value"):
        return str(connector_type.value)
    return str(connector_type)


async def _start_obsidian_sync_notification(
    session: AsyncSession,
    *,
    user: User,
    connector: SearchSourceConnector,
    total_count: int,
):
    """Create/update the rolling inbox item for Obsidian plugin sync.

    Obsidian sync is continuous and batched, so we keep one stable
    operation_id per connector instead of creating a new notification per batch.
    """
    handler = NotificationService.connector_indexing
    operation_id = f"obsidian_sync_connector_{connector.id}"
    connector_name = connector.name or "Obsidian"
    notification = await handler.find_or_create_notification(
        session=session,
        user_id=user.id,
        operation_id=operation_id,
        title=f"Syncing: {connector_name}",
        message="Syncing from Obsidian plugin",
        search_space_id=connector.search_space_id,
        initial_metadata={
            "connector_id": connector.id,
            "connector_name": connector_name,
            "connector_type": _connector_type_value(connector),
            "sync_stage": "processing",
            "indexed_count": 0,
            "failed_count": 0,
            "total_count": total_count,
            "source": "obsidian_plugin",
        },
    )
    return await handler.update_notification(
        session=session,
        notification=notification,
        status="in_progress",
        metadata_updates={
            "sync_stage": "processing",
            "total_count": total_count,
        },
    )


async def _finish_obsidian_sync_notification(
    session: AsyncSession,
    *,
    notification,
    indexed: int,
    failed: int,
):
    """Mark the rolling Obsidian sync inbox item complete or failed."""
    handler = NotificationService.connector_indexing
    connector_name = notification.notification_metadata.get(
        "connector_name", "Obsidian"
    )
    if failed > 0 and indexed == 0:
        title = f"Failed: {connector_name}"
        message = (
            f"Sync failed: {failed} file(s) failed"
            if failed > 1
            else "Sync failed: 1 file failed"
        )
        status_value = "failed"
        stage = "failed"
    else:
        title = f"Ready: {connector_name}"
        if failed > 0:
            message = f"Partially synced: {indexed} file(s) synced, {failed} failed."
        elif indexed == 0:
            message = "Already up to date!"
        elif indexed == 1:
            message = "Now searchable! 1 file synced."
        else:
            message = f"Now searchable! {indexed} files synced."
        status_value = "completed"
        stage = "completed"

    await handler.update_notification(
        session=session,
        notification=notification,
        title=title,
        message=message,
        status=status_value,
        metadata_updates={
            "indexed_count": indexed,
            "failed_count": failed,
            "sync_stage": stage,
        },
    )


async def _resolve_vault_connector(
    session: AsyncSession,
    *,
    user: User,
    vault_id: str,
) -> SearchSourceConnector:
    """Find the OBSIDIAN_CONNECTOR row that owns ``vault_id`` for this user."""
    # ``config`` is core ``JSON`` (not ``JSONB``); ``as_string()`` is the
    # cross-dialect equivalent of ``.astext`` and compiles to ``->>``.
    stmt = select(SearchSourceConnector).where(
        and_(
            SearchSourceConnector.user_id == user.id,
            SearchSourceConnector.connector_type
            == SearchSourceConnectorType.OBSIDIAN_CONNECTOR,
            SearchSourceConnector.config["vault_id"].as_string() == vault_id,
            SearchSourceConnector.config["source"].as_string() == "plugin",
        )
    )

    connector = (await session.execute(stmt)).scalars().first()
    if connector is not None:
        return connector

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "code": "VAULT_NOT_REGISTERED",
            "message": (
                "No Obsidian plugin connector found for this vault. "
                "Call POST /obsidian/connect first."
            ),
            "vault_id": vault_id,
        },
    )


def _queue_obsidian_attachment(
    *, connector_id: int, note_payload: dict, user_id: str
) -> None:
    """Enqueue one non-markdown Obsidian note for background ETL/indexing."""
    index_obsidian_attachment_task.delay(
        connector_id=connector_id,
        payload_data=note_payload,
        user_id=user_id,
    )


async def _ensure_search_space_access(
    session: AsyncSession,
    *,
    user: User,
    search_space_id: int,
) -> SearchSpace:
    """Owner-only access to the search space (shared spaces are a follow-up)."""
    result = await session.execute(
        select(SearchSpace).where(
            and_(SearchSpace.id == search_space_id, SearchSpace.user_id == user.id)
        )
    )
    space = result.scalars().first()
    if space is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "SEARCH_SPACE_FORBIDDEN",
                "message": "You don't own that search space.",
            },
        )
    return space


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/health", response_model=HealthResponse)
async def obsidian_health(
    user: User = Depends(current_active_user),
) -> HealthResponse:
    """Return the API contract handshake; plugin caches it per onload."""
    return HealthResponse(
        **_build_handshake(),
        server_time_utc=datetime.now(UTC),
    )


async def _find_by_vault_id(
    session: AsyncSession, *, user_id, vault_id: str
) -> SearchSourceConnector | None:
    stmt = select(SearchSourceConnector).where(
        and_(
            SearchSourceConnector.user_id == user_id,
            SearchSourceConnector.connector_type
            == SearchSourceConnectorType.OBSIDIAN_CONNECTOR,
            SearchSourceConnector.config["source"].as_string() == "plugin",
            SearchSourceConnector.config["vault_id"].as_string() == vault_id,
        )
    )
    return (await session.execute(stmt)).scalars().first()


async def _find_by_fingerprint(
    session: AsyncSession, *, user_id, vault_fingerprint: str
) -> SearchSourceConnector | None:
    stmt = select(SearchSourceConnector).where(
        and_(
            SearchSourceConnector.user_id == user_id,
            SearchSourceConnector.connector_type
            == SearchSourceConnectorType.OBSIDIAN_CONNECTOR,
            SearchSourceConnector.config["source"].as_string() == "plugin",
            SearchSourceConnector.config["vault_fingerprint"].as_string()
            == vault_fingerprint,
        )
    )
    return (await session.execute(stmt)).scalars().first()


def _build_config(payload: ConnectRequest, *, now_iso: str) -> dict[str, object]:
    return {
        "vault_id": payload.vault_id,
        "vault_name": payload.vault_name,
        "vault_fingerprint": payload.vault_fingerprint,
        "source": "plugin",
        "last_connect_at": now_iso,
    }


def _display_name(vault_name: str) -> str:
    return f"Obsidian - {vault_name}"


@router.post("/connect", response_model=ConnectResponse)
async def obsidian_connect(
    payload: ConnectRequest,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> ConnectResponse:
    """Register a vault, refresh an existing one, or adopt another device's row.

    Resolution order:
      1. ``(user_id, vault_id)`` → known device, refresh metadata.
      2. ``(user_id, vault_fingerprint)`` → another device of the same vault,
         caller adopts the surviving ``vault_id``.
      3. Insert a new row.

    Fingerprint collisions on (1) trigger ``merge_obsidian_connectors`` so
    the partial unique index can never produce two live rows for one vault.
    """
    await _ensure_search_space_access(
        session, user=user, search_space_id=payload.search_space_id
    )

    now_iso = datetime.now(UTC).isoformat()
    cfg = _build_config(payload, now_iso=now_iso)
    display_name = _display_name(payload.vault_name)

    existing_by_vid = await _find_by_vault_id(
        session, user_id=user.id, vault_id=payload.vault_id
    )
    if existing_by_vid is not None:
        collision = await _find_by_fingerprint(
            session, user_id=user.id, vault_fingerprint=payload.vault_fingerprint
        )
        if collision is not None and collision.id != existing_by_vid.id:
            await merge_obsidian_connectors(
                session, source=existing_by_vid, target=collision
            )
            collision_cfg = dict(collision.config or {})
            collision_cfg["vault_name"] = payload.vault_name
            collision_cfg["last_connect_at"] = now_iso
            collision.config = collision_cfg
            collision.name = _display_name(payload.vault_name)
            response = ConnectResponse(
                connector_id=collision.id,
                vault_id=collision_cfg["vault_id"],
                search_space_id=collision.search_space_id,
                **_build_handshake(),
            )
            await session.commit()
            return response

        existing_by_vid.name = display_name
        existing_by_vid.config = cfg
        existing_by_vid.search_space_id = payload.search_space_id
        existing_by_vid.is_indexable = False
        response = ConnectResponse(
            connector_id=existing_by_vid.id,
            vault_id=payload.vault_id,
            search_space_id=existing_by_vid.search_space_id,
            **_build_handshake(),
        )
        await session.commit()
        return response

    existing_by_fp = await _find_by_fingerprint(
        session, user_id=user.id, vault_fingerprint=payload.vault_fingerprint
    )
    if existing_by_fp is not None:
        survivor_cfg = dict(existing_by_fp.config or {})
        survivor_cfg["vault_name"] = payload.vault_name
        survivor_cfg["last_connect_at"] = now_iso
        existing_by_fp.config = survivor_cfg
        existing_by_fp.name = display_name
        response = ConnectResponse(
            connector_id=existing_by_fp.id,
            vault_id=survivor_cfg["vault_id"],
            search_space_id=existing_by_fp.search_space_id,
            **_build_handshake(),
        )
        await session.commit()
        return response

    # ON CONFLICT DO NOTHING matches any unique index (vault_id OR
    # fingerprint), so concurrent first-time connects from two devices
    # of the same vault never raise IntegrityError — the loser just
    # gets an empty RETURNING and falls through to re-fetch the winner.
    insert_stmt = (
        pg_insert(SearchSourceConnector)
        .values(
            name=display_name,
            connector_type=SearchSourceConnectorType.OBSIDIAN_CONNECTOR,
            is_indexable=False,
            config=cfg,
            user_id=user.id,
            search_space_id=payload.search_space_id,
        )
        .on_conflict_do_nothing()
        .returning(
            SearchSourceConnector.id,
            SearchSourceConnector.search_space_id,
        )
    )
    inserted = (await session.execute(insert_stmt)).first()
    if inserted is not None:
        response = ConnectResponse(
            connector_id=inserted.id,
            vault_id=payload.vault_id,
            search_space_id=inserted.search_space_id,
            **_build_handshake(),
        )
        await session.commit()
        return response

    winner = await _find_by_fingerprint(
        session, user_id=user.id, vault_fingerprint=payload.vault_fingerprint
    )
    if winner is None:
        winner = await _find_by_vault_id(
            session, user_id=user.id, vault_id=payload.vault_id
        )
    if winner is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="vault registration conflicted but winning row could not be located",
        )
    response = ConnectResponse(
        connector_id=winner.id,
        vault_id=(winner.config or {})["vault_id"],
        search_space_id=winner.search_space_id,
        **_build_handshake(),
    )
    await session.commit()
    return response


@router.post("/sync", response_model=SyncAck)
async def obsidian_sync(
    payload: SyncBatchRequest,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> SyncAck:
    """Batch-upsert notes; returns per-note ack so the plugin can dequeue/retry."""
    connector = await _resolve_vault_connector(
        session, user=user, vault_id=payload.vault_id
    )
    notification = None
    try:
        notification = await _start_obsidian_sync_notification(
            session, user=user, connector=connector, total_count=len(payload.notes)
        )
    except Exception:
        logger.warning(
            "obsidian sync notification start failed connector=%s user=%s",
            connector.id,
            user.id,
            exc_info=True,
        )

    items: list[SyncAckItem] = []
    indexed = 0
    failed = 0

    for note in payload.notes:
        try:
            if note.is_binary:
                _queue_obsidian_attachment(
                    connector_id=connector.id,
                    note_payload=note.model_dump(mode="json"),
                    user_id=str(user.id),
                )
                indexed += 1
                items.append(SyncAckItem(path=note.path, status="queued"))
                continue

            doc = await upsert_note(
                session, connector=connector, payload=note, user_id=str(user.id)
            )
            indexed += 1
            items.append(SyncAckItem(path=note.path, status="ok", document_id=doc.id))
        except HTTPException:
            raise
        except Exception as exc:
            failed += 1
            logger.exception(
                "obsidian /sync failed for path=%s vault=%s",
                note.path,
                payload.vault_id,
            )
            items.append(
                SyncAckItem(path=note.path, status="error", error=str(exc)[:300])
            )

    if notification is not None:
        try:
            await _finish_obsidian_sync_notification(
                session,
                notification=notification,
                indexed=indexed,
                failed=failed,
            )
        except Exception:
            logger.warning(
                "obsidian sync notification finish failed connector=%s user=%s",
                connector.id,
                user.id,
                exc_info=True,
            )

    return SyncAck(
        vault_id=payload.vault_id,
        indexed=indexed,
        failed=failed,
        items=items,
    )


@router.post("/rename", response_model=RenameAck)
async def obsidian_rename(
    payload: RenameBatchRequest,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> RenameAck:
    """Apply a batch of vault rename events."""
    connector = await _resolve_vault_connector(
        session, user=user, vault_id=payload.vault_id
    )

    items: list[RenameAckItem] = []
    renamed = 0
    missing = 0

    for item in payload.renames:
        try:
            doc = await rename_note(
                session,
                connector=connector,
                old_path=item.old_path,
                new_path=item.new_path,
                vault_id=payload.vault_id,
            )
            if doc is None:
                missing += 1
                items.append(
                    RenameAckItem(
                        old_path=item.old_path,
                        new_path=item.new_path,
                        status="missing",
                    )
                )
            else:
                renamed += 1
                items.append(
                    RenameAckItem(
                        old_path=item.old_path,
                        new_path=item.new_path,
                        status="ok",
                        document_id=doc.id,
                    )
                )
        except Exception as exc:
            logger.exception(
                "obsidian /rename failed for old=%s new=%s vault=%s",
                item.old_path,
                item.new_path,
                payload.vault_id,
            )
            items.append(
                RenameAckItem(
                    old_path=item.old_path,
                    new_path=item.new_path,
                    status="error",
                    error=str(exc)[:300],
                )
            )

    return RenameAck(
        vault_id=payload.vault_id,
        renamed=renamed,
        missing=missing,
        items=items,
    )


@router.delete("/notes", response_model=DeleteAck)
async def obsidian_delete_notes(
    payload: DeleteBatchRequest,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> DeleteAck:
    """Soft-delete a batch of notes by vault-relative path."""
    connector = await _resolve_vault_connector(
        session, user=user, vault_id=payload.vault_id
    )

    deleted = 0
    missing = 0
    items: list[DeleteAckItem] = []
    for path in payload.paths:
        try:
            ok = await delete_note(
                session,
                connector=connector,
                vault_id=payload.vault_id,
                path=path,
            )
            if ok:
                deleted += 1
                items.append(DeleteAckItem(path=path, status="ok"))
            else:
                missing += 1
                items.append(DeleteAckItem(path=path, status="missing"))
        except Exception as exc:
            logger.exception(
                "obsidian DELETE /notes failed for path=%s vault=%s",
                path,
                payload.vault_id,
            )
            items.append(DeleteAckItem(path=path, status="error", error=str(exc)[:300]))

    return DeleteAck(
        vault_id=payload.vault_id,
        deleted=deleted,
        missing=missing,
        items=items,
    )


@router.get("/manifest", response_model=ManifestResponse)
async def obsidian_manifest(
    vault_id: str = Query(..., description="Plugin-side stable vault UUID"),
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> ManifestResponse:
    """Return ``{path: {hash, mtime}}`` for the plugin's onload reconcile diff."""
    connector = await _resolve_vault_connector(session, user=user, vault_id=vault_id)
    return await get_manifest(session, connector=connector, vault_id=vault_id)


@router.get("/stats", response_model=StatsResponse)
async def obsidian_stats(
    vault_id: str = Query(..., description="Plugin-side stable vault UUID"),
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> StatsResponse:
    """Active-note count + last sync time for the web tile.

    ``files_synced`` excludes tombstones so it matches ``/manifest``;
    ``last_sync_at`` includes them so deletes advance the freshness signal.
    """
    connector = await _resolve_vault_connector(session, user=user, vault_id=vault_id)

    is_active = Document.document_metadata["deleted_at"].as_string().is_(None)

    row = (
        await session.execute(
            select(
                func.count(case((is_active, 1))).label("files_synced"),
                func.max(Document.updated_at).label("last_sync_at"),
            ).where(
                and_(
                    Document.connector_id == connector.id,
                    Document.document_type == DocumentType.OBSIDIAN_CONNECTOR,
                )
            )
        )
    ).first()

    return StatsResponse(
        vault_id=vault_id,
        files_synced=int(row[0] or 0),
        last_sync_at=row[1],
    )
