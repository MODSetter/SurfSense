"""Thread-scoped sandbox lifecycle for the deep agent.

Provider selection, session caching and recovery now live in ``app.sandbox``;
what remains here is the local-disk persistence that keeps sandbox-produced
files downloadable after the sandbox is gone.

That persistence is obsoleted by `save_artifact` (artifacts go to object
storage at generation time) and is removed in phase 4 along with the
`/threads/{id}/sandbox/download` route.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from app.config import config as app_config
from app.sandbox import get_registry

__all__ = [
    "delete_local_sandbox_files",
    "delete_sandbox",
    "get_local_sandbox_file",
    "persist_and_delete_sandbox",
    "sync_files_to_sandbox",
]

logger = logging.getLogger(__name__)
SANDBOX_DOCUMENTS_ROOT = "/workspace/documents"
_seeded_files: dict[str, dict[str, str]] = {}


async def sync_files_to_sandbox(
    thread_id: int | str,
    files: dict[str, dict],
    *,
    workspace_id: int | str,
    is_new: bool = False,
) -> None:
    """Upload changed virtual-filesystem files through the provider protocol."""
    key = str(thread_id)
    if is_new:
        _seeded_files.pop(key, None)

    tracked = _seeded_files.get(key, {})
    changed = [
        (vpath, fdata)
        for vpath, fdata in files.items()
        if tracked.get(vpath) != fdata.get("modified_at", "")
    ]
    if not changed:
        return

    registry = await get_registry()
    session = await registry.get_session(thread_id, workspace_id)
    for vpath, fdata in changed:
        content = "\n".join(fdata.get("content", [])).encode()
        await session.write_file(f"{SANDBOX_DOCUMENTS_ROOT}{vpath}", content)

    _seeded_files[key] = {
        vpath: fdata.get("modified_at", "") for vpath, fdata in files.items()
    }
    logger.info("Synced %d file(s) to sandbox for thread %s", len(changed), key)


async def delete_sandbox(thread_id: int | str) -> None:
    """Kill the thread's sandbox. Safe to call when there is none."""
    _seeded_files.pop(str(thread_id), None)
    registry = await get_registry()
    await registry.terminate(thread_id)


# ---------------------------------------------------------------------------
# Local file persistence
# ---------------------------------------------------------------------------


def _local_path_for(thread_id: int | str, sandbox_path: str) -> Path:
    """Map a sandbox-internal absolute path to a local filesystem path."""
    relative = sandbox_path.lstrip("/")
    base = (Path(app_config.SANDBOX_FILES_DIR) / str(thread_id)).resolve()
    target = (base / relative).resolve()
    if not target.is_relative_to(base):
        raise ValueError(f"Path traversal blocked: {sandbox_path}")
    return target


def get_local_sandbox_file(thread_id: int | str, sandbox_path: str) -> bytes | None:
    """Read a previously-persisted sandbox file, or None if it isn't there."""
    local = _local_path_for(thread_id, sandbox_path)
    return local.read_bytes() if local.is_file() else None


def delete_local_sandbox_files(thread_id: int | str) -> None:
    """Remove all locally-persisted sandbox files for a thread."""
    thread_dir = Path(app_config.SANDBOX_FILES_DIR) / str(thread_id)
    if thread_dir.is_dir():
        shutil.rmtree(thread_dir, ignore_errors=True)
        logger.info("Deleted local sandbox files for thread %s", thread_id)


async def persist_and_delete_sandbox(
    thread_id: int | str,
    sandbox_file_paths: list[str],
) -> None:
    """Copy sandbox files to local storage, then kill the sandbox.

    Per-file errors are logged but never block the kill: freeing the sandbox
    matters more than rescuing any one file.
    """
    registry = await get_registry()
    session = registry.get_cached(thread_id)
    if session is None:
        logger.info("No live sandbox for thread %s — nothing to persist", thread_id)
        return

    for path in sandbox_file_paths:
        try:
            content = await session.read_file(path)
            local = _local_path_for(thread_id, path)
            local.parent.mkdir(parents=True, exist_ok=True)
            local.write_bytes(content)
            logger.info("Persisted sandbox file %s → %s", path, local)
        except Exception:
            logger.warning(
                "Failed to persist sandbox file %s for thread %s",
                path,
                thread_id,
                exc_info=True,
            )

    await registry.terminate(thread_id)
