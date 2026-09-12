"""``build_resume_routing`` must route parent-side interrupts (doom-loop / asks).

Guards the bug where unstamped parent-graph interrupts were dropped on resume,
hanging the turn.
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
    """Decision routes to the doom-loop's ``Interrupt.id`` as a raw dict, not a bundle."""
    decision = {"type": "reject"}
    agent = _FakeAgent(SimpleNamespace(interrupts=(_doom_loop_interrupt("i-doom"),)))

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


def _structured_question_interrupt(interrupt_id: str, tool_call_id: str):
    return SimpleNamespace(
        id=interrupt_id,
        value={
            "type": "structured_question",
            "version": 1,
            "title": "Choose a style",
            "origin": {
                "kind": "preset",
                "preset_id": "infographic.visual-style",
                "preset_version": 1,
            },
            "questions": [
                {
                    "id": "visual-style",
                    "prompt": "Which visual style should be used?",
                    "input_type": "single_select",
                    "presentation": "visual_cards",
                    "options": [
                        {"id": "auto", "label": "Auto"},
                        {"id": "kawaii", "label": "Kawaii"},
                    ],
                }
            ],
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


async def test_id_stamped_decisions_route_by_identity_across_boundary():
    """Id-stamped decisions route correctly even reversed vs ``state.interrupts``."""
    agent = _FakeAgent(
        SimpleNamespace(
            interrupts=(
                _subagent_interrupt("i-A", "tcid-A", 1),
                _subagent_interrupt("i-B", "tcid-B", 1),
            )
        )
    )
    decisions = [
        {"type": "reject", "tool_call_id": "tcid-B"},
        {"type": "approve", "tool_call_id": "tcid-A"},
    ]

    routing = await build_resume_routing(agent, chat_id=1, decisions=decisions)

    assert routing.routed_resume_value == {
        "tcid-A": {"decisions": [{"type": "approve", "tool_call_id": "tcid-A"}]},
        "tcid-B": {"decisions": [{"type": "reject", "tool_call_id": "tcid-B"}]},
    }
    assert routing.lg_resume_map == {
        "i-A": {"decisions": [{"type": "approve", "tool_call_id": "tcid-A"}]},
        "i-B": {"decisions": [{"type": "reject", "tool_call_id": "tcid-B"}]},
    }


async def test_structured_question_response_is_validated_and_routed():
    response = {
        "type": "respond",
        "preset_id": "infographic.visual-style",
        "preset_version": 1,
        "answers": [{"question_id": "visual-style", "option_ids": ["kawaii"]}],
    }
    agent = _FakeAgent(
        SimpleNamespace(
            interrupts=(_structured_question_interrupt("i-style", "tcid-style"),)
        )
    )

    routing = await build_resume_routing(agent, chat_id=1, decisions=[response])

    expected = {"decisions": [response]}
    assert routing.routed_resume_value == {"tcid-style": expected}
    assert routing.lg_resume_map == {"i-style": expected}


@pytest.mark.parametrize(
    "response, match",
    [
        ({"type": "approve"}, "requires respond or cancel"),
        (
            {
                "type": "respond",
                "preset_id": "infographic.visual-style",
                "preset_version": 2,
                "answers": [
                    {"question_id": "visual-style", "option_ids": ["kawaii"]}
                ],
            },
            "stale preset",
        ),
    ],
)
async def test_structured_question_rejects_wrong_response(
    response: dict, match: str
):
    agent = _FakeAgent(
        SimpleNamespace(
            interrupts=(_structured_question_interrupt("i-style", "tcid-style"),)
        )
    )

    with pytest.raises(ValueError, match=match):
        await build_resume_routing(agent, chat_id=1, decisions=[response])


async def test_structured_response_without_pending_question_is_rejected():
    agent = _FakeAgent(
        SimpleNamespace(interrupts=(_subagent_interrupt("i-A", "tcid-A", 1),))
    )

    with pytest.raises(ValueError, match="No structured question is pending"):
        await build_resume_routing(
            agent,
            chat_id=1,
            decisions=[{"type": "cancel", "preset_id": "infographic.visual-style"}],
        )


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
