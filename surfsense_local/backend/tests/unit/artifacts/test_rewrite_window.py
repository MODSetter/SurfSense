"""The window check of a Refine: what it counts, and the numbers it hands on."""

from modules.artifacts.refused import refused
from modules.artifacts.studio_documents.window import TooLong, too_long

# 4,000 characters are 1,000 tokens; 40 are 10. With the prompt's 1,500 and the
# spec written again a quarter longer: 1,500 + 10 + 1,000 + 1,250.
_SPEC = "x" * 4_000
_INSTRUCTION = "y" * 40
_NEEDED = 3_760


def test_a_rewrite_that_fits_exactly_is_not_too_long() -> None:
    """The window is a limit the rewrite may reach."""
    assert too_long(_SPEC, _INSTRUCTION, "Qwen3-4B", _NEEDED) is None


def test_one_token_short_gives_the_numbers_of_the_sentence() -> None:
    """Each number is handed on as it is counted, not as text."""
    found = too_long(_SPEC, _INSTRUCTION, "Qwen3-4B", _NEEDED - 1)

    assert found == TooLong(
        model="Qwen3-4B",
        spec_tokens=1_000,
        needed_tokens=_NEEDED,
        window_tokens=_NEEDED - 1,
    )


def test_the_list_of_figures_is_counted() -> None:
    """Its characters are priced like the rest, rounded up."""
    found = too_long(_SPEC, _INSTRUCTION, "Qwen3-4B", _NEEDED, figures_chars=5)

    assert found is not None
    assert found.needed_tokens == _NEEDED + 2


def test_the_sentence_is_built_from_the_same_numbers() -> None:
    """The fallback an interface without a line for the code shows."""
    found = TooLong(
        model="Qwen3-4B", spec_tokens=12_345, needed_tokens=29_300, window_tokens=8_192
    )

    assert found.reason == (
        "This document is too long for Qwen3-4B to rewrite in one go: it is about "
        "12,345 tokens, and reading it and writing it again needs about 29,300 of "
        "the model's 8,192-token window."
    )


def test_a_refusal_carries_its_values_beside_the_sentence_and_the_code() -> None:
    """Raw, under their own keys, so the interface formats them."""
    refusal = refused(
        409, "the sentence", "the_code", model="Qwen3-4B", window_tokens=8_192
    )

    assert refusal.status_code == 409
    assert refusal.detail == {
        "message": "the sentence",
        "code": "the_code",
        "model": "Qwen3-4B",
        "window_tokens": 8_192,
    }
