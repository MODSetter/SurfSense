"""A tested row matches the same model however another server spells it, and never another size or version."""

import pytest

from modules.llm.capability.match_key import match_key

pytestmark = pytest.mark.unit

QWEN = match_key("qwen3-8-27b")


@pytest.mark.parametrize(
    "model_id",
    [
        "qwen/qwen3.8-27b",
        "Qwen/Qwen3.8-27B-Instruct",
        "qwen3.8:27b",
        "Qwen3.8-27B-Q4_K_M.gguf",
        "Qwen3.8-27B-UD-Q4_K_XL",
        "qwen3.8-27b-fp8",
        "unsloth/Qwen3.8-27B-GGUF",
        "qwen3.8:27b-instruct-q8_0",
        "Qwen3.8-27B-IQ4_XS",
        "Qwen3.8-27B-AWQ",
        "qwen3.8-27b-bf16",
        "lmstudio-community/Qwen3.8-27B-GGUF/Qwen3.8-27B-Q6_K.gguf",
        "Qwen3.8-27B-Chat",
        "qwen3.8-27b-it",
        "mlx-community/Qwen3.8-27B-4bit",
    ],
)
def test_a_server_s_spelling_of_the_model_matches_its_row(model_id: str) -> None:
    """Quantisation tags, a file extension, the instruct tag and Ollama's name:tag fold away."""
    assert match_key(model_id) == QWEN


@pytest.mark.parametrize(
    "model_id",
    ["qwen3.6-35b-a3b", "qwen3.8-14b", "qwen3-8b", "qwen3.5-27b", "qwen3.8:14b"],
)
def test_another_size_or_version_never_matches(model_id: str) -> None:
    """27B is not 14B, and 3.8 is not 3.6 or 3.5."""
    assert match_key(model_id) != QWEN


def test_ollama_s_name_without_a_hyphen_matches_the_hyphenated_row() -> None:
    """Ollama writes gemma4:31b for what OpenRouter calls google/gemma-4-31b-it."""
    assert match_key("gemma4:31b") == match_key("gemma-4-31b-it")
    assert match_key("gemma4:31b-it-qat") == match_key("gemma-4-31b-it")


@pytest.mark.parametrize(
    "model_id", ["qwen3.8:latest", "~anthropic/claude-haiku-latest", "", "  "]
)
def test_an_alias_or_latest_stays_unmatched(model_id: str) -> None:
    """An alias moves to a new model without its id changing."""
    assert match_key(model_id) is None


def test_a_variant_that_changes_behaviour_keeps_its_own_key() -> None:
    """A thinking variant or a flash model is another model, not a spelling."""
    assert match_key("anthropic/claude-haiku-4.5:thinking") != match_key(
        "claude-haiku-4-5"
    )
    assert match_key("z-ai/glm-5.3-flash") != match_key("glm-5-3")
