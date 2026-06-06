"""``slack`` permission ruleset (rules over MCP tool names)."""

from __future__ import annotations

from app.agents.chat.multi_agent_chat.shared.permissions import Rule, Ruleset

NAME = "slack"

RULESET = Ruleset(
    origin=NAME,
    rules=[
        Rule(permission="slack_search_channels", pattern="*", action="allow"),
        Rule(permission="slack_search_messages", pattern="*", action="allow"),
        Rule(permission="slack_search_users", pattern="*", action="allow"),
        Rule(permission="slack_read_channel", pattern="*", action="allow"),
        Rule(permission="slack_read_thread", pattern="*", action="allow"),
        Rule(permission="slack_send_message", pattern="*", action="ask"),
    ],
)
