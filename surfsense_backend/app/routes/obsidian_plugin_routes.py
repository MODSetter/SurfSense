"""Obsidian plugin ingestion routes (``/api/v1/obsidian/*``).

Wire surface for the ``surfsense_obsidian/`` plugin. API stability is the
``/api/v1/`` prefix plus the additive ``capabilities`` array on /health;
no plugin-version gate.
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


# Bumped only on non-additive wire changes; additive ones ride extra='ignore'.
OBSIDIAN_API_VERSION = "1"

# Plugins feature-gate on these. Add entries, never rename or remove.
OBSIDIAN_CAPABILITIES: list[str] = ["sync", "rename", "delete", "manifest"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_handshake() -> dict[str, object]:
    return {
        "api_version": OBSIDIAN_API_VERSION,
        "capabilities": list(OBSIDIAN_CAPABILITIES),
    }


def _upsert_device(
    existing_devices: object,
    device_id: str,
    now_iso: str,
) -> dict[str, dict[str, str]]:
    """Upsert ``device_id`` into ``{device_id: {first_seen_at, last_seen_at}}``.

    Keyed by device_id for O(1) dedup; ``len(devices)`` is the count.
    Timestamps are kept for a future stale-device pruner.
    """
    devices: dict[str, dict[str, str]] = {}
    if isinstance(existing_devices, dict):
        for key, val in existing_devices.items():
            if not isinstance(key, str) or not key or not isinstance(val, dict):
                continue
            devices[key] = {
                "first_seen_at": str(val.get("first_seen_at") or now_iso),
                "last_seen_at": str(val.get("last_seen_at") or now_iso),
            }

    prev = devices.get(device_id)
    devices[device_id] = {
        "first_seen_at": prev["first_seen_at"] if prev else now_iso,
        "last_seen_at": now_iso,
    }
    return devices


async def _resolve_vault_connector(
    session: AsyncSession,
    *,
    user: User,
    vault_id: str,
) -> SearchSourceConnector:
    """Find the OBSIDIAN_CONNECTOR row that owns ``vault_id`` for this user."""
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
    plugin onload as a heartbeat — upserts ``device_id`` into
    ``config['devices']`` so the web UI can show a "Devices: N" tile.
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
        devices = _upsert_device(cfg.get("devices"), payload.device_id, now_iso)
        cfg.update(
            {
                "vault_id": payload.vault_id,
                "vault_name": payload.vault_name,
                "source": "plugin",
                "plugin_version": payload.plugin_version,
                "devices": devices,
                "device_count": len(devices),
                "last_connect_at": now_iso,
            }
        )
        cfg.pop("legacy", None)
        cfg.pop("vault_path", None)
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
        devices = _upsert_device(None, payload.device_id, now_iso)
        connector = SearchSourceConnector(
            name=f"Obsidian — {payload.vault_name}",
            connector_type=SearchSourceConnectorType.OBSIDIAN_CONNECTOR,
            is_indexable=False,
            config={
                "vault_id": payload.vault_id,
                "vault_name": payload.vault_name,
                "source": "plugin",
                "plugin_version": payload.plugin_version,
                "devices": devices,
                "device_count": len(devices),
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
    """Return ``{path: {hash, mtime}}`` for the plugin's onload reconcile diff."""
    connector = await _resolve_vault_connector(
        session, user=user, vault_id=vault_id
    )
    return await get_manifest(session, connector=connector, vault_id=vault_id)
