"""The revised copies a turn made, their downloads and the next versions Studio makes of them, and the source they came from."""

import asyncio
import time
from typing import Any

from modules.documents.models import Document
from modules.documents.original_file import original_path
from shared.db import create_session_factory
from tests.live.live_agent import LiveAgent, steps

REVISE = "surfsense_revise_document"
VERSION_SECONDS = 300


async def last_revised(
    live: LiveAgent, frames: list[dict[str, Any]], turn: str
) -> dict[str, Any]:
    """The newest ready version a turn's revise calls made, with its revision record."""
    made = [
        s["artifact"]["id"]
        for s in steps(frames, REVISE)
        if s["status"] == "completed" and s.get("artifact")
    ]
    assert made, f"{turn}: no revised copy was made"
    detail = await _detail(live, made[-1])
    assert detail["status"] == "ready", f"{turn}: {detail['id']} is {detail['status']}"
    assert detail["revision"] is not None, f"{turn}: {detail['id']} is no revised copy"
    return detail


async def download(live: LiveAgent, artifact_id: int, variant: str) -> bytes:
    """A revised copy's download, "changes" or "clean", as the Studio button serves it."""
    got = await live.http.get(
        f"/artifacts/{artifact_id}/revised-copy/download", params={"variant": variant}
    )
    got.raise_for_status()
    return got.content


async def decided(live: LiveAgent, artifact_id: int, decision: str) -> dict[str, Any]:
    """The ready version Studio makes when the user picks "accept-all" or "reject-all"."""
    started = await live.http.post(f"/artifacts/{artifact_id}/revisions/{decision}")
    started.raise_for_status()
    deadline = time.monotonic() + VERSION_SECONDS
    while True:
        detail = await _detail(live, started.json()["id"])
        if detail["status"] == "ready":
            return detail
        assert detail["status"] not in ("failed", "cancelled"), detail
        assert time.monotonic() < deadline, f"{decision} not ready in time: {detail}"
        await asyncio.sleep(1)


def source_bytes(live: LiveAgent, document_id: int) -> bytes:
    """The user's file as it is on disk now."""
    with create_session_factory(live.engine)() as session:
        document = session.get(Document, document_id)
        assert document is not None
        path = original_path(document)
    assert path is not None, f"source {document_id}'s file is gone"
    return path.read_bytes()


async def _detail(live: LiveAgent, artifact_id: int) -> dict[str, Any]:
    read = await live.http.get(f"/artifacts/{artifact_id}")
    read.raise_for_status()
    return read.json()
