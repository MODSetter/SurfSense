"""Editing a Studio image: the instruction and the open version's picture go to
the edit model, and what comes back is the document's next version."""

import asyncio

import pytest
from httpx import AsyncClient, Response
from huey import Huey
from sqlalchemy.orm import Session

from modules.artifacts.models import Artifact
from modules.artifacts.schemas import StudioJobCreate
from modules.artifacts.service import create_artifact_job
from modules.documents.models import Document, DocumentStatus
from modules.llm.model_type import ModelType
from modules.llm.models import SelectedModel
from modules.llm.providers.openai_compatible import NonRetryableImageError
from modules.llm.providers.protocols import GeneratedImage
from modules.llm.resolution import (
    ResolvedImageEdit,
    ResolvedImageGeneration,
    resolve_image_edit,
)
from modules.workspaces.models import Workspace
from shared.config import get_storage_settings
from shared.queue import studio_queue
from tests.integration.worker.conftest import stub_model  # noqa: F401

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("stub_model")]

DRAWN = b"\x89PNG\r\n\x1a\ndrawn"
WRITER = '{"title": "Lighthouse", "prompt": "a lighthouse at dusk"}'


class Painter:
    """The image model: draws v1, and records each edit it is asked for."""

    def __init__(self) -> None:
        self.edits: list[tuple[str, bytes]] = []
        self.fail_with: Exception | None = None

    async def generate(self, _model: str, _prompt: str) -> GeneratedImage:
        return GeneratedImage(DRAWN, "image/png")

    async def edit(
        self, _model: str, prompt: str, image: GeneratedImage
    ) -> GeneratedImage:
        if self.fail_with is not None:
            raise self.fail_with
        self.edits.append((prompt, image.content))
        number = len(self.edits)
        return GeneratedImage(b"\x89PNG\r\n\x1a\nedit%d" % number, "image/png")


@pytest.fixture
def painter(session: Session, monkeypatch: pytest.MonkeyPatch) -> Painter:
    """A chat model, an image model and an edit model, all chosen."""
    session.add(
        SelectedModel(model_type=ModelType.TEXT_GEN, provider="llamacpp", name="m")
    )
    for model_type in (ModelType.IMAGE_GEN, ModelType.IMAGE_EDIT):
        session.add(SelectedModel(model_type=model_type, provider="sdcpp", name="m"))
    session.commit()
    fake = Painter()
    selection = type("Selection", (), {"provider": "fake", "name": "m"})()
    monkeypatch.setattr(
        "worker.studio.shared.generate.run_model", lambda *_a, **_k: WRITER
    )
    monkeypatch.setattr(
        "worker.studio.job.resolve_image_generation",
        lambda _session: ResolvedImageGeneration(selection, fake),
    )
    edit_model = lambda _session: ResolvedImageEdit(selection, fake)  # noqa: E731
    monkeypatch.setattr("worker.studio.job.resolve_image_edit", edit_model)
    monkeypatch.setattr(
        "modules.artifacts.image_edits.model.resolve_image_edit", edit_model
    )
    return fake


async def _work_off(queue: Huey) -> None:
    """On a thread, as Studio's worker runs: the image clients start their own loop."""

    def work() -> None:
        while (task := queue.dequeue()) is not None:
            queue.execute(task)

    await asyncio.to_thread(work)


def _primary(artifact: Artifact) -> bytes:
    (file,) = artifact.files
    return (get_storage_settings().data_dir / file.storage_key).read_bytes()


async def _drawn(
    session: Session, workspace: Workspace, source: Document, fmt: str = "image"
) -> Artifact:
    artifact = create_artifact_job(
        session, workspace, StudioJobCreate(format=fmt, document_ids=[source.id])
    )
    await _work_off(studio_queue)
    session.expire_all()
    assert artifact.document.status is DocumentStatus.READY, (
        artifact.document.error_message
    )
    return artifact


async def _edit(
    client: AsyncClient, session: Session, artifact_id: int, instruction: str
) -> Response:
    """Asked with the test's own read transaction ended: SQLite has one writer."""
    session.commit()
    return await client.post(
        f"/artifacts/{artifact_id}/image-edit", json={"instruction": instruction}
    )


async def _edited(
    client: AsyncClient, session: Session, artifact_id: int, instruction: str
) -> Artifact:
    response = await _edit(client, session, artifact_id, instruction)
    assert response.status_code == 202, response.text
    await _work_off(studio_queue)
    session.expire_all()
    edited = session.get(Artifact, response.json()["id"])
    assert edited.document.status is DocumentStatus.READY, edited.document.error_message
    return edited


async def test_a_drawn_image_is_v1_of_its_own_document(
    client: AsyncClient,
    session: Session,
    workspace: Workspace,
    logo_source: Document,
    painter: Painter,
) -> None:
    """So the list groups its edits under it and the viewer can switch between them."""
    first = await _drawn(session, workspace, logo_source)
    session.commit()

    listed = (await client.get(f"/artifacts/{first.id}")).json()

    assert listed["version"] == {"root_id": first.id, "number": 1, "parent_id": None}
    assert listed["image_editable"] is True
    assert listed["refinable"] is False


async def test_an_edit_is_the_next_version_drawn_from_the_open_ones_picture(
    client: AsyncClient,
    session: Session,
    workspace: Workspace,
    logo_source: Document,
    painter: Painter,
) -> None:
    """The instruction goes to the model as written; v1 keeps its own picture."""
    first = await _drawn(session, workspace, logo_source)

    response = await _edit(client, session, first.id, "Make it night")

    assert response.status_code == 202, response.text
    body = response.json()
    assert body["status"] == "pending"
    assert body["format"] == "image"
    assert body["title"] == "Lighthouse"
    assert body["version"] == {"root_id": first.id, "number": 2, "parent_id": first.id}

    await _work_off(studio_queue)
    session.expire_all()
    second = session.get(Artifact, body["id"])
    assert second.document.status is DocumentStatus.READY, second.document.error_message
    assert painter.edits == [("Make it night", DRAWN)]
    assert _primary(second) == b"\x89PNG\r\n\x1a\nedit1"
    assert _primary(first) == DRAWN
    # Findable by what it shows, and by how it moved from the base.
    assert (
        second.document.content == f"{first.document.content}\n\nEdited: Make it night"
    )
    assert second.artifact_metadata["recipe"] == {
        "kind": "image_edit",
        "instruction": "Make it night",
        "base_artifact_id": first.id,
    }


async def test_editing_v2_starts_from_v2s_picture(
    client: AsyncClient,
    session: Session,
    workspace: Workspace,
    logo_source: Document,
    painter: Painter,
) -> None:
    """Edits chain; an old version edited makes the newest number."""
    first = await _drawn(session, workspace, logo_source)
    second = await _edited(client, session, first.id, "Make it night")

    third = await _edited(client, session, second.id, "Add a moon")
    fourth = await _edited(client, session, first.id, "Add a boat")

    assert painter.edits[1] == ("Add a moon", _primary(second))
    assert painter.edits[2] == ("Add a boat", DRAWN)
    assert third.artifact_metadata["version"]["number"] == 3
    assert fourth.artifact_metadata["version"] == {
        "root": first.id,
        "number": 4,
        "parent": first.id,
    }


async def test_an_infographic_is_edited_the_same_way(
    client: AsyncClient,
    session: Session,
    workspace: Workspace,
    logo_source: Document,
    painter: Painter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Its brief is not asked for again: the instruction records how it moved."""
    monkeypatch.setattr(
        "worker.studio.shared.generate.run_model",
        lambda *_a, **_k: '{"title": "Rings", "summary": "s", "sections": []}',
    )
    first = await _drawn(session, workspace, logo_source, fmt="infographic")

    second = await _edited(client, session, first.id, "Use a dark background")

    assert second.format == "infographic"
    assert painter.edits == [("Use a dark background", DRAWN)]


async def test_regenerating_an_edit_repeats_it_on_the_same_base(
    client: AsyncClient,
    session: Session,
    workspace: Workspace,
    logo_source: Document,
    painter: Painter,
) -> None:
    """A new sample of the same edit, not a new draw from the sources."""
    first = await _drawn(session, workspace, logo_source)
    second = await _edited(client, session, first.id, "Make it night")

    session.commit()
    response = await client.post(f"/artifacts/{second.id}/regenerate")
    assert response.status_code == 202, response.text
    await _work_off(studio_queue)

    assert painter.edits == [("Make it night", DRAWN), ("Make it night", DRAWN)]
    session.expire_all()
    assert _primary(second) == b"\x89PNG\r\n\x1a\nedit2"


async def test_a_failed_edit_is_not_retried_and_leaves_earlier_versions_alone(
    client: AsyncClient,
    session: Session,
    workspace: Workspace,
    logo_source: Document,
    painter: Painter,
) -> None:
    """The user asked for one call; Retry asks again."""
    first = await _drawn(session, workspace, logo_source)
    painter.fail_with = NonRetryableImageError("sd-server returned HTTP 429")

    response = await _edit(client, session, first.id, "Make it night")
    await _work_off(studio_queue)

    session.expire_all()
    failed = session.get(Artifact, response.json()["id"])
    assert failed.document.status is DocumentStatus.FAILED
    assert failed.document.error_message == "sd-server returned HTTP 429"
    assert first.document.status is DocumentStatus.READY
    assert _primary(first) == DRAWN


async def test_editing_with_no_edit_model_says_so_as_a_code(
    client: AsyncClient,
    session: Session,
    workspace: Workspace,
    logo_source: Document,
    painter: Painter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The box shows the interface's own sentence, as Refine does for a chat model."""
    first = await _drawn(session, workspace, logo_source)
    monkeypatch.setattr(
        "modules.artifacts.image_edits.model.resolve_image_edit", resolve_image_edit
    )
    session.delete(session.get(SelectedModel, ModelType.IMAGE_EDIT))

    response = await _edit(client, session, first.id, "Make it night")

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "message": "Needs an image editing model",
        "code": "needs_image_edit",
    }


async def test_only_a_ready_image_or_infographic_can_be_edited(
    client: AsyncClient,
    session: Session,
    workspace: Workspace,
    logo_source: Document,
    painter: Painter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A summary has no picture to edit."""
    monkeypatch.setattr(
        "worker.studio.shared.generate.run_model", lambda *_a, **_k: "# Rings"
    )
    summary = await _drawn(session, workspace, logo_source, fmt="summary")

    response = await _edit(client, session, summary.id, "Make it night")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "not_editable"
    session.commit()
    assert (await client.get(f"/artifacts/{summary.id}")).json()[
        "image_editable"
    ] is False


async def test_a_version_still_being_made_cannot_be_edited(
    client: AsyncClient,
    session: Session,
    workspace: Workspace,
    logo_source: Document,
    painter: Painter,
) -> None:
    """It has no picture yet."""
    first = await _drawn(session, workspace, logo_source)
    pending = await _edit(client, session, first.id, "Make it night")

    response = await _edit(client, session, pending.json()["id"], "Add a moon")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "already_generating"


async def test_a_failed_version_is_not_edited(
    client: AsyncClient,
    session: Session,
    workspace: Workspace,
    logo_source: Document,
    painter: Painter,
) -> None:
    """It shows nothing to edit; Retry it, or edit another version."""
    first = await _drawn(session, workspace, logo_source)
    painter.fail_with = NonRetryableImageError("no")
    failed = await _edit(client, session, first.id, "Make it night")
    await _work_off(studio_queue)

    response = await _edit(client, session, failed.json()["id"], "Add a moon")

    assert response.status_code == 409
    # Its own code: Refine's would say "refine another version" under a picture.
    assert response.json()["detail"]["code"] == "image_version_unfinished"


async def test_a_picture_that_is_not_raster_is_not_edited(
    client: AsyncClient,
    session: Session,
    workspace: Workspace,
    logo_source: Document,
    painter: Painter,
) -> None:
    """A remote model may return an SVG, which edit models do not read."""
    first = await _drawn(session, workspace, logo_source)
    (file,) = first.files
    file.mime_type = "image/svg+xml"
    session.commit()

    assert (await client.get(f"/artifacts/{first.id}")).json()[
        "image_editable"
    ] is False
    response = await _edit(client, session, first.id, "Make it night")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "not_editable"


@pytest.mark.parametrize("instruction", ["", "   ", "x" * 2001])
async def test_an_instruction_must_say_something_and_fit(
    client: AsyncClient,
    session: Session,
    workspace: Workspace,
    logo_source: Document,
    painter: Painter,
    instruction: str,
) -> None:
    """The limits Refine's box has."""
    first = await _drawn(session, workspace, logo_source)

    response = await _edit(client, session, first.id, instruction)

    assert response.status_code == 422
