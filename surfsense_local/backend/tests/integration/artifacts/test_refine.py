"""Refine: one model call rewrites a version's whole spec into the next version."""

from io import BytesIO
from typing import Any

import docx
import pytest
from httpx import AsyncClient, Response
from huey import Huey
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from modules.artifacts.models import Artifact
from modules.artifacts.schemas import StudioJobCreate
from modules.artifacts.script_documents.service import create_script_document
from modules.artifacts.service import create_artifact_job
from modules.documents.models import Document, DocumentStatus
from modules.documents.source_figures.layout import figures_dir, write_index
from modules.llm.model_type import ModelType
from modules.llm.models import SelectedModel
from modules.llm.profile import Tier
from modules.llm.providers.types import Message
from modules.llm.resolution import ResolvedGeneration
from modules.workspaces.models import Workspace
from shared.config import get_storage_settings
from shared.queue import studio_queue
from tests.integration.worker.conftest import stub_model  # noqa: F401

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("stub_model")]

DRAFT = (
    "# Halvorsen Freight proposal\n\nWe propose a two-phase rollout over six months."
)
REVISED = "# Halvorsen Freight proposal\n\nA two-phase rollout."

SCRIPT = """\
# title: Client proposal
import os
import docx

document = docx.Document()
document.add_heading("Client proposal", level=1)
document.add_paragraph("{line}")
document.save(os.environ["OUTPUT_PATH"])
"""


@pytest.fixture
def local_model(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """A model on llama.cpp, whose window the refine route reads as 32k tokens."""
    session.add(
        SelectedModel(
            model_type=ModelType.TEXT_GEN, provider="llamacpp", name="Qwen3-4B"
        )
    )
    session.commit()
    _window(monkeypatch, 32_768)
    selection = type(
        "Selection",
        (),
        {"provider": "llamacpp", "name": "Qwen3-4B", "tier": Tier.CAPABLE},
    )()
    monkeypatch.setattr(
        "worker.studio.job.resolve_generation",
        lambda _session: ResolvedGeneration(selection, None),
    )


def _window(monkeypatch: pytest.MonkeyPatch, tokens: int) -> None:
    async def window(_session: Session) -> tuple[str, int]:
        return "Qwen3-4B", tokens

    monkeypatch.setattr(
        "modules.artifacts.studio_documents.router.selected_model_window", window
    )


def _draft_reply(monkeypatch: pytest.MonkeyPatch, reply: str) -> None:
    monkeypatch.setattr(
        "worker.studio.shared.generate.run_model", lambda *_a, **_k: reply
    )


def _refine_reply(monkeypatch: pytest.MonkeyPatch, reply: str) -> list[list[Message]]:
    calls: list[list[Message]] = []

    def fake(_model: object, messages: list[Message], **_kwargs: Any) -> str:
        calls.append(messages)
        return reply

    monkeypatch.setattr("worker.studio.shared.generate.complete", fake)
    return calls


def _work_off(queue: Huey) -> None:
    while (task := queue.dequeue()) is not None:
        queue.execute(task)


async def _refine(
    client: AsyncClient, session: Session, artifact_id: int, instruction: str
) -> Response:
    """Ask over HTTP with the test's own read transaction ended: SQLite has one writer."""
    session.commit()
    return await client.post(
        f"/artifacts/{artifact_id}/refine", json={"instruction": instruction}
    )


def _markdown_v1(
    session: Session,
    workspace: Workspace,
    logo_source: Document,
    monkeypatch: pytest.MonkeyPatch,
) -> Artifact:
    _draft_reply(monkeypatch, DRAFT)
    artifact = create_artifact_job(
        session,
        workspace,
        StudioJobCreate(format="docx", document_ids=[logo_source.id]),
    )
    _work_off(studio_queue)
    session.expire_all()
    assert artifact.document.status is DocumentStatus.READY
    return artifact


def _primary(artifact: Artifact) -> bytes:
    (file,) = artifact.files
    return (get_storage_settings().data_dir / file.storage_key).read_bytes()


def _count(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(Artifact))


async def test_refining_markdown_makes_the_next_version_and_leaves_the_first_alone(
    client: AsyncClient,
    session: Session,
    workspace: Workspace,
    logo_source: Document,
    local_model: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The rewritten Markdown is v2's spec and file; v1 keeps its own."""
    first = _markdown_v1(session, workspace, logo_source, monkeypatch)
    first_bytes = _primary(first)
    calls = _refine_reply(monkeypatch, f"```markdown\n{REVISED}\n```")

    response = await _refine(client, session, first.id, "Make it shorter")

    assert response.status_code == 202, response.text
    body = response.json()
    assert body["status"] == "pending"
    assert body["spec_kind"] == "markdown"
    assert body["version"] == {"root_id": first.id, "number": 2, "parent_id": first.id}
    assert body["title"] == "Halvorsen Freight proposal"

    _work_off(studio_queue)

    session.expire_all()
    second = session.get(Artifact, body["id"])
    assert second.document.status is DocumentStatus.READY, second.document.error_message
    assert second.artifact_metadata["spec"]["text"] == REVISED
    assert second.artifact_metadata["spec"]["kind"] == "markdown"
    assert (
        "A two-phase rollout."
        in docx.Document(BytesIO(_primary(second))).paragraphs[1].text
    )
    # One call, holding the whole current Markdown and the instruction.
    (messages,) = calls
    assert DRAFT in messages[-1].content
    assert "Make it shorter" in messages[-1].content
    assert first.artifact_metadata["spec"]["text"] == DRAFT
    assert _primary(first) == first_bytes


async def test_refining_a_script_runs_the_rewritten_script_in_the_runner(
    client: AsyncClient,
    session: Session,
    workspace: Workspace,
    local_model: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The rewritten script runs as v2 through the runner; v1 keeps its script and file."""
    first = create_script_document(
        session,
        workspace,
        title="Client proposal",
        format="docx",
        script=SCRIPT.format(line="Six months."),
        base_artifact_id=None,
        image_names=[],
    )
    _work_off(studio_queue)
    session.commit()
    revised = SCRIPT.format(line="Three months.")
    _refine_reply(monkeypatch, f"```python\n{revised}```")

    response = await _refine(client, session, first.id, "Halve the timeline")
    assert response.status_code == 202, response.text
    assert response.json()["spec_kind"] == "python"
    _work_off(studio_queue)

    session.expire_all()
    second = session.get(Artifact, response.json()["id"])
    assert second.document.status is DocumentStatus.READY, second.document.error_message
    assert second.artifact_metadata["spec"]["text"] == revised.strip()
    assert second.artifact_metadata["version"]["number"] == 2
    assert (
        docx.Document(BytesIO(_primary(second))).paragraphs[1].text == "Three months."
    )
    assert first.artifact_metadata["spec"]["text"] == SCRIPT.format(line="Six months.")
    assert docx.Document(BytesIO(_primary(first))).paragraphs[1].text == "Six months."


async def test_a_failed_refine_leaves_earlier_versions_untouched(
    client: AsyncClient,
    session: Session,
    workspace: Workspace,
    local_model: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A rewrite that fails fails only its own version, which keeps no spec."""
    first = create_script_document(
        session,
        workspace,
        title="Client proposal",
        format="docx",
        script=SCRIPT.format(line="Six months."),
        base_artifact_id=None,
        image_names=[],
    )
    _work_off(studio_queue)
    _refine_reply(monkeypatch, "raise ValueError('lost the table')")

    response = await _refine(client, session, first.id, "Add a table")
    _work_off(studio_queue)

    session.expire_all()
    second = session.get(Artifact, response.json()["id"])
    assert second.document.status is DocumentStatus.FAILED
    assert "lost the table" in (second.document.error_message or "")
    assert "spec" not in second.artifact_metadata
    assert first.document.status is DocumentStatus.READY
    assert first.artifact_metadata["spec"]["text"] == SCRIPT.format(line="Six months.")


async def test_a_document_longer_than_the_models_window_is_refused_with_a_reason(
    client: AsyncClient,
    session: Session,
    workspace: Workspace,
    logo_source: Document,
    local_model: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nothing is created or queued when the rewrite cannot fit the window."""
    first = _markdown_v1(session, workspace, logo_source, monkeypatch)
    _window(monkeypatch, 1_000)
    before = _count(session)

    response = await _refine(client, session, first.id, "Make it shorter")

    assert response.status_code == 409
    assert "too long for Qwen3-4B" in response.json()["detail"]
    assert _count(session) == before
    assert studio_queue.pending_count() == 0


async def test_an_artifact_without_a_spec_cannot_be_refined(
    client: AsyncClient,
    session: Session,
    workspace: Workspace,
    logo_source: Document,
    local_model: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only a Word document or PDF keeps a spec to rewrite."""
    _draft_reply(monkeypatch, "# Summary\n\nRings.")
    summary = create_artifact_job(
        session,
        workspace,
        StudioJobCreate(format="summary", document_ids=[logo_source.id]),
    )
    _work_off(studio_queue)

    response = await _refine(client, session, summary.id, "Shorter")

    assert response.status_code == 409
    assert "Word document or PDF" in response.json()["detail"]


async def test_a_version_still_being_made_cannot_be_refined(
    client: AsyncClient,
    session: Session,
    workspace: Workspace,
    logo_source: Document,
    local_model: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A pending version has no spec yet to rewrite."""
    first = _markdown_v1(session, workspace, logo_source, monkeypatch)
    pending = await _refine(client, session, first.id, "Shorter")

    response = await _refine(client, session, pending.json()["id"], "Shorter still")

    assert response.status_code == 409


@pytest.mark.parametrize("instruction", ["", "   ", "x" * 2001])
async def test_an_instruction_must_say_something_and_fit(
    client: AsyncClient,
    session: Session,
    workspace: Workspace,
    logo_source: Document,
    local_model: None,
    monkeypatch: pytest.MonkeyPatch,
    instruction: str,
) -> None:
    """An empty or overlong instruction is refused before anything is read."""
    first = _markdown_v1(session, workspace, logo_source, monkeypatch)

    response = await _refine(client, session, first.id, instruction)

    assert response.status_code == 422


async def test_refining_an_unknown_artifact_is_not_found(
    client: AsyncClient, local_model: None
) -> None:
    """An id no artifact has is a 404."""
    response = await client.post(
        "/artifacts/999/refine", json={"instruction": "Shorter"}
    )

    assert response.status_code == 404


async def test_the_figures_listed_in_the_prompt_count_against_the_window(
    client: AsyncClient,
    session: Session,
    workspace: Workspace,
    logo_source: Document,
    local_model: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A source with many captioned figures lengthens the prompt the model reads."""
    first = _markdown_v1(session, workspace, logo_source, monkeypatch)
    folder = figures_dir(
        get_storage_settings().document_dir(workspace.id, logo_source.id)
    )
    folder.mkdir(parents=True, exist_ok=True)
    caption = "Figure: freight volume by depot and quarter, " * 5
    entries = [
        {"n": n, "width": 40, "height": 20, "page": 1, "caption": caption}
        for n in range(1, 101)
    ]
    write_index(folder, entries, None)
    # Room for the short spec and the prompt, not for 100 figures' lines.
    _window(monkeypatch, 4_000)
    before = _count(session)

    response = await _refine(client, session, first.id, "Make it shorter")

    assert response.status_code == 409, response.text
    assert "too long for Qwen3-4B" in response.json()["detail"]
    assert _count(session) == before
