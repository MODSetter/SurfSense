"""How a turn's holding grows: by whole plugins, never a tool at a time.

Each change makes a local model read its prompt again from the first tool that
changed, 9 to 57 s on a laptop, so a holding grows rarely and in batches: the
plugin the agent asked for, the one it was using, or the one search found.

A call never brings another plugin: guessed from the call, it was the one the request
needed about one time in four, and after each call of a one-app request it loaded one
nothing needed. The agent reaches another plugin through the catalogue or by asking.
"""

from collections.abc import Sequence

from starlette.concurrency import run_in_threadpool

from modules.agent.opencode_client import OpencodeClient
from modules.agent.plugin_tools.turn_plugins import opencode_tool_name
from modules.agent.tool_exposure.holdings import Holding, hold
from modules.agent.tool_exposure.ranking import Embed, ranked


async def hold_plugins(
    client: OpencodeClient, holding: Holding, plugin_ids: Sequence[str]
) -> set[str]:
    """Hold these plugins whole; the tool names newly held."""
    return await hold(client, holding, holding.with_plugins(plugin_ids))


async def grow_after_call(
    client: OpencodeClient, holding: Holding, plugin_id: str
) -> set[str]:
    """After a plugin call: the rest of that plugin."""
    return await hold_plugins(client, holding, [plugin_id])


async def grow_by_search(
    client: OpencodeClient, holding: Holding, query: str, embed: Embed | None
) -> set[str]:
    """What `surfsense_find_tools` holds: the plugin of the best tool not held."""
    found = await run_in_threadpool(_best_plugins, holding, query, embed)
    return await hold_plugins(client, holding, found[:1])


def _best_plugins(holding: Holding, query: str, embed: Embed | None) -> list[str]:
    """Plugins in the order their best tool not yet held ranks."""
    unheld = [t for t in holding.tools if _name(t) not in holding.held]
    order: dict[str, None] = {}
    for tool in ranked(unheld, query, embed):
        order.setdefault(tool.ready.plugin_id, None)
    return list(order)


def _name(tool) -> str:
    return opencode_tool_name(tool.ready.plugin_id, tool.ready.tool)
