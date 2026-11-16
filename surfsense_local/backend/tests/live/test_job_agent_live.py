"""A job reached from an Agentic chat on a live model: with a pack installed, the agent loads the
job's skill and runs the job on the ticked workbook and policies, rather than answering itself.

The pack and the case come from SURFSENSE_LIVE_JOB_PACK and SURFSENSE_LIVE_JOB_CASE, as
for test_job_run_live.py; the case's gold scores the answers the run kept.
"""

import json
import os
import time
from pathlib import Path

import pytest

from modules.jobs.packs.access import DEV_SWITCH
from tests.integration.agent.test_agent_threads import send
from tests.integration.conftest import base_url  # noqa: F401
from tests.live.live_agent import LiveAgent, answer, steps

pytestmark = pytest.mark.live

CASE = "job-agent"
PROMPT = (
    "Fill in the client's security questionnaire, {workbook}, from our security "
    "policies, then tell me how it went."
)
RUN_SECONDS = 1_200


async def test_the_agent_runs_the_job_on_the_ticked_files(
    live: LiveAgent,
    base_url: str,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The agent calls the job tool on the workbook, the run fills it as a revised copy, and no Yes goes unsupported."""
    if not os.environ.get("SURFSENSE_LIVE_JOB_PACK") or not os.environ.get(
        "SURFSENSE_LIVE_JOB_CASE"
    ):
        pytest.skip("set SURFSENSE_LIVE_JOB_PACK and SURFSENSE_LIVE_JOB_CASE")
    monkeypatch.setenv(DEV_SWITCH, "1")
    # The Studio worker reaches the model through the API, at the address Electron hands it.
    monkeypatch.setenv("SURFSENSE_LOCAL_PORT", base_url.rsplit(":", 1)[1])
    folder = Path(os.environ["SURFSENSE_LIVE_JOB_CASE"])
    case = json.loads((folder / "case.json").read_text(encoding="utf-8"))
    gold = json.loads((folder / case["gold"]).read_text(encoding="utf-8"))["rows"]
    installed = await live.http.post(
        "/job-packs/install", json={"path": os.environ["SURFSENSE_LIVE_JOB_PACK"]}
    )
    assert installed.status_code == 200, installed.text
    workbook_path = folder / case["workbook"]
    sources = [
        await live.upload(Path(path).name, (folder / path).read_bytes())
        for path in case["sources"]
    ]
    workbook = await live.upload(workbook_path.name, workbook_path.read_bytes())
    await live.wait_ready(*sources, workbook)
    thread = await live.thread()

    frames: list[dict] = []

    async def keep(frame: dict) -> None:
        frames.append(frame)

    prompt = PROMPT.format(workbook=workbook_path.name)
    started = time.monotonic()
    try:
        await send(
            live,  # type: ignore[arg-type]
            thread,
            prompt,
            on_frame=keep,
            source_scope={"document_ids": [*sources, workbook]},
        )
    finally:
        live.run.add_turn(prompt, frames)
    calls = [
        s for s in steps(frames, "surfsense_run_job") if s["status"] == "completed"
    ]
    metrics = live.run.metrics
    metrics["seconds"] = round(time.monotonic() - started, 1)
    metrics["job_calls"] = len(calls)
    metrics["revise_calls"] = len(steps(frames, "surfsense_revise_document"))
    metrics["reply"] = answer(frames)
    assert calls, "the agent never ran the job"

    runs = [a for a in await live.artifacts() if a["format"] == "xlsx"]
    assert runs, "no revised copy of the workbook"
    run_id = runs[0]["id"]
    while True:
        read = (
            await live.http.get(f"/workspaces/{live.workspace_id}/job-runs/{run_id}")
        ).json()
        if read["status"] in ("ready", "failed", "cancelled"):
            break
        assert time.monotonic() - started < RUN_SECONDS, "the run took too long"
        await live.http.get("/health")
        time.sleep(3)
    assert read["status"] == "ready", read["error"]
    by_cell = {(a["sheet"].casefold(), a["cell"]): a for a in read["report"]["answers"]}
    rows = [
        {
            "cell": row["cell"],
            "gold": row["answer"],
            "answer": by_cell.get((row["sheet"].casefold(), row["cell"]), {}).get(
                "answer"
            ),
        }
        for row in gold
    ]
    metrics["correct"] = sum(1 for r in rows if r["answer"] == r["gold"])
    metrics["scored"] = len(rows)
    metrics["false_yes"] = sum(
        1 for r in rows if r["answer"] == "Yes" and r["gold"] != "Yes"
    )
    metrics["rows"] = rows
    live.run.keep_document(
        f"{run_id}-filled{workbook_path.suffix}", await live.file(run_id), None
    )
    assert metrics["false_yes"] == 0, "a Yes the gold does not support"
