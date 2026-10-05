"""Which engine a new thread gets, from what the selected model is measured and known to do."""

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
from modules.llm.capability.agent_trial import set_agent_trial
from modules.llm.model_type import ModelType
from modules.llm.models import ProviderConnection, SelectedModel
from shared.config import get_agent_settings, get_llm_settings
from shared.db import create_session_factory

pytestmark = pytest.mark.integration

LOCAL_MODEL = "Qwen3-8B-UD-Q4_K_XL"
# Nothing is sent to these: the choice reads the catalog and the capability list.
ANTHROPIC = "https://api.anthropic.com/v1"
OPENAI = "https://api.openai.com/v1"
OPENROUTER = "https://openrouter.ai/api/v1"


@pytest.fixture
def session(engine: Engine, monkeypatch: pytest.MonkeyPatch) -> Iterator[Session]:
    """A session on this test's migrated database, with the developer switch on."""
    monkeypatch.setattr(get_agent_settings(), "agent_untested_models", True)
    with create_session_factory(engine)() as session:
        yield session


@pytest.fixture
def no_switch(monkeypatch: pytest.MonkeyPatch) -> None:
    """The app as it ships: no developer switch."""
    monkeypatch.setattr(get_agent_settings(), "agent_untested_models", False)


@dataclass
class LocalRuntime:
    """llama-server in router mode, as far as the engine choice reads it."""

    # What `/props` reports about the model's chat template.
    template_caps: dict = field(default_factory=dict)
    # The window llama-server loaded the model with.
    n_ctx: int = 32768


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
                "default_generation_settings": {"n_ctx": runtime.n_ctx},
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


def select_local(session: Session, *, opted_in: bool = False) -> None:
    """Select a model the local runtime serves."""
    selected = SelectedModel(
        model_type=ModelType.TEXT_GEN, provider="llamacpp", name=LOCAL_MODEL
    )
    set_agent_trial(selected, opted_in)
    session.add(selected)
    session.commit()


def select_remote(
    session: Session,
    name: str,
    catalog_provider: str,
    *,
    base_url: str = "http://127.0.0.1:1/v1",
    opted_in: bool = False,
) -> None:
    """Select a model behind a connection that names its catalog provider."""
    connection = ProviderConnection(
        label="Remote",
        provider="openai_compatible",
        base_url=base_url,
        catalog_provider=catalog_provider,
    )
    session.add(connection)
    session.flush()
    selected = SelectedModel(
        model_type=ModelType.TEXT_GEN,
        provider="openai_compatible",
        connection_id=connection.id,
        name=name,
    )
    set_agent_trial(selected, opted_in)
    session.add(selected)
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


async def test_with_the_switch_a_model_the_catalog_does_not_know_gets_the_agent(
    session: Session,
) -> None:
    """A model released after the packaged catalog is the one most worth trying; only a stated no keeps it out."""
    select_remote(session, "anthropic/claude-sonnet-99", "openrouter")

    assert await selected_model_can_run_agent(session) is True


async def test_without_the_switch_or_an_opt_in_an_unmeasured_model_gets_the_chat(
    session: Session, no_switch: None
) -> None:
    """Calling tools is not calling them well: a measured pass, the opt-in or the switch lets one in."""
    select_remote(session, "gpt-4o-mini", "openai", base_url=OPENAI)

    assert await selected_model_can_run_agent(session) is False


@pytest.mark.parametrize(
    ("name", "catalog_provider", "base_url"),
    [
        ("claude-opus-5-5", "anthropic", ANTHROPIC),
        ("anthropic/claude-haiku-4.5", "openrouter", OPENROUTER),  # near the bar
    ],
)
async def test_a_model_measured_at_or_near_the_bar_gets_the_agent(
    session: Session, no_switch: None, name: str, catalog_provider: str, base_url: str
) -> None:
    """Opus passed every case; Haiku passed 5 of 8 and may need a nudge."""
    select_remote(session, name, catalog_provider, base_url=base_url)

    assert await selected_model_can_run_agent(session) is True


async def test_a_model_measured_to_fail_gets_the_chat_even_opted_in(
    session: Session, no_switch: None
) -> None:
    """The opt-in is for a model nobody measured, not one that failed."""
    select_remote(
        session,
        "google/gemma-4-31b-it",
        "openrouter",
        base_url=OPENROUTER,
        opted_in=True,
    )

    assert await selected_model_can_run_agent(session) is False


async def test_the_switch_lets_in_even_a_model_measured_to_fail(
    session: Session,
) -> None:
    """A developer measuring a model needs it on the agent whatever the list says."""
    select_remote(session, "google/gemma-4-31b-it", "openrouter", base_url=OPENROUTER)

    assert await selected_model_can_run_agent(session) is True


async def test_an_unmeasured_model_the_user_opted_in_gets_the_agent(
    session: Session, no_switch: None
) -> None:
    """The user's opt-in, once the catalog confirms its tool calls and window."""
    select_remote(session, "gpt-4o-mini", "openai", base_url=OPENAI, opted_in=True)

    assert await selected_model_can_run_agent(session) is True


async def test_an_opt_in_needs_tool_calls_the_catalog_confirms(
    session: Session, no_switch: None
) -> None:
    """A model the catalog says nothing of is the switch's to try, not the user's."""
    select_remote(
        session,
        "anthropic/claude-sonnet-99",
        "openrouter",
        base_url=OPENROUTER,
        opted_in=True,
    )

    assert await selected_model_can_run_agent(session) is False


async def test_an_opt_in_needs_a_window_the_agent_fits_in(
    session: Session, no_switch: None
) -> None:
    """Berget serves Mistral Small 3.2 at 32,000 tokens, under the 32,768 floor."""
    select_remote(
        session,
        "mistralai/Mistral-Small-3.2-24B-Instruct-2506",
        "berget",
        base_url="https://api.berget.ai/v1",
        opted_in=True,
    )

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


async def test_an_opted_in_local_model_whose_template_calls_tools_gets_the_agent(
    session: Session, no_switch: None, local_runtime: LocalRuntime
) -> None:
    """The opt-in reads the same template caps the switch does."""
    local_runtime.template_caps = {"supports_tools": True, "supports_tool_calls": True}
    select_local(session, opted_in=True)

    assert await selected_model_can_run_agent(session) is True


async def test_an_opted_in_local_model_loaded_with_a_short_window_gets_the_chat(
    session: Session, no_switch: None, local_runtime: LocalRuntime
) -> None:
    """opencode would compact on every step below the 32,768 floor."""
    local_runtime.template_caps = {"supports_tools": True, "supports_tool_calls": True}
    local_runtime.n_ctx = 16384
    select_local(session, opted_in=True)

    assert await selected_model_can_run_agent(session) is False
