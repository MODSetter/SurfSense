"""At most LIVE_INSTANCES thread instances stay in opencode: after a turn, the least recently used past them are disposed.

Each holds about 30 MB after a turn (test_thread_isolation) and opencode frees
none until it exits. A disposed thread's next call starts a fresh instance from
its stored session. Called from the event loop only.
"""

import logging
from collections import Counter, OrderedDict
from pathlib import Path

import httpx

from modules.agent.opencode_client import OpencodeClient

LIVE_INSTANCES = 6

logger = logging.getLogger(__name__)

# Thread folders opencode holds an instance for, least recently used first.
_used: OrderedDict[Path, None] = OrderedDict()
# Turns streaming in each folder; an approval waits inside its turn's stream.
_turns: Counter[Path] = Counter()


def instance_used(folder: Path) -> None:
    """A call ran in the folder's instance, starting it if it was not running."""
    _used[folder] = None
    _used.move_to_end(folder)


def turn_began(folder: Path) -> None:
    """The folder's instance may not be disposed until the turn ends."""
    _turns[folder] += 1
    instance_used(folder)


async def turn_ended(client: OpencodeClient, folder: Path) -> None:
    """Dispose the least recently used idle instances past the cap."""
    _turns[folder] -= 1
    if _turns[folder] <= 0:
        del _turns[folder]
    instance_used(folder)
    idle = [used for used in _used if used not in _turns]
    for stale in idle[: max(0, len(_used) - LIVE_INSTANCES)]:
        if stale in _turns:
            continue  # a turn began there while another was being disposed
        _used.pop(stale, None)
        try:
            await client.dispose_instance(stale)
        except httpx.HTTPError:
            logger.warning("opencode kept the instance of %s", stale, exc_info=True)


def forget_instance(folder: Path) -> None:
    """The folder's instance was disposed with its deleted thread."""
    _used.pop(folder, None)
