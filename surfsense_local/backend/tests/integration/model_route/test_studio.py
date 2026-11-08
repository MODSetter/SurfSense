"""Studio's text generation goes through the API's model route, for every model."""

import contextlib
import os
import threading
import time
from collections.abc import Iterator
from typing import Any

import pytest
import uvicorn
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from api.main import create_app
from modules.artifacts.models import Artifact
from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.documents.source_figures.layout import (
    figure_png,
    figures_dir,
    write_index,
)
from modules.llm.model_type import ModelType
from modules.llm.models import SelectedModel
from shared.config import get_storage_settings
from shared.db import create_session_factory
from tests.integration.model_route.conftest import (
    LOCAL_MODEL,
    Runtime,
    request_tokens,
)
from tests.integration.worker.test_studio import make_artifact
from worker.studio import run

pytestmark = pytest.mark.integration

# A source far longer than any window here: about 40,000 characters.
REPORT = "\n".join(
    f"Ring {n} of Saturn holds ice and dust at its own distance." for n in range(700)
)


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """A session on the migrated database the worker opens again by path."""
    with create_session_factory(engine)() as opened:
        yield opened


@pytest.fixture
def api_for_the_worker(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    """The API on a real port, at the address Electron hands the worker."""
    app = create_app()
    app.state.session_factory = create_session_factory(engine)
    server = uvicorn.Server(
        uvicorn.Config(
            app, host="127.0.0.1", port=0, lifespan="off", log_level="warning"
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.01)
    port = server.servers[0].sockets[0].getsockname()[1]
    monkeypatch.setenv("SURFSENSE_LOCAL_HOST", "127.0.0.1")
    monkeypatch.setenv("SURFSENSE_LOCAL_PORT", str(port))
    yield
    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture
def no_embedder(monkeypatch: pytest.MonkeyPatch) -> None:
    """Index the artifact's body without a model on disk."""

    def embed(spec: Any, texts: list[str], _purpose: Any) -> list[list[float]]:
        return [[float(len(text) % 97)] * spec.dimension for text in texts]

    monkeypatch.setattr("modules.embedding.encoder.embed", embed)
    monkeypatch.setattr(
        "worker.ingestion.chunking._default_tokenizer", lambda: "character"
    )


def _select(
    session: Session, provider: str, name: str, connection_id: int | None
) -> None:
    session.add(
        SelectedModel(
            model_type=ModelType.TEXT_GEN,
            provider=provider,
            name=name,
            connection_id=connection_id,
        )
    )
    session.commit()


def test_a_summary_on_the_local_runtime_is_written_through_the_route(
    session: Session, runtime: Runtime, api_for_the_worker: None, no_embedder: None
) -> None:
    """A local model writes Studio's text through the API, not directly."""
    _select(session, "llamacpp", LOCAL_MODEL, None)
    artifact = make_artifact(session, fmt="summary")

    run(artifact.id)

    session.expire_all()
    assert artifact.document.status is DocumentStatus.READY, (
        artifact.document.error_message
    )
    assert "Saturn has rings." in artifact.document.content
    sent = runtime.requests[0]
    assert sent["model"] == LOCAL_MODEL
    assert sent["messages"][0]["role"] == "system"


def test_sources_longer_than_a_small_local_window_are_cut_to_fit_it(
    session: Session, runtime: Runtime, api_for_the_worker: None, no_embedder: None
) -> None:
    """#2421: a model loaded at the 8,192-token floor was sent 24,000 characters
    of sources and refused them; they are cut to the window instead."""
    runtime.window = 8_192
    _select(session, "llamacpp", LOCAL_MODEL, None)
    artifact = make_artifact(session, source=REPORT, fmt="summary")

    run(artifact.id)

    session.expire_all()
    assert artifact.document.status is DocumentStatus.READY, (
        artifact.document.error_message
    )
    assert len(runtime.requests) == 1
    # Cut, not dropped: the sources still fill a good part of the window.
    assert len(runtime.requests[0]["messages"][1]["content"]) > 8_192


DOES_NOT_FIT = (
    "The selected sources don't fit the model's context window. Select fewer "
    "sources, or choose a model with a larger context window."
)


def test_sources_the_runtime_refuses_as_too_long_fail_with_why_and_no_retry(
    session: Session, runtime: Runtime, api_for_the_worker: None, no_embedder: None
) -> None:
    """A window the runtime does not state cannot be budgeted for. Its refusal is
    no unreachable model, and the same request would be refused again."""
    runtime.window = 8_192
    runtime.states_window = False
    _select(session, "llamacpp", LOCAL_MODEL, None)
    artifact = make_artifact(session, source=REPORT, fmt="summary")

    run(artifact.id)  # returning, not raising, is what spares a Huey retry

    session.expire_all()
    assert artifact.document.status is DocumentStatus.FAILED
    assert artifact.document.error_message == DOES_NOT_FIT


def test_a_word_drafts_figure_list_leaves_its_reply_room(
    session: Session, runtime: Runtime, api_for_the_worker: None, no_embedder: None
) -> None:
    """A Word or PDF draft lists every figure of its sources in the prompt, so
    the text gives way to that list, not the reply."""
    runtime.window = 8_192
    _select(session, "llamacpp", LOCAL_MODEL, None)
    artifact = make_artifact(session, source=REPORT, fmt="docx")
    _keep_figures(session, artifact, 40)

    run(artifact.id)

    session.expire_all()
    assert artifact.document.status is DocumentStatus.READY, (
        artifact.document.error_message
    )
    (sent,) = runtime.requests
    assert "Figures you may place" in sent["messages"][0]["content"]
    # A quarter of the window is the reply's, as the budget keeps it.
    assert request_tokens(sent) <= 8_192 * 3 // 4


def _keep_figures(session: Session, artifact: Artifact, count: int) -> None:
    """The artifact's source becomes a file whose figures were kept, each captioned."""
    source = session.get(Document, artifact.artifact_metadata["source_document_ids"][0])
    source.document_type = DocumentType.FILE
    session.commit()
    folder = figures_dir(
        get_storage_settings().document_dir(source.workspace_id, source.id)
    )
    folder.mkdir(parents=True)
    caption = ("Freight volume by depot and quarter, " * 6)[:200]
    for n in range(1, count + 1):
        figure_png(folder, n).write_bytes(b"\x89PNG\r\n\x1a\n")
    write_index(
        folder,
        [
            {"n": n, "width": 40, "height": 20, "page": 1, "caption": caption}
            for n in range(1, count + 1)
        ],
        None,
    )


def test_a_window_too_small_for_any_sources_fails_before_the_model_is_asked(
    session: Session, runtime: Runtime, api_for_the_worker: None, no_embedder: None
) -> None:
    """What the prompt and the reply need leaves no room for even a passage."""
    runtime.window = 2_048
    _select(session, "llamacpp", LOCAL_MODEL, None)
    artifact = make_artifact(session, source=REPORT, fmt="summary")

    run(artifact.id)  # returning, not raising, is what spares a Huey retry

    session.expire_all()
    assert artifact.document.status is DocumentStatus.FAILED
    assert artifact.document.error_message == (
        "The model's context window, 2,048 tokens, is too small to hold any of "
        "the sources. Choose a model with a larger context window."
    )
    assert runtime.requests == []


def test_a_remote_models_context_length_refusal_reads_the_same(
    session: Session,
    runtime: Runtime,
    remote_over_its_window: int,
    api_for_the_worker: None,
    no_embedder: None,
) -> None:
    """OpenAI's `context_length_exceeded`, which compatible servers copy, is the
    same refusal as llama-server's."""
    _select(session, "openai_compatible", "remote-model", remote_over_its_window)
    artifact = make_artifact(session, source=REPORT, fmt="summary")

    run(artifact.id)  # returning, not raising, is what spares a Huey retry

    session.expire_all()
    assert artifact.document.status is DocumentStatus.FAILED
    assert artifact.document.error_message == DOES_NOT_FIT


def test_a_summary_on_a_remote_model_is_written_through_the_same_route(
    session: Session,
    runtime: Runtime,
    remote_connection: int,
    api_for_the_worker: None,
    no_embedder: None,
) -> None:
    """A remote model takes the same one path, never the local runtime."""
    _select(session, "openai_compatible", "remote-model", remote_connection)
    artifact = make_artifact(session, fmt="summary")

    run(artifact.id)

    session.expire_all()
    assert artifact.document.status is DocumentStatus.READY, (
        artifact.document.error_message
    )
    assert "Saturn has rings." in artifact.document.content
    assert runtime.requests == []


def test_a_local_model_removed_since_fails_the_job_with_the_routes_reason(
    session: Session, runtime: Runtime, api_for_the_worker: None, no_embedder: None
) -> None:
    """The API resolves the model, so a job learns it is gone instead of asking
    the runtime for a model it no longer has."""
    _select(session, "llamacpp", "Removed-Q4_K_M", None)
    artifact = make_artifact(session, fmt="summary")

    # Failed, then raised for Huey to retry, as any model failure is.
    with contextlib.suppress(Exception):
        run(artifact.id)

    session.expire_all()
    assert artifact.document.status is DocumentStatus.FAILED
    assert "no longer installed" in (artifact.document.error_message or "")
    assert runtime.requests == []


def test_without_the_api_a_remote_model_is_not_called_directly(
    session: Session,
    runtime: Runtime,
    remote_connection: int,
    monkeypatch: pytest.MonkeyPatch,
    no_embedder: None,
) -> None:
    """Every text model goes through the API; the worker holds no path of its own."""
    import socket

    with socket.socket() as closed:
        closed.bind(("127.0.0.1", 0))
        port = closed.getsockname()[1]
    monkeypatch.setenv("SURFSENSE_LOCAL_HOST", "127.0.0.1")
    monkeypatch.setenv("SURFSENSE_LOCAL_PORT", str(port))
    _select(session, "openai_compatible", "remote-model", remote_connection)
    artifact = make_artifact(session, fmt="summary")

    # A failure may be retried by Huey or recorded; either way nothing is written.
    with contextlib.suppress(Exception):
        run(artifact.id)

    session.expire_all()
    assert artifact.document.status is not DocumentStatus.READY


async def test_a_request_queued_past_the_silence_limit_still_completes(
    session: Session,
    runtime: Runtime,
    api_for_the_worker: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Waiting behind the runtime is not silence: the route keeps the line alive,
    so a long wait never fails a job the way a direct call's start timer would."""
    import asyncio

    from modules.llm.model_route.client import RoutedGenerator
    from modules.llm.model_route.schemas import ModelRef
    from modules.llm.providers.types import Message

    monkeypatch.setattr("modules.llm.model_route.keep_alive.KEEP_ALIVE_SECONDS", 0.02)
    monkeypatch.setattr("modules.llm.model_route.client.SILENCE_SECONDS", 0.15)
    runtime.stall = threading.Event()
    url = f"http://127.0.0.1:{os.environ['SURFSENSE_LOCAL_PORT']}"
    generator = RoutedGenerator(url, ModelRef(provider="llamacpp", name=LOCAL_MODEL))
    ask = [Message("user", "Summarise Saturn.")]

    async def collect() -> str:
        return "".join([piece async for piece in generator.chat(LOCAL_MODEL, ask)])

    holding = asyncio.create_task(collect())
    while not runtime.requests:
        await asyncio.sleep(0.01)
    waiting = asyncio.create_task(collect())
    await asyncio.sleep(0.6)
    runtime.stall.set()

    assert await holding == "Saturn has rings."
    assert await waiting == "Saturn has rings."
