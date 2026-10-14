"""Live runs: the real agent path with a paid model behind a recording proxy.

The model is Claude Sonnet 5.5 on Anthropic unless SURFSENSE_LIVE_MODEL and
SURFSENSE_LIVE_PROVIDER choose another (live_model.py). Skipped unless
SURFSENSE_LIVE_TESTS=1 and the provider's key are set, so CI and ordinary runs
never call a paid model. Every run checks the spend ledger first.
"""

import os
import secrets
import threading
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import Engine

from api.config import get_settings
from modules.agent.previews.snapshot_key import get_snapshot_key_settings
from modules.llm.model_type import ModelType
from modules.llm.models import ProviderConnection, SelectedModel
from shared.config import get_agent_settings, get_storage_settings
from shared.db import create_session_factory
from shared.queue import ingest_queue
from tests.integration import conftest as integration_conftest
from tests.integration.agent.conftest import studio_worker  # noqa: F401
from tests.integration.agent.opencode_harness import (
    StandInForElectron,
    needs_staged_opencode,
)
from tests.integration.conftest import base_url  # noqa: F401
from tests.live.lane_ports import free_port
from tests.live.live_agent import LiveAgent
from tests.live.live_model import LiveModel, chosen_model, chosen_provider
from tests.live.recording_proxy import RecordingProxy
from tests.live.run_folder import RunFolder
from tests.live.spend_ledger import SpendLedger
from tests.live.word_printer import WordPrinter

# A turn waits on the model and on renders of up to 150 s each.
_TURN_TIMEOUT = httpx.Timeout(900.0, connect=10.0)
_OUTCOME = pytest.StashKey[pytest.TestReport]()

# The app's uvicorn port comes from the lane's block too (lane_ports.py).
integration_conftest._free_port = free_port


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
    """Keep the call's report, so the run folder can say how the case ended."""
    report = yield
    if report.when == "call" or report.outcome != "passed":
        item.stash[_OUTCOME] = report
    return report


@pytest.fixture(autouse=True)
def only_when_asked(request: pytest.FixtureRequest) -> None:
    """Skip a live case unless the maintainer asked for paid calls."""
    if request.node.get_closest_marker("live") is None:
        return
    key_env = chosen_provider().key_env
    if os.environ.get("SURFSENSE_LIVE_TESTS") != "1" or not os.environ.get(key_env):
        pytest.skip(f"set SURFSENSE_LIVE_TESTS=1 and {key_env} to call a paid model")


@dataclass(frozen=True)
class OpencodeAddress:
    port: int
    password: str
    # The Word snapshot key Electron hands the API it launches.
    snapshot_key: str


@pytest.fixture(autouse=True)
def opencode_address(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> OpencodeAddress | None:
    """Where opencode will listen and the snapshot key, set before the app is built: only then does it mount the agent's routes."""
    if request.node.get_closest_marker("live") is None:
        return None
    address = OpencodeAddress(
        free_port(), secrets.token_urlsafe(16), secrets.token_urlsafe(16)
    )
    monkeypatch.setattr(
        get_snapshot_key_settings(), "docx_snapshot_key", address.snapshot_key
    )
    agent = get_agent_settings()
    monkeypatch.setattr(agent, "opencode_url", f"http://127.0.0.1:{address.port}")
    monkeypatch.setattr(agent, "opencode_password", address.password)
    monkeypatch.setattr(agent, "agent_untested_models", True)
    return address


@pytest.fixture
def live_model() -> LiveModel:
    """The model this run calls, priced when the run starts."""
    return chosen_model()


@pytest.fixture
def ledger() -> SpendLedger:
    """The cumulative ledger; a run that starts at the stop is refused."""
    spent = SpendLedger()
    if not spent.has_room(0):
        pytest.skip(f"the live budget stop is reached: ${spent.dollars():.2f} spent")
    return spent


@pytest.fixture
def ingest_worker() -> Iterator[None]:
    """The worker's ingest consumer on a thread, with real Docling and the real embedder."""
    stopping = threading.Event()

    def consume() -> None:
        while not stopping.is_set():
            task = ingest_queue.dequeue()
            if task is None:
                stopping.wait(0.1)
            else:
                ingest_queue.execute(task)

    thread = threading.Thread(target=consume, daemon=True)
    thread.start()
    yield
    stopping.set()
    thread.join(timeout=120)


@pytest_asyncio.fixture(loop_scope="function")
async def live(
    request: pytest.FixtureRequest,
    base_url: str,  # noqa: F811
    engine: Engine,
    ledger: SpendLedger,
    live_model: LiveModel,
    real_model: object,
    ingest_worker: None,
    studio_worker: None,  # noqa: F811
    opencode_address: OpencodeAddress,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[LiveAgent]:
    """The app on a port, opencode beside it, the model behind the proxy; outputs kept afterwards."""
    needs_staged_opencode()
    case = request.module.CASE
    run = RunFolder(case, live_model)
    # opencode's provider points at this API's model endpoint, on its real port.
    monkeypatch.setattr(get_settings(), "port", int(base_url.rsplit(":", 1)[1]))

    with RecordingProxy(
        live_model.upstream,
        os.environ[live_model.provider.key_env],
        ledger,
        case,
        model=live_model,
    ) as proxy:
        _connect_model(engine, proxy.url, live_model)
        async with httpx.AsyncClient(base_url=base_url, timeout=_TURN_TIMEOUT) as http:
            workspace = await http.post("/workspaces", json={"name": "Live run"})
            workspace.raise_for_status()
            agent = LiveAgent(http, workspace.json()["id"], engine, proxy, run)
            with (
                StandInForElectron(
                    get_storage_settings().agent_dir,
                    opencode_address.port,
                    opencode_address.password,
                ),
                WordPrinter(base_url, opencode_address.snapshot_key) as printer,
            ):
                try:
                    yield agent
                finally:
                    await _keep_outputs(agent)
                    report = request.node.stash.get(_OUTCOME, None)
                    run.finish(
                        exchanges=proxy.transcript(),
                        usage=proxy.usage(),
                        ledger=ledger,
                        outcome=report.outcome if report else "unknown",
                        detail=str(report.longrepr) if report and report.failed else "",
                        redact=proxy.redact,
                        word_previews=printer.summary(),
                    )


def _connect_model(engine: Engine, proxy_url: str, model: LiveModel) -> None:
    """The model as the user connects it: its provider's OpenAI-compatible API, as the text model.

    The connection holds a placeholder: the proxy carries the real key.
    """
    with create_session_factory(engine)() as session:
        connection = ProviderConnection(
            label=model.provider.label,
            provider="openai_compatible",
            base_url=proxy_url,
            catalog_provider=model.provider.catalog_provider,
        )
        connection.api_key = "carried-by-the-recording-proxy"
        session.add(connection)
        session.flush()
        session.add(
            SelectedModel(
                model_type=ModelType.TEXT_GEN,
                provider="openai_compatible",
                connection_id=connection.id,
                name=model.name,
            )
        )
        session.commit()


async def _keep_outputs(agent: LiveAgent) -> None:
    """Every version the agent rendered and its script, every file a tool made, the previews it was shown and what each analysis saved."""
    for artifact in await agent.artifacts():
        if artifact["version"] is None:
            # A file a tool made is stored before Studio indexes it.
            made = await agent.http.get(f"/artifacts/{artifact['id']}/files/primary")
            if made.is_success:
                name = f"{artifact['id']}-{artifact['title']}.{artifact['format']}"
                agent.run.keep_document(name, made.content, None)
            continue
        ready = artifact["status"] == "ready"
        number = artifact["version"]["number"]
        name = f"{artifact['id']}-{artifact['title']}-v{number}"
        name += f".{artifact['format']}" if ready else f"-{artifact['status']}"
        data = await agent.file(artifact["id"]) if ready else None
        agent.run.keep_document(name, data, agent.spec(artifact["id"]).get("text"))
    threads = get_storage_settings().agent_threads_dir(agent.workspace_id)
    for previews in sorted(threads.glob("*/outputs/previews")):
        agent.run.keep_previews(previews)
    for analysis in sorted(threads.glob("*/outputs/analysis")):
        agent.run.keep_analysis(analysis)
