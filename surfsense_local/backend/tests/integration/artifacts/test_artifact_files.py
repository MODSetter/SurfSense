"""An artifact's file, streamed to a viewer or saved by Download."""

import sqlite3
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import Engine

from api.main import create_app
from modules.artifacts.models import Artifact, ArtifactFile, ArtifactFileRole
from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.workspaces.models import Workspace
from shared.db import create_session_factory

pytestmark = pytest.mark.integration

# Several of FileResponse's 64 KiB chunks, as a podcast is many.
AUDIO = b"\x01" * (256 * 1024)


@pytest.fixture
def artifact_id(engine: Engine, data_dir: Path) -> int:
    """A ready podcast with its WAV on disk."""
    with create_session_factory(engine)() as session:
        workspace = Workspace(name="Saturn")
        session.add(workspace)
        session.flush()
        document = Document(
            workspace_id=workspace.id,
            title="Podcast",
            document_type=DocumentType.ARTIFACT,
            status=DocumentStatus.READY,
        )
        session.add(document)
        session.flush()
        artifact = Artifact(
            document_id=document.id,
            workspace_id=workspace.id,
            format="podcast",
            artifact_metadata={},
        )
        session.add(artifact)
        session.flush()
        key = f"artifacts/{artifact.id}/primary.wav"
        (data_dir / key).parent.mkdir(parents=True)
        (data_dir / key).write_bytes(AUDIO)
        session.add(
            ArtifactFile(
                artifact_id=artifact.id,
                role=ArtifactFileRole.PRIMARY,
                storage_key=key,
                original_filename="saturn.wav",
                mime_type="audio/wav",
                size_bytes=len(AUDIO),
                checksum_sha256="0" * 64,
            )
        )
        session.commit()
        return artifact.id


async def test_a_file_streams_inline_and_downloads_as_an_attachment(
    client: AsyncClient, artifact_id: int
) -> None:
    """The app's window and the API are two origins, so a link's `download`
    attribute is ignored: only the header can make a click save the file."""
    url = f"/artifacts/{artifact_id}/files/primary"

    streamed = await client.get(url)
    saved = await client.get(f"{url}?download=1")

    assert streamed.headers["content-disposition"].startswith("inline")
    assert saved.headers["content-disposition"].startswith("attachment")
    assert "saturn.wav" in saved.headers["content-disposition"]
    assert saved.content == AUDIO


async def test_a_file_being_streamed_leaves_the_database_free(
    engine: Engine, artifact_id: int
) -> None:
    """A player reads a long podcast for minutes. The request's transaction
    holds SQLite's write lock, so it must end before the file streams, or
    every other request waits past its busy timeout and fails as locked."""
    app = create_app()
    app.state.session_factory = create_session_factory(engine)
    writable: list[bool] = []

    def someone_else_writes() -> bool:
        other = sqlite3.connect(engine.url.database, timeout=0.2)
        try:
            other.execute("BEGIN IMMEDIATE")
            other.execute("ROLLBACK")
            return True
        except sqlite3.OperationalError:
            return False
        finally:
            other.close()

    async def receive() -> dict:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict) -> None:
        if message["type"] == "http.response.body" and not writable:
            writable.append(someone_else_writes())

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": f"/artifacts/{artifact_id}/files/primary",
        "raw_path": f"/artifacts/{artifact_id}/files/primary".encode(),
        "query_string": b"",
        "headers": [(b"host", b"test")],
        "client": ("127.0.0.1", 1),
        "server": ("test", 80),
        "root_path": "",
    }
    await app(scope, receive, send)

    assert writable == [True]
