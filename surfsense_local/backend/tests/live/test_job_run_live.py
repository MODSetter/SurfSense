"""A job pack's job, run in the app on a live model: install the pack, upload a case's real files,
start the run, and score the filled workbook against the case's gold answers.

The pack and the case live with the job's own content, outside this tree:
SURFSENSE_LIVE_JOB_PACK is the pack folder, SURFSENSE_LIVE_JOB_CASE a case folder
holding case.json. The bundled embedder is read from SURFSENSE_LIVE_MODELS_DIR when
this checkout has none staged.
"""

import asyncio
import io
import json
import os
import time
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import openpyxl
import pytest
import pytest_asyncio
from sqlalchemy import Engine

from modules.jobs.packs.access import DEV_SWITCH
from tests.integration.agent.conftest import studio_worker  # noqa: F401
from tests.integration.conftest import base_url  # noqa: F401
from tests.live.conftest import _connect_model, ingest_worker  # noqa: F401
from tests.live.live_agent import LiveAgent
from tests.live.live_model import LiveModel
from tests.live.recording_proxy import RecordingProxy
from tests.live.run_folder import RunFolder
from tests.live.spend_ledger import SpendLedger

pytestmark = pytest.mark.live

CASE = "job-run"
RUN_SECONDS = 1_800


@pytest.fixture
def embedder(monkeypatch: pytest.MonkeyPatch) -> None:
    """The bundled embedder ingest needs, from this checkout or the folder named."""
    folder = os.environ.get("SURFSENSE_LIVE_MODELS_DIR")
    if folder:
        monkeypatch.setenv("SURFSENSE_LOCAL_MODELS_DIR", folder)
    elif not os.environ.get("SURFSENSE_LOCAL_MODELS_DIR"):
        pytest.skip(
            "set SURFSENSE_LIVE_MODELS_DIR to the folder holding bge-small-en-v1.5"
        )


@pytest_asyncio.fixture(loop_scope="function")
async def app(
    base_url: str,  # noqa: F811
    engine: Engine,
    ledger: SpendLedger,
    live_model: LiveModel,
    embedder: None,
    ingest_worker: None,  # noqa: F811
    studio_worker: None,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[LiveAgent]:
    """The app on a port with its ingest and Studio workers, the model behind the proxy; no agent."""
    if not os.environ.get("SURFSENSE_LIVE_JOB_PACK") or not os.environ.get(
        "SURFSENSE_LIVE_JOB_CASE"
    ):
        pytest.skip("set SURFSENSE_LIVE_JOB_PACK and SURFSENSE_LIVE_JOB_CASE")
    monkeypatch.setenv(DEV_SWITCH, "1")
    # The Studio worker reaches the model through the API, at the address Electron hands it.
    monkeypatch.setenv("SURFSENSE_LOCAL_PORT", base_url.rsplit(":", 1)[1])
    run = RunFolder(CASE, live_model)
    with RecordingProxy(
        live_model.upstream,
        os.environ[live_model.provider.key_env],
        ledger,
        CASE,
        model=live_model,
    ) as proxy:
        _connect_model(engine, proxy.url, live_model)
        async with httpx.AsyncClient(
            base_url=base_url, timeout=httpx.Timeout(120.0)
        ) as http:
            workspace = await http.post("/workspaces", json={"name": "Live job run"})
            workspace.raise_for_status()
            agent = LiveAgent(http, workspace.json()["id"], engine, proxy, run)
            try:
                yield agent
            finally:
                run.finish(
                    exchanges=proxy.transcript(),
                    usage=proxy.usage(),
                    ledger=ledger,
                    outcome="done",
                    detail="",
                    redact=proxy.redact,
                    word_previews={},
                )


async def test_the_job_fills_a_real_questionnaire_in_the_app(app: LiveAgent) -> None:
    """The installed job fills a real questionnaire from real policies in the app, never gives an unsupported Yes, and writes what its report says."""
    pack = Path(os.environ["SURFSENSE_LIVE_JOB_PACK"])
    folder = Path(os.environ["SURFSENSE_LIVE_JOB_CASE"])
    case = json.loads((folder / "case.json").read_text(encoding="utf-8"))
    gold = json.loads((folder / case["gold"]).read_text(encoding="utf-8"))["rows"]

    installed = await app.http.post("/job-packs/install", json={"path": str(pack)})
    assert installed.status_code == 200, installed.text
    [listed] = installed.json()
    assert listed["unlocked"]
    workbook_path = folder / case["workbook"]
    original = workbook_path.read_bytes()
    sources = [
        await app.upload(Path(path).name, (folder / path).read_bytes())
        for path in case["sources"]
    ]
    workbook = await app.upload(workbook_path.name, original)
    await app.wait_ready(*sources, workbook)

    started = time.monotonic()
    begun = await app.http.post(
        f"/workspaces/{app.workspace_id}/job-runs",
        json={"job": case["job"], "document_id": workbook, "source_ids": sources},
    )
    assert begun.status_code == 201, begun.text
    artifact_id = begun.json()["artifact_id"]
    while True:
        read = (
            await app.http.get(f"/workspaces/{app.workspace_id}/job-runs/{artifact_id}")
        ).json()
        if read["status"] in ("ready", "failed", "cancelled"):
            break
        assert time.monotonic() - started < RUN_SECONDS, "the run took too long"
        await asyncio.sleep(3)
    seconds = round(time.monotonic() - started, 1)
    assert read["status"] == "ready", read["error"]

    filled = await app.file(artifact_id)
    assert app.original(workbook) == original
    report = read["report"]
    by_cell = {(a["sheet"].casefold(), a["cell"]): a for a in report["answers"]}
    rows = []
    for row in gold:
        # As the job names its cells, and as the eval reads the gold.
        cell = str(row["cell"]).strip().upper()
        answer = by_cell.get((row["sheet"].casefold(), cell), {})
        rows.append(
            {
                "cell": cell,
                "gold": row["answer"],
                "answer": answer.get("answer"),
                "quote": answer.get("quote"),
                "source": answer.get("source"),
            }
        )
    correct = sum(1 for r in rows if r["answer"] == r["gold"])
    false_yes = sum(1 for r in rows if r["answer"] == "Yes" and r["gold"] != "Yes")
    book = openpyxl.load_workbook(io.BytesIO(filled))
    written = {
        (sheet.title.casefold(), cell.coordinate): cell.value
        for sheet in book.worksheets
        for row in sheet.iter_rows()
        for cell in row
        if cell.value is not None
    }
    uploaded = openpyxl.load_workbook(io.BytesIO(original))
    before = {
        (sheet.title.casefold(), cell.coordinate): cell.value
        for sheet in uploaded.worksheets
        for row in sheet.iter_rows()
        for cell in row
    }
    app.run.metrics.update(
        {
            "seconds": seconds,
            "correct": correct,
            "scored": len(rows),
            "false_yes": false_yes,
            "counts": report["counts"],
            "rows": rows,
        }
    )
    app.run.keep_document(f"{artifact_id}-filled{workbook_path.suffix}", filled, None)
    # The score is the run folder's to report: a live run measures, it does not gate on accuracy.
    assert false_yes == 0, f"{false_yes} Yes answers the gold does not support"
    for answer in report["answers"]:
        key = (answer["sheet"].casefold(), answer["cell"])
        if answer["written"] is not None:
            assert written.get(key) == answer["written"]
        else:
            # A blank answer leaves the cell as the requester sent it, placeholder and all.
            assert written.get(key) == before.get(key)
