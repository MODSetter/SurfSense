"""A curated chat model answers at its publisher's sampling for the mode it is in."""

import pytest

from modules.llm.catalog.local.engines.llamacpp.manifest_fields import SamplingSet
from modules.llm.catalog.local.engines.llamacpp.sampling import publisher_sampling
from modules.llm.catalog.local.manifest import load_local_manifest

pytestmark = pytest.mark.unit

QWEN3_THINKING = SamplingSet(temperature=0.6, top_p=0.95, top_k=20, min_p=0.0)
GEMMA_3 = SamplingSet(temperature=1.0, top_p=0.95, top_k=64, min_p=0.01)


def runtime_name(model_id: str) -> str:
    """What llama-server calls the entry's first build once it is installed."""
    model = next(m for m in load_local_manifest().models if m.id == model_id)
    return model.as_builds()[0].runtime_name


@pytest.mark.parametrize(
    ("model_id", "reasoning", "expected"),
    [
        # Qwen3 thinks by default, and its entry commits the thinking set.
        ("qwen3-4b", None, QWEN3_THINKING),
        # With thinking turned off it answers in a mode its entry has no set for.
        ("qwen3-4b", False, None),
        # Gemma 3 never thinks, so its only set is the one it answers in.
        ("gemma-3-4b", None, GEMMA_3),
    ],
)
def test_the_set_follows_the_mode_the_model_answers_in(
    model_id: str, reasoning: bool | None, expected: SamplingSet | None
) -> None:
    """Sending the other mode's settings would be a guess the publisher never made."""
    models = load_local_manifest().models

    assert publisher_sampling(models, runtime_name(model_id), reasoning) == expected


def test_a_model_no_entry_names_keeps_the_runtimes_default() -> None:
    """A searched or hand-copied file has no reviewed settings to send."""
    assert publisher_sampling(load_local_manifest().models, "my-own-q4", None) is None
