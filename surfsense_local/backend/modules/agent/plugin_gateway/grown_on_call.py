"""A plugin call grows its opencode turn's holding before the call's result goes back.

opencode reads the session's rules before each step: written now, the rest of the
plugin the agent is using is its at its next step. A Claude Code turn holds every
tool, and no holding: the call is sent back as it is.
"""

import json
import logging

from modules.agent.opencode_runtime import AgentUnavailableError, connect_opencode
from modules.agent.tool_exposure import holdings
from modules.agent.tool_exposure.growing import grow_after_call

logger = logging.getLogger(__name__)


async def grow_on_call(thread_id: int, plugin_id: str, body: bytes) -> None:
    holding = holdings.holding_of(thread_id)
    if holding is None or not _is_call(body):
        return
    try:
        client = connect_opencode()
    except AgentUnavailableError:
        return
    try:
        await grow_after_call(client, holding, plugin_id)
    except Exception:
        # The call's result matters more than more tools: it goes back regardless.
        logger.warning("a plugin call did not grow its turn's tools", exc_info=True)
    finally:
        await client.close()


def _is_call(body: bytes) -> bool:
    """Whether the request is a single `tools/call`."""
    try:
        message = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return False
    return isinstance(message, dict) and message.get("method") == "tools/call"
