"""The running app as a live case drives it: sources in, chat turns, the versions that came out."""

import asyncio
import time
from dataclasses import dataclass
from typing import Any

import httpx
from sqlalchemy import Engine

from modules.artifacts.models import Artifact
from modules.documents.models import Document
from modules.documents.original_file import original_path
from shared.db import create_session_factory
from tests.integration.agent.test_agent_threads import open_thread, send
from tests.live.recording_proxy import RecordingProxy
from tests.live.run_folder import RunFolder

# Docling's first load reads its models from disk; a two-page PDF then takes seconds.
INGEST_SECONDS = 900


@dataclass
class LiveAgent:
    http: httpx.AsyncClient
    workspace_id: int
    engine: Engine
    proxy: RecordingProxy
    run: RunFolder

    async def note(self, title: str, text: str) -> int:
        """A note the user wrote, ingested by the real worker."""
        made = await self.http.post(
            f"/workspaces/{self.workspace_id}/documents",
            json={"title": title, "content": text},
        )
        made.raise_for_status()
        self.run.keep_source(f"{title}.md", text.encode())
        return made.json()["id"]

    async def upload(self, name: str, data: bytes) -> int:
        """A file the user dropped in, ingested by the real worker."""
        made = await self.http.post(
            f"/workspaces/{self.workspace_id}/documents/upload",
            files=[("files", (name, data))],
        )
        made.raise_for_status()
        (created,) = made.json()["created"]
        self.run.keep_source(name, data)
        return created["id"]

    async def wait_ready(self, *document_ids: int) -> None:
        """Block until every source is searchable; fail on one that is not."""
        deadline = time.monotonic() + INGEST_SECONDS
        waiting = set(document_ids)
        while waiting:
            for document_id in list(waiting):
                read = await self.http.get(
                    f"/workspaces/{self.workspace_id}/documents/{document_id}"
                )
                status = read.json()["status"]
                if status == "failed":
                    raise AssertionError(f"ingest failed: {read.json()}")
                if status == "ready":
                    waiting.discard(document_id)
            if time.monotonic() > deadline:
                raise AssertionError(f"sources {waiting} not ready in time")
            await asyncio.sleep(1)

    async def thread(self) -> int:
        """An Agentic chat, as the cases measure the agent: an untested model's default is Basic."""
        return (await open_thread(self, "Live run", mode="agentic"))["id"]  # type: ignore[arg-type]

    async def turn(self, thread_id: int, text: str) -> list[dict[str, Any]]:
        """One message and the agent's whole reply, kept for the transcript."""
        frames: list[dict[str, Any]] = []

        async def keep(frame: dict[str, Any]) -> None:
            frames.append(frame)

        try:
            await send(self, thread_id, text, on_frame=keep)  # type: ignore[arg-type]
        finally:
            self.run.add_turn(text, frames)
        return frames

    async def artifacts(self) -> list[dict[str, Any]]:
        listed = await self.http.get(f"/workspaces/{self.workspace_id}/artifacts")
        listed.raise_for_status()
        return listed.json()

    async def file(self, artifact_id: int) -> bytes:
        primary = await self.http.get(f"/artifacts/{artifact_id}/files/primary")
        primary.raise_for_status()
        return primary.content

    def original(self, document_id: int) -> bytes:
        """The user's own file as it is on disk now."""
        with create_session_factory(self.engine)() as session:
            document = session.get(Document, document_id)
            assert document is not None
            path = original_path(document)
            assert path is not None, f"source {document_id}'s file is gone"
            return path.read_bytes()

    def spec(self, artifact_id: int) -> dict[str, Any]:
        """The script and images a version was rendered from."""
        with create_session_factory(self.engine)() as session:
            artifact = session.get(Artifact, artifact_id)
            assert artifact is not None
            return dict((artifact.artifact_metadata or {}).get("spec") or {})


def steps(frames: list[dict[str, Any]], tool: str) -> list[dict[str, Any]]:
    """The last state of each call to `tool` in a reply."""
    last: dict[str, dict[str, Any]] = {}
    for frame in frames:
        if frame["type"] == "agent-step" and frame["tool"] == tool:
            last[frame["id"]] = frame
    return list(last.values())


def answer(frames: list[dict[str, Any]]) -> str:
    """The reply's text, as it streamed."""
    return "".join(frame["text"] for frame in frames if frame["type"] == "delta")
