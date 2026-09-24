from collections.abc import Iterator
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import Engine

from modules.artifacts.models import Artifact
from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.llm.catalog.local.dependencies import get_local_catalog
from modules.llm.catalog.local.installs import InstalledBuild, record_install
from modules.llm.model_type import ModelType
from modules.llm.models import ProviderConnection, SelectedModel
from shared.config import get_llm_settings
from shared.db import create_session_factory
from shared.queue import studio_queue

pytestmark = pytest.mark.integration


@pytest.fixture
async def workspace_id(client: AsyncClient) -> int:
    """Every Studio route hangs off a workspace, so every test needs one."""
    created = await client.post("/workspaces", json={"name": "Research"})
    return int(created.json()["id"])


@pytest.fixture
def choose_model(engine: Engine) -> None:
    """A generation model must be selected before a job can run."""
    with create_session_factory(engine)() as session:
        session.add(
            SelectedModel(model_type=ModelType.TEXT_GEN, provider="llamacpp", name="Qwen3-4B-Q4_K_M")
        )
        session.commit()


def make_ready_source(engine: Engine, workspace_id: int) -> int:
    """A source has to be indexed before it can feed a job."""
    with create_session_factory(engine)() as session:
        document = Document(
            workspace_id=workspace_id,
            title="Facts",
            document_type=DocumentType.NOTE,
            status=DocumentStatus.READY,
            content="Saturn has rings.",
        )
        session.add(document)
        session.commit()
        return document.id


async def test_formats_lists_summary_as_available(
    client: AsyncClient, workspace_id: int, choose_model: None
) -> None:
    """Generation-backed formats are available with the selected chat model."""
    response = await client.get(f"/workspaces/{workspace_id}/studio/formats")

    assert response.status_code == 200
    summary = next(f for f in response.json() if f["key"] == "summary")
    assert summary["available"] is True
    assert summary["requires_model_types"] == ["text_gen"]
    assert summary["unavailable_reason"] is None

    image = next(f for f in response.json() if f["key"] == "image")
    assert image["available"] is False
    assert image["requires_model_types"] == ["image_gen", "text_gen"]


async def test_a_format_missing_both_models_says_so(
    client: AsyncClient, workspace_id: int
) -> None:
    """No `choose_model` fixture: nothing is selected at all.

    Image and Infographic need two roles, and reporting only whichever was
    checked first names the chat model on the two tiles where the image model
    is the distinguishing requirement. The user then selects a chat model and
    the reason changes under them, which reads as the gate moving rather than
    as one of two being satisfied.
    """
    response = await client.get(f"/workspaces/{workspace_id}/studio/formats")

    image = next(f for f in response.json() if f["key"] == "image")
    assert image["available"] is False
    assert image["unavailable_reason"] == "Needs a chat model and an image model"

    summary = next(f for f in response.json() if f["key"] == "summary")
    assert summary["unavailable_reason"] == "Needs a chat model"


async def test_infographic_needs_the_image_model_and_the_chat_model(
    client: AsyncClient, engine: Engine, workspace_id: int, choose_model: None
) -> None:
    """The chat model writes the brief, the image model paints it: both gate it."""
    listed = await client.get(f"/workspaces/{workspace_id}/studio/formats")
    infographic = next(f for f in listed.json() if f["key"] == "infographic")
    assert infographic["requires_model_types"] == ["image_gen", "text_gen"]
    assert infographic["available"] is False
    assert infographic["unavailable_reason"] == "Needs an image model"

    with create_session_factory(engine)() as session:
        session.add(
            SelectedModel(
                model_type=ModelType.IMAGE_GEN, provider="sdcpp", name="sdxl-base-1.0"
            )
        )
        session.commit()

    listed = await client.get(f"/workspaces/{workspace_id}/studio/formats")
    infographic = next(f for f in listed.json() if f["key"] == "infographic")
    assert infographic["available"] is True


async def test_podcast_is_gated_on_an_audio_model(
    client: AsyncClient, workspace_id: int, choose_model: None
) -> None:
    """It drafts with the chat model and voices with the audio model, so it
    names the one missing."""
    url = f"/workspaces/{workspace_id}/studio/formats"
    podcast = next(f for f in (await client.get(url)).json() if f["key"] == "podcast")

    assert podcast["available"] is False
    assert podcast["unavailable_reason"] == "Needs an audio model"
    assert podcast["requires_model_types"] == ["text_gen", "audio_gen"]


async def test_a_podcast_voices_only_on_this_computer(
    client: AsyncClient, engine: Engine, workspace_id: int, choose_model: None
) -> None:
    """A server's audio model can be chosen, but nothing calls a remote speech
    endpoint yet, so the podcast says where the model must run."""
    with create_session_factory(engine)() as session:
        server = ProviderConnection(
            label="speech server", provider="openai_compatible", base_url="http://tts"
        )
        session.add(server)
        session.flush()
        session.add(
            SelectedModel(
                model_type=ModelType.AUDIO_GEN,
                provider="openai_compatible",
                connection_id=server.id,
                name="tts-1",
            )
        )
        session.commit()

    url = f"/workspaces/{workspace_id}/studio/formats"
    podcast = next(f for f in (await client.get(url)).json() if f["key"] == "podcast")

    assert podcast["available"] is False
    assert podcast["unavailable_reason"] == "Needs an audio model on this computer"


KOKORO = ("kokoro-82m-q8_0", "Q8_0")
KITTEN = ("kitten-tts-mini-0.8-orig", "orig")


@pytest.fixture
def audio_folder(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Path]:
    """A build that ships audio.cpp: its models folder, empty."""
    audio = tmp_path / "audio"
    audio.mkdir()
    monkeypatch.setattr(get_llm_settings(), "audio_models_dir", audio)
    get_local_catalog.cache_clear()
    yield audio
    get_local_catalog.cache_clear()


def choose_voice(engine: Engine, audio: Path, build: tuple[str, str]) -> None:
    """One curated audio build installed and chosen for the audio slot."""
    model_id, quantization = build
    (audio / f"{model_id}.gguf").write_bytes(b"GGUF")
    record_install(
        audio,
        InstalledBuild(
            model_id=model_id,
            repo="audio-cpp/audio.cpp-gguf",
            revision="0a104324546d2622985e3c676a4b5550cc772127",
            quantization=quantization,
            weights=(f"{model_id}.gguf",),
        ),
    )
    with create_session_factory(engine)() as session:
        session.merge(
            SelectedModel(
                model_type=ModelType.AUDIO_GEN, provider="audiocpp", name=model_id
            )
        )
        session.commit()


@pytest.fixture
def local_voice(engine: Engine, audio_folder: Path) -> None:
    """Kokoro, installed and chosen."""
    choose_voice(engine, audio_folder, KOKORO)


async def test_a_local_audio_model_makes_the_podcast_available(
    client: AsyncClient, workspace_id: int, choose_model: None, local_voice: None
) -> None:
    """Drafted by the chat model, voiced by audio.cpp on this computer."""
    url = f"/workspaces/{workspace_id}/studio/formats"
    podcast = next(f for f in (await client.get(url)).json() if f["key"] == "podcast")

    assert podcast["available"] is True
    assert podcast["unavailable_reason"] is None


async def test_a_podcast_job_checks_and_stores_its_brief(
    client: AsyncClient,
    engine: Engine,
    workspace_id: int,
    choose_model: None,
    local_voice: None,
) -> None:
    """A brief with a wrong voice is refused at the door; a good one is stored."""
    source_id = make_ready_source(engine, workspace_id)
    url = f"/workspaces/{workspace_id}/studio/jobs"
    speakers = [{"name": "Ana", "role": "host", "voice": "pf_dora"}]

    refused = await client.post(
        url,
        json={
            "format": "podcast",
            "document_ids": [source_id],
            "options": {"language": "en-US", "speakers": speakers},
        },
    )
    assert refused.status_code == 422
    assert "Ana" in refused.json()["detail"]

    created = await client.post(
        url,
        json={
            "format": "podcast",
            "document_ids": [source_id],
            "options": {"language": "pt-BR", "speakers": speakers},
        },
    )
    assert created.status_code == 201
    with create_session_factory(engine)() as session:
        artifact = session.get(Artifact, created.json()["id"])
        assert artifact is not None
        stored = artifact.artifact_metadata["options"]
    assert stored["style"] == "conversational"
    assert stored["duration"] == "standard"
    assert stored["speakers"] == speakers


async def test_the_brief_opens_with_defaults_then_with_the_last_episode(
    client: AsyncClient,
    engine: Engine,
    workspace_id: int,
    choose_model: None,
    local_voice: None,
) -> None:
    """First visit: two English speakers and the voice catalog. After an episode:
    that episode's brief, so the user only changes what differs."""
    url = f"/workspaces/{workspace_id}/studio/podcast/brief"

    opened = (await client.get(url)).json()
    assert opened["brief"]["language"] == "en-US"
    assert [s["role"] for s in opened["brief"]["speakers"]] == ["host", "guest"]
    assert {"id", "label", "languages"} <= set(opened["voices"][0])
    spoken = {language for voice in opened["voices"] for language in voice["languages"]}
    assert spoken >= {"en-US", "pt-BR"}

    speakers = [{"name": "Ana", "role": "narrator", "voice": "pf_dora"}]
    await client.post(
        f"/workspaces/{workspace_id}/studio/jobs",
        json={
            "format": "podcast",
            "document_ids": [make_ready_source(engine, workspace_id)],
            "options": {"language": "pt-BR", "duration": "long", "speakers": speakers},
        },
    )

    reopened = (await client.get(url)).json()["brief"]
    assert reopened["language"] == "pt-BR"
    assert reopened["duration"] == "long"
    assert reopened["speakers"] == speakers


async def test_the_brief_needs_an_audio_model(
    client: AsyncClient, workspace_id: int
) -> None:
    """No audio model, no voices to choose from: the reason the format shows."""
    opened = await client.get(f"/workspaces/{workspace_id}/studio/podcast/brief")
    assert opened.status_code == 409
    assert opened.json()["detail"] == "Needs an audio model"


async def test_a_model_without_en_us_opens_in_a_language_it_speaks(
    client: AsyncClient, engine: Engine, workspace_id: int, audio_folder: Path
) -> None:
    """Kitten lists English as plain `en`: the brief opens there, with two of
    its own voices, rather than empty."""
    choose_voice(engine, audio_folder, KITTEN)

    url = f"/workspaces/{workspace_id}/studio/podcast/brief"
    opened = (await client.get(url)).json()

    assert opened["brief"]["language"] == "en"
    assert [s["voice"] for s in opened["brief"]["speakers"]] == ["Bella", "Jasper"]


async def test_a_brief_the_chosen_model_cannot_voice_falls_back_to_the_defaults(
    client: AsyncClient,
    engine: Engine,
    workspace_id: int,
    choose_model: None,
    audio_folder: Path,
) -> None:
    """Last episode's voices were Kokoro's; with Kitten chosen, they are gone."""
    choose_voice(engine, audio_folder, KOKORO)
    await client.post(
        f"/workspaces/{workspace_id}/studio/jobs",
        json={
            "format": "podcast",
            "document_ids": [make_ready_source(engine, workspace_id)],
            "options": {
                "language": "pt-BR",
                "speakers": [{"name": "Ana", "role": "host", "voice": "pf_dora"}],
            },
        },
    )
    choose_voice(engine, audio_folder, KITTEN)

    url = f"/workspaces/{workspace_id}/studio/podcast/brief"
    opened = (await client.get(url)).json()

    assert opened["brief"]["language"] == "en"
    assert {s["voice"] for s in opened["brief"]["speakers"]} <= {
        v["id"] for v in opened["voices"]
    }


async def test_a_job_creates_a_pending_artifact(
    client: AsyncClient, engine: Engine, workspace_id: int, choose_model: None
) -> None:
    """The row is written and enqueued; the worker (absent here) would finish it."""
    source_id = make_ready_source(engine, workspace_id)

    created = await client.post(
        f"/workspaces/{workspace_id}/studio/jobs",
        json={"format": "summary", "document_ids": [source_id]},
    )

    assert created.status_code == 201
    body = created.json()
    assert body["format"] == "summary"
    assert body["status"] == "pending"

    listed = await client.get(f"/workspaces/{workspace_id}/artifacts")
    assert [a["id"] for a in listed.json()] == [body["id"]]

    detail = await client.get(f"/artifacts/{body['id']}")
    assert detail.json()["content"] is None
    assert detail.json()["files"] == []


async def test_a_job_needs_a_generation_model(
    client: AsyncClient, engine: Engine, workspace_id: int
) -> None:
    """Fail fast at submit, not as a failed job the user has to inspect."""
    source_id = make_ready_source(engine, workspace_id)

    response = await client.post(
        f"/workspaces/{workspace_id}/studio/jobs",
        json={"format": "summary", "document_ids": [source_id]},
    )

    assert response.status_code == 409


async def test_a_job_rejects_an_unknown_format(
    client: AsyncClient, engine: Engine, workspace_id: int, choose_model: None
) -> None:
    """A format with no builder is refused at submit, not enqueued to fail."""
    source_id = make_ready_source(engine, workspace_id)

    response = await client.post(
        f"/workspaces/{workspace_id}/studio/jobs",
        json={"format": "hologram", "document_ids": [source_id]},
    )

    assert response.status_code == 422


async def test_a_job_rejects_a_source_from_another_workspace(
    client: AsyncClient, engine: Engine, workspace_id: int, choose_model: None
) -> None:
    """One workspace's id must not pull another's document into a job."""
    other = await client.post("/workspaces", json={"name": "Other"})
    foreign_id = make_ready_source(engine, int(other.json()["id"]))

    response = await client.post(
        f"/workspaces/{workspace_id}/studio/jobs",
        json={"format": "summary", "document_ids": [foreign_id]},
    )

    assert response.status_code == 422


async def test_a_job_waits_for_a_source_to_index(
    client: AsyncClient, workspace_id: int, choose_model: None
) -> None:
    """A pending note is not searchable yet, so it cannot ground a summary."""
    note = await client.post(
        f"/workspaces/{workspace_id}/documents",
        json={"title": "Draft", "content": "unindexed"},
    )

    response = await client.post(
        f"/workspaces/{workspace_id}/studio/jobs",
        json={"format": "summary", "document_ids": [int(note.json()["id"])]},
    )

    assert response.status_code == 409


async def test_an_artifact_can_be_deleted(
    client: AsyncClient, engine: Engine, workspace_id: int, choose_model: None
) -> None:
    """Deleting the artifact removes its row; the detail route then 404s."""
    source_id = make_ready_source(engine, workspace_id)
    created = await client.post(
        f"/workspaces/{workspace_id}/studio/jobs",
        json={"format": "summary", "document_ids": [source_id]},
    )
    artifact_id = created.json()["id"]

    deleted = await client.delete(f"/artifacts/{artifact_id}")
    assert deleted.status_code == 204

    gone = await client.get(f"/artifacts/{artifact_id}")
    assert gone.status_code == 404


async def test_a_failed_artifact_can_be_regenerated(
    client: AsyncClient, engine: Engine, workspace_id: int, choose_model: None
) -> None:
    """Regenerate requeues the same job, clears the reason, bumps the generation."""
    source_id = make_ready_source(engine, workspace_id)
    created = await client.post(
        f"/workspaces/{workspace_id}/studio/jobs",
        json={"format": "summary", "document_ids": [source_id]},
    )
    artifact_id = created.json()["id"]

    # Still queued: the worker is absent here, so the row is as the API left it.
    busy = await client.post(f"/artifacts/{artifact_id}/regenerate")
    assert busy.status_code == 409

    with create_session_factory(engine)() as session:
        document = session.get(Document, created.json()["document_id"])
        document.status = DocumentStatus.FAILED
        document.error_message = "the model refused"
        session.commit()
    studio_queue.flush()  # Drop the job the first request enqueued.

    again = await client.post(f"/artifacts/{artifact_id}/regenerate")
    assert again.status_code == 202
    body = again.json()
    assert body["status"] == "pending"
    assert body["error_message"] is None
    assert body["generation"] == 2
    assert [job.args for job in studio_queue.pending()] == [(artifact_id,)]


async def test_a_pending_artifact_can_be_cancelled(
    client: AsyncClient, engine: Engine, workspace_id: int, choose_model: None
) -> None:
    """Cancel drops the queued generation so the worker never picks it up."""
    source_id = make_ready_source(engine, workspace_id)
    created = await client.post(
        f"/workspaces/{workspace_id}/studio/jobs",
        json={"format": "summary", "document_ids": [source_id]},
    )
    artifact_id = created.json()["id"]
    assert studio_queue.pending()

    response = await client.post(f"/artifacts/{artifact_id}/cancel")

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert response.json()["error_message"] is None
    task = studio_queue.pending()[0]
    assert studio_queue.is_revoked(task)


async def test_a_ready_artifact_cannot_be_cancelled(
    client: AsyncClient, engine: Engine, workspace_id: int, choose_model: None
) -> None:
    """Stopping a finished generation would look like success and then vanish."""
    source_id = make_ready_source(engine, workspace_id)
    created = await client.post(
        f"/workspaces/{workspace_id}/studio/jobs",
        json={"format": "summary", "document_ids": [source_id]},
    )
    artifact_id = created.json()["id"]
    with create_session_factory(engine)() as session:
        document = session.get(Document, created.json()["document_id"])
        document.status = DocumentStatus.READY
        session.commit()

    response = await client.post(f"/artifacts/{artifact_id}/cancel")

    assert response.status_code == 409
