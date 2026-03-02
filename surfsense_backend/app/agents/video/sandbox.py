"""
Daytona sandbox provider for the video deep agent.

Wraps the shared sandbox infrastructure with a Remotion/Node.js snapshot
and a separate label key to avoid collision with chat sandboxes.
Set DAYTONA_REMOTION_SNAPSHOT_ID in the environment to the pre-built snapshot ID.
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

# Path inside the sandbox where the official @remotion/skills are baked into the snapshot.
# Matches SKILLS_DIR in scripts/create_remotion_snapshot.py.
SKILLS_SANDBOX_PATH = "/home/daytona/skills/remotion-best-practices"

logger = logging.getLogger(__name__)

VIDEO_LABEL_KEY = "surfsense_video_thread"


def _remotion_snapshot_params(labels: dict) -> CreateSandboxFromSnapshotParams:
    snapshot_id = os.environ.get("DAYTONA_REMOTION_SNAPSHOT_ID")
    if snapshot_id:
        return CreateSandboxFromSnapshotParams(
            snapshot=snapshot_id,
            labels=labels,
        )
    return CreateSandboxFromSnapshotParams(language="javascript", labels=labels)


def _find_or_create_video(thread_id: str) -> _TimeoutAwareSandbox:
    """Find an existing video sandbox for *thread_id*, or create a new one from the Remotion snapshot."""
    client = _get_client()
    labels = {VIDEO_LABEL_KEY: thread_id}

    try:
        sandbox = client.find_one(labels=labels)
        logger.info(
            "[video] Found existing sandbox %s (state=%s)", sandbox.id, sandbox.state
        )

        if sandbox.state in (
            SandboxState.STOPPED,
            SandboxState.STOPPING,
            SandboxState.ARCHIVED,
        ):
            logger.info("[video] Starting stopped sandbox %s …", sandbox.id)
            sandbox.start(timeout=60)
            logger.info("[video] Sandbox %s is now started", sandbox.id)
        elif sandbox.state in (
            SandboxState.ERROR,
            SandboxState.BUILD_FAILED,
            SandboxState.DESTROYED,
        ):
            logger.warning(
                "[video] Sandbox %s in unrecoverable state %s — creating a new one",
                sandbox.id,
                sandbox.state,
            )
            sandbox = client.create(_remotion_snapshot_params(labels))
            logger.info("[video] Created replacement sandbox: %s", sandbox.id)
        elif sandbox.state != SandboxState.STARTED:
            sandbox.wait_for_sandbox_start(timeout=60)

    except Exception:
        logger.info(
            "[video] No existing sandbox for thread %s — creating one", thread_id
        )
        sandbox = client.create(_remotion_snapshot_params(labels))
        logger.info("[video] Created new sandbox: %s", sandbox.id)

    return _TimeoutAwareSandbox(sandbox=sandbox)


async def get_or_create_video_sandbox(thread_id: int | str) -> _TimeoutAwareSandbox:
    """Get or create a Remotion sandbox for a video generation thread.

    Skills are pre-installed in the snapshot at SKILLS_SANDBOX_PATH —
    no upload needed at runtime.
    """
    return await asyncio.to_thread(_find_or_create_video, str(thread_id))


async def delete_video_sandbox(thread_id: int | str) -> None:
    """Delete the video sandbox for a thread."""

    def _delete() -> None:
        client = _get_client()
        labels = {VIDEO_LABEL_KEY: str(thread_id)}
        try:
            sandbox = client.find_one(labels=labels)
        except DaytonaError:
            logger.debug(
                "[video] No sandbox to delete for thread %s (already removed)",
                thread_id,
            )
            return
        try:
            client.delete(sandbox)
            logger.info("[video] Sandbox deleted: %s", sandbox.id)
        except Exception:
            logger.warning(
                "[video] Failed to delete sandbox for thread %s",
                thread_id,
                exc_info=True,
            )

    await asyncio.to_thread(_delete)

