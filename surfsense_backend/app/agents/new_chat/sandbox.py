"""
Daytona sandbox provider for SurfSense deep agent.

Manages the lifecycle of sandboxed code execution environments.
Each conversation thread gets its own isolated sandbox instance
via the Daytona cloud API, identified by labels.

Files created during a session are persisted to local storage before
the sandbox is deleted so they remain downloadable after cleanup.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import shutil
from pathlib import Path

from daytona import (
    CreateSandboxFromSnapshotParams,
    Daytona,
    DaytonaConfig,
    SandboxState,
)
from daytona.common.errors import DaytonaError
from deepagents.backends.protocol import ExecuteResponse
from langchain_daytona import DaytonaSandbox

logger = logging.getLogger(__name__)


class _TimeoutAwareSandbox(DaytonaSandbox):
    """DaytonaSandbox subclass that accepts the per-command *timeout*
    kwarg required by the deepagents middleware.

    The upstream ``langchain-daytona`` ``execute()`` ignores timeout,
    so deepagents raises *"This sandbox backend does not support
    per-command timeout overrides"* on every first call.  This thin
    wrapper forwards the parameter to the Daytona SDK.
    """

    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        t = timeout if timeout is not None else self._timeout
        result = self._sandbox.process.exec(command, timeout=t)
        return ExecuteResponse(
            output=result.result,
            exit_code=result.exit_code,
            truncated=False,
        )

    async def aexecute(
        self, command: str, *, timeout: int | None = None
    ) -> ExecuteResponse:  # type: ignore[override]
        return await asyncio.to_thread(self.execute, command, timeout=timeout)


_daytona_client: Daytona | None = None
_sandbox_cache: dict[str, _TimeoutAwareSandbox] = {}
_SANDBOX_CACHE_MAX_SIZE = 20
THREAD_LABEL_KEY = "surfsense_thread"


def is_sandbox_enabled() -> bool:
    return os.environ.get("DAYTONA_SANDBOX_ENABLED", "FALSE").upper() == "TRUE"


def _get_client() -> Daytona:
    global _daytona_client
    if _daytona_client is None:
        config = DaytonaConfig(
            api_key=os.environ.get("DAYTONA_API_KEY", ""),
            api_url=os.environ.get("DAYTONA_API_URL", "https://app.daytona.io/api"),
            target=os.environ.get("DAYTONA_TARGET", "us"),
        )
        _daytona_client = Daytona(config)
    return _daytona_client


def _find_or_create(thread_id: str) -> _TimeoutAwareSandbox:
    """Find an existing sandbox for *thread_id*, or create a new one.

    If an existing sandbox is found but is stopped/archived, it will be
    restarted automatically before returning.
    """
    client = _get_client()
    labels = {THREAD_LABEL_KEY: thread_id}

    try:
        sandbox = client.find_one(labels=labels)
        logger.info("Found existing sandbox %s (state=%s)", sandbox.id, sandbox.state)

        if sandbox.state in (
            SandboxState.STOPPED,
            SandboxState.STOPPING,
            SandboxState.ARCHIVED,
        ):
            logger.info("Starting stopped sandbox %s …", sandbox.id)
            sandbox.start(timeout=60)
            logger.info("Sandbox %s is now started", sandbox.id)
        elif sandbox.state in (
            SandboxState.ERROR,
            SandboxState.BUILD_FAILED,
            SandboxState.DESTROYED,
        ):
            logger.warning(
                "Sandbox %s in unrecoverable state %s — creating a new one",
                sandbox.id,
                sandbox.state,
            )
            sandbox = client.create(
                CreateSandboxFromSnapshotParams(language="python", labels=labels)
            )
            logger.info("Created replacement sandbox: %s", sandbox.id)
        elif sandbox.state != SandboxState.STARTED:
            sandbox.wait_for_sandbox_start(timeout=60)

    except Exception:
        logger.info("No existing sandbox for thread %s — creating one", thread_id)
        sandbox = client.create(
            CreateSandboxFromSnapshotParams(language="python", labels=labels)
        )
        logger.info("Created new sandbox: %s", sandbox.id)

    return _TimeoutAwareSandbox(sandbox=sandbox)


async def get_or_create_sandbox(thread_id: int | str) -> _TimeoutAwareSandbox:
    """Get or create a sandbox for a conversation thread.

    Uses an in-process cache keyed by thread_id so subsequent messages
    in the same conversation reuse the sandbox object without an API call.

    Args:
        thread_id: The conversation thread identifier.

    Returns:
        DaytonaSandbox connected to the sandbox.
    """
    key = str(thread_id)
    cached = _sandbox_cache.get(key)
    if cached is not None:
        logger.info("Reusing cached sandbox for thread %s", key)
        return cached
    sandbox = await asyncio.to_thread(_find_or_create, key)
    _sandbox_cache[key] = sandbox

    if len(_sandbox_cache) > _SANDBOX_CACHE_MAX_SIZE:
        oldest_key = next(iter(_sandbox_cache))
        _sandbox_cache.pop(oldest_key, None)
        logger.debug("Evicted oldest sandbox cache entry: %s", oldest_key)

    return sandbox


async def delete_sandbox(thread_id: int | str) -> None:
    """Delete the sandbox for a conversation thread."""
    _sandbox_cache.pop(str(thread_id), None)

    def _delete() -> None:
        client = _get_client()
        labels = {THREAD_LABEL_KEY: str(thread_id)}
        try:
            sandbox = client.find_one(labels=labels)
        except DaytonaError:
            logger.debug(
                "No sandbox to delete for thread %s (already removed)", thread_id
            )
            return
        try:
            client.delete(sandbox)
            logger.info("Sandbox deleted: %s", sandbox.id)
        except Exception:
            logger.warning(
                "Failed to delete sandbox for thread %s",
                thread_id,
                exc_info=True,
            )

    await asyncio.to_thread(_delete)


# ---------------------------------------------------------------------------
# Local file persistence
# ---------------------------------------------------------------------------


def _get_sandbox_files_dir() -> Path:
    return Path(os.environ.get("SANDBOX_FILES_DIR", "sandbox_files"))


def _local_path_for(thread_id: int | str, sandbox_path: str) -> Path:
    """Map a sandbox-internal absolute path to a local filesystem path."""
    relative = sandbox_path.lstrip("/")
    return _get_sandbox_files_dir() / str(thread_id) / relative


def get_local_sandbox_file(thread_id: int | str, sandbox_path: str) -> bytes | None:
    """Read a previously-persisted sandbox file from local storage.

    Returns the file bytes, or *None* if the file does not exist locally.
    """
    local = _local_path_for(thread_id, sandbox_path)
    if local.is_file():
        return local.read_bytes()
    return None


def delete_local_sandbox_files(thread_id: int | str) -> None:
    """Remove all locally-persisted sandbox files for a thread."""
    thread_dir = _get_sandbox_files_dir() / str(thread_id)
    if thread_dir.is_dir():
        shutil.rmtree(thread_dir, ignore_errors=True)
        logger.info("Deleted local sandbox files for thread %s", thread_id)


async def persist_and_delete_sandbox(
    thread_id: int | str,
    sandbox_file_paths: list[str],
) -> None:
    """Download sandbox files to local storage, then delete the sandbox.

    Each file in *sandbox_file_paths* is downloaded from the Daytona
    sandbox and saved under ``{SANDBOX_FILES_DIR}/{thread_id}/…``.
    Per-file errors are logged but do **not** prevent the sandbox from
    being deleted — freeing Daytona storage is the priority.
    """
    _sandbox_cache.pop(str(thread_id), None)

    def _persist_and_delete() -> None:
        client = _get_client()
        labels = {THREAD_LABEL_KEY: str(thread_id)}

        try:
            sandbox = client.find_one(labels=labels)
        except Exception:
            logger.info(
                "No sandbox found for thread %s — nothing to persist", thread_id
            )
            return

        # Ensure the sandbox is running so we can download files
        if sandbox.state != SandboxState.STARTED:
            try:
                sandbox.start(timeout=60)
            except Exception:
                logger.warning(
                    "Could not start sandbox %s for file download — deleting anyway",
                    sandbox.id,
                    exc_info=True,
                )
                with contextlib.suppress(Exception):
                    client.delete(sandbox)
                return

        for path in sandbox_file_paths:
            try:
                content: bytes = sandbox.fs.download_file(path)
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

        try:
            client.delete(sandbox)
            logger.info("Sandbox deleted after file persistence: %s", sandbox.id)
        except Exception:
            logger.warning(
                "Failed to delete sandbox %s after persistence",
                sandbox.id,
                exc_info=True,
            )

    await asyncio.to_thread(_persist_and_delete)
