"""Tests for PermissionMiddleware end-to-end behavior."""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from app.agents.new_chat.errors import CorrectedError, RejectedError
from app.agents.new_chat.middleware.permission import (
    PermissionMiddleware,
    _normalize_permission_decision,
)
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
        assert any(r.permission == "send_email" for r in new_rules)


class TestNormalizeDecision:
    """Resume shapes ``_normalize_permission_decision`` must accept."""

    def test_legacy_decision_type_dict_passes_through(self) -> None:
        decision = {"decision_type": "once"}
        assert _normalize_permission_decision(decision) == {"decision_type": "once"}

    def test_legacy_decision_type_with_feedback_passes_through(self) -> None:
        decision = {"decision_type": "reject", "feedback": "no thanks"}
        assert _normalize_permission_decision(decision) == decision

    def test_plain_string_wrapped(self) -> None:
        assert _normalize_permission_decision("once") == {"decision_type": "once"}
        assert _normalize_permission_decision("reject") == {"decision_type": "reject"}

    def test_lc_envelope_approve_maps_to_once(self) -> None:
        decision = {"decisions": [{"type": "approve"}]}
        assert _normalize_permission_decision(decision) == {"decision_type": "once"}

    def test_lc_envelope_reject_maps_to_reject(self) -> None:
        decision = {"decisions": [{"type": "reject"}]}
        assert _normalize_permission_decision(decision) == {"decision_type": "reject"}

    def test_lc_envelope_reject_with_message_carries_feedback(self) -> None:
        decision = {
            "decisions": [{"type": "reject", "message": "wrong recipient"}]
        }
        out = _normalize_permission_decision(decision)
        assert out == {"decision_type": "reject", "feedback": "wrong recipient"}

    def test_lc_envelope_reject_with_feedback_field(self) -> None:
        decision = {
            "decisions": [{"type": "reject", "feedback": "tighten the subject"}]
        }
        out = _normalize_permission_decision(decision)
        assert out == {"decision_type": "reject", "feedback": "tighten the subject"}

    def test_lc_envelope_edit_maps_to_once(self) -> None:
        # Pins the contract: edited args are NOT merged by permission.
        decision = {
            "decisions": [
                {
                    "type": "edit",
                    "edited_action": {
                        "name": "send_email",
                        "args": {"subject": "edited"},
                    },
                }
            ]
        }
        assert _normalize_permission_decision(decision) == {"decision_type": "once"}

    def test_lc_single_decision_without_envelope(self) -> None:
        assert _normalize_permission_decision({"type": "approve"}) == {
            "decision_type": "once"
        }

    def test_unknown_type_falls_back_to_reject(self) -> None:
        decision = {"decisions": [{"type": "totally_unknown"}]}
        assert _normalize_permission_decision(decision) == {"decision_type": "reject"}

    def test_missing_type_falls_back_to_reject(self) -> None:
        assert _normalize_permission_decision({"decisions": [{}]}) == {
            "decision_type": "reject"
        }

    def test_non_dict_non_string_falls_back_to_reject(self) -> None:
        assert _normalize_permission_decision(None) == {"decision_type": "reject"}
        assert _normalize_permission_decision(42) == {"decision_type": "reject"}

    def test_empty_decisions_list_falls_back_to_reject(self) -> None:
        # Fail-closed on a malformed reply rather than treat it as approve.
        assert _normalize_permission_decision({"decisions": []}) == {
            "decision_type": "reject"
        }


class TestResumeShapesEndToEnd:
    """LangChain HITL envelope reaches ``_process`` correctly via ``_raise_interrupt``."""

    def test_lc_approve_envelope_keeps_call(self) -> None:
        mw = PermissionMiddleware(rulesets=[])
        mw._raise_interrupt = lambda **kw: {  # type: ignore[assignment]
            "decisions": [{"type": "approve"}]
        }
        state = {"messages": [_msg({"name": "send_email", "args": {}, "id": "1"})]}
        original = mw._raise_interrupt
        mw._raise_interrupt = lambda **kw: _normalize_permission_decision(  # type: ignore[assignment]
            original(**kw)
        )
        out = mw.after_model(state, _FakeRuntime())
        assert out is None

    def test_lc_reject_envelope_raises(self) -> None:
        mw = PermissionMiddleware(rulesets=[])
        original = lambda **kw: {"decisions": [{"type": "reject"}]}  # noqa: E731
        mw._raise_interrupt = lambda **kw: _normalize_permission_decision(  # type: ignore[assignment]
            original(**kw)
        )
        state = {"messages": [_msg({"name": "send_email", "args": {}, "id": "1"})]}
        with pytest.raises(RejectedError):
            mw.after_model(state, _FakeRuntime())

    def test_lc_reject_with_message_raises_corrected(self) -> None:
        mw = PermissionMiddleware(rulesets=[])
        original = lambda **kw: {  # noqa: E731
            "decisions": [{"type": "reject", "message": "wrong recipient"}]
        }
        mw._raise_interrupt = lambda **kw: _normalize_permission_decision(  # type: ignore[assignment]
            original(**kw)
        )
        state = {"messages": [_msg({"name": "send_email", "args": {}, "id": "1"})]}
        with pytest.raises(CorrectedError) as excinfo:
            mw.after_model(state, _FakeRuntime())
        assert excinfo.value.feedback == "wrong recipient"

    def test_lc_edit_envelope_keeps_call_with_original_args(self) -> None:
        # Pins the "edit -> once, args unchanged" contract.
        mw = PermissionMiddleware(rulesets=[])
        original = lambda **kw: {  # noqa: E731
            "decisions": [
                {
                    "type": "edit",
                    "edited_action": {
                        "name": "send_email",
                        "args": {"to": "edited@example.com"},
                    },
                }
            ]
        }
        mw._raise_interrupt = lambda **kw: _normalize_permission_decision(  # type: ignore[assignment]
            original(**kw)
        )
        state = {
            "messages": [
                _msg(
                    {
                        "name": "send_email",
                        "args": {"to": "original@example.com"},
                        "id": "1",
                    }
                )
            ]
        }
        out = mw.after_model(state, _FakeRuntime())
        assert out is None
