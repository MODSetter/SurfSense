"""A curated chat model answers at its publisher's temperature for the mode it is in."""

import pytest

from modules.llm.catalog.local.engines.llamacpp.sampling import publisher_temperature
from modules.llm.catalog.local.manifest import load_local_manifest

pytestmark = pytest.mark.unit


def runtime_name(model_id: str) -> str:
    """What llama-server calls the entry's first build once it is installed."""
    model = next(m for m in load_local_manifest().models if m.id == model_id)
    return model.as_builds()[0].runtime_name


@pytest.mark.parametrize(
    ("model_id", "reasoning", "expected"),
    [
        # Qwen3 thinks by default, and its entry commits the thinking set.
        ("qwen3-4b", None, 0.6),
        # With thinking turned off it answers in a mode its entry has no set for.
        ("qwen3-4b", False, None),
        # Gemma 3 never thinks, so its only set is the one it answers in.
        ("gemma-3-4b", None, 1.0),
    ],
)
def test_the_set_follows_the_mode_the_model_answers_in(
    model_id: str, reasoning: bool | None, expected: float | None
) -> None:
    """Sending the other mode's settings would be a guess the publisher never made."""
    models = load_local_manifest().models

    assert publisher_temperature(models, runtime_name(model_id), reasoning) == expected


def test_a_model_no_entry_names_keeps_the_runtimes_default() -> None:
    """A searched or hand-copied file has no reviewed settings to send."""
    assert (
        publisher_temperature(load_local_manifest().models, "my-own-q4", None) is None
    )
