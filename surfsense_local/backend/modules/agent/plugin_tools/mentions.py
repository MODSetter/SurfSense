"""Plugins the user named in their message as `@<plugin id>`, which the composer inserts.

A mention is the user choosing the plugin: the turn gives every ready tool of it past
the limit, and the agent is told, then picks the tools itself. Only a ready plugin
counts, and only its ready tools, so a mention never unblocks one.
"""

import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from modules.plugins.gateway.listing import list_tools

# A plugin id: lowercase words joined by hyphens.
_MENTION = re.compile(r"@([a-z0-9-]+)")


@dataclass(frozen=True)
class Mention:
    plugin_id: str
    plugin: str


def mentioned_plugins(session: Session, text: str) -> list[Mention]:
    named = set(_MENTION.findall(text))
    if not named:
        return []
    ready = {tool.plugin_id: tool.plugin_name for tool in list_tools(session)}
    return [Mention(key, name) for key, name in ready.items() if key in named]


def mention_note(mentions: list[Mention]) -> str | None:
    """What the agent is told beside the user's words, as the scope note is."""
    if not mentions:
        return None
    return " ".join(
        f"The user asked you to use the {m.plugin} plugin for this." for m in mentions
    )
