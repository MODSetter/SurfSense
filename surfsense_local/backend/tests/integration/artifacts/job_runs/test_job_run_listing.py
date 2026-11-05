"""A workspace's job runs as the Jobs screen reads them: newest first, how far each has got, its
counts and the suggested answers still open, any version of its copy reading the run, and
exactly the keys the screen is typed by."""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from httpx import AsyncClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from modules.artifacts.models import Artifact
from modules.artifacts.revised_copies.service import create_revised_copy
from modules.artifacts.revised_copies.source_file import sha256_of, source_file
from modules.documents.models import DocumentStatus
from modules.jobs.packs.access import DEV_SWITCH
from modules.jobs.packs.install import install_pack
from modules.jobs.packs.installed import packs_dir
from modules.jobs.runs.record import job_run_of
from modules.workspaces.models import Workspace
from shared.db import create_session_factory
from tests.integration.artifacts.job_runs.started_runs import questionnaire, start_run
from tests.integration.artifacts.revised_copies.source_files import (
    add_source,
    pricing_xlsx,
)
from tests.integration.worker.conftest import stub_model  # noqa: F401
from tests.job_pack_samples import JOB, PACK_ID, write_questionnaire_pack
from worker.studio import run

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("stub_model")]

HOSTED = (
    "The data centres are hosted by Google Cloud, which runs their physical security."
)
POLICY = f"## Hosting\n\n{HOSTED}"
QUESTIONS = (
    "Is physical access to the data centre controlled?",
    "Is the data centre's power redundant?",
)

# The keys of spec 4.10, which the frontend's api.ts is typed by.
SUMMARY_KEYS = {
    "artifact_id",
    "title",
    "job",
    "pack_id",
    "pack_version",
    "status",
    "error",
    "created_at",
    "progress",
    "tally",
    "open_suggestion_count",
    "newest_version_id",
    "newest_version_number",
    "newest_ready_version_id",
    "running",
}
READ_KEYS = SUMMARY_KEYS | {"pack", "report", "open_suggestions", "confirmed"}
TALLY_KEYS = {"questions", "answered", "for_person", "suggested", "skipped"}
SUGGESTION_KEYS = {"sheet", "cell", "question", "suggested", "written", "comment"}
CONFIRMED_KEYS = {"sheet", "cell", "artifact_id"}
PACK_KEYS = {
    "id",
    "version",
    "name",
    "publisher",
    "access",
    "unlocked",
    "locked_reason",
    "locked_code",
    "jobs",
}
JOB_KEYS = {
    "key",
    "name",
    "description",
    "entitlement",
    "unlocked",
    "locked_reason",
    "locked_code",
}
NOT_FOUND = {"code": "NOT_FOUND", "message": "No such job run."}


@pytest.fixture(autouse=True)
def unlocked(monkeypatch: pytest.MonkeyPatch) -> None:
    """Paid jobs run without a license, as on a developer's build."""
    monkeypatch.setenv(DEV_SWITCH, "1")


@pytest.fixture
def pack(tmp_path: Path) -> None:
    """The test pack with its second check and its statement gate."""
    install_pack(
        write_questionnaire_pack(tmp_path / "pack-source", checks=True), packs_dir()
    )


@pytest.fixture
def model(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Every question gets N/A on the hosting sentence, which the check supports, so each is
    left to a person with N/A suggested. Returns the questions asked."""
    asked: list[str] = []

    def complete(_model, messages, **_):
        if messages[0].content.startswith("Check"):
            return json.dumps({"supported": True, "missing": ""})
        asked.append(messages[-1].content)
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
    return asked


async def made(session: Session, artifact_id: int) -> None:
    """Work a run or a version out in the Studio worker, as its own process would."""
    await asyncio.to_thread(run, artifact_id)
    session.expire_all()
    artifact = session.get(Artifact, artifact_id)
    assert artifact.document.status is DocumentStatus.READY, (
        artifact.document.error_message
    )
    # Every transaction holds the write lock; the routes need it.
    session.rollback()


async def worked_out(
    client: AsyncClient, session: Session, workspace_id: int, questions: int = 1
) -> int:
    """A finished run over a questionnaire of `questions` rows."""
    run_id = await start_run(
        client, session, workspace_id, questionnaire(*QUESTIONS[:questions]), POLICY
    )
    await made(session, run_id)
    return run_id


async def confirm(
    client: AsyncClient, workspace_id: int, run_id: int, *cells: str
) -> int:
    """Confirm the run's suggestions at `cells`, or every one; the new version's id."""
    body = (
        {"cells": [{"sheet": "Questions", "cell": cell} for cell in cells]}
        if cells
        else {}
    )
    confirmed = await client.post(
        f"/workspaces/{workspace_id}/job-runs/{run_id}/confirm", json=body
    )
    assert confirmed.status_code == 202, confirmed.text
    return confirmed.json()["artifact_id"]


async def test_the_run_routes_answer_exactly_the_documented_keys(
    client: AsyncClient,
    session: Session,
    workspace: Workspace,
    pack: None,
    model: list[str],
) -> None:
    """The list, the read and the pack listing carry the keys of the screen's types, no more."""
    workspace_id = workspace.id
    run_id = await worked_out(client, session, workspace_id, questions=2)
    await made(session, await confirm(client, workspace_id, run_id, "B2"))

    (summary,) = (await client.get(f"/workspaces/{workspace_id}/job-runs")).json()
    read = (await client.get(f"/workspaces/{workspace_id}/job-runs/{run_id}")).json()
    (listed,) = (await client.get("/job-packs")).json()

    assert set(summary) == SUMMARY_KEYS
    assert set(summary["progress"]) == {"done", "total"}
    assert set(summary["tally"]) == TALLY_KEYS
    assert set(read) == READ_KEYS
    assert {key: read[key] for key in SUMMARY_KEYS} == summary
    (still_open,) = read["open_suggestions"]
    assert set(still_open) == SUGGESTION_KEYS
    (confirmed,) = read["confirmed"]
    assert set(confirmed) == CONFIRMED_KEYS
    assert set(listed) == PACK_KEYS
    assert set(listed["jobs"][0]) == JOB_KEYS


async def test_runs_are_listed_newest_first_with_progress_and_tally(
    client: AsyncClient,
    session: Session,
    workspace: Workspace,
    pack: None,
    model: list[str],
) -> None:
    """Each run says what it is, how far it got and what it came to, newest first."""
    workspace_id = workspace.id
    first = await worked_out(client, session, workspace_id)
    second = await worked_out(client, session, workspace_id, questions=2)
    path = f"/workspaces/{workspace_id}/job-runs"

    listed = (await client.get(path)).json()

    assert [r["artifact_id"] for r in listed] == [second, first]
    newest = listed[0]
    assert (newest["title"], newest["job"], newest["pack_id"]) == (
        "Questionnaire (revised)",
        JOB,
        PACK_ID,
    )
    assert (newest["pack_version"], newest["status"], newest["error"]) == (
        "1.0.0",
        "ready",
        None,
    )
    assert newest["progress"] == {"done": 2, "total": 2}
    assert newest["tally"] == {
        "questions": 2,
        "answered": 0,
        "for_person": 0,
        "suggested": 2,
        "skipped": 0,
    }
    assert newest["open_suggestion_count"] == 2
    assert (
        newest["newest_version_id"],
        newest["newest_version_number"],
        newest["newest_ready_version_id"],
        newest["running"],
    ) == (second, 1, second, False)
    assert [r["artifact_id"] for r in (await client.get(f"{path}?limit=1")).json()] == [
        second
    ]
    assert (await client.get(f"{path}?limit=0")).status_code == 422


async def test_progress_shows_the_total_before_the_first_answer_and_keeps_the_final_count(
    client: AsyncClient,
    session: Session,
    workspace: Workspace,
    engine: Engine,
    pack: None,
    model: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A run waiting for the worker has no progress; while the first question is asked the
    total is already written, by a session of the worker's own; at the end every count is."""
    import worker.studio.job_run.pipeline as pipeline

    workspace_id = workspace.id
    run_id = await start_run(
        client, session, workspace_id, questionnaire(*QUESTIONS), POLICY
    )
    path = f"/workspaces/{workspace_id}/job-runs/{run_id}"
    pending = (await client.get(path)).json()
    assert (pending["status"], pending["progress"], pending["tally"]) == (
        "pending",
        None,
        None,
    )
    assert (pending["running"], pending["newest_ready_version_id"]) == (True, None)
    answer = pipeline.complete
    seen: list[dict] = []

    def complete(model_, messages, **kwargs):
        if not seen:
            with create_session_factory(engine)() as reader:
                record = job_run_of(reader.get(Artifact, run_id).artifact_metadata)
                seen.append(record["progress"])
        return answer(model_, messages, **kwargs)

    monkeypatch.setattr(pipeline, "complete", complete)

    await made(session, run_id)

    assert seen == [{"done": 0, "total": 2}]
    assert (await client.get(path)).json()["progress"] == {"done": 2, "total": 2}


async def test_open_suggestions_and_confirmed_cells_are_read_with_the_run(
    client: AsyncClient,
    session: Session,
    workspace: Workspace,
    pack: None,
    model: list[str],
) -> None:
    """A suggestion is open until a version of the copy writes its cell; the run keeps which
    version confirmed it."""
    workspace_id = workspace.id
    run_id = await worked_out(client, session, workspace_id)
    path = f"/workspaces/{workspace_id}/job-runs/{run_id}"

    before = (await client.get(path)).json()

    (suggestion,) = before["open_suggestions"]
    assert {k: v for k, v in suggestion.items() if k != "comment"} == {
        "sheet": "Questions",
        "cell": "B2",
        "question": QUESTIONS[0],
        "suggested": "N/A",
        "written": "N/A",
    }
    assert suggestion["comment"].startswith("Google Cloud runs the data centres.")
    assert (before["open_suggestion_count"], before["confirmed"]) == (1, [])

    version = await confirm(client, workspace_id, run_id)
    making = (await client.get(path)).json()

    assert (making["running"], making["newest_version_id"]) == (True, version)
    assert making["newest_version_number"] == 2
    assert making["newest_ready_version_id"] == run_id
    assert (making["open_suggestions"], making["open_suggestion_count"]) == ([], 0)
    assert making["confirmed"] == [
        {"sheet": "Questions", "cell": "B2", "artifact_id": version}
    ]

    await made(session, version)
    after = (await client.get(path)).json()

    assert (after["running"], after["newest_ready_version_id"]) == (False, version)
    assert after["tally"]["suggested"] == 1


async def test_any_version_reads_the_run_and_nothing_outside_it_does(
    client: AsyncClient,
    session: Session,
    workspace: Workspace,
    pack: None,
    model: list[str],
) -> None:
    """Studio opens a copy's newest version and reads its run by it; a revised copy no job
    made is no run, and another workspace's run is neither listed nor read."""
    workspace_id = workspace.id
    run_id = await worked_out(client, session, workspace_id)
    version = await confirm(client, workspace_id, run_id)
    source = source_file(
        session,
        workspace_id,
        add_source(session, workspace_id, "Pricing.xlsx", pricing_xlsx()),
    )
    plain = create_revised_copy(
        session,
        workspace_id,
        source,
        source_sha256=sha256_of(source.path),
        operations=[{"op": "set_cell", "sheet": "Pricing", "cell": "B2", "value": 1}],
        chat_thread_id=None,
    ).id
    elsewhere = Workspace(name="Elsewhere")
    session.add(elsewhere)
    session.commit()
    other_id = elsewhere.id

    by_version = await client.get(f"/workspaces/{workspace_id}/job-runs/{version}")
    no_run = await client.get(f"/workspaces/{workspace_id}/job-runs/{plain}")
    other_list = await client.get(f"/workspaces/{other_id}/job-runs")
    other_read = await client.get(f"/workspaces/{other_id}/job-runs/{run_id}")

    assert by_version.json()["artifact_id"] == run_id
    assert (no_run.status_code, no_run.json()["detail"]) == (404, NOT_FOUND)
    assert other_list.json() == []
    assert (other_read.status_code, other_read.json()["detail"]) == (404, NOT_FOUND)


async def test_a_workbook_without_questions_fails_with_its_reason(
    client: AsyncClient,
    session: Session,
    workspace: Workspace,
    pack: None,
    model: list[str],
) -> None:
    """A sheet of figures fails the run with what a questionnaire needs, and asks no model."""
    workspace_id = workspace.id
    run_id = await start_run(client, session, workspace_id, pricing_xlsx(), POLICY)

    await asyncio.to_thread(run, run_id)

    read = (await client.get(f"/workspaces/{workspace_id}/job-runs/{run_id}")).json()
    assert (read["status"], read["error"]) == (
        "failed",
        "SurfSense found no questions in this workbook. It needs a column of questions "
        "and a column for answers, or answer dropdowns.",
    )
    assert (read["progress"], read["tally"]) == (None, None)
    assert model == []
