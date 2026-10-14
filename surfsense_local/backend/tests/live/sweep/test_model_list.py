"""Which listed models the sweep runs, which it assumes, and which it leaves to the ladder's rows."""

import json
from pathlib import Path

import pytest

from tests.live.sweep.model_list import measured_keys, pick, select

pytestmark = pytest.mark.unit


def _entry(
    model_id: str,
    prompt: str = "0.0000002",
    completion: str = "0.0000008",
    *,
    tools: bool = True,
    context: int = 131_072,
    images: bool = False,
) -> dict:
    return {
        "id": model_id,
        "context_length": context,
        "supported_parameters": ["tools", "tool_choice"] if tools else ["temperature"],
        "pricing": {"prompt": prompt, "completion": completion},
        "architecture": {"input_modalities": ["text", "image"] if images else ["text"]},
    }


def test_only_priced_tool_calling_fixed_models_with_32k_are_kept() -> None:
    """No tools, under 32k, free or batch tiers, aliases, routers and variable prices are dropped."""
    listing = {
        "data": [
            _entry("acme/keeps", images=True),
            _entry("acme/no-tools", tools=False),
            _entry("acme/short", context=16_384),
            _entry("acme/edge", context=32_768),
            _entry("acme/gift:free"),
            _entry("acme/slow:batch"),
            _entry("~acme/alias"),
            _entry("openrouter/auto"),
            _entry("acme/variable", prompt="-1", completion="-1"),
        ]
    }

    chosen = select(listing, set())

    assert [m.id for m in chosen.sweep] == ["acme/keeps", "acme/edge"]
    keeps = chosen.sweep[0]
    assert (keeps.key, keeps.prompt, keeps.completion, keeps.reads_images) == (
        "keeps",
        0.2,
        0.8,
        True,
    )
    assert keeps.folder == "acme__keeps"


def test_variants_of_one_model_key_keep_the_cheapest() -> None:
    """qwen3.8-27b and its dated, routed and nitro ids are one model."""
    listing = {
        "data": [
            _entry("qwen/qwen3.8-27b", "0.0000004"),
            _entry("other/qwen3.8-27b", "0.0000001"),
            _entry("qwen/qwen3.8-27b:nitro", "0.0000009"),
        ]
    }

    (only,) = select(listing, set()).sweep

    assert (only.id, only.key) == ("other/qwen3.8-27b", "qwen3-8-27b")


def test_measured_keys_are_left_out_and_flagships_from_3_dollars_are_assumed() -> None:
    """The ladder's rows stand; input at $3/M and up is assumed to pass, just under is run."""
    listing = {
        "data": [
            _entry("qwen/qwen3.8-27b"),
            _entry("big/flagship", "0.000003", "0.000015"),
            _entry("big/just-under", "0.00000299"),
            _entry("anthropic/claude-opus-9", "0.000005"),
        ]
    }

    chosen = select(listing, {"qwen3-8-27b"})

    assert [m.id for m in chosen.sweep] == ["big/just-under"]
    assert [m.id for m in chosen.assumed] == ["big/flagship", "anthropic/claude-opus-9"]
    assert chosen.measured == ["qwen3-8-27b"]
    assert chosen.eligible == 4


def test_opus_and_fable_are_never_run_even_when_cheap() -> None:
    """The maintainer's rule holds for the list and for --only."""
    listing = {"data": [_entry("anthropic/claude-fable-5-mini"), _entry("a/fine")]}

    assert [m.id for m in select(listing, set()).sweep] == ["a/fine"]
    with pytest.raises(ValueError, match="never run"):
        pick(listing, ["anthropic/claude-fable-5-mini"])


def test_only_picks_exactly_the_ids_named_measured_or_not() -> None:
    """A pilot runs measured models too; an unlisted id is refused."""
    listing = {"data": [_entry("qwen/qwen3.8-27b"), _entry("a/other")]}

    assert [m.id for m in pick(listing, ["qwen/qwen3.8-27b"])] == ["qwen/qwen3.8-27b"]
    with pytest.raises(ValueError, match="does not list"):
        pick(listing, ["a/missing"])


def test_the_shipped_rows_keys_are_read_from_capabilities_json() -> None:
    """The 8-case ladder's rows are the ones left out."""
    assert {"qwen3-8-27b", "gemma-4-31b-it"} <= measured_keys()


def test_an_assumed_flagship_is_not_taken_for_measured(tmp_path: Path) -> None:
    """Assumed when it cost $3/M and up, it is screened once its price falls under."""
    shipped = tmp_path / "capabilities.json"
    shipped.write_text(
        json.dumps(
            {
                "models": [
                    {"suite": "create-and-edit", "match": {"keys": ["qwen3-8-27b"]}},
                    {"suite": "openrouter-screen", "match": {"keys": ["glm-5-3"]}},
                    {"suite": "assumed", "match": {"keys": ["gpt-5-5"]}},
                ]
            }
        ),
        encoding="utf-8",
    )

    assert measured_keys(shipped) == {"qwen3-8-27b", "glm-5-3"}


def test_models_named_to_assume_are_assumed_whatever_their_price() -> None:
    """The maintainer's call for reasoning flagships that cost more than a case's stop to run."""
    listing = {
        "data": [_entry("openai/gpt-5.4", "0.0000025", "0.000015"), _entry("a/fine")]
    }

    chosen = select(listing, set(), frozenset({"openai/gpt-5.4"}))

    assert [m.id for m in chosen.sweep] == ["a/fine"]
    assert [m.id for m in chosen.assumed] == ["openai/gpt-5.4"]


def test_a_model_to_assume_must_be_listed() -> None:
    """A mistyped id fails loudly rather than quietly running the model."""
    with pytest.raises(ValueError, match="does not list openai/gpt-5-4"):
        select({"data": [_entry("a/fine")]}, set(), frozenset({"openai/gpt-5-4"}))
