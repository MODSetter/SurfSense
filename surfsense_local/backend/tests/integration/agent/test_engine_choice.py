"""Which engine a new thread gets, from what the selected model is known to do."""

import json
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from modules.agent.engine_choice import selected_model_can_run_agent
from modules.llm.model_type import ModelType
from modules.llm.models import ProviderConnection, SelectedModel
from shared.config import get_agent_settings, get_llm_settings
from shared.db import create_session_factory

pytestmark = pytest.mark.integration

LOCAL_MODEL = "Qwen3-8B-UD-Q4_K_XL"


@pytest.fixture
def session(engine: Engine, monkeypatch: pytest.MonkeyPatch) -> Iterator[Session]:
    """A session on this test's migrated database, with the developer switch on."""
    monkeypatch.setattr(get_agent_settings(), "agent_untested_models", True)
    with create_session_factory(engine)() as session:
        yield session


@dataclass
class LocalRuntime:
    """llama-server in router mode, as far as the engine choice reads it."""

    # What `/props` reports about the model's chat template.
    template_caps: dict = field(default_factory=dict)


class _LocalHandler(BaseHTTPRequestHandler):
    """Answers `GET /models` and `GET /props` in the shapes llama-server sends at b11050."""

    def do_GET(self) -> None:
        runtime: LocalRuntime = self.server.runtime  # type: ignore[attr-defined]
        path = urlsplit(self.path).path
        if path == "/models":
            reply = {
                "object": "list",
                "data": [
                    {
                        "id": LOCAL_MODEL,
                        "architecture": {"input_modalities": ["text"]},
                        "status": {"value": "loaded"},
                    }
                ],
            }
        elif path == "/props":
            reply = {
                "chat_template_caps": runtime.template_caps,
                "default_generation_settings": {"n_ctx": 32768},
            }
        else:
            self.send_error(404)
            return
        body = json.dumps(reply).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        """Keep the request log out of the test output."""


@pytest.fixture
def local_runtime(monkeypatch: pytest.MonkeyPatch) -> Iterator[LocalRuntime]:
    """A llama-server on a real port, which the local runtime's address points at."""
    runtime = LocalRuntime()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _LocalHandler)
    server.runtime = runtime  # type: ignore[attr-defined]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setattr(
        get_llm_settings(),
        "llamacpp_base_url",
        f"http://127.0.0.1:{server.server_port}",
    )
    yield runtime
    server.shutdown()
    server.server_close()


def select_local(session: Session) -> None:
    """Select a model the local runtime serves."""
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


async def test_a_remote_model_that_cannot_call_tools_gets_the_chat(
    session: Session,
) -> None:
    """The catalog records `tool_call: false`: opencode could take no step with it."""
    select_remote(session, "gpt-3.5-turbo", "openai")

    assert await selected_model_can_run_agent(session) is False


async def test_a_remote_model_that_calls_tools_gets_the_agent(session: Session) -> None:
    """The catalog records `tool_call: true` for the provider the connection names."""
    select_remote(session, "gpt-4o-mini", "openai")

    assert await selected_model_can_run_agent(session) is True


async def test_a_remote_model_the_catalog_does_not_know_gets_the_chat(
    session: Session,
) -> None:
    """A user's own endpoint may serve anything: support that is not stated is not confirmed."""
    select_remote(session, "stub-model", "custom")

    assert await selected_model_can_run_agent(session) is False


async def test_without_the_switch_even_a_model_that_calls_tools_gets_the_chat(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Calling tools is not calling them well: only the tested list, or the switch, lets one in."""
    monkeypatch.setattr(get_agent_settings(), "agent_untested_models", False)
    select_remote(session, "gpt-4o-mini", "openai")

    assert await selected_model_can_run_agent(session) is False


async def test_a_local_model_whose_template_calls_tools_gets_the_agent(
    session: Session, local_runtime: LocalRuntime
) -> None:
    """llama-server parses tool calls only when the template reports `supports_tool_calls`."""
    local_runtime.template_caps = {"supports_tools": True, "supports_tool_calls": True}
    select_local(session)

    assert await selected_model_can_run_agent(session) is True


async def test_a_local_model_whose_template_parses_no_tool_calls_gets_the_chat(
    session: Session, local_runtime: LocalRuntime
) -> None:
    """Rendering tools is not enough: llama-server would drop them without a warning."""
    local_runtime.template_caps = {"supports_tools": True, "supports_tool_calls": False}
    select_local(session)

    assert await selected_model_can_run_agent(session) is False


async def test_a_local_model_whose_runtime_cannot_be_read_gets_the_chat(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A thread must open whatever state the runtime is in, and unread is not confirmed."""
    monkeypatch.setattr(get_llm_settings(), "llamacpp_base_url", "http://127.0.0.1:9")
    select_local(session)

    assert await selected_model_can_run_agent(session) is False
