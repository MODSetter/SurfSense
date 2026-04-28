"""Tests for PermissionMiddleware end-to-end behavior."""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from app.agents.new_chat.errors import CorrectedError, RejectedError
from app.agents.new_chat.middleware.permission import PermissionMiddleware
from app.agents.new_chat.permissions import Rule, Ruleset

pytestmark = pytest.mark.unit


class _FakeRuntime:
    config: dict = {"configurable": {"thread_id": "test"}}


def _msg(*tool_calls: dict) -> AIMessage:
    return AIMessage(content="", tool_calls=list(tool_calls))


class TestAllow:
    def test_passthrough_when_allow(self) -> None:
        rs = Ruleset(rules=[Rule("send_email", "*", "allow")])
        mw = PermissionMiddleware(rulesets=[rs])
        state = {"messages": [_msg({"name": "send_email", "args": {}, "id": "1"})]}
        out = mw.after_model(state, _FakeRuntime())
        assert out is None  # no change


class TestDeny:
    def test_replaces_with_deny_tool_message(self) -> None:
        rs = Ruleset(rules=[Rule("send_email", "*", "deny")])
        mw = PermissionMiddleware(rulesets=[rs])
        state = {"messages": [_msg({"name": "send_email", "args": {}, "id": "1"})]}
        out = mw.after_model(state, _FakeRuntime())
        assert out is not None
        msgs = out["messages"]
        # Find the deny ToolMessage
        deny_msgs = [m for m in msgs if isinstance(m, ToolMessage)]
        assert len(deny_msgs) == 1
        assert deny_msgs[0].status == "error"
        assert "permission_denied" in str(deny_msgs[0].additional_kwargs)
        # AIMessage's tool_calls should now be empty (denied call removed)
        ai_msg = next(m for m in msgs if isinstance(m, AIMessage))
        assert ai_msg.tool_calls == []

    def test_mixed_allow_deny(self) -> None:
        rs = Ruleset(
            rules=[
                Rule("send_email", "*", "deny"),
                Rule("read", "*", "allow"),
            ]
        )
        mw = PermissionMiddleware(rulesets=[rs])
        state = {
            "messages": [
                _msg(
                    {"name": "send_email", "args": {}, "id": "1"},
                    {"name": "read", "args": {}, "id": "2"},
                )
            ]
        }
        out = mw.after_model(state, _FakeRuntime())
        assert out is not None
        ai_msg = next(m for m in out["messages"] if isinstance(m, AIMessage))
        assert len(ai_msg.tool_calls) == 1
        assert ai_msg.tool_calls[0]["name"] == "read"


class TestAsk:
    def test_reject_without_feedback_raises(self) -> None:
        # Default: nothing matches -> ask
        rs = Ruleset(rules=[])
        mw = PermissionMiddleware(rulesets=[rs])

        # Bypass real interrupt — patch the helper
        mw._raise_interrupt = lambda **kw: {"decision_type": "reject"}  # type: ignore[assignment]
        state = {"messages": [_msg({"name": "send_email", "args": {}, "id": "1"})]}
        with pytest.raises(RejectedError):
            mw.after_model(state, _FakeRuntime())

    def test_reject_with_feedback_raises_corrected(self) -> None:
        rs = Ruleset(rules=[])
        mw = PermissionMiddleware(rulesets=[rs])
        mw._raise_interrupt = lambda **kw: {  # type: ignore[assignment]
            "decision_type": "reject",
            "feedback": "use a different subject line",
        }
        state = {"messages": [_msg({"name": "send_email", "args": {}, "id": "1"})]}
        with pytest.raises(CorrectedError) as excinfo:
            mw.after_model(state, _FakeRuntime())
        assert excinfo.value.feedback == "use a different subject line"

    def test_once_proceeds_without_persisting(self) -> None:
        mw = PermissionMiddleware(rulesets=[])
        mw._raise_interrupt = lambda **kw: {"decision_type": "once"}  # type: ignore[assignment]
        state = {"messages": [_msg({"name": "send_email", "args": {}, "id": "1"})]}
        out = mw.after_model(state, _FakeRuntime())
        # No state change because all calls kept
        assert out is None
        # No new rule persisted
        assert mw._runtime_ruleset.rules == []

    def test_always_persists_runtime_rule(self) -> None:
        mw = PermissionMiddleware(rulesets=[])
        mw._raise_interrupt = lambda **kw: {"decision_type": "always"}  # type: ignore[assignment]
        state = {"messages": [_msg({"name": "send_email", "args": {}, "id": "1"})]}
        out = mw.after_model(state, _FakeRuntime())
        assert out is None  # call kept
        # Runtime ruleset got the always-allow rule
        new_rules = [r for r in mw._runtime_ruleset.rules if r.action == "allow"]
        assert any(
            r.permission == "send_email" for r in new_rules
        )
