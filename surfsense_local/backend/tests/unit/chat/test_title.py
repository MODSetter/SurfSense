from collections.abc import AsyncIterator

import pytest

from modules.chat.title import generate_title, valid_title
from modules.llm.providers.types import Message

pytestmark = pytest.mark.unit


class StubGenerator:
    """Records the bounded title request and streams a fixed response."""

    def __init__(self, deltas: list[str]) -> None:
        self.deltas = deltas
        self.request: (
            tuple[str, list[Message], int | None, float | None, bool | None] | None
        ) = None

    async def chat(
        self,
        model: str,
        messages: list[Message],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        reasoning: bool | None = None,
    ) -> AsyncIterator[str]:
        self.request = (model, messages, max_tokens, temperature, reasoning)
        for delta in self.deltas:
            yield delta


async def test_title_generation_is_short_bounded_and_uses_the_selected_model() -> None:
    """The hidden inference cannot silently switch models or generate a long reply."""
    generator = StubGenerator(["Quarterly ", "Revenue"])

    title = await generate_title(generator, "qwen3:1.7b", "Explain the quarter")

    assert title == "Quarterly Revenue"
    assert generator.request is not None
    model, messages, max_tokens, temperature, reasoning = generator.request
    assert model == "qwen3:1.7b"
    assert "Explain the quarter" in messages[0].content
    assert "Rewrite the request; do not copy it." in messages[0].content
    assert "Chat Content Overview" in messages[0].content
    assert max_tokens == 12
    assert temperature == 0
    assert reasoning is False


@pytest.mark.parametrize(
    "raw",
    ["", "one two three four five six seven", "Internal:\nDetails"],
)
def test_invalid_model_output_is_never_exposed_as_a_title(raw: str) -> None:
    """Malformed output is rejected instead of leaking model prose into the UI."""
    assert valid_title(raw) is None


def test_normal_title_punctuation_is_preserved() -> None:
    """A contraction from a small model is still a valid human-readable title."""
    assert valid_title("what's there in chat") == "what's there in chat"
