"""One key per model, however a provider spells its id."""

import pytest

from modules.llm.capability import model_key

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("model_id", "key"),
    [
        ("claude-haiku-4-5", "claude-haiku-4-5"),
        ("claude-haiku-4-5-20251001", "claude-haiku-4-5"),
        ("anthropic/claude-haiku-4.5", "claude-haiku-4-5"),
        ("claude-haiku-4-5@20251001", "claude-haiku-4-5"),
        ("qwen/qwen3.8-27b", "qwen3-8-27b"),
        ("qwen/qwen3.8-27b:free", "qwen3-8-27b"),
        ("Z-AI/GLM-5.3", "glm-5-3"),
        ("deepseek/deepseek-v4-pro-0813", "deepseek-v4-pro-0813"),
        ("mistralai/ministral-14b-2512", "ministral-14b-2512"),
        ("google/gemma-4-31b-it", "gemma-4-31b-it"),
    ],
)
def test_a_provider_prefix_a_dot_or_a_snapshot_date_names_the_same_model(
    model_id: str, key: str
) -> None:
    """A routing suffix such as `:free` picks hosts, not a model."""
    assert model_key(model_id) == key


@pytest.mark.parametrize(
    "model_id",
    [
        "~anthropic/claude-haiku-latest",
        "claude-3-7-sonnet-latest",
        "llama3:latest",
        "",
        "   ",
    ],
)
def test_an_alias_or_an_empty_id_has_no_key(model_id: str) -> None:
    """An alias moves without its id changing."""
    assert model_key(model_id) is None


def test_a_variant_that_changes_behaviour_keeps_its_own_key() -> None:
    """Only routing suffixes fold into the model; a thinking variant is another model."""
    assert model_key("anthropic/claude-haiku-4.5:thinking") != "claude-haiku-4-5"
    assert model_key("z-ai/glm-5.3-flash") != model_key("z-ai/glm-5.3")
