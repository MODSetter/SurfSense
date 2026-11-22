"""How much of the model's window the agent's plugin tools may take, and how many of them.

A quarter of the window: at 32k and up that is at least 8,000 tokens, which held
every needed tool for 90% of measured tasks, and a larger window holds more. No
table of model tiers: what a model handles shifts with each release.
"""

from modules.llm.catalog.remote.manifest.lookup import CallRoute

WINDOW_SHARE = 4

# Each provider's own limit on tools in one request, where it documents one.
# Anthropic, OpenAI's Responses API and llama.cpp document none.
_CHAT_LIMITS = {"openai": 128, "vertex": 128, "gemini": 512, "xai": 350}


def plugin_share(window: int) -> int:
    """Tokens of plugin tool definitions the agent may hold."""
    return window // WINDOW_SHARE


def plugin_tool_limit(
    provider: str | None, route: CallRoute, own_tools: int
) -> int | None:
    """How many plugin tools a request may carry beside `own_tools`; None for no limit."""
    if route != "chat_completions" or provider not in _CHAT_LIMITS:
        return None
    return _CHAT_LIMITS[provider] - own_tools
