"""What a new chat on the selected model may be: Agentic for every model a gate allows, Basic by default unless it passed."""

import pytest

from modules.llm.capability import resolve
from modules.llm.capability.agent_gate import ToolFacts
from modules.llm.capability.measured.schema import MeasuredModel
from modules.llm.capability.modes import (
    ChatMode,
    new_chat_modes,
    remember_mode,
    remembered_mode,
)
from modules.llm.model_type import ModelType
from modules.llm.models import ProviderConnection, SelectedModel
from shared.config import get_agent_settings

pytestmark = pytest.mark.unit

CALLS_TOOLS = ToolFacts(tool_calls=True, window=200_000)
UNKNOWN = ToolFacts(tool_calls=None, window=None)
OPENROUTER = "https://openrouter.ai/api/v1"
OLLAMA = "http://localhost:11434/v1"


@pytest.fixture(autouse=True)
def opencode_staged(monkeypatch: pytest.MonkeyPatch) -> None:
    """As an installer ships: opencode beside the API, no developer switch."""
    settings = get_agent_settings()
    monkeypatch.setattr(settings, "opencode_url", "http://127.0.0.1:9")
    monkeypatch.setattr(settings, "opencode_password", "password")
    monkeypatch.setattr(settings, "agent_untested_models", False)


def _selected(
    name: str, base_url: str = OPENROUTER, settings: dict | None = None
) -> SelectedModel:
    return SelectedModel(
        model_type=ModelType.TEXT_GEN,
        provider="openai_compatible",
        name=name,
        settings=settings,
        connection=ProviderConnection(
            label="Server",
            provider="openai_compatible",
            base_url=base_url,
            catalog_provider="openrouter",
        ),
    )


def test_a_model_that_passed_on_a_remote_host_starts_agentic() -> None:
    """Kimi K3 passed all eight cases."""
    modes = new_chat_modes(_selected("moonshotai/kimi-k3"), CALLS_TOOLS)

    assert modes.agentic_allowed is True
    assert modes.blocked is None
    assert modes.default_mode is ChatMode.AGENTIC
    assert (modes.reason.code, modes.reason.values) == (
        "measured_pass",
        {"passed": 8, "counted": 8},
    )
    assert modes.remembered_mode is None


def test_a_model_near_the_bar_starts_agentic_with_its_counts() -> None:
    """Haiku 4.5 passed 5 of 8."""
    modes = new_chat_modes(_selected("anthropic/claude-haiku-4.5"), CALLS_TOOLS)

    assert modes.default_mode is ChatMode.AGENTIC
    assert (modes.reason.code, modes.reason.values) == (
        "measured_near",
        {"passed": 5, "counted": 8},
    )


def test_a_low_scorer_starts_basic_and_may_still_choose_agentic() -> None:
    """Gemma 4 31B passed 2 of 8: offered, with its score, never refused."""
    modes = new_chat_modes(_selected("google/gemma-4-31b-it"), CALLS_TOOLS)

    assert modes.agentic_allowed is True
    assert modes.default_mode is ChatMode.BASIC
    assert (modes.reason.code, modes.reason.values) == (
        "measured_below",
        {"passed": 2, "counted": 8},
    )


@pytest.mark.parametrize("facts", [CALLS_TOOLS, UNKNOWN])
def test_an_untested_model_starts_basic_and_may_choose_agentic(
    facts: ToolFacts,
) -> None:
    """A catalog that says nothing of tool calls is not a no."""
    modes = new_chat_modes(_selected("anthropic/claude-sonnet-99"), facts)

    assert modes.agentic_allowed is True
    assert modes.default_mode is ChatMode.BASIC
    assert modes.reason.code == "untested"


@pytest.mark.parametrize("name", ["qwen3.8:27b", "Qwen3.8-27B-Q4_K_M.gguf"])
def test_a_local_copy_of_a_passing_model_starts_basic_with_a_note(name: str) -> None:
    """It passed on its full-size version; a copy here may do worse."""
    modes = new_chat_modes(_selected(name, base_url=OLLAMA), UNKNOWN)

    assert modes.agentic_allowed is True
    assert modes.default_mode is ChatMode.BASIC
    assert (modes.reason.code, modes.reason.values) == (
        "local_copy",
        {"host": "openrouter.ai"},
    )


def test_an_assumed_flagship_starts_agentic_and_says_it_was_not_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Listed at the agent level without runs."""
    assumed = MeasuredModel.model_validate(
        {
            "key": "claude-opus-4-6",
            "match": {"keys": ["claude-opus-4-6"], "served": ["remote"]},
            "level": "agent",
            "suite": "assumed",
            "suite_version": 1,
            "measured_on": "2026-10-07",
            "provider": "openrouter",
            "host": "openrouter.ai",
            "model_id": "anthropic/claude-opus-4.6",
            "reads_images": True,
            "passes": {"passed": 0, "counted": 0, "run": 0},
            "note": "Not run: an expensive flagship assumed to pass",
        }
    )
    monkeypatch.setattr(resolve, "find_row", lambda _model: assumed)

    modes = new_chat_modes(_selected("anthropic/claude-opus-4.6"), CALLS_TOOLS)

    assert modes.default_mode is ChatMode.AGENTIC
    assert (modes.reason.code, modes.reason.values) == ("assumed", {})


@pytest.mark.parametrize(
    ("facts", "blocked"),
    [
        (ToolFacts(tool_calls=False, window=128_000), "tool_calls_unsupported"),
        (ToolFacts(tool_calls=True, window=32_000), "window_below_floor"),
    ],
)
def test_a_stated_gate_keeps_even_a_passing_model_basic(
    facts: ToolFacts, blocked: str
) -> None:
    """Only what is stated blocks: no tool calls, or a window under 32,768."""
    modes = new_chat_modes(_selected("moonshotai/kimi-k3"), facts)

    assert modes.agentic_allowed is False
    assert modes.blocked == blocked
    assert modes.default_mode is ChatMode.BASIC


def test_without_opencode_agentic_is_not_installed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A build that stages no opencode has no agent to start."""
    monkeypatch.setattr(get_agent_settings(), "opencode_url", None)

    modes = new_chat_modes(_selected("moonshotai/kimi-k3"), CALLS_TOOLS)

    assert (modes.agentic_allowed, modes.blocked) == (False, "agent_not_installed")
    assert modes.default_mode is ChatMode.BASIC


@pytest.mark.parametrize(
    ("name", "remembered"),
    [
        ("moonshotai/kimi-k3", ChatMode.BASIC),
        ("anthropic/claude-sonnet-99", ChatMode.AGENTIC),
    ],
)
def test_the_mode_last_chosen_for_the_model_is_its_default(
    name: str, remembered: ChatMode
) -> None:
    """Over the measured default, either way."""
    modes = new_chat_modes(
        _selected(name, settings={"chat_mode": remembered.value}), CALLS_TOOLS
    )

    assert modes.default_mode is remembered
    assert modes.remembered_mode is remembered


def test_a_remembered_agentic_a_gate_now_blocks_starts_basic() -> None:
    """The choice stays remembered for when the gate lifts."""
    modes = new_chat_modes(
        _selected("anthropic/claude-sonnet-99", settings={"chat_mode": "agentic"}),
        ToolFacts(tool_calls=False, window=None),
    )

    assert modes.default_mode is ChatMode.BASIC
    assert modes.remembered_mode is ChatMode.AGENTIC


def test_the_developer_switch_starts_every_model_agentic_past_the_window_floor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SURFSENSE_LOCAL_AGENT_UNTESTED_MODELS=1, held only to a stated no on tool calls."""
    monkeypatch.setattr(get_agent_settings(), "agent_untested_models", True)

    short = new_chat_modes(
        _selected("anthropic/claude-sonnet-99"), ToolFacts(True, 16_384)
    )
    no_tools = new_chat_modes(
        _selected("anthropic/claude-sonnet-99"), ToolFacts(False, None)
    )

    assert (short.agentic_allowed, short.default_mode) == (True, ChatMode.AGENTIC)
    assert no_tools.blocked == "tool_calls_unsupported"


def test_the_old_agent_trial_reads_as_a_remembered_agentic() -> None:
    """A model the user turned "Try the agent" on for keeps starting Agentic."""
    selected = _selected("gpt-4o-mini", settings={"agent_trial": True})

    assert remembered_mode(selected) is ChatMode.AGENTIC


def test_remembering_a_mode_replaces_the_old_trial_and_keeps_other_settings() -> None:
    """Settings are keyed by the slice that owns each entry."""
    selected = _selected(
        "gpt-4o-mini", settings={"agent_trial": True, "voices": ["alloy"]}
    )

    remember_mode(selected, ChatMode.BASIC)

    assert selected.settings == {"voices": ["alloy"], "chat_mode": "basic"}
    assert remembered_mode(selected) is ChatMode.BASIC
