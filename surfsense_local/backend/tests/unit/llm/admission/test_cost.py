"""Pricing a request's prompt: the same count, without walking it a character at a time."""

import pytest

from modules.llm.admission.cost import MESSAGE_OVERHEAD_TOKENS, request_cost
from modules.llm.providers.types import Message

pytestmark = pytest.mark.unit

TEXTS = [
    "Revenue rose in Q3, as the launch drew new customers.",
    "市場は第三四半期に成長した",
    "Q3 市場 café — \U0001f4c8 grew",
    "abc\ud800def",
    "\x85 x\u2028y\u2029z",
    "",
]


def _per_character(text: str) -> int:
    """The count as first written, one character at a time."""
    ascii_chars = sum(1 for char in text if char.isascii())
    return -(-ascii_chars // 3) + (len(text) - ascii_chars)


class _Unwalkable(str):
    """A prompt that fails if anything walks it character by character in Python."""

    def __iter__(self):
        raise AssertionError("the prompt was walked a character at a time")


@pytest.mark.parametrize(
    "text", TEXTS, ids=["ascii", "cjk", "mixed", "surrogate", "separators", "empty"]
)
def test_a_prompt_costs_what_it_always_did(text: str) -> None:
    """ASCII, CJK, mixed, a lone surrogate, line separators and nothing at all."""
    cost = request_cost([Message("user", text)], 0, budget=None, slots=1)

    assert cost == _per_character(text) + MESSAGE_OVERHEAD_TOKENS


@pytest.mark.parametrize(
    "text", [TEXTS[0] * 20_000, TEXTS[2] * 20_000], ids=["ascii", "mixed"]
)
def test_a_long_prompt_is_priced_without_a_python_loop(text: str) -> None:
    """A 1 MB agent prompt took 35 ms of the event loop, at every step."""
    cost = request_cost([Message("user", _Unwalkable(text))], 0, budget=None, slots=1)

    assert cost == _per_character(text) + MESSAGE_OVERHEAD_TOKENS
