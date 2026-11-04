"""A firm's settings for a job reach its runs, a second model can make the checks, and a suggested
answer is confirmed in one step as the next version of the run's revised copy."""

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

from modules.agent.tool_endpoint import confirm_job
from modules.agent.tool_endpoint.tool import ToolCallError
from modules.agent.tool_endpoint.turn_scope import TurnScope
from modules.artifacts.models import Artifact
from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.jobs.packs.access import DEV_SWITCH
from modules.jobs.packs.install import install_pack
from modules.jobs.packs.installed import packs_dir
from modules.jobs.runs.record import job_run_of
from modules.workspaces.models import Workspace
from shared.config import get_storage_settings
from tests.integration.artifacts.revised_copies.source_files import add_source
from tests.integration.worker.conftest import stub_model  # noqa: F401
from tests.job_pack_samples import JOB, write_questionnaire_pack
from worker.studio import run

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("stub_model")]

HOSTED = (
    "The data centres are hosted by Google Cloud, which runs their physical security."
)
POLICY = f"## Hosting\n\n{HOSTED}"
CHECKER = {"provider": "llamacpp", "name": "gemma-4-31b", "connection_id": None}


@pytest.fixture
def pack(tmp_path: Path) -> None:
    """The test pack with its checks, its statement gate and its provider setting."""
    install_pack(
        write_questionnaire_pack(tmp_path / "pack-source", checks=True), packs_dir()
    )


@pytest.fixture
def models(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """The answering model says N/A on the hosting sentence; the check, on whichever model,
    supports it. Returns which model each call went to."""
    calls: list[str] = []

    def complete(model, messages, **_):
        calls.append(model.selection.name)
        if messages[0].content.startswith("Check"):
            return json.dumps({"supported": True, "missing": ""})
        return json.dumps(
            {
                "quotes": [{"passage": 1, "quote": HOSTED}],
                "answer": "N/A",
                "comment": "Google Cloud runs the data centres.",
                "confidence": "high",
            }
        )

    async def window(_session):
        return "answers", 32_768

    selected = SimpleNamespace(
        selection=SimpleNamespace(provider="llamacpp", name="qwen3.8-27b")
    )
    monkeypatch.setattr("worker.studio.job_run.pipeline.complete", complete)
    monkeypatch.setattr("worker.studio.job_run.pipeline.selected_model_window", window)
    monkeypatch.setattr(
        "worker.studio.job_run.pipeline.resolve_routed_generation",
        lambda _session: selected,
    )
    monkeypatch.setattr(
        "worker.studio.job_run.pipeline.api_url", lambda: "http://127.0.0.1:1"
    )
    return calls


def _questionnaire(dropdown: str = "Yes,No,N/A", questions: int = 1) -> bytes:
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.title = "Questions"
    sheet.append(["Question", "Answer", "Comments"])
    sheet.append(["Is physical access to the data centre controlled?", None, None])
    if questions > 1:
        sheet.append(["Is the data centre's power redundant?", None, None])
    rule = DataValidation(type="list", formula1=f'"{dropdown}"', allow_blank=True)
    rule.add(f"B2:B{1 + questions}")
    sheet.add_data_validation(rule)
    data = BytesIO()
    book.save(data)
    return data.getvalue()


def _sources(
    session: Session,
    workspace_id: int,
    dropdown: str = "Yes,No,N/A",
    questions: int = 1,
) -> tuple[int, int]:
    workbook_id = add_source(
        session, workspace_id, "Questionnaire.xlsx", _questionnaire(dropdown, questions)
    )
    policy = Document(
        workspace_id=workspace_id,
        title="Hosting standard",
        document_type=DocumentType.NOTE,
        status=DocumentStatus.READY,
        content=POLICY,
    )
    session.add(policy)
    session.commit()
    return workbook_id, policy.id


async def _ran(
    client: AsyncClient,
    session: Session,
    workspace_id: int,
    dropdown: str = "Yes,No,N/A",
    questions: int = 1,
) -> tuple[int, dict]:
    workbook_id, policy_id = _sources(session, workspace_id, dropdown, questions)
    started = await client.post(
        f"/workspaces/{workspace_id}/job-runs",
        json={"job": JOB, "document_id": workbook_id, "source_ids": [policy_id]},
    )
    assert started.status_code == 201, started.text
    artifact_id = started.json()["artifact_id"]
    await asyncio.to_thread(run, artifact_id)
    session.expire_all()
    artifact = session.get(Artifact, artifact_id)
    assert artifact.document.status is DocumentStatus.READY, (
        artifact.document.error_message
    )
    record = job_run_of(artifact.artifact_metadata)
    session.rollback()
    return artifact_id, record


def _filled(session: Session, artifact_id: int) -> openpyxl.Workbook:
    artifact = session.get(Artifact, artifact_id)
    (file,) = artifact.files
    stored = get_storage_settings().data_dir / file.storage_key
    session.rollback()
    return openpyxl.load_workbook(stored)


async def test_a_job_s_settings_are_read_and_set_whole(
    client: AsyncClient, pack: None
) -> None:
    """Every setting the pack declares is listed at its default until the firm sets it; a
    setting the job does not declare is refused."""
    path = f"/job-packs/jobs/{JOB}/settings"
    first = (await client.get(path)).json()
    assert first["settings"][0]["key"] == "provider_na"
    assert not first["settings"][0]["value"] and first["checker"] is None

    put = await client.put(
        path, json={"settings": {"provider_na": True}, "checker": CHECKER}
    )
    assert put.status_code == 200, put.text
    after = (await client.get(path)).json()
    assert after["settings"][0]["value"] and after["checker"] == CHECKER

    refused = await client.put(path, json={"settings": {"guess": True}})
    assert refused.status_code == 422
    assert refused.json()["detail"]["code"] == "BAD_JOB_SETTINGS"
    missing = await client.get("/job-packs/jobs/no-such-job/settings")
    assert missing.status_code == 404


async def test_a_suggested_n_a_is_confirmed_as_the_next_version(
    session: Session,
    workspace: Workspace,
    client: AsyncClient,
    pack: None,
    models: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Off by default, the provider N/A is left to a person with N/A suggested; one call
    confirms it, in the requester's cells and on both added sheets."""
    monkeypatch.setenv(DEV_SWITCH, "1")
    workspace_id = workspace.id
    artifact_id, record = await _ran(client, session, workspace_id)

    report = record["report"]
    (answer,) = report["answers"]
    assert record["settings"] == {"provider_na": False}
    assert (answer["answer"], answer["suggested"]) == ("Needs review", "N/A")
    assert report["suggested"] == 1 and answer["confirm"]["written"] == "N/A"
    first = _filled(session, artifact_id)
    assert first["Questions"]["B2"].value is None
    assert first["Questions"]["C2"].value.startswith("Needs review: Suggested: N/A.")

    confirmed = await client.post(
        f"/workspaces/{workspace_id}/job-runs/{artifact_id}/confirm", json={}
    )
    assert confirmed.status_code == 202, confirmed.text
    version = confirmed.json()["artifact_id"]
    await asyncio.to_thread(run, version)
    session.expire_all()
    made = session.get(Artifact, version)
    assert made.document.status is DocumentStatus.READY, made.document.error_message
    session.rollback()

    second = _filled(session, version)
    questions = second["Questions"]
    assert questions["B2"].value == "N/A"
    assert questions["C2"].value.startswith("Google Cloud runs the data centres.")
    assert second["SurfSense answers"]["D2"].value == "N/A"
    assert second["SurfSense exceptions"]["E2"].value == "Confirmed by a person: N/A."

    again = await client.post(
        f"/workspaces/{workspace_id}/job-runs/{artifact_id}/confirm", json={}
    )
    assert again.status_code == 409
    assert "no suggested answers left" in again.json()["detail"]["message"]


async def test_the_agent_confirms_a_suggestion_by_its_cell(
    session: Session,
    workspace: Workspace,
    client: AsyncClient,
    pack: None,
    models: list[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Asked to, the agent confirms one suggestion by its cell; asked again, it is told the
    suggestion is already confirmed."""
    monkeypatch.setenv(DEV_SWITCH, "1")
    workspace_id = workspace.id
    artifact_id, _ = await _ran(client, session, workspace_id)

    def made(_session, version_id, _seconds):
        run(version_id)
        return SimpleNamespace(status=DocumentStatus.READY, error_message=None)

    monkeypatch.setattr(
        "modules.agent.tool_endpoint.confirm_job.wait_for_outcome", made
    )
    scope = TurnScope(workspace_id, 1, tmp_path, frozenset(), known=False)
    arguments = {"artifact_id": artifact_id, "cells": ["Questions!B2"]}

    said = await asyncio.to_thread(confirm_job.run, session, scope, arguments)

    assert said.startswith("Done: The confirmed version")
    with pytest.raises(ToolCallError, match="No suggestion is left to confirm"):
        await asyncio.to_thread(confirm_job.run, session, scope, arguments)


async def test_the_firm_s_setting_and_checker_reach_the_run(
    session: Session,
    workspace: Workspace,
    client: AsyncClient,
    pack: None,
    models: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With the provider setting on, the checked N/A is written; the check goes to the
    firm's checker model, and the run records both."""
    monkeypatch.setenv(DEV_SWITCH, "1")
    put = await client.put(
        f"/job-packs/jobs/{JOB}/settings",
        json={"settings": {"provider_na": True}, "checker": CHECKER},
    )
    assert put.status_code == 200, put.text

    artifact_id, record = await _ran(client, session, workspace.id)

    assert record["settings"] == {"provider_na": True}
    assert record["checker"] == CHECKER
    (answer,) = record["report"]["answers"]
    assert (answer["answer"], answer["suggested"]) == ("N/A", None)
    assert record["report"]["checker"] == "gemma-4-31b"
    assert models == ["qwen3.8-27b", "gemma-4-31b"]
    assert _filled(session, artifact_id)["Questions"]["B2"].value == "N/A"


async def test_a_confirmation_whose_version_failed_can_be_made_again(
    session: Session,
    workspace: Workspace,
    client: AsyncClient,
    pack: None,
    models: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A version that failed confirmed nothing: its suggestion is offered again, and the next
    confirmation makes another version."""
    monkeypatch.setenv(DEV_SWITCH, "1")
    workspace_id = workspace.id
    artifact_id, _ = await _ran(client, session, workspace_id)
    path = f"/workspaces/{workspace_id}/job-runs/{artifact_id}/confirm"

    first = await client.post(path, json={})
    assert first.status_code == 202, first.text
    failed = session.get(Artifact, first.json()["artifact_id"])
    failed.document.status = DocumentStatus.FAILED
    session.commit()

    again = await client.post(
        path, json={"cells": [{"sheet": "Questions", "cell": "B2"}]}
    )

    assert again.status_code == 202, again.text
    assert again.json()["artifact_id"] != first.json()["artifact_id"]


async def test_a_suggestion_the_dropdown_cannot_hold_is_not_offered(
    session: Session,
    workspace: Workspace,
    client: AsyncClient,
    pack: None,
    models: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With no N/A on the cell's dropdown, the suggestion stays in the comment, and the run
    offers nothing to confirm."""
    monkeypatch.setenv(DEV_SWITCH, "1")
    workspace_id = workspace.id
    artifact_id, record = await _ran(client, session, workspace_id, dropdown="Yes,No")

    (answer,) = record["report"]["answers"]
    assert (answer["suggested"], answer["confirm"]) == ("N/A", None)
    assert record["report"]["suggested"] == 0
    refused = await client.post(
        f"/workspaces/{workspace_id}/job-runs/{artifact_id}/confirm", json={}
    )
    assert refused.status_code == 409


async def _confirm(client: AsyncClient, workspace_id: int, artifact_id: int, *cells):
    body = (
        {"cells": [{"sheet": "Questions", "cell": c} for c in cells]} if cells else {}
    )
    return await client.post(
        f"/workspaces/{workspace_id}/job-runs/{artifact_id}/confirm", json=body
    )


async def test_a_deleted_confirmation_is_offered_again_though_its_id_comes_back(
    session: Session,
    workspace: Workspace,
    client: AsyncClient,
    pack: None,
    models: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The database hands a deleted version's id to the next version; what is offered is read
    from the versions that stand, so the deleted one's suggestion is open again."""
    monkeypatch.setenv(DEV_SWITCH, "1")
    workspace_id = workspace.id
    artifact_id, _ = await _ran(client, session, workspace_id, questions=2)

    first = await _confirm(client, workspace_id, artifact_id, "B2")
    assert first.status_code == 202, first.text
    version_id = first.json()["artifact_id"]
    await asyncio.to_thread(run, version_id)
    deleted = await client.delete(f"/artifacts/{version_id}")
    assert deleted.status_code == 204, deleted.text

    second = await _confirm(client, workspace_id, artifact_id, "B3")
    assert second.status_code == 202, second.text
    assert second.json()["artifact_id"] == version_id  # the id came back
    await asyncio.to_thread(run, version_id)

    again = await _confirm(client, workspace_id, artifact_id, "B2")
    assert again.status_code == 202, again.text
    taken = await _confirm(client, workspace_id, artifact_id, "B3")
    assert taken.status_code == 409


async def test_a_cancelled_confirmation_is_offered_again(
    session: Session,
    workspace: Workspace,
    client: AsyncClient,
    pack: None,
    models: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A version cancelled in Studio wrote nothing, so its suggestion is still open."""
    monkeypatch.setenv(DEV_SWITCH, "1")
    workspace_id = workspace.id
    artifact_id, _ = await _ran(client, session, workspace_id)
    first = await _confirm(client, workspace_id, artifact_id)
    cancelled = session.get(Artifact, first.json()["artifact_id"])
    cancelled.document.status = DocumentStatus.CANCELLED
    session.commit()

    again = await _confirm(client, workspace_id, artifact_id, "B2")

    assert again.status_code == 202, again.text


async def test_the_agent_says_when_its_confirmed_version_was_cancelled(
    session: Session,
    workspace: Workspace,
    client: AsyncClient,
    pack: None,
    models: list[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The tool commits the run's record of what it confirmed, and says so plainly when the
    version it made was cancelled in Studio."""
    monkeypatch.setenv(DEV_SWITCH, "1")
    workspace_id = workspace.id
    artifact_id, _ = await _ran(client, session, workspace_id)
    monkeypatch.setattr(
        "modules.agent.tool_endpoint.confirm_job.wait_for_outcome",
        lambda _session, _id, _seconds: SimpleNamespace(
            status=DocumentStatus.CANCELLED, error_message=None
        ),
    )
    scope = TurnScope(workspace_id, 1, tmp_path, frozenset(), known=False)

    said = await asyncio.to_thread(
        confirm_job.run, session, scope, {"artifact_id": artifact_id}
    )

    assert "was cancelled in Studio" in said
    session.expire_all()
    record = job_run_of(session.get(Artifact, artifact_id).artifact_metadata)
    assert [c["cell"] for c in record["confirmed"]] == ["B2"]
