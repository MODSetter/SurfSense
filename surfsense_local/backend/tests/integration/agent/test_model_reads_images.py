"""Whether the agent's model is shown the page images it opens: the runtime's answer or the catalog's."""

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from modules.agent.model_reads_images import selected_model_reads_images
from modules.llm.model_type import ModelType
from modules.llm.models import ProviderConnection, SelectedModel
from shared.config import get_agent_settings, get_llm_settings
from shared.db import create_session_factory

pytestmark = pytest.mark.integration

LOCAL_MODEL = "Qwen3-VL-8B-UD-Q4_K_XL"


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """A session on this test's migrated database."""
    with create_session_factory(engine)() as session:
        yield session


class _Router(BaseHTTPRequestHandler):
    """Answers `GET /models` as llama-server's router does at b11050."""

    def do_GET(self) -> None:
        if urlsplit(self.path).path != "/models":
            self.send_error(404)
            return
        inputs = self.server.inputs  # type: ignore[attr-defined]
        body = json.dumps(
            {
                "object": "list",
                "data": [
                    {
                        "id": LOCAL_MODEL,
                        "architecture": {"input_modalities": inputs},
                        "status": {"value": "unloaded"},
                    }
                ],
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        """Keep the request log out of the test output."""


@pytest.fixture
def local_runtime(monkeypatch: pytest.MonkeyPatch) -> Iterator[ThreadingHTTPServer]:
    """A llama-server router on a real port; a test sets the inputs it lists."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Router)
    server.inputs = ["text"]  # type: ignore[attr-defined]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setattr(
        get_llm_settings(),
        "llamacpp_base_url",
        f"http://127.0.0.1:{server.server_port}",
    )
    yield server
    server.shutdown()
    server.server_close()


def select_local(session: Session) -> None:
    """Select the model the local runtime serves."""
    session.add(
        SelectedModel(
            model_type=ModelType.TEXT_GEN, provider="llamacpp", name=LOCAL_MODEL
        )
    )
    session.commit()


def select_remote(session: Session, name: str, catalog_provider: str) -> None:
    """Select a model behind a remote connection that names its catalog provider."""
    connection = ProviderConnection(
        label="Remote",
        provider="openai_compatible",
        base_url="http://127.0.0.1:1/v1",
        catalog_provider=catalog_provider,
    )
    session.add(connection)
    session.flush()
    session.add(
        SelectedModel(
            model_type=ModelType.TEXT_GEN,
            provider="openai_compatible",
            connection_id=connection.id,
            name=name,
        )
    )
    session.commit()


async def test_a_local_model_with_a_projector_reads_images(
    session: Session, local_runtime: ThreadingHTTPServer
) -> None:
    """llama-server lists `image` for a model whose preset gives it a projector (ADR 0034)."""
    local_runtime.inputs = ["text", "image"]  # type: ignore[attr-defined]
    select_local(session)

    assert await selected_model_reads_images(session) is True


async def test_a_local_model_without_one_reads_none(
    session: Session, local_runtime: ThreadingHTTPServer
) -> None:
    """Without a projector llama-server lists text alone."""
    select_local(session)

    assert await selected_model_reads_images(session) is False


async def test_a_local_runtime_that_does_not_answer_is_a_no(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No answer is no: an image the model refuses would fail the whole request."""
    monkeypatch.setattr(get_llm_settings(), "llamacpp_base_url", "http://127.0.0.1:9")
    select_local(session)

    assert await selected_model_reads_images(session) is False


@pytest.mark.parametrize("switch", [False, True])
async def test_a_remote_model_reads_images_when_the_catalog_says_so(
    session: Session, monkeypatch: pytest.MonkeyPatch, switch: bool
) -> None:
    """The catalog's word holds whatever the developer switch says."""
    monkeypatch.setattr(get_agent_settings(), "agent_untested_models", switch)
    select_remote(session, "gpt-4o-mini", "openai")

    assert await selected_model_reads_images(session) is True


@pytest.mark.parametrize("switch", [False, True])
async def test_a_remote_model_the_catalog_says_reads_none_is_shown_none(
    session: Session, monkeypatch: pytest.MonkeyPatch, switch: bool
) -> None:
    """A stated no holds under the switch too."""
    monkeypatch.setattr(get_agent_settings(), "agent_untested_models", switch)
    select_remote(session, "gpt-3.5-turbo", "openai")

    assert await selected_model_reads_images(session) is False


@pytest.mark.parametrize("switch", [False, True])
async def test_a_remote_model_the_catalog_does_not_know_is_shown_none(
    session: Session, monkeypatch: pytest.MonkeyPatch, switch: bool
) -> None:
    """Unknown is no, as in the chat: an image a text model refuses fails the turn and every one after."""
    monkeypatch.setattr(get_agent_settings(), "agent_untested_models", switch)
    select_remote(session, "anthropic/claude-sonnet-99", "openrouter")

    assert await selected_model_reads_images(session) is False


@pytest.mark.parametrize("switch", [False, True])
async def test_a_model_the_catalog_disagrees_on_is_shown_none(
    session: Session, monkeypatch: pytest.MonkeyPatch, switch: bool
) -> None:
    """A text-only model some gateway lists with images, behind LM Studio or vLLM."""
    monkeypatch.setattr(get_agent_settings(), "agent_untested_models", switch)
    select_remote(session, "gpt-oss-120b", "custom")

    assert await selected_model_reads_images(session) is False


@pytest.mark.parametrize("catalog_provider", ["anthropic", "custom"])
async def test_claude_sonnet_reads_images(
    session: Session, catalog_provider: str
) -> None:
    """The live runs' model: the catalog knows it, so the pages it opens reach it."""
    select_remote(session, "claude-sonnet-5-5", catalog_provider)

    assert await selected_model_reads_images(session) is True
