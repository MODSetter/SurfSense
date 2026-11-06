"""A contract redline runs through Studio as a revised copy: SurfSense's tracked changes and
comments in a copy of the contract, its internal comments kept out of the other side's file, and
the user's own file never written."""

import asyncio
import io
import json
from pathlib import Path
from types import SimpleNamespace

import docx
import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session

from modules.artifacts.models import Artifact
from modules.artifacts.revised_copies.revision import EXTERNAL, REVISION_KEY
from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.jobs.packs.access import DEV_SWITCH
from modules.jobs.packs.install import install_pack
from modules.jobs.packs.installed import packs_dir
from modules.workspaces.models import Workspace
from shared.config import get_storage_settings
from tests.integration.artifacts.job_runs.started_runs import questionnaire
from tests.integration.artifacts.revised_copies.source_files import (
    add_source,
    source_path,
)
from tests.integration.worker.conftest import stub_model  # noqa: F401
from tests.job_pack_samples import REDLINE_JOB, write_contract_pack
from tests.live.revised_files import RedlinedWord
from worker.studio import run

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("stub_model")]

PLAYBOOK = (
    "## Compelled disclosure\n\nBefore any disclosure the law compels, the Receiving Party "
    "gives the Disclosing Party prompt written notice where the law allows."
)
NOTICE = "gives the Disclosing Party prompt written notice where the law allows"
REASON = "We ask for notice before any compelled disclosure."
REPLIES = {
    "Compelled disclosure": {
        "paragraphs": ["P3"],
        "playbook_passage": 1,
        "playbook_quote": NOTICE,
        "internal_comment": "The contract allows a compelled disclosure without notice.",
        "verdict": "deviates",
        "edit": {
            "kind": "replace",
            "paragraph": "P3",
            "old_text": "when required by law",
            "new_text": "when required by law, after prompt written notice",
        },
        "external_comment": REASON,
    },
    "Term": {
        "paragraphs": [],
        "playbook_passage": 0,
        "playbook_quote": "",
        "internal_comment": "The playbook says nothing on the term.",
        "verdict": "not_covered",
        "edit": {"kind": "none", "paragraph": "", "old_text": "", "new_text": ""},
        "external_comment": "",
    },
}


def _contract() -> bytes:
    document = docx.Document()
    document.add_paragraph("MUTUAL NON-DISCLOSURE AGREEMENT", style="Title")
    for clause in (
        "The Receiving Party shall keep Confidential Information secret.",
        "The Receiving Party may disclose Confidential Information when required by law.",
    ):
        document.add_paragraph(clause, style="List Number")
    data = io.BytesIO()
    document.save(data)
    return data.getvalue()


@pytest.fixture
def pack(tmp_path: Path) -> None:
    """The test redline pack, installed where the app finds packs."""
    install_pack(write_contract_pack(tmp_path / "redline-source"), packs_dir())


@pytest.fixture
def model(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """The selected model, settling each review point from REPLIES; returns the points asked."""
    asked: list[str] = []

    def complete(_model, messages, **_):
        point = messages[1].content.split("Point:")[-1].strip()
        asked.append(point)
        return json.dumps(REPLIES[point])

    async def window(_session):
        return "fake", 32_768

    selected = SimpleNamespace(selection=SimpleNamespace(provider="fake", name="fake"))
    monkeypatch.setattr("worker.studio.job_run.pipeline.complete", complete)
    monkeypatch.setattr("worker.studio.job_run.pipeline.selected_model_window", window)
    monkeypatch.setattr(
        "worker.studio.job_run.pipeline.resolve_routed_generation",
        lambda _session: selected,
    )
    return asked


def _playbook(session: Session, workspace_id: int) -> int:
    playbook = Document(
        workspace_id=workspace_id,
        title="NDA playbook",
        document_type=DocumentType.NOTE,
        status=DocumentStatus.READY,
        content=PLAYBOOK,
    )
    session.add(playbook)
    session.commit()
    return playbook.id


async def test_a_redline_tracks_its_changes_in_a_copy_and_keeps_the_users_file(
    session: Session,
    workspace: Workspace,
    client: AsyncClient,
    pack: None,
    model: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A redline started by the route makes SurfSense's tracked change and comments in a copy, keeps its reasoning out of the file for the other side, reports its points, and leaves the user's contract byte for byte."""
    monkeypatch.setenv(DEV_SWITCH, "1")
    original = _contract()
    workspace_id = workspace.id
    contract_id = add_source(session, workspace_id, "Their NDA.docx", original)
    playbook_id = _playbook(session, workspace_id)

    started = await client.post(
        f"/workspaces/{workspace_id}/job-runs",
        json={
            "job": REDLINE_JOB,
            "document_id": contract_id,
            "source_ids": [playbook_id],
        },
    )
    assert started.status_code == 201, started.text
    artifact_id = started.json()["artifact_id"]
    await asyncio.to_thread(run, artifact_id)

    session.expire_all()
    artifact = session.get(Artifact, artifact_id)
    assert artifact.document.status is DocumentStatus.READY, (
        artifact.document.error_message
    )
    assert (
        source_path(workspace_id, contract_id, "Their NDA.docx").read_bytes()
        == original
    )
    data_dir = get_storage_settings().data_dir
    (file,) = artifact.files
    stored = data_dir / file.storage_key
    external = (
        data_dir / artifact.artifact_metadata[REVISION_KEY][EXTERNAL]["storage_key"]
    )
    # Every transaction holds the write lock; the route below needs it.
    session.rollback()
    revised = RedlinedWord(stored.read_bytes())
    assert [i.text for i in revised.insertions] == [", after prompt written notice"]
    assert {i.author for i in revised.insertions} == {"SurfSense"}
    comments = [c.text for c in revised.comments]
    assert REASON in comments
    assert any(NOTICE in c for c in comments)
    assert any("SurfSense reviewed 2 points" in c for c in comments)
    other_side = RedlinedWord(external.read_bytes())
    assert [c.text for c in other_side.comments] == [REASON]
    assert sorted(model) == ["Compelled disclosure", "Term"]

    read = (
        await client.get(f"/workspaces/{workspace_id}/job-runs/{artifact_id}")
    ).json()
    assert read["report"]["counts"] == {
        "changed": 1,
        "meets": 0,
        "not_covered": 1,
        "for_person": 0,
        "skipped": 0,
    }
    assert read["tally"]["questions"] == 2
    assert read["tally"]["for_person"] == 0


async def test_a_redline_takes_a_word_contract_not_a_workbook(
    session: Session,
    workspace: Workspace,
    client: AsyncClient,
    pack: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The redline refuses a workbook in the contract's place, saying what it takes."""
    monkeypatch.setenv(DEV_SWITCH, "1")
    workbook_id = add_source(session, workspace.id, "Q.xlsx", questionnaire())
    playbook_id = _playbook(session, workspace.id)

    refused = await client.post(
        f"/workspaces/{workspace.id}/job-runs",
        json={
            "job": REDLINE_JOB,
            "document_id": workbook_id,
            "source_ids": [playbook_id],
        },
    )

    assert refused.status_code == 409
    assert "reviews a Word contract (.docx)" in refused.json()["detail"]["message"]


async def test_the_listing_names_each_jobs_runner(
    client: AsyncClient, pack: None
) -> None:
    """Each listed job names its runner, so a screen can offer the form for its file."""
    listed = (await client.get("/job-packs")).json()

    assert [(j["key"], j["runner"]) for p in listed for j in p["jobs"]] == [
        (REDLINE_JOB, "word-clauses/1")
    ]


async def test_a_redline_without_a_second_check_says_so_in_its_settings(
    client: AsyncClient, pack: None
) -> None:
    """A job whose pack makes no second check says so, so no screen offers a checker it
    would never use."""
    read = (await client.get(f"/job-packs/jobs/{REDLINE_JOB}/settings")).json()

    assert read["checks"] is False
    assert [s["key"] for s in read["settings"]] == ["external_comments"]
