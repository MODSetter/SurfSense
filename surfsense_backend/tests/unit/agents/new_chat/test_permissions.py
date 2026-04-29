"""Tests for the wildcard matcher and rule evaluator (parity with OpenCode evaluate.ts)."""

from __future__ import annotations

import pytest

from app.agents.new_chat.permissions import (
    Rule,
    Ruleset,
    aggregate_action,
    evaluate,
    evaluate_many,
    wildcard_match,
)

pytestmark = pytest.mark.unit


class TestWildcardMatch:
    @pytest.mark.parametrize(
        "value,pattern,expected",
        [
            ("edit", "edit", True),
            ("edit", "*", True),
            ("read", "edit", False),
            ("/documents/secrets/x", "/documents/secrets/**", True),
            # Single-segment glob: '*' does not cross '/'
            ("/documents/secrets/x", "/documents/*/x", True),
            ("/documents/foo/bar/x", "/documents/*/x", False),
            ("/documents/foo/x", "/documents/*/x", True),
            ("linear_create", "linear_*", True),
            ("notion_create", "linear_*", False),
            # ':' is not a separator, so '*' matches it
            ("mcp:notion:create_page", "mcp:*", True),
            ("mcp:notion:create_page", "mcp:**", True),
            # But '/' IS a separator
            ("foo/bar", "foo/*", True),
            ("foo/bar/baz", "foo/*", False),
        ],
    )
    def test_match(self, value: str, pattern: str, expected: bool) -> None:
        assert wildcard_match(value, pattern) is expected


class TestEvaluate:
    def test_default_action_is_ask(self) -> None:
        rule = evaluate("edit", "/foo/bar")
        assert rule.action == "ask"
        assert rule.permission == "edit"

    def test_last_match_wins(self) -> None:
        rs = Ruleset(
            rules=[
                Rule("edit", "*", "allow"),
                Rule("edit", "/secrets/**", "deny"),
            ]
        )
        # Second rule (deny) is more specific AND specified later
        assert evaluate("edit", "/secrets/x", rs).action == "deny"
        # First rule (allow) covers the rest
        assert evaluate("edit", "/public/x", rs).action == "allow"

    def test_layered_rulesets_later_overrides_earlier(self) -> None:
        defaults = Ruleset(rules=[Rule("edit", "*", "ask")], origin="defaults")
        space = Ruleset(rules=[Rule("edit", "*", "allow")], origin="space")
        thread = Ruleset(rules=[Rule("edit", "*", "deny")], origin="thread")
        # All three layered: thread wins
        assert evaluate("edit", "x", defaults, space, thread).action == "deny"
        # Without thread: space wins
        assert evaluate("edit", "x", defaults, space).action == "allow"

    def test_permission_wildcard(self) -> None:
        rs = Ruleset(rules=[Rule("linear_*", "*", "allow")])
        assert evaluate("linear_create_issue", "x", rs).action == "allow"
        assert evaluate("notion_create", "x", rs).action == "ask"

    def test_pattern_wildcard(self) -> None:
        rs = Ruleset(rules=[Rule("edit", "/documents/secrets/**", "deny")])
        assert evaluate("edit", "/documents/secrets/foo", rs).action == "deny"
        assert evaluate("edit", "/documents/public/foo", rs).action == "ask"

    def test_evaluate_many(self) -> None:
        rs = Ruleset(
            rules=[
                Rule("edit", "*", "allow"),
                Rule("edit", "/secrets/*", "deny"),
            ]
        )
        results = evaluate_many("edit", ["/public/x", "/secrets/y"], rs)
        assert [r.action for r in results] == ["allow", "deny"]


class TestAggregateAction:
    def test_any_deny_means_deny(self) -> None:
        rules = [
            Rule("a", "*", "allow"),
            Rule("a", "*", "deny"),
            Rule("a", "*", "ask"),
        ]
        assert aggregate_action(rules) == "deny"

    def test_any_ask_means_ask_when_no_deny(self) -> None:
        rules = [Rule("a", "*", "allow"), Rule("a", "*", "ask")]
        assert aggregate_action(rules) == "ask"

    def test_all_allow_means_allow(self) -> None:
        rules = [Rule("a", "*", "allow"), Rule("a", "*", "allow")]
        assert aggregate_action(rules) == "allow"

    def test_empty_means_ask(self) -> None:
        assert aggregate_action([]) == "ask"
