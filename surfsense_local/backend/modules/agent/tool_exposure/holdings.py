"""What a thread's turn holds of its plugins' tools, grown during the turn, never shrunk.

opencode reads a session's rules before every step, and a rule set replaces the
last whole. A rule written before a plugin call's result returns counts at the
next step; one written after it missed the next step three times in three, so
everything that grows a holding writes the rules before it answers.
"""

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass, field

from modules.agent.opencode_client import OpencodeClient
from modules.agent.plugin_tools.turn_plugins import TurnPlugin
from modules.agent.tool_endpoint.registration import SERVER
from modules.agent.tool_exposure.held_tools import Asked
from modules.agent.tool_exposure.ranking import Embed, IndexedTool


@dataclass
class Holding:
    """One turn's plugins as opencode holds them, and the tools it may call now."""

    session_id: str
    plugins: list[TurnPlugin]
    # Every server opencode holds in the thread's folder, SurfSense's own aside.
    servers: set[str]
    # opencode's names of the tools the agent may call now.
    held: set[str]
    tools: list[IndexedTool] = field(default_factory=list)
    asked: Asked = field(default_factory=lambda: Asked(""))
    embed: Embed | None = None
    # The provider's own limit on plugin tools in one request.
    limit: int | None = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def rules(self) -> list[dict[str, str]]:
        """Every plugin tool denied, then each held one allowed or asked about."""
        rules = [_rule(f"{name}_*", "deny") for name in sorted(self.servers - {SERVER})]
        for plugin in self.plugins:
            for name, effect in plugin.rules.items():
                if name in self.held:
                    rules.append(_rule(name, effect))
        return rules

    def plugin_of(self, tool_name: str) -> TurnPlugin | None:
        """The plugin a tool name of opencode's belongs to, if it is one of the turn's."""
        return next((p for p in self.plugins if tool_name in p.rules), None)

    def with_plugins(self, plugin_ids: Sequence[str]) -> set[str]:
        """The tool names holding these whole plugins would add."""
        return {
            name
            for plugin in self.plugins
            if plugin.name in plugin_ids
            for name in plugin.rules
        } - self.held


def _rule(permission: str, action: str) -> dict[str, str]:
    return {"permission": permission, "pattern": "*", "action": action}


async def hold(client: OpencodeClient, holding: Holding, names: set[str]) -> set[str]:
    """Hold more tools and write the session's rules; the names newly held."""
    async with holding.lock:
        added = {name for name in names if holding.plugin_of(name)} - holding.held
        if holding.limit is not None:
            room = max(holding.limit - len(holding.held), 0)
            added = set(sorted(added)[:room])
        if not added:
            return set()
        holding.held |= added
        await client.set_session_rules(holding.session_id, holding.rules())
        return added


# A turn's holding while it runs, by thread, for what grows it from elsewhere:
# SurfSense's own tools, the plugin gateway and the turn's own events.
_turns: dict[int, Holding] = {}


def begin(thread_id: int, holding: Holding) -> None:
    _turns[thread_id] = holding


def holding_of(thread_id: int) -> Holding | None:
    return _turns.get(thread_id)


def end(thread_id: int, holding: Holding) -> None:
    if _turns.get(thread_id) is holding:
        del _turns[thread_id]
