"""Lock in the default-allow layering used by ``chat_deepagent``.

The agent factory wires ``PermissionMiddleware`` with three rulesets,
earliest -> latest:

1. ``surfsense_defaults`` (single ``allow */*`` rule)
2. ``connector_synthesized`` (deny rules for tools whose required
   connector is missing)
3. (future) user-defined rules from the Agent Permissions UI

Without #1 every read-only built-in (``ls``, ``read_file``, ``grep``,
``glob``, ``web_search`` …) defaulted to ``ask`` because
``permissions.evaluate`` returns ``ask`` when no rule matches. That
caused two production-painful behaviors:

* Resume payloads with a prior reject decision bled into innocent
  read-only tool calls, raising ``RejectedError("ls")``.
* Mutating connector tools got *double* prompted — once via the
  middleware ``ask`` and again via the per-tool ``interrupt()`` in
  ``app.agents.new_chat.tools.hitl``.

These tests pin the layering so a refactor that drops the default
ruleset fails loud.
"""

from __future__ import annotations

import pytest

from app.agents.new_chat.permissions import (
    Rule,
    Ruleset,
    aggregate_action,
    evaluate_many,
)

pytestmark = pytest.mark.unit


def _layered_rulesets(connector_denies: list[Rule]) -> list[Ruleset]:
    """Replicate ``chat_deepagent`` layering for the test."""
    return [
        Ruleset(
            rules=[Rule(permission="*", pattern="*", action="allow")],
            origin="surfsense_defaults",
        ),
        Ruleset(rules=connector_denies, origin="connector_synthesized"),
    ]


class TestReadOnlyToolsAllowed:
    """Read-only built-ins must NOT default to ask."""

    @pytest.mark.parametrize(
        "tool_name",
        [
            "ls",
            "read_file",
            "grep",
            "glob",
            "web_search",
            "scrape_webpage",
            "search_surfsense_docs",
            "get_connected_accounts",
            "write_todos",
            "task",
            "_noop",
            "invalid",
            "update_memory",
        ],
    )
    def test_default_allow_covers_safe_builtin(self, tool_name: str) -> None:
        rulesets = _layered_rulesets(connector_denies=[])
        rules = evaluate_many(tool_name, [tool_name], *rulesets)
        assert aggregate_action(rules) == "allow"


class TestConnectorDenyOverridesDefaultAllow:
    """Connector-synthesized denies must beat the default-allow rule."""

    def test_missing_connector_tool_is_denied(self) -> None:
        rulesets = _layered_rulesets(
            connector_denies=[
                Rule(permission="linear_create_issue", pattern="*", action="deny")
            ]
        )
        rules = evaluate_many(
            "linear_create_issue", ["linear_create_issue"], *rulesets
        )
        assert aggregate_action(rules) == "deny"

    def test_default_allow_still_applies_to_other_tools(self) -> None:
        """A deny rule for one tool must not bleed onto unrelated calls."""
        rulesets = _layered_rulesets(
            connector_denies=[
                Rule(permission="linear_create_issue", pattern="*", action="deny")
            ]
        )
        rules = evaluate_many("ls", ["ls"], *rulesets)
        assert aggregate_action(rules) == "allow"


class TestUserRuleOverridesDefault:
    """User rules layered last must override the default-allow rule."""

    def test_user_ask_overrides_default_allow(self) -> None:
        defaults = Ruleset(
            rules=[Rule(permission="*", pattern="*", action="allow")],
            origin="surfsense_defaults",
        )
        user_ruleset = Ruleset(
            rules=[Rule(permission="ls", pattern="*", action="ask")],
            origin="user",
        )
        rules = evaluate_many("ls", ["ls"], defaults, user_ruleset)
        assert aggregate_action(rules) == "ask"

    def test_user_deny_overrides_default_allow(self) -> None:
        defaults = Ruleset(
            rules=[Rule(permission="*", pattern="*", action="allow")],
            origin="surfsense_defaults",
        )
        user_ruleset = Ruleset(
            rules=[Rule(permission="send_*", pattern="*", action="deny")],
            origin="user",
        )
        rules = evaluate_many("send_gmail_email", ["send_gmail_email"], defaults, user_ruleset)
        assert aggregate_action(rules) == "deny"
