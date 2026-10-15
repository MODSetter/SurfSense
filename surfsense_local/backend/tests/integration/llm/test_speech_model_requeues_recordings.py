"""Recordings uploaded before any speech model wait for one, and choosing one
queues every one of them again, so nothing is uploaded twice."""

import pytest
from httpx import AsyncClient
from sqlalchemy import Engine

from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.documents.tasks import PRIORITY_BULK
from modules.workspaces.models import Workspace
from shared.db import create_session_factory
from shared.queue import ingest_queue
from tests.integration.llm.installs import install_curated

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

NEMOTRON = "nemotron-3.5-asr-streaming-0.6b"
MODEL = "nemotron-3.5-asr-streaming-0.6b-q8_0"
WAITING = "Waiting for a speech model."


def add_sources(engine: Engine) -> dict[str, int]:
    """Two workspaces' recordings waiting for a model, a recording that failed
    otherwise, and a failed PDF."""
    with create_session_factory(engine)() as session:
        first, second = Workspace(name="Standups"), Workspace(name="Interviews")
        session.add_all([first, second])
        session.flush()

        def failed(
            workspace: Workspace, title: str, metadata: dict, reason: str
        ) -> Document:
            document = Document(
                workspace_id=workspace.id,
                title=title,
                document_type=DocumentType.FILE,
                status=DocumentStatus.FAILED,
                error_message=reason,
                document_metadata=metadata,
            )
            session.add(document)
            return document

        audio = {"mime_type": "audio/mpeg", "suffix": ".mp3"}
        rows = {
            "monday": failed(
                first,
                "monday.mp3",
                {**audio, "transcription": {"awaiting": True}},
                WAITING,
            ),
            "guest": failed(
                second,
                "guest.mp3",
                {**audio, "transcription": {"awaiting": True}},
                WAITING,
            ),
            "silent": failed(
                first, "silent.mp3", audio, "No speech was found in this recording."
            ),
            "report": failed(
                first, "report.pdf", {"mime_type": "application/pdf"}, "boom"
            ),
        }
        session.commit()
        return {name: row.id for name, row in rows.items()}


def read(engine: Engine, document_id: int) -> Document:
    """The row as it is now, outside any session."""
    with create_session_factory(engine)() as session:
        document = session.get(Document, document_id)
        session.expunge(document)
        session.commit()
        return document


def queued() -> list[tuple[int, int]]:
    """Each queued ingest's document and priority."""
    return sorted(
        (task.args[0], task.priority)
        for task in ingest_queue.pending()
        if task.name == "ingest_document"
    )


async def test_choosing_a_speech_model_queues_every_waiting_recording(
    client: AsyncClient, engine: Engine, audio_dir, fake_hub
) -> None:
    """Behind interactive work, in every workspace; nothing else is retried."""
    ids = add_sources(engine)
    await install_curated(client, NEMOTRON, "Q8_0")

    chosen = await client.put(
        "/llm/selection/speech_to_text", json={"provider": "audiocpp", "name": MODEL}
    )

    assert chosen.status_code == 200, chosen.text
    assert queued() == sorted(
        [(ids["monday"], PRIORITY_BULK), (ids["guest"], PRIORITY_BULK)]
    )
    monday = read(engine, ids["monday"])
    assert (monday.status, monday.error_message) == (DocumentStatus.PENDING, None)
    assert "transcription" not in monday.document_metadata
    assert read(engine, ids["silent"]).status is DocumentStatus.FAILED
    assert read(engine, ids["report"]).status is DocumentStatus.FAILED


async def test_a_download_that_chooses_the_model_queues_them_too(
    client: AsyncClient, engine: Engine, audio_dir, fake_hub
) -> None:
    """The set-up popover's Download and set up selects as it installs."""
    ids = add_sources(engine)

    await install_curated(client, NEMOTRON, "Q8_0", select=True)

    assert [document_id for document_id, _ in queued()] == sorted(
        [ids["monday"], ids["guest"]]
    )


async def test_choosing_another_kind_of_model_queues_nothing(
    client: AsyncClient, engine: Engine, audio_dir, fake_hub, bundled_voice
) -> None:
    """Only a speech model is what they wait for."""
    add_sources(engine)

    chosen = await client.put(
        "/llm/selection/audio_gen",
        json={"provider": "audiocpp", "name": "kokoro-82m-q8_0"},
    )

    assert chosen.status_code == 200, chosen.text
    assert queued() == []
