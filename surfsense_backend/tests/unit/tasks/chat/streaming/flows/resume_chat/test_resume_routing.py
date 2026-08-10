"""Resume routing must wake parent-side interrupts (doom-loop / main-agent asks).

Regression guard for the bug where ``build_resume_routing`` dropped every
interrupt that lacked a ``tool_call_id`` stamp. Those stamps are only added
when an interrupt bubbles up through a ``task`` subagent call
(``propagation.wrap_with_tool_call_id``); interrupts raised directly in the
parent graph — ``DoomLoopMiddleware`` pauses and main-agent
``PermissionMiddleware`` asks — carry no stamp, so the user's decision could
never reach the paused site and the turn hung forever.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.tasks.chat.streaming.flows.resume_chat.resume_routing import (
    build_resume_routing,
)


class _FakeAgent:
    """Minimal stand-in exposing the ``aget_state`` the router reads."""

    def __init__(self, state):
        self._state = state

    async def aget_state(self, _config):
        return self._state


def _doom_loop_interrupt(interrupt_id: str):
    """A parent-side doom-loop interrupt: no ``tool_call_id``, no ``action_requests``."""
    return SimpleNamespace(
        id=interrupt_id,
        value={
            "type": "permission_ask",
            "action": {"tool": "search_run", "params": {}},
            "context": {"permission": "doom_loop", "threshold": 3},
        },
    )


async def test_parent_side_doom_loop_interrupt_is_routable():
    """The user's decision must be delivered to the doom-loop's ``Interrupt.id``.

    The doom-loop site consumes the resume value directly as the return of
    ``interrupt(...)`` (it reads ``decision["type"]``), so the map value must be
    the raw decision dict — not a ``{"decisions": [...]}`` bundle.
    """
    decision = {"type": "reject"}
    agent = _FakeAgent(
        SimpleNamespace(interrupts=(_doom_loop_interrupt("i-doom"),))
    )

    routing = await build_resume_routing(agent, chat_id=42, decisions=[decision])

    assert routing.lg_resume_map == {"i-doom": decision}
    # No subagent bridge for parent-side interrupts.
    assert routing.routed_resume_value == {}


def _permission_ask_interrupt(interrupt_id: str):
    """A parent-side main-agent permission ask: LC HITL bundle, still no stamp."""
    return SimpleNamespace(
        id=interrupt_id,
        value={
            "type": "permission_ask",
            "action_requests": [{"name": "create_automation", "args": {}}],
        },
    )


async def test_parent_side_permission_ask_is_routable():
    """Main-agent permission asks (unstamped) route their single decision by id."""
    decision = {"type": "approve"}
    agent = _FakeAgent(
        SimpleNamespace(interrupts=(_permission_ask_interrupt("i-perm"),))
    )

    routing = await build_resume_routing(agent, chat_id=7, decisions=[decision])

    assert routing.lg_resume_map == {"i-perm": decision}


def _subagent_interrupt(interrupt_id: str, tool_call_id: str, action_count: int):
    return SimpleNamespace(
        id=interrupt_id,
        value={
            "action_requests": [{"name": "n", "args": {}}] * action_count,
            "tool_call_id": tool_call_id,
        },
    )


async def test_subagent_path_is_unchanged():
    """Regression guard: stamped subagent interrupts still route via the bridge."""
    decisions = [{"type": "approve"}, {"type": "reject"}]
    agent = _FakeAgent(
        SimpleNamespace(interrupts=(_subagent_interrupt("i-A", "tcid-A", 2),))
    )

    routing = await build_resume_routing(agent, chat_id=1, decisions=decisions)

    assert routing.routed_resume_value == {"tcid-A": {"decisions": decisions}}
    assert routing.lg_resume_map == {"i-A": {"decisions": decisions}}


async def test_mixed_parent_and_subagent_pauses_fail_loud():
    """A pause holding both interrupt kinds is unsupported and must not mis-route."""
    agent = _FakeAgent(
        SimpleNamespace(
            interrupts=(
                _subagent_interrupt("i-A", "tcid-A", 1),
                _doom_loop_interrupt("i-doom"),
            )
        )
    )

    with pytest.raises(ValueError, match="mixed HITL routing"):
        await build_resume_routing(
            agent, chat_id=1, decisions=[{"type": "approve"}, {"type": "reject"}]
        )
