import pytest

from modules.llm.providers.ollama.provider import MIN_CTX, num_ctx
from modules.llm.providers.types import Message

pytestmark = pytest.mark.unit


def test_a_short_chat_keeps_the_default_window() -> None:
    """Small prompts must not pay for a window they do not need."""
    assert num_ctx([Message(role="user", content="hi")], max_tokens=12) == MIN_CTX


def test_a_full_studio_grounding_gets_a_window_that_holds_it() -> None:
    """gather()'s 24k-char budget is ~7k tokens; 4096 silently truncates it."""
    messages = [
        Message(role="system", content="x" * 2_000),
        Message(role="user", content="y" * 24_000),
    ]
    window = num_ctx(messages, max_tokens=None)
    assert window >= 26_000 // 3 + 2048
    assert window & (window - 1) == 0  # a power of two, as Ollama sizes its caches
