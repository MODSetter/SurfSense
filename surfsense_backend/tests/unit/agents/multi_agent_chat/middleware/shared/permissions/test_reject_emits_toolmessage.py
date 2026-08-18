"""Reject must degrade to a ToolMessage the model can continue from, not raise.

``PermissionMiddleware`` used to ``raise RejectedError``/``CorrectedError`` on a
reject decision. Nothing caught them, so a user rejection surfaced as a 500
(``SERVER_ERROR``) and, for subagent-gated tools, killed the parent turn. Reject
must instead emit a denial ToolMessage (mirroring the deny path) so the AI/Tool
pairing stays valid and the model can adapt.
"""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from app.agents.chat.multi_agent_chat.shared.permissions.middleware import core
from app.agents.chat.multi_agent_chat.shared.permissions.middleware.core import (
    PermissionMiddleware,
)
from app.agents.chat.multi_agent_chat.shared.permissions.model import Rule, Ruleset

pytestmark = pytest.mark.unit


def _mw(monkeypatch, decision: dict) -> PermissionMiddleware:
    monkeypatch.setattr(core, "request_permission_decision", lambda **_kw: decision)
    return PermissionMiddleware(
        rulesets=[
            Ruleset(
                rules=[Rule(permission="edit_file", pattern="*", action="ask")],
                origin="test",
            )
        ]
    )


def _state() -> dict:
    ai = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "edit_file",
                "args": {"path": "/x"},
                "id": "c1",
                "type": "tool_call",
            }
        ],
    )
    return {"messages": [ai]}


def test_reject_emits_toolmessage_and_drops_call(monkeypatch) -> None:
    mw = _mw(monkeypatch, {"decision_type": "reject"})

    update, _ = mw._process(_state(), None)

    assert update is not None
    tms = [m for m in update["messages"] if isinstance(m, ToolMessage)]
    ai = next(m for m in update["messages"] if isinstance(m, AIMessage))
    assert len(tms) == 1
    assert tms[0].tool_call_id == "c1"
    assert tms[0].status == "error"
    assert ai.tool_calls == []


def test_reject_with_feedback_carries_feedback(monkeypatch) -> None:
    mw = _mw(monkeypatch, {"decision_type": "reject", "feedback": "use the trash bin"})

    update, _ = mw._process(_state(), None)

    tms = [m for m in update["messages"] if isinstance(m, ToolMessage)]
    assert len(tms) == 1
    assert "use the trash bin" in tms[0].content
