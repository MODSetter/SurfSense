import pytest

from modules.llm.profile import Fingerprint, Line, Tier, classify

pytestmark = pytest.mark.unit


def test_a_stated_parameter_count_decides_the_tier() -> None:
    """A count needs no inference, so it outranks every other signal."""
    tier = classify(Fingerprint(provider="llamacpp", name="Qwen3-8B-Q4_K_M", params_b=8.0))

    assert tier is Tier.CAPABLE


def test_a_model_too_small_for_a_scaffold_gets_the_compact_prompt() -> None:
    """Steps and worked examples cost a 3B model accuracy instead of buying it."""
    tier = classify(Fingerprint(provider="llamacpp", name="Llama-3.2-3B-Q4_K_M", params_b=3.2))

    assert tier is Tier.COMPACT


def test_a_model_large_enough_to_outgrow_a_scaffold_gets_the_frontier_prompt() -> None:
    """Past this size a model writes better from judgement than from steps."""
    tier = classify(
        Fingerprint(provider="llamacpp", name="DeepSeek-V3-Q4_K_M", params_b=671.0)
    )

    assert tier is Tier.FRONTIER


def test_a_vendor_that_never_ships_weights_has_no_count_and_gets_frontier() -> None:
    """No public count exists for a closed line, and every one of them is large."""
    tier = classify(
        Fingerprint(
            provider="openai_compatible",
            name="anthropic/claude-sonnet-4.5",
            vendor="anthropic",
        )
    )

    assert tier is Tier.FRONTIER


def test_a_hosted_model_with_no_count_is_placed_by_its_line() -> None:
    """The 2026 flagships dropped counts from their names but kept the line word."""
    hosted = {"provider": "openai_compatible", "params_b": None}
    flagship = classify(Fingerprint(name="z-ai/glm-5.3", line=Line.FLAGSHIP, **hosted))
    small = classify(
        Fingerprint(name="thinkingmachines/inkling-small", line=Line.SMALL, **hosted)
    )

    assert (flagship, small) == (Tier.FRONTIER, Tier.CAPABLE)


def test_a_model_revealing_nothing_falls_back_to_what_its_provider_serves() -> None:
    """The local runtime runs on the user's machine; a hosted one runs a cluster.

    Keyed on locality rather than on the provider's name, so a small model served
    through some other local endpoint is still compact.
    """
    local = classify(Fingerprint(provider="llamacpp", name="custom-model"))
    remote = classify(Fingerprint(provider="openai_compatible", name="internal-v2"))

    assert (local, remote) == (Tier.COMPACT, Tier.CAPABLE)
