"""Whether a model can carry the agent at all: tool calls it makes, and a window it fits in.

Only what is stated keeps a model out; a score never does, and neither does a
catalog that says nothing.
"""

import logging
from dataclasses import dataclass

from modules.llm.catalog.remote.manifest.loader import remote_lookup
from modules.llm.catalog.remote.rows import CUSTOM
from modules.llm.models import SelectedModel
from modules.llm.providers import get_provider, llamacpp

__all__ = [
    "WINDOW_FLOOR",
    "ToolFacts",
    "catalog_facts",
    "gate_block",
    "local_facts",
    "remote_facts",
]

logger = logging.getLogger(__name__)

# The smallest window the agent runs at; opencode compacts early below it.
WINDOW_FLOOR = 32_768


@dataclass(frozen=True)
class ToolFacts:
    # None when nothing says: a catalog that lags its provider, or a runtime unread.
    tool_calls: bool | None
    window: int | None


UNKNOWN = ToolFacts(None, None)


def remote_facts(name: str, catalog_provider: str | None) -> ToolFacts:
    """What the remote catalog records, under the provider the connection names."""
    provider = None if catalog_provider in (None, CUSTOM) else catalog_provider
    found = remote_lookup().classify(name, provider=provider).supports
    if found is None:
        return UNKNOWN
    return ToolFacts(found.tool_call, found.context_window)


async def local_facts(name: str) -> ToolFacts:
    """What llama-server reports, loading the model if it is not resident."""
    provider = get_provider(llamacpp.PROVIDER)
    if not isinstance(provider, llamacpp.LlamaCppProvider):
        return UNKNOWN  # pragma: no cover - fixed registry invariant
    try:
        caps = await provider.capabilities(name)
    except Exception:
        logger.warning("could not read whether %s calls tools", name, exc_info=True)
        return UNKNOWN
    return ToolFacts(caps.tool_calls, caps.context_tokens)


def catalog_facts(selected: SelectedModel, catalog_provider: str | None) -> ToolFacts:
    """As far as the catalog tells without a call.

    A local model's are read when a chat starts: asking llama-server here would
    load the model on every read.
    """
    if selected.provider == llamacpp.PROVIDER:
        return UNKNOWN
    return remote_facts(selected.name, catalog_provider)


def gate_block(facts: ToolFacts, *, window_floor: bool = True) -> str | None:
    """Why the agent may not run on these facts, as a reason code; None when it may.

    `window_floor` off is the developer switch, held only to a stated no on tool calls.
    """
    if facts.tool_calls is False:
        return "tool_calls_unsupported"
    if window_floor and facts.window is not None and facts.window < WINDOW_FLOOR:
        return "window_below_floor"
    return None
