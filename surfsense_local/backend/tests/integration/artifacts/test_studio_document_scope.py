"""A Word or PDF draft grounds on the ticked sources like every other format, and
its Retry keeps to them; a refine's Retry rewrites without them."""

from typing import Any

import pytest
from httpx import AsyncClient
from huey import Huey
from sqlalchemy.orm import Session

from modules.artifacts.models import Artifact
from modules.artifacts.schemas import StudioJobCreate
from modules.artifacts.service import create_artifact_job
from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.folders.ensure_path import ensure_folder_path
from modules.llm.model_type import ModelType
from modules.llm.models import SelectedModel
from modules.llm.profile import Fingerprint, Tier
from modules.llm.resolution import ResolvedGeneration
from modules.source_roots.managed_root import ensure_managed_root
from modules.source_scope.schemas import SourceScope
from modules.workspaces.models import Workspace
from shared.queue import studio_queue
from tests.integration.worker.conftest import stub_model  # noqa: F401
from worker.studio.shared.artifact import Source

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("stub_model")]

DRAFT = "# Halvorsen Freight proposal\n\nWe propose a two-phase rollout."
REVISED = "# Halvorsen Freight proposal\n\nA two-phase rollout."


@pytest.fixture
def small_model(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """A model on this computer, so Word and PDF are drafted as Markdown."""
    session.add(
        SelectedModel(model_type=ModelType.TEXT_GEN, provider="llamacpp", name="m")
    )
    session.commit()
    selection = type(
        "Selection",
        (),
        {
            "provider": "llamacpp",
            "name": "m",
            "tier": Tier.CAPABLE,
            "fingerprint": Fingerprint("llamacpp", "m"),
        },
    )()
    monkeypatch.setattr(
        "worker.studio.job.resolve_generation",
        lambda _session: ResolvedGeneration(selection, None),
    )

    async def window(_session: Session) -> tuple[str, int]:
        return "m", 32_768

    monkeypatch.setattr(
        "modules.artifacts.studio_documents.fits.selected_model_window", window
    )


def _drafts(monkeypatch: pytest.MonkeyPatch) -> list[list[Source]]:
    """The sources each draft was grounded on."""
    grounded: list[list[Source]] = []

    def fake(_model: object, _system: str, sources: list[Source], **_kw: Any) -> str:
        grounded.append(sources)
        return DRAFT

    monkeypatch.setattr("worker.studio.shared.generate.run_model", fake)
    return grounded


def _folder(
    session: Session, workspace: Workspace, name: str, notes: int
) -> tuple[int, list[int]]:
    """A folder in the managed root holding `notes` ready notes."""
    folder = ensure_folder_path(
        session, ensure_managed_root(session, workspace.id), [name]
    )
    ids = []
    for number in range(notes):
        note = Document(
            workspace_id=workspace.id,
            title=f"{name} {number}",
            document_type=DocumentType.NOTE,
            status=DocumentStatus.READY,
            content=f"{name} note {number}: the pilot costs 12,000.",
            folder_id=folder.id,
        )
        session.add(note)
        session.flush()
        ids.append(note.id)
    session.commit()
    return folder.id, ids


def _work_off(queue: Huey) -> None:
    while (task := queue.dequeue()) is not None:
        queue.execute(task)


def _ready(session: Session, artifact_id: int) -> dict[str, Any]:
    """Its metadata once it finished, read in a transaction ended at once:
    SQLite has one writer, and the routes the test calls next need it."""
    session.expire_all()
    artifact = session.get(Artifact, artifact_id)
    assert artifact.document.status is DocumentStatus.READY, (
        artifact.document.error_message
    )
    meta = dict(artifact.artifact_metadata)
    session.commit()
    return meta


def _folder_draft(session: Session, workspace: Workspace, folder_id: int) -> int:
    artifact = create_artifact_job(
        session,
        workspace,
        StudioJobCreate(
            format="docx", source_scope=SourceScope(folder_ids=[folder_id])
        ),
    )
    _work_off(studio_queue)
    return artifact.id


async def test_a_folder_scoped_word_draft_grounds_on_that_folders_sources(
    session: Session,
    workspace: Workspace,
    small_model: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only the ticked folder reaches the model, and every key either side keeps is kept."""
    ticked, inside = _folder(session, workspace, "Halvorsen", notes=2)
    _folder(session, workspace, "Unrelated", notes=1)
    grounded = _drafts(monkeypatch)

    artifact_id = _folder_draft(session, workspace, ticked)
    meta = _ready(session, artifact_id)

    assert [[source.document_id for source in call] for call in grounded] == [inside]
    assert meta["source_document_ids"] == inside
    assert meta["source_scope"]["folder_ids"] == [ticked]
    assert meta["grounded_document_ids"] == inside
    assert meta["spec"]["kind"] == "markdown"
    assert meta["spec"]["text"] == DRAFT
    assert meta["version"] == {"root": artifact_id, "number": 1, "parent": None}
    assert meta["recipe"] == {"kind": "draft"}


async def test_retrying_a_folder_scoped_draft_drafts_again_from_what_is_left(
    client: AsyncClient,
    session: Session,
    workspace: Workspace,
    small_model: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A deleted source drops out of the re-resolved scope; v1 stays v1."""
    workspace_id = workspace.id
    ticked, (gone, kept) = _folder(session, workspace, "Halvorsen", notes=2)
    grounded = _drafts(monkeypatch)
    artifact_id = _folder_draft(session, workspace, ticked)
    _ready(session, artifact_id)
    deleted = await client.delete(f"/workspaces/{workspace_id}/documents/{gone}")
    assert deleted.status_code == 204, deleted.text

    retried = await client.post(f"/artifacts/{artifact_id}/regenerate")
    _work_off(studio_queue)

    assert retried.status_code == 202, retried.text
    meta = _ready(session, artifact_id)
    assert [source.document_id for source in grounded[-1]] == [kept]
    assert meta["source_document_ids"] == [kept]
    assert meta["grounded_document_ids"] == [kept]
    assert meta["version"]["number"] == 1
    assert meta["recipe"] == {"kind": "draft"}


async def test_retrying_a_refine_needs_none_of_its_sources(
    client: AsyncClient,
    session: Session,
    workspace: Workspace,
    small_model: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A refine rewrites its base's spec, so Retry repeats it with every source gone."""
    workspace_id = workspace.id
    ticked, inside = _folder(session, workspace, "Halvorsen", notes=1)
    _drafts(monkeypatch)
    first_id = _folder_draft(session, workspace, ticked)
    _ready(session, first_id)
    monkeypatch.setattr(
        "worker.studio.shared.generate.complete",
        lambda *_a, **_k: f"```markdown\n{REVISED}\n```",
    )
    refined = await client.post(
        f"/artifacts/{first_id}/refine", json={"instruction": "Make it shorter"}
    )
    assert refined.status_code == 202, refined.text
    second_id = refined.json()["id"]
    _work_off(studio_queue)
    # Its figures come from the sources the draft resolved, not the scope.
    assert _ready(session, second_id)["source_document_ids"] == inside
    for source_id in inside:
        await client.delete(f"/workspaces/{workspace_id}/documents/{source_id}")

    retried = await client.post(f"/artifacts/{second_id}/regenerate")
    _work_off(studio_queue)

    assert retried.status_code == 202, retried.text
    second = _ready(session, second_id)
    assert second["spec"]["text"] == REVISED
    assert second["version"]["number"] == 2
