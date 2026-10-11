"""Tools the user named in their message as `@<plugin>_<tool>`, which the composer inserts.

A mention is the user choosing the tool: the turn gives it past the limit, and the
agent is told. Only a ready tool counts, so a mention never unblocks one.
"""

import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from modules.agent.plugin_tools.turn_plugins import opencode_tool_name
from modules.plugins.gateway.listing import list_tools

# The characters opencode keeps in a tool's name.
_MENTION = re.compile(r"@([A-Za-z0-9_-]+)")


@dataclass(frozen=True)
class Mention:
    name: str
    tool: str
    plugin: str


def mentioned_tools(session: Session, text: str) -> list[Mention]:
    named = set(_MENTION.findall(text))
    if not named:
        return []
    mentions = []
    for tool in list_tools(session):
        name = opencode_tool_name(tool.plugin_id, tool.tool)
        if name in named:
            mentions.append(Mention(name, tool.title or tool.tool, tool.plugin_name))
    return mentions


def mention_note(mentions: list[Mention]) -> str | None:
    """What the agent is told beside the user's words, as the scope note is."""
    if not mentions:
        return None
    return " ".join(
        f"The user asked you to use {m.tool} from {m.plugin} ({m.name}) for this."
        for m in mentions
    )
