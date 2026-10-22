"""A plugin call grows its opencode turn's holding before the call's result goes back.

opencode reads the session's rules before each step: written now, the rest of the
plugin the agent is using, and the plugin of the tool that best fits what it is
doing, are its at its next step. A Claude Code turn holds every tool, and no
holding: the call is sent back as it is.
"""

import json
import logging

from modules.agent.opencode_runtime import AgentUnavailableError, connect_opencode
from modules.agent.tool_exposure import holdings
from modules.agent.tool_exposure.growing import grow_after_call

logger = logging.getLogger(__name__)


async def grow_on_call(thread_id: int, plugin_id: str, body: bytes) -> None:
    holding = holdings.holding_of(thread_id)
    tool = _called(body)
    if holding is None or tool is None:
        return
    try:
        client = connect_opencode()
    except AgentUnavailableError:
        return
    try:
        await grow_after_call(client, holding, plugin_id, tool, holding.embed)
    except Exception:
        # The call's result matters more than more tools: it goes back regardless.
        logger.warning("a plugin call did not grow its turn's tools", exc_info=True)
    finally:
        await client.close()


def _called(body: bytes) -> str | None:
    """The tool a single `tools/call` names; None for anything else."""
    try:
        message = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(message, dict) or message.get("method") != "tools/call":
        return None
    params = message.get("params")
    name = params.get("name") if isinstance(params, dict) else None
    return name if isinstance(name, str) else None
