"""The plugin tools a turn's agent holds: all of them when they fit, else what the request needs.

Past the model's share, it holds its mentioned plugins whole, its best tools of each
plugin the message names, the tools the thread used, then what retrieval ranks
highest until the share is spent; never more than the provider takes. The rest
stay in reach through the catalogue and `surfsense_open_plugin`.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass, field

from modules.agent.plugin_tools.turn_plugins import opencode_tool_name
from modules.agent.tool_exposure.ranking import Embed, IndexedTool, ranked
from modules.agent.tool_exposure.tool_cost import tool_tokens
from modules.plugins.gateway.ready_tool import ReadyTool

# A plugin the message names: its best tools, not all, so one big plugin cannot
# crowd the share.
NAMED_TOOLS = 5


@dataclass(frozen=True)
class Asked:
    """What the turn asks: the user's words, the turn before, and what the thread chose."""

    message: str
    previous: str = ""
    mentioned: frozenset[str] = frozenset()
    # Tools the thread called since it last compacted, as opencode names them.
    used: frozenset[str] = frozenset()

    @property
    def query(self) -> str:
        return f"{self.message}\n{self.previous}".strip()


@dataclass(frozen=True)
class Held:
    tools: list[ReadyTool] = field(default_factory=list)
    # Every ready tool: nothing is in the catalogue only.
    everything: bool = False


def held_tools(
    tools: Sequence[IndexedTool],
    asked: Asked,
    share: int,
    limit: int | None,
    embed: Embed | None,
) -> Held:
    if all_fit(tools, share, limit):
        return Held([t.ready for t in tools], everything=True)
    cost = {id(t): tool_tokens(t.ready) for t in tools}

    held: dict[int, IndexedTool] = {}
    spent = 0

    def hold(tool: IndexedTool, within_share: bool) -> bool:
        nonlocal spent
        if id(tool) in held:
            return True
        if limit is not None and len(held) >= limit:
            return False
        if within_share and spent + cost[id(tool)] > share:
            return False
        held[id(tool)] = tool
        spent += cost[id(tool)]
        return True

    for tool in tools:
        if tool.ready.plugin_id in asked.mentioned:
            hold(tool, within_share=False)
    for plugin in _named(tools, asked.message):
        own = [t for t in tools if t.ready.plugin_id == plugin]
        for tool in ranked(own, asked.query, embed)[:NAMED_TOOLS]:
            hold(tool, within_share=False)
    for tool in tools:
        if opencode_tool_name(tool.ready.plugin_id, tool.ready.tool) in asked.used:
            hold(tool, within_share=False)
    for tool in ranked([t for t in tools if id(t) not in held], asked.query, embed):
        hold(tool, within_share=True)
    return Held([t.ready for t in tools if id(t) in held])


def all_fit(tools: Sequence[IndexedTool], share: int, limit: int | None) -> bool:
    """Whether every tool fits the share and the provider's limit, so all are held."""
    within = limit is None or len(tools) <= limit
    return within and sum(tool_tokens(t.ready) for t in tools) <= share


def _named(tools: Sequence[IndexedTool], message: str) -> list[str]:
    """Plugins whose name or id the message says as a word of its own."""
    said = message.lower()
    named: dict[str, None] = {}
    for tool in tools:
        ready = tool.ready
        for name in (ready.plugin_name, ready.plugin_id):
            if re.search(rf"(?<![\w-]){re.escape(name.lower())}(?![\w-])", said):
                named[ready.plugin_id] = None
    return list(named)
