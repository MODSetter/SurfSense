"""Which engine a new thread gets: the mode asked for, else the selected model's default, held only to technical gates."""

import json
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from modules.agent.engine_choice import (
    AgenticRefusedError,
    new_thread_mode,
    remember_thread_mode,
    selected_model_can_run_agent,
)
from modules.llm.capability.modes import ChatMode, remembered_mode
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


def select_local(session: Session, name: str = LOCAL_MODEL) -> None:
    """Select a model the local runtime serves."""
    session.add(
        SelectedModel(model_type=ModelType.TEXT_GEN, provider="llamacpp", name=name)
    )
    session.commit()


def select_remote(
    session: Session,
    name: str,
    catalog_provider: str,
    *,
    base_url: str = "http://127.0.0.1:1/v1",
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
    session.add(
        SelectedModel(
            model_type=ModelType.TEXT_GEN,
            provider="openai_compatible",
            connection_id=connection.id,
            name=name,
        )
    )
    session.commit()


async def refused(session: Session, requested: ChatMode) -> str:
    """The gate's code when the mode asked for is refused."""
    with pytest.raises(AgenticRefusedError) as raised:
        await new_thread_mode(session, requested)
    return raised.value.code


@pytest.mark.parametrize(
    ("name", "catalog_provider", "base_url"),
    [
        ("claude-opus-5-5", "anthropic", ANTHROPIC),
        ("anthropic/claude-haiku-4.5", "openrouter", OPENROUTER),  # near the bar
    ],
)
async def test_with_no_mode_asked_a_model_measured_at_or_near_the_bar_opens_agentic(
    session: Session, no_switch: None, name: str, catalog_provider: str, base_url: str
) -> None:
    """Opus passed every case; Haiku passed 5 of 8 and may need a nudge."""
    select_remote(session, name, catalog_provider, base_url=base_url)

    assert (await new_thread_mode(session, None)).mode is ChatMode.AGENTIC


@pytest.mark.parametrize(
    ("name", "catalog_provider", "base_url"),
    [
        ("gpt-4o-mini", "openai", OPENAI),  # untested
        ("google/gemma-4-31b-it", "openrouter", OPENROUTER),  # 2 of 8
    ],
)
async def test_with_no_mode_asked_an_untested_model_or_a_low_scorer_opens_basic(
    session: Session, no_switch: None, name: str, catalog_provider: str, base_url: str
) -> None:
    """Agentic is theirs to choose; Basic is where they start."""
    select_remote(session, name, catalog_provider, base_url=base_url)

    assert (await new_thread_mode(session, None)).mode is ChatMode.BASIC


@pytest.mark.parametrize(
    ("name", "catalog_provider", "base_url"),
    [
        ("google/gemma-4-31b-it", "openrouter", OPENROUTER),  # measured to fail
        ("gpt-4o-mini", "openai", OPENAI),  # untested
        ("anthropic/claude-sonnet-99", "openrouter", OPENROUTER),  # catalog silent
    ],
)
async def test_agentic_asked_for_opens_agentic_whatever_the_score(
    session: Session, no_switch: None, name: str, catalog_provider: str, base_url: str
) -> None:
    """No measured score blocks Agentic, and neither does a catalog that says nothing."""
    select_remote(session, name, catalog_provider, base_url=base_url)

    assert (await new_thread_mode(session, ChatMode.AGENTIC)).mode is ChatMode.AGENTIC


async def test_basic_asked_for_opens_basic_even_for_a_model_that_passed(
    session: Session, no_switch: None
) -> None:
    """The user's choice over the measured default."""
    select_remote(session, "claude-opus-5-5", "anthropic", base_url=ANTHROPIC)

    assert (await new_thread_mode(session, ChatMode.BASIC)).mode is ChatMode.BASIC


async def test_agentic_on_a_model_that_cannot_call_tools_is_refused(
    session: Session,
) -> None:
    """The catalog records `tool_call: false`: opencode could take no step with it."""
    select_remote(session, "gpt-3.5-turbo", "openai")

    assert await refused(session, ChatMode.AGENTIC) == "tool_calls_unsupported"
    # Nothing asked, the default falls back rather than refusing.
    assert (await new_thread_mode(session, None)).mode is ChatMode.BASIC


async def test_a_window_under_the_floor_is_refused_but_not_under_the_switch(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Berget serves Mistral Small 3.2 at 32,000 tokens, under the 32,768 floor."""
    select_remote(
        session,
        "mistralai/Mistral-Small-3.2-24B-Instruct-2506",
        "berget",
        base_url="https://api.berget.ai/v1",
    )

    assert (await new_thread_mode(session, None)).mode is ChatMode.AGENTIC
    monkeypatch.setattr(get_agent_settings(), "agent_untested_models", False)
    assert await refused(session, ChatMode.AGENTIC) == "window_below_floor"


async def test_agentic_without_opencode_is_refused_as_not_installed(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A build that stages no opencode has no agent to start."""
    monkeypatch.setattr(get_agent_settings(), "opencode_url", None)
    select_remote(session, "claude-opus-5-5", "anthropic", base_url=ANTHROPIC)

    assert await refused(session, ChatMode.AGENTIC) == "agent_not_installed"
    assert (await new_thread_mode(session, None)).mode is ChatMode.BASIC


async def test_agentic_with_no_chat_model_is_refused(session: Session) -> None:
    """There is no model to run it."""
    assert await refused(session, ChatMode.AGENTIC) == "no_model"
    assert (await new_thread_mode(session, None)).mode is ChatMode.BASIC


async def test_a_local_model_whose_template_calls_tools_opens_agentic(
    session: Session, no_switch: None, local_runtime: LocalRuntime
) -> None:
    """llama-server parses tool calls only when the template reports `supports_tool_calls`."""
    local_runtime.template_caps = {"supports_tools": True, "supports_tool_calls": True}
    select_local(session)

    assert (await new_thread_mode(session, ChatMode.AGENTIC)).mode is ChatMode.AGENTIC


async def test_a_local_model_whose_template_parses_no_tool_calls_is_refused(
    session: Session, local_runtime: LocalRuntime
) -> None:
    """Rendering tools is not enough: llama-server would drop them without a warning."""
    local_runtime.template_caps = {"supports_tools": True, "supports_tool_calls": False}
    select_local(session)

    assert await refused(session, ChatMode.AGENTIC) == "tool_calls_unsupported"
    assert (await new_thread_mode(session, None)).mode is ChatMode.BASIC


async def test_a_local_model_loaded_with_a_short_window_is_refused(
    session: Session, no_switch: None, local_runtime: LocalRuntime
) -> None:
    """opencode would compact on every step below the 32,768 floor."""
    local_runtime.template_caps = {"supports_tools": True, "supports_tool_calls": True}
    local_runtime.n_ctx = 16384
    select_local(session)

    assert await refused(session, ChatMode.AGENTIC) == "window_below_floor"


async def test_a_local_model_whose_runtime_cannot_be_read_may_still_open_agentic(
    session: Session, no_switch: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unread is not a stated no; the turn says what went wrong if the model fails."""
    monkeypatch.setattr(get_llm_settings(), "llamacpp_base_url", "http://127.0.0.1:9")
    select_local(session)

    assert (await new_thread_mode(session, ChatMode.AGENTIC)).mode is ChatMode.AGENTIC


async def test_a_local_copy_of_a_model_that_passed_opens_basic(
    session: Session, no_switch: None
) -> None:
    """It passed on its full-size version; a copy here starts Basic, with Agentic offered."""
    select_local(session, "Qwen3.8-27B-Q4_K_M")

    assert (await new_thread_mode(session, None)).mode is ChatMode.BASIC


async def test_the_mode_a_chat_opened_in_is_the_model_s_next_default(
    session: Session, no_switch: None
) -> None:
    """Remembered on the selection, over the measured default."""
    select_remote(session, "gpt-4o-mini", "openai", base_url=OPENAI)
    opening = await new_thread_mode(session, ChatMode.AGENTIC)
    assert opening.entry is not None

    await remember_thread_mode(session, opening.entry, ChatMode.AGENTIC)

    assert (await new_thread_mode(session, None)).mode is ChatMode.AGENTIC
    session.expire_all()
    selected = session.get(SelectedModel, ModelType.TEXT_GEN)
    assert selected is not None and remembered_mode(selected) is ChatMode.AGENTIC


async def test_an_agent_thread_s_next_turn_is_held_only_to_technical_gates(
    session: Session, no_switch: None
) -> None:
    """A model measured to fail may carry on; one that cannot call tools may not."""
    select_remote(session, "google/gemma-4-31b-it", "openrouter", base_url=OPENROUTER)
    assert await selected_model_can_run_agent(session) is True

    selected = session.get(SelectedModel, ModelType.TEXT_GEN)
    assert selected is not None and selected.connection is not None
    selected.name = "gpt-3.5-turbo"
    selected.connection.catalog_provider = "openai"
    session.commit()
    assert await selected_model_can_run_agent(session) is False
