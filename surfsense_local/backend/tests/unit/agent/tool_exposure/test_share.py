"""How much the opencode agent may hold of its plugins' tools."""

import pytest

from modules.agent.tool_exposure.share import plugin_share, plugin_tool_limit

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("window", "share"),
    [
        # A small local window: a quarter of it.
        (16_384, 4_096),
        # 32k and up: at least 8,000 tokens, which held every needed tool for 90%
        # of measured tasks, and more as the window grows.
        (32_768, 8_192),
        (200_000, 50_000),
    ],
)
def test_the_share_is_a_quarter_of_the_window(window: int, share: int) -> None:
    """No table of model tiers: a larger window simply holds more."""
    assert plugin_share(window) == share


@pytest.mark.parametrize(
    ("provider", "route", "limit"),
    [
        # OpenAI's chat completions take 128 tools a request; its Responses API, any.
        ("openai", "chat_completions", 128),
        ("openai", "responses", None),
        ("vertex", "chat_completions", 128),
        ("gemini", "chat_completions", 512),
        ("xai", "chat_completions", 350),
        ("anthropic", "chat_completions", None),
        # A local model, through llama.cpp, documents none.
        (None, "chat_completions", None),
    ],
)
def test_the_providers_own_limit_leaves_room_for_the_agents_other_tools(
    provider: str | None, route: str, limit: int | None
) -> None:
    """The count includes opencode's and SurfSense's own tools."""
    allowed = plugin_tool_limit(provider, route, own_tools=20)

    assert allowed == (None if limit is None else limit - 20)
