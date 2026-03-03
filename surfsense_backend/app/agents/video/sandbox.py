"""Daytona sandbox lifecycle for video generation.

Manages Remotion/Node.js sandboxes: find existing, create from snapshot,
start stopped instances, and delete.
"""

from __future__ import annotations

import asyncio
import logging
import os

from daytona import CreateSandboxFromSnapshotParams, SandboxState
from daytona.common.errors import DaytonaError

from app.agents.new_chat.sandbox import (
    _TimeoutAwareSandbox,
    _get_client,
)
from app.agents.video.constants import SANDBOX_THREAD_LABEL_KEY

logger = logging.getLogger(__name__)


def _build_sandbox_creation_params(labels: dict) -> CreateSandboxFromSnapshotParams:
    """Build the parameters for creating a sandbox, using the Remotion snapshot if configured."""
    snapshot_id = os.environ.get("DAYTONA_REMOTION_SNAPSHOT_ID")
    if snapshot_id:
        return CreateSandboxFromSnapshotParams(
            snapshot=snapshot_id,
            labels=labels,
        )
    return CreateSandboxFromSnapshotParams(language="javascript", labels=labels)


def _find_or_create_video_sandbox(thread_id: str) -> _TimeoutAwareSandbox:
    """Find an existing sandbox for the thread, or create a new one from the Remotion snapshot."""
    client = _get_client()
    thread_labels = {SANDBOX_THREAD_LABEL_KEY: thread_id}

    try:
        existing_sandbox = client.find_one(labels=thread_labels)
        logger.info(
            "[video/sandbox] Found existing sandbox %s (state=%s)",
            existing_sandbox.id,
            existing_sandbox.state,
        )

        if existing_sandbox.state in (
            SandboxState.STOPPED,
            SandboxState.STOPPING,
            SandboxState.ARCHIVED,
        ):
            logger.info("[video/sandbox] Starting stopped sandbox %s…", existing_sandbox.id)
            existing_sandbox.start(timeout=60)
            logger.info("[video/sandbox] Sandbox %s started", existing_sandbox.id)
        elif existing_sandbox.state in (
            SandboxState.ERROR,
            SandboxState.BUILD_FAILED,
            SandboxState.DESTROYED,
        ):
            logger.warning(
                "[video/sandbox] Sandbox %s in unrecoverable state %s — creating replacement",
                existing_sandbox.id,
                existing_sandbox.state,
            )
            existing_sandbox = client.create(_build_sandbox_creation_params(thread_labels))
            logger.info("[video/sandbox] Created replacement sandbox: %s", existing_sandbox.id)
        elif existing_sandbox.state != SandboxState.STARTED:
            existing_sandbox.wait_for_sandbox_start(timeout=60)

    except Exception:
        logger.info(
            "[video/sandbox] No existing sandbox for thread %s — creating new one", thread_id
        )
        existing_sandbox = client.create(_build_sandbox_creation_params(thread_labels))
        logger.info("[video/sandbox] Created sandbox: %s", existing_sandbox.id)

    return _TimeoutAwareSandbox(sandbox=existing_sandbox)


async def get_or_create_sandbox(thread_id: int | str) -> _TimeoutAwareSandbox:
    """Get or create a Remotion sandbox for a video generation thread."""
    return await asyncio.to_thread(_find_or_create_video_sandbox, str(thread_id))


async def delete_sandbox(thread_id: int | str) -> None:
    """Delete the video sandbox for a thread."""

    def _delete() -> None:
        client = _get_client()
        thread_labels = {SANDBOX_THREAD_LABEL_KEY: str(thread_id)}
        try:
            target_sandbox = client.find_one(labels=thread_labels)
        except DaytonaError:
            logger.debug(
                "[video/sandbox] No sandbox found for thread %s (already removed)",
                thread_id,
            )
            return
        try:
            client.delete(target_sandbox)
            logger.info("[video/sandbox] Deleted sandbox: %s", target_sandbox.id)
        except Exception:
            logger.warning(
                "[video/sandbox] Failed to delete sandbox for thread %s",
                thread_id,
                exc_info=True,
            )

    await asyncio.to_thread(_delete)
