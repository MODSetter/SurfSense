"""What the selected model is measured to do, read off the list shipped with the app."""

import pytest

from modules.llm.capability import Level, capability_of, measured_list
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
    """It keeps today's behaviour."""
    capability = capability_of("gpt-4o-mini", OPENROUTER)

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
    """Screening runs, one per cell: provisional until the committed matrix."""
    shipped = measured_list()

    assert shipped.provisional is True
    assert {row.suite_version for row in shipped.models} == {1}
    assert len(shipped.models) == 11
