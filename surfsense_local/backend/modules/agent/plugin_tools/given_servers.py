"""What each thread folder's opencode was given for each server, as a digest, to give it again only on a change.

Giving a server again opens a new MCP session, losing a stateful plugin's state.
Only a digest is kept, so no credential stays here. Called from the event loop only.
"""

import hashlib
import json
from pathlib import Path

from modules.agent.plugin_tools.turn_plugins import TurnPlugin

_given: dict[tuple[Path, str], str] = {}


def digest(plugin: TurnPlugin) -> str:
    return server_digest(plugin.url, plugin.headers)


def server_digest(url: str, headers: dict[str, str]) -> str:
    given = json.dumps([url, headers], sort_keys=True)
    return hashlib.sha256(given.encode()).hexdigest()


def given_as(folder: Path, name: str) -> str | None:
    return _given.get((folder, name))


def remember_given(folder: Path, name: str, as_given: str | None) -> None:
    if as_given is None:
        _given.pop((folder, name), None)
    else:
        _given[(folder, name)] = as_given
