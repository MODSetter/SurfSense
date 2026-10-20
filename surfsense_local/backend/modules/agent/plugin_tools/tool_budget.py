"""Which ready tools a turn offers a runtime that sends every tool's definition with every request.

A share of the model's window rather than a count, so a large window offers more than a
small local one. A mentioned plugin's tools go first, whatever they cost; then the plugins
take turns, one tool each, so one with many tools cannot crowd out the rest. The tools the
user's message matches go first: in each plugin, and the plugin with the best match.
opencode 1.x fixes a turn's tools when it starts, so this is chosen before the model asks.
"""

import json

from modules.agent.plugin_tools.tool_relevance import message_words, relevance
from modules.plugins.gateway.ready_tool import ReadyTool

# Claude Code defers MCP tools past the same share of its window (ENABLE_TOOL_SEARCH=auto).
WINDOW_SHARE = 0.10
# opencode's own estimate of a token, used for its tool output too.
CHARS_PER_TOKEN = 4


def window_budget(window: int) -> int:
    return int(window * WINDOW_SHARE)


def tool_tokens(tool: ReadyTool) -> int:
    told = [tool.tool, tool.title or "", tool.description or "", tool.input_schema]
    return len(json.dumps(told)) // CHARS_PER_TOKEN


def offered_tools(
    ready: list[ReadyTool], mentioned: frozenset[str], budget: int | None, text: str
) -> list[ReadyTool]:
    """In `ready`'s order; None offers every one, for a runtime that searches its tools."""
    if budget is None:
        return ready
    words = message_words(text)
    score = {id(tool): relevance(tool, words) for tool in ready}
    chosen = {id(tool) for tool in ready if tool.plugin_id in mentioned}
    spent = sum(tool_tokens(tool) for tool in ready if id(tool) in chosen)
    queues: dict[str, list[ReadyTool]] = {}
    for tool in ready:
        if id(tool) not in chosen:
            queues.setdefault(tool.plugin_id, []).append(tool)
    for queue in queues.values():
        # Stable: tools that match nothing keep their server's order.
        queue.sort(key=lambda tool: -score[id(tool)])
    order = sorted(queues, key=lambda plugin_id: -score[id(queues[plugin_id][0])])
    queues = {plugin_id: queues[plugin_id] for plugin_id in order}
    while queues:
        for plugin_id in list(queues):
            tool = queues[plugin_id].pop(0)
            cost = tool_tokens(tool)
            if spent + cost > budget:
                # Its next tool would not fit either; the others may still have smaller ones.
                del queues[plugin_id]
                continue
            chosen.add(id(tool))
            spent += cost
            if not queues[plugin_id]:
                del queues[plugin_id]
    return [tool for tool in ready if id(tool) in chosen]
