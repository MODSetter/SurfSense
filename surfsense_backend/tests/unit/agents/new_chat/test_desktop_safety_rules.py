"""Tests for the desktop-mode safety ruleset.

In desktop mode the agent operates against the user's real disk with no
revision history, so destructive filesystem operations must require
explicit approval. These tests pin the set of tools that get the ``ask``
gate so it cannot silently regress.
"""

from __future__ import annotations

import pytest

from app.agents.new_chat.middleware.permission import PermissionMiddleware
from app.agents.new_chat.permissions import (
    Rule,
    Ruleset,
    aggregate_action,
    evaluate_many,
)

pytestmark = pytest.mark.unit


# Mirror the ruleset built inside ``chat_deepagent._build_compiled_agent_blocking``
# when ``filesystem_mode == FilesystemMode.DESKTOP_LOCAL_FOLDER``. Keeping a
# copy here means the rule contract has a focused regression test even when
# the larger graph-build helper is hard to instantiate in unit tests.
DESKTOP_SAFETY_RULESET = Ruleset(
    rules=[
        Rule(permission="rm", pattern="*", action="ask"),
        Rule(permission="rmdir", pattern="*", action="ask"),
        Rule(permission="move_file", pattern="*", action="ask"),
        Rule(permission="edit_file", pattern="*", action="ask"),
        Rule(permission="write_file", pattern="*", action="ask"),
    ],
    origin="desktop_safety",
)

SURFSENSE_DEFAULTS = Ruleset(
    rules=[Rule(permission="*", pattern="*", action="allow")],
    origin="surfsense_defaults",
)


def _action_for(tool_name: str, *rulesets: Ruleset) -> str:
    rules = evaluate_many(tool_name, [tool_name], *rulesets)
    return aggregate_action(rules)


class TestDesktopSafetyRulesGateDestructiveOps:
    @pytest.mark.parametrize(
        "tool_name",
        ["rm", "rmdir", "move_file", "edit_file", "write_file"],
    )
    def test_destructive_op_resolves_to_ask(self, tool_name: str) -> None:
        # surfsense_defaults says "allow */*"; desktop_safety must override
        # because it's layered later (last-match-wins).
        action = _action_for(tool_name, SURFSENSE_DEFAULTS, DESKTOP_SAFETY_RULESET)
        assert action == "ask", (
            f"{tool_name} must require approval in desktop mode "
            f"(no revert path on real disk); got {action!r}"
        )

    @pytest.mark.parametrize(
        "tool_name",
        ["read_file", "ls", "list_tree", "grep", "glob", "cd", "pwd", "mkdir"],
    )
    def test_safe_ops_remain_allowed(self, tool_name: str) -> None:
        # Read-only and trivially-reversible tools must NOT get gated —
        # otherwise every navigation in desktop mode pops an interrupt.
        action = _action_for(tool_name, SURFSENSE_DEFAULTS, DESKTOP_SAFETY_RULESET)
        assert action == "allow", (
            f"{tool_name} should not be gated in desktop mode; got {action!r}"
        )


class TestDesktopSafetyOverridesAllowDefault:
    def test_layer_order_last_match_wins(self) -> None:
        # If desktop_safety is layered BEFORE surfsense_defaults, the allow
        # default would win and the safety net would be inert. This test
        # protects against accidentally swapping the rulesets in
        # ``_build_compiled_agent_blocking``.
        action = _action_for("rm", DESKTOP_SAFETY_RULESET, SURFSENSE_DEFAULTS)
        # Layered "wrong way" — the broad allow now wins.
        assert action == "allow"

        # Correct order: defaults < desktop_safety -> ask wins.
        action = _action_for("rm", SURFSENSE_DEFAULTS, DESKTOP_SAFETY_RULESET)
        assert action == "ask"


class TestPermissionMiddlewareIntegration:
    def test_middleware_raises_interrupt_for_rm_in_desktop_mode(self) -> None:
        from langchain_core.messages import AIMessage

        from app.agents.new_chat.errors import RejectedError

        mw = PermissionMiddleware(rulesets=[SURFSENSE_DEFAULTS, DESKTOP_SAFETY_RULESET])
        # Stub the interrupt to a "reject" decision so we can assert the
        # ask path was taken without spinning up the LangGraph runtime.
        mw._raise_interrupt = lambda **kw: {"decision_type": "reject"}  # type: ignore[assignment]

        state = {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "rm",
                            "args": {"path": "/Users/me/Documents/important.docx"},
                            "id": "tc-rm",
                        }
                    ],
                )
            ]
        }

        class _FakeRuntime:
            config: dict = {"configurable": {"thread_id": "test"}}

        with pytest.raises(RejectedError):
            mw.after_model(state, _FakeRuntime())
