"""
Obsidian plugin ingestion routes.

This is the public surface that the SurfSense Obsidian plugin
(``surfsense_obsidian/``) speaks to. It is a separate router from the
legacy server-path Obsidian connector — the legacy code stays in place
until the ``obsidian-legacy-cleanup`` plan ships.

Endpoints
---------

- ``GET    /api/v1/obsidian/health``     — version handshake
- ``POST   /api/v1/obsidian/connect``    — register or get a vault row
- ``POST   /api/v1/obsidian/sync``       — batch upsert
- ``POST   /api/v1/obsidian/rename``     — batch rename
- ``DELETE /api/v1/obsidian/notes``      — batch soft-delete
- ``GET    /api/v1/obsidian/manifest``   — reconcile manifest

Auth contract
-------------

Every endpoint requires ``Depends(current_active_user)`` — the same JWT
bearer the rest of the API uses; future PAT migration is transparent.

API stability is provided by the ``/api/v1/...`` URL prefix and the
``capabilities`` array advertised on ``/health`` (additive only). There
is no plugin-version gate; "your plugin is out of date" notices are
delegated to Obsidian's built-in community-store updater.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db import (
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


# Bumped manually whenever the wire contract gains a non-additive change.
# Additive (extra='ignore'-safe) changes do NOT bump this.
OBSIDIAN_API_VERSION = "1"

# Capabilities advertised on /health and /connect. Plugins use this list
# for feature gating ("does this server understand attachments_v2?"). Add
# new strings, never rename/remove existing ones — older plugins ignore
# unknown entries safely.
OBSIDIAN_CAPABILITIES: list[str] = ["sync", "rename", "delete", "manifest"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_handshake() -> dict[str, object]:
    return {
        "api_version": OBSIDIAN_API_VERSION,
        "capabilities": list(OBSIDIAN_CAPABILITIES),
    }


async def _resolve_vault_connector(
    session: AsyncSession,
    *,
    user: User,
    vault_id: str,
) -> SearchSourceConnector:
    """Find the OBSIDIAN_CONNECTOR row that owns ``vault_id`` for this user.

    Looked up by the (user_id, connector_type, config['vault_id']) tuple
    so users can have multiple vaults each backed by its own connector
    row (one per search space).
    """
    result = await session.execute(
        select(SearchSourceConnector).where(
            and_(
                SearchSourceConnector.user_id == user.id,
                SearchSourceConnector.connector_type
                == SearchSourceConnectorType.OBSIDIAN_CONNECTOR,
            )
        )
    )
    candidates = result.scalars().all()
    for connector in candidates:
        cfg = connector.config or {}
        if cfg.get("vault_id") == vault_id and cfg.get("source") == "plugin":
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
    """Confirm the user owns the requested search space.

    Plugin currently does not support shared search spaces (RBAC roles)
    — that's a follow-up. Restricting to owner-only here keeps the
    surface narrow and avoids leaking other members' connectors.
    """
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
    """Return the API contract handshake.

    The plugin calls this once per ``onload`` and caches the result for
    capability-gating decisions.
    """
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

    Idempotent on the (user_id, OBSIDIAN_CONNECTOR, vault_id) tuple so
    re-installing the plugin or reconnecting from a new device picks up
    the same connector — and therefore the same documents.
    """
    await _ensure_search_space_access(
        session, user=user, search_space_id=payload.search_space_id
    )

    result = await session.execute(
        select(SearchSourceConnector).where(
            and_(
                SearchSourceConnector.user_id == user.id,
                SearchSourceConnector.connector_type
                == SearchSourceConnectorType.OBSIDIAN_CONNECTOR,
            )
        )
    )
    existing: SearchSourceConnector | None = None
    for candidate in result.scalars().all():
        cfg = candidate.config or {}
        if cfg.get("vault_id") == payload.vault_id:
            existing = candidate
            break

    now_iso = datetime.now(UTC).isoformat()

    if existing is not None:
        cfg = dict(existing.config or {})
        cfg.update(
            {
                "vault_id": payload.vault_id,
                "vault_name": payload.vault_name,
                "source": "plugin",
                "plugin_version": payload.plugin_version,
                "device_id": payload.device_id,
                "last_connect_at": now_iso,
            }
        )
        if payload.device_label:
            cfg["device_label"] = payload.device_label
        cfg.pop("legacy", None)
        cfg.pop("vault_path", None)
        existing.config = cfg
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
            config={
                "vault_id": payload.vault_id,
                "vault_name": payload.vault_name,
                "source": "plugin",
                "plugin_version": payload.plugin_version,
                "device_id": payload.device_id,
                "device_label": payload.device_label,
                "files_synced": 0,
                "last_connect_at": now_iso,
            },
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
    """Batch-upsert notes pushed by the plugin.

    Returns per-note ack so the plugin can dequeue successes and retry
    failures.
    """
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

    cfg = dict(connector.config or {})
    cfg["last_sync_at"] = datetime.now(UTC).isoformat()
    cfg["files_synced"] = int(cfg.get("files_synced", 0)) + indexed
    connector.config = cfg
    await session.commit()

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
    """Return the server-side ``{path: {hash, mtime}}`` manifest.

    Used by the plugin's ``onload`` reconcile to find files that were
    edited or deleted while the plugin was offline.
    """
    connector = await _resolve_vault_connector(
        session, user=user, vault_id=vault_id
    )
    return await get_manifest(session, connector=connector, vault_id=vault_id)
