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
    DeleteBatchRequest,
    HealthResponse,
    ManifestResponse,
    RenameBatchRequest,
    SyncBatchRequest,
)
from app.services.obsidian_plugin_indexer import (
    delete_note,
    get_manifest,
    rename_note,
    upsert_note,
)
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


async def _resolve_vault_connector(
    session: AsyncSession,
    *,
    user: User,
    vault_id: str,
) -> SearchSourceConnector:
    """Find the OBSIDIAN_CONNECTOR row that owns ``vault_id`` for this user."""
    stmt = select(SearchSourceConnector).where(
        and_(
            SearchSourceConnector.user_id == user.id,
            SearchSourceConnector.connector_type
            == SearchSourceConnectorType.OBSIDIAN_CONNECTOR,
            SearchSourceConnector.config["vault_id"].astext == vault_id,
            SearchSourceConnector.config["source"].astext == "plugin",
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


@router.post("/connect", response_model=ConnectResponse)
async def obsidian_connect(
    payload: ConnectRequest,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> ConnectResponse:
    """Register a vault, or return the existing connector row.

    Idempotent on (user_id, OBSIDIAN_CONNECTOR, vault_id). Called on every
    plugin onload as a heartbeat.
    """
    await _ensure_search_space_access(
        session, user=user, search_space_id=payload.search_space_id
    )

    # FOR UPDATE so concurrent /connect calls for the same vault can't race.
    existing: SearchSourceConnector | None = (
        (
            await session.execute(
                select(SearchSourceConnector)
                .where(
                    and_(
                        SearchSourceConnector.user_id == user.id,
                        SearchSourceConnector.connector_type
                        == SearchSourceConnectorType.OBSIDIAN_CONNECTOR,
                        SearchSourceConnector.config["vault_id"].astext
                        == payload.vault_id,
                    )
                )
                .with_for_update()
            )
        )
        .scalars()
        .first()
    )

    now_iso = datetime.now(UTC).isoformat()
    cfg = {
        "vault_id": payload.vault_id,
        "vault_name": payload.vault_name,
        "source": "plugin",
        "last_connect_at": now_iso,
    }

    if existing is not None:
        existing.config = cfg
        # Re-stamp on every connect so vault renames in Obsidian propagate;
        # the web UI hides the Name input for Obsidian connectors.
        existing.name = f"Obsidian — {payload.vault_name}"
        existing.is_indexable = False
        existing.search_space_id = payload.search_space_id
        await session.commit()
        await session.refresh(existing)
        connector = existing
    else:
        connector = SearchSourceConnector(
            name=f"Obsidian — {payload.vault_name}",
            connector_type=SearchSourceConnectorType.OBSIDIAN_CONNECTOR,
            is_indexable=False,
            config=cfg,
            user_id=user.id,
            search_space_id=payload.search_space_id,
        )
        session.add(connector)
        await session.commit()
        await session.refresh(connector)

    return ConnectResponse(
        connector_id=connector.id,
        vault_id=payload.vault_id,
        search_space_id=connector.search_space_id,
        **_build_handshake(),
    )


@router.post("/sync")
async def obsidian_sync(
    payload: SyncBatchRequest,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    """Batch-upsert notes; returns per-note ack so the plugin can dequeue/retry."""
    connector = await _resolve_vault_connector(
        session, user=user, vault_id=payload.vault_id
    )

    results: list[dict[str, object]] = []
    indexed = 0
    failed = 0

    for note in payload.notes:
        try:
            doc = await upsert_note(
                session, connector=connector, payload=note, user_id=str(user.id)
            )
            indexed += 1
            results.append(
                {"path": note.path, "status": "ok", "document_id": doc.id}
            )
        except HTTPException:
            raise
        except Exception as exc:
            failed += 1
            logger.exception(
                "obsidian /sync failed for path=%s vault=%s",
                note.path,
                payload.vault_id,
            )
            results.append(
                {"path": note.path, "status": "error", "error": str(exc)[:300]}
            )

    return {
        "vault_id": payload.vault_id,
        "indexed": indexed,
        "failed": failed,
        "results": results,
    }


@router.post("/rename")
async def obsidian_rename(
    payload: RenameBatchRequest,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    """Apply a batch of vault rename events."""
    connector = await _resolve_vault_connector(
        session, user=user, vault_id=payload.vault_id
    )

    results: list[dict[str, object]] = []
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
                results.append(
                    {
                        "old_path": item.old_path,
                        "new_path": item.new_path,
                        "status": "missing",
                    }
                )
            else:
                renamed += 1
                results.append(
                    {
                        "old_path": item.old_path,
                        "new_path": item.new_path,
                        "status": "ok",
                        "document_id": doc.id,
                    }
                )
        except Exception as exc:
            logger.exception(
                "obsidian /rename failed for old=%s new=%s vault=%s",
                item.old_path,
                item.new_path,
                payload.vault_id,
            )
            results.append(
                {
                    "old_path": item.old_path,
                    "new_path": item.new_path,
                    "status": "error",
                    "error": str(exc)[:300],
                }
            )

    return {
        "vault_id": payload.vault_id,
        "renamed": renamed,
        "missing": missing,
        "results": results,
    }


@router.delete("/notes")
async def obsidian_delete_notes(
    payload: DeleteBatchRequest,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    """Soft-delete a batch of notes by vault-relative path."""
    connector = await _resolve_vault_connector(
        session, user=user, vault_id=payload.vault_id
    )

    deleted = 0
    missing = 0
    results: list[dict[str, object]] = []
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
                results.append({"path": path, "status": "ok"})
            else:
                missing += 1
                results.append({"path": path, "status": "missing"})
        except Exception as exc:
            logger.exception(
                "obsidian DELETE /notes failed for path=%s vault=%s",
                path,
                payload.vault_id,
            )
            results.append(
                {"path": path, "status": "error", "error": str(exc)[:300]}
            )

    return {
        "vault_id": payload.vault_id,
        "deleted": deleted,
        "missing": missing,
        "results": results,
    }


@router.get("/manifest", response_model=ManifestResponse)
async def obsidian_manifest(
    vault_id: str = Query(..., description="Plugin-side stable vault UUID"),
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> ManifestResponse:
    """Return ``{path: {hash, mtime}}`` for the plugin's onload reconcile diff."""
    connector = await _resolve_vault_connector(
        session, user=user, vault_id=vault_id
    )
    return await get_manifest(session, connector=connector, vault_id=vault_id)


@router.get("/stats")
async def obsidian_stats(
    vault_id: str = Query(..., description="Plugin-side stable vault UUID"),
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    """Active-note count + last sync time for the web tile.

    ``files_synced`` excludes tombstones so it matches ``/manifest``;
    ``last_sync_at`` includes them so deletes advance the freshness signal.
    """
    connector = await _resolve_vault_connector(
        session, user=user, vault_id=vault_id
    )

    is_active = Document.document_metadata["deleted_at"].astext.is_(None)

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

    return {
        "vault_id": vault_id,
        "files_synced": int(row[0] or 0),
        "last_sync_at": row[1].isoformat() if row[1] else None,
    }
