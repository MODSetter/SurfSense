"""Whether a model can carry the agent at all: tool calls it makes, and a window it fits in."""

import logging
from dataclasses import dataclass

from modules.llm.catalog.remote.manifest.loader import remote_lookup
from modules.llm.catalog.remote.rows import CUSTOM
from modules.llm.providers import get_provider, llamacpp

__all__ = ["WINDOW_FLOOR", "ToolFacts", "gate_block", "local_facts", "remote_facts"]

logger = logging.getLogger(__name__)

# The smallest window the agent runs at; opencode compacts early below it.
WINDOW_FLOOR = 32_768


@dataclass(frozen=True)
class ToolFacts:
    # None when nothing says: a catalog that lags its provider.
    tool_calls: bool | None
    window: int | None


def remote_facts(name: str, catalog_provider: str | None) -> ToolFacts:
    """What the remote catalog records, under the provider the connection names."""
    provider = None if catalog_provider in (None, CUSTOM) else catalog_provider
    found = remote_lookup().classify(name, provider=provider).supports
    if found is None:
        return ToolFacts(None, None)
    return ToolFacts(found.tool_call, found.context_window)


async def local_facts(name: str) -> ToolFacts:
    """What llama-server reports, loading the model if it is not resident."""
    provider = get_provider(llamacpp.PROVIDER)
    if not isinstance(provider, llamacpp.LlamaCppProvider):
        return ToolFacts(False, None)  # pragma: no cover - fixed registry invariant
    try:
        caps = await provider.capabilities(name)
    except Exception:
        logger.warning("could not read whether %s calls tools", name, exc_info=True)
        # Unread is not confirmed.
        return ToolFacts(False, None)
    return ToolFacts(caps.tool_calls, caps.context_tokens)


def gate_block(facts: ToolFacts, *, measured: bool) -> str | None:
    """Why the agent may not run on these facts, as a reason code; None when it may.

    A measured model has shown it calls tools, so only a stated no keeps it out.
    """
    if facts.tool_calls is False or (facts.tool_calls is None and not measured):
        return "tool_calls_unconfirmed"
    if facts.window is not None and facts.window < WINDOW_FLOOR:
        return "window_below_floor"
    return None
