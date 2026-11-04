"""A job run fills in the requester's workbook through Studio, as a revised copy whose answers
the worker works out, and never writes the user's own file."""

import asyncio
import json
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import openpyxl
import pytest
from httpx import AsyncClient
from openpyxl.worksheet.datavalidation import DataValidation
from sqlalchemy.orm import Session

from modules.artifacts.models import Artifact
from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.jobs.packs.access import DEV_SWITCH
from modules.jobs.packs.install import install_pack
from modules.jobs.packs.installed import packs_dir
from modules.workspaces.models import Workspace
from shared.config import get_storage_settings
from tests.integration.artifacts.revised_copies.source_files import (
    add_source,
    source_path,
)
from tests.integration.worker.conftest import stub_model  # noqa: F401
from tests.job_pack_samples import JOB, write_questionnaire_pack
from worker.studio import run

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("stub_model")]

PLAN = (
    "## Access\n\nAccess to client data is granted on a least-privilege basis.\n\n"
    "## Payments\n\nThe firm does not store or process card payments."
)
REPLIES = {
    "minimum access": {
        "quotes": [
            {
                "passage": 1,
                "quote": "Access to client data is granted on a least-privilege basis.",
            }
        ],
        "answer": "Yes",
    },
    "card data": {
        "quotes": [
            {
                "passage": 2,
                "quote": "The firm does not store or process card payments.",
            }
        ],
        "answer": "N/A",
    },
    "breach": {"quotes": [], "answer": "Needs review"},
}


def _questionnaire() -> bytes:
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.title = "Questions"
    sheet.append(["Question", "Answer", "Comments"])
    sheet.append(["Do users have the minimum access they need?", None, None])
    sheet.append(["Is card data encrypted when stored?", None, None])
    sheet.append(["Have you had a breach this year?", None, None])
    rule = DataValidation(type="list", formula1='"Yes,No,NA"', allow_blank=True)
    rule.add("B2:B4")
    sheet.add_data_validation(rule)
    data = BytesIO()
    book.save(data)
    return data.getvalue()


@pytest.fixture
def pack(tmp_path: Path) -> None:
    """The test pack, installed where the app finds packs."""
    install_pack(write_questionnaire_pack(tmp_path / "pack-source"), packs_dir())


@pytest.fixture
def model(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """The selected model, answering each question from REPLIES; returns what it was asked."""
    asked: list[str] = []

    def complete(_model, messages, **_):
        question = messages[-1].content.split("Question:")[-1]
        asked.append(question)
        reply = next(r for key, r in REPLIES.items() if key in question)
        return json.dumps({**reply, "comment": "From the plan.", "confidence": "high"})

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


def _plan(session: Session, workspace_id: int) -> int:
    plan = Document(
        workspace_id=workspace_id,
        title="Security plan",
        document_type=DocumentType.NOTE,
        status=DocumentStatus.READY,
        content=PLAN,
    )
    session.add(plan)
    session.commit()
    return plan.id


async def test_a_run_answers_in_the_requesters_cells_and_keeps_the_users_file(
    session: Session,
    workspace: Workspace,
    client: AsyncClient,
    pack: None,
    model: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A run started by the route answers in the requester's own cells, adds its two sheets, reports its counts, and leaves the user's file byte for byte."""
    monkeypatch.setenv(DEV_SWITCH, "1")
    original = _questionnaire()
    workspace_id = workspace.id
    workbook_id = add_source(
        session, workspace_id, "Client questionnaire.xlsx", original
    )
    plan_id = _plan(session, workspace_id)

    started = await client.post(
        f"/workspaces/{workspace_id}/job-runs",
        json={"job": JOB, "document_id": workbook_id, "source_ids": [plan_id]},
    )
    assert started.status_code == 201, started.text
    artifact_id = started.json()["artifact_id"]
    # The worker runs in its own process, with no event loop of its own running.
    await asyncio.to_thread(run, artifact_id)

    session.expire_all()
    artifact = session.get(Artifact, artifact_id)
    assert artifact.document.status is DocumentStatus.READY, (
        artifact.document.error_message
    )
    assert (
        source_path(workspace_id, workbook_id, "Client questionnaire.xlsx").read_bytes()
        == original
    )
    (file,) = artifact.files
    stored = get_storage_settings().data_dir / file.storage_key
    # Every transaction holds the write lock; the route below needs it.
    session.rollback()
    filled = openpyxl.load_workbook(stored)
    answers = filled["Questions"]
    assert [answers[f"B{r}"].value for r in (2, 3, 4)] == ["Yes", "NA", None]
    assert answers["C4"].value.startswith("Needs review:")
    assert filled.sheetnames == [
        "Questions",
        "SurfSense answers",
        "SurfSense exceptions",
    ]
    assert len(model) == 3

    read = await client.get(f"/workspaces/{workspace_id}/job-runs/{artifact_id}")
    report = read.json()["report"]
    assert report["counts"] == {
        "Yes": 1,
        "N/A": 1,
        "Needs review": 1,
        "blank": 1,
        "skipped": 0,
    }
    assert [row["source"] for row in report["answers"]] == [
        "Security plan",
        "Security plan",
        "",
    ]


async def test_a_paid_job_needs_a_business_licence(
    session: Session, workspace: Workspace, client: AsyncClient, pack: None
) -> None:
    """Without a Business licence or the developer switch, a paid job does not start."""
    workbook_id = add_source(session, workspace.id, "Q.xlsx", _questionnaire())
    plan_id = _plan(session, workspace.id)

    refused = await client.post(
        f"/workspaces/{workspace.id}/job-runs",
        json={"job": JOB, "document_id": workbook_id, "source_ids": [plan_id]},
    )

    assert refused.status_code == 409
    assert "Business licence" in refused.json()["detail"]["message"]


async def test_installed_packs_are_listed_with_whether_they_may_run(
    client: AsyncClient, pack: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The pack list says which packs may run, so a screen can offer or explain them."""
    locked = (await client.get("/job-packs")).json()
    monkeypatch.setenv(DEV_SWITCH, "1")
    unlocked = (await client.get("/job-packs")).json()

    assert [(p["id"], p["unlocked"]) for p in locked] == [("test-jobs", False)]
    assert unlocked[0]["unlocked"] and unlocked[0]["jobs"][0]["key"] == JOB
    (job,) = locked[0]["jobs"]
    assert (job["entitlement"], job["unlocked"]) == ("JOB_TEST_QUESTIONNAIRE", False)
    assert "Business licence" in job["locked_reason"]
    assert job["locked_reason"] == locked[0]["locked_reason"]


async def test_a_run_retried_without_access_fails_with_the_reason(
    session: Session,
    workspace: Workspace,
    client: AsyncClient,
    pack: None,
    model: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The worker checks access as well, so a run worked out after access is lost, as Studio's
    Retry does, fails with the licence's reason and asks the model nothing."""
    monkeypatch.setenv(DEV_SWITCH, "1")
    workspace_id = workspace.id
    workbook_id = add_source(session, workspace_id, "Q.xlsx", _questionnaire())
    plan_id = _plan(session, workspace_id)
    started = await client.post(
        f"/workspaces/{workspace_id}/job-runs",
        json={"job": JOB, "document_id": workbook_id, "source_ids": [plan_id]},
    )
    assert started.status_code == 201, started.text
    monkeypatch.delenv(DEV_SWITCH)

    await asyncio.to_thread(run, started.json()["artifact_id"])

    session.expire_all()
    artifact = session.get(Artifact, started.json()["artifact_id"])
    assert artifact.document.status is DocumentStatus.FAILED
    assert "Business licence" in (artifact.document.error_message or "")
    assert model == []
