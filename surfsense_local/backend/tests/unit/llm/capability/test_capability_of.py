"""What the selected model is measured to do, read off the list shipped with the app."""

from collections.abc import Iterator

import pytest

from modules.llm.capability import Level, capability_of, measured_list, resolve
from modules.llm.capability.measured import loader
from modules.llm.capability.measured.schema import (
    ASSUMED_SUITE,
    LADDER_SUITE,
    SCREEN_SUITE,
    MeasuredModel,
)
from modules.llm.models import ProviderConnection

pytestmark = pytest.mark.unit

ANTHROPIC = ProviderConnection(
    label="Anthropic",
    provider="openai_compatible",
    base_url="https://api.anthropic.com/v1",
    catalog_provider="anthropic",
)
OPENROUTER = ProviderConnection(
    label="OpenRouter",
    provider="openai_compatible",
    base_url="https://openrouter.ai/api/v1",
    catalog_provider="openrouter",
)
LM_STUDIO = ProviderConnection(
    label="LM Studio",
    provider="openai_compatible",
    base_url="http://127.0.0.1:1234/v1",
    catalog_provider="custom",
)
OLLAMA = ProviderConnection(
    label="Ollama",
    provider="openai_compatible",
    base_url="http://localhost:11434/v1",
    catalog_provider="custom",
)
TOGETHER = ProviderConnection(
    label="Together",
    provider="openai_compatible",
    base_url="https://api.together.xyz/v1",
    catalog_provider="togetherai",
)


@pytest.mark.parametrize(
    ("model", "connection"),
    [
        ("claude-haiku-4-5", ANTHROPIC),
        ("claude-haiku-4-5-20251001", ANTHROPIC),
        ("anthropic/claude-haiku-4.5", OPENROUTER),
    ],
)
def test_one_model_is_one_row_whichever_provider_names_it(
    model: str, connection: ProviderConnection
) -> None:
    """Anthropic's dated and undated ids and OpenRouter's dotted one are the model measured."""
    capability = capability_of(model, connection)

    assert capability.level is Level.AGENT_LIMITED
    assert capability.reason.code == "measured_near"
    assert capability.row is not None and capability.row.key == "claude-haiku-4-5"


def test_a_model_that_passed_the_bar_runs_the_agent() -> None:
    """Kimi K3 and Opus 5.5 passed all eight cases."""
    assert capability_of("moonshotai/kimi-k3", OPENROUTER).level is Level.AGENT
    assert capability_of("claude-opus-5-5", ANTHROPIC).level is Level.AGENT


def test_a_text_only_model_is_not_held_to_the_cases_that_need_images() -> None:
    """GLM-5.3 failed only the figure swap, which needs a chart read off an image."""
    capability = capability_of("z-ai/glm-5.3", OPENROUTER)

    assert capability.level is Level.AGENT
    assert capability.row is not None and capability.row.reads_images is False


def test_a_measured_failure_takes_the_agent_away() -> None:
    """Gemma 4 31B passed 2 of 8; the reason carries the counts."""
    capability = capability_of("google/gemma-4-31b-it", OPENROUTER)

    assert capability.level is Level.STUDIO_ONLY
    assert capability.reason.code == "measured_fail"
    assert capability.reason.values == {
        "passed": 2,
        "counted": 8,
        "suite_version": 1,
        "measured_on": "2026-10-04",
    }


@pytest.mark.parametrize(
    "alias",
    ["~anthropic/claude-haiku-latest", "claude-haiku-latest", "ministral-14b-latest"],
)
def test_a_latest_alias_is_never_taken_for_the_model_measured(alias: str) -> None:
    """It moves to a new model without the id changing."""
    capability = capability_of(alias, ANTHROPIC)

    assert capability.level is Level.NOT_MEASURED
    assert capability.reason.code == "alias"


def test_a_model_off_the_list_is_not_measured() -> None:
    """It keeps today's behaviour. Made up, so no sweep the list takes in can list it."""
    capability = capability_of("anthropic/claude-sonnet-99", OPENROUTER)

    assert capability.level is Level.NOT_MEASURED
    assert capability.reason.code == "no_row"
    assert capability.row is None


@pytest.mark.parametrize(
    ("model", "connection"),
    [("qwen/qwen3.8-27b", LM_STUDIO), ("qwen3.8-27b", None)],
)
def test_a_pass_measured_on_a_remote_host_does_not_hold_on_this_computer(
    model: str, connection: ProviderConnection | None
) -> None:
    """A quantized copy on this machine is a different measurement, not yet made."""
    capability = capability_of(model, connection)

    assert capability.level is Level.NOT_MEASURED
    assert capability.reason.code == "measured_elsewhere"


@pytest.mark.parametrize(
    "base_url",
    [
        "http://192.168.1.20:1234/v1",
        "http://10.0.0.5:11434/v1",
        "http://100.101.102.103:1234/v1",
        "http://[fd00::5]:1234/v1",
        "http://gaming-pc:1234/v1",
        "http://nas.local:1234/v1",
    ],
)
def test_a_pass_measured_on_a_remote_host_does_not_hold_on_a_server_of_ones_own(
    base_url: str,
) -> None:
    """LM Studio on another machine at home serves its own quantization, as one here does."""
    own_server = ProviderConnection(
        label="LM Studio",
        provider="openai_compatible",
        base_url=base_url,
        catalog_provider="custom",
    )

    capability = capability_of("qwen/qwen3.8-27b@q3_k_m", own_server)

    assert capability.level is Level.NOT_MEASURED
    assert capability.reason.code == "measured_elsewhere"


@pytest.mark.parametrize(
    "model", ["Qwen/Qwen3.8-27B-Instruct", "qwen/qwen3.8-27b-fp8", "Qwen3.8-27B-Chat"]
)
def test_another_remote_host_s_spelling_of_a_tested_model_holds_its_row(
    model: str,
) -> None:
    """A row measured on one remote host holds on every other remote host."""
    capability = capability_of(model, TOGETHER)

    assert capability.level is Level.AGENT
    assert capability.row is not None and capability.row.key == "qwen3-8-27b"


@pytest.mark.parametrize(
    ("model", "connection"),
    [
        ("qwen3.8:27b", OLLAMA),
        ("Qwen3.8-27B-Q4_K_M", None),
        ("unsloth/Qwen3.8-27B-GGUF", LM_STUDIO),
    ],
)
def test_a_local_copy_of_a_tested_model_finds_its_row_but_not_its_pass(
    model: str, connection: ProviderConnection | None
) -> None:
    """The row says it passed on its full-size version; the copy here is not measured."""
    capability = capability_of(model, connection)

    assert capability.level is Level.NOT_MEASURED
    assert capability.reason.code == "measured_elsewhere"
    assert capability.row is not None and capability.row.key == "qwen3-8-27b"


def test_a_local_copy_of_a_model_measured_to_fail_holds_the_failure() -> None:
    """Ollama's gemma4:31b is the Gemma 4 31B that passed 2 of 8."""
    assert capability_of("gemma4:31b", OLLAMA).level is Level.STUDIO_ONLY


@pytest.fixture
def ladder_rows_only(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """The ladder's own rows: a sweep may list these other sizes as models of their own."""
    shipped = measured_list()
    ladder = shipped.model_copy(
        update={"models": [row for row in shipped.models if row.suite == LADDER_SUITE]}
    )
    monkeypatch.setattr(loader, "measured_list", lambda: ladder)
    _forget_rows()
    yield
    _forget_rows()


def _forget_rows() -> None:
    loader._by_key.cache_clear()
    loader._by_match_key.cache_clear()


@pytest.mark.usefixtures("ladder_rows_only")
@pytest.mark.parametrize("model", ["qwen3.8-14b", "qwen3.5-27b", "qwen3-8b"])
def test_another_size_or_version_of_a_tested_model_is_not_measured(model: str) -> None:
    """Matching is looser across servers, never across sizes or versions."""
    capability = capability_of(model, TOGETHER)

    assert capability.level is Level.NOT_MEASURED
    assert capability.row is None


def test_a_flagship_assumed_to_pass_says_so_rather_than_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """It was never run, so no case count stands behind its level."""
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

    capability = capability_of("anthropic/claude-opus-4.6", OPENROUTER)

    assert capability.level is Level.AGENT
    assert capability.reason.code == "assumed"
    assert capability.reason.values == {}


def test_a_failure_measured_on_a_remote_host_holds_on_a_server_of_ones_own() -> None:
    """A copy at home is the same model or a smaller one."""
    own_server = ProviderConnection(
        label="LM Studio",
        provider="openai_compatible",
        base_url="http://192.168.1.20:1234/v1",
        catalog_provider="custom",
    )

    assert capability_of("qwen/qwen3.5-9b", own_server).level is Level.STUDIO_ONLY


def test_a_failure_measured_on_a_remote_host_holds_on_this_computer() -> None:
    """A smaller copy of a model that failed does not pass by being local."""
    assert capability_of("qwen/qwen3.5-9b", LM_STUDIO).level is Level.STUDIO_ONLY


def test_the_list_shipped_with_the_app_is_provisional_suite_one() -> None:
    """Screening runs, one per cell: provisional until the committed matrix.

    The ladder's 11 rows; a sweep's screened and assumed rows join them.
    """
    shipped = measured_list()
    ladder = [row for row in shipped.models if row.suite == LADDER_SUITE]

    assert shipped.provisional is True
    assert {row.suite_version for row in shipped.models} == {1}
    assert len(ladder) == 11
    assert {row.suite for row in shipped.models} <= {
        LADDER_SUITE,
        SCREEN_SUITE,
        ASSUMED_SUITE,
    }
