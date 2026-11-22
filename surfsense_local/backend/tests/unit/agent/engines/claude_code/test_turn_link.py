"""Each tool call of a Claude Code turn meets the gate; an `ask` waits on the user's answer."""

import asyncio
from pathlib import Path

import pytest
from claude_agent_sdk import PermissionResultAllow, PermissionResultDeny

from modules.agent.engines.claude_code.approvals import Approvals
from modules.agent.engines.claude_code.gate import Gate
from modules.agent.engines.claude_code.turn_link import TurnLink

pytestmark = pytest.mark.unit
THREAD = 7


def _link(tmp_path: Path) -> tuple[TurnLink, Approvals, asyncio.Queue]:
    folder = tmp_path / "7"
    (folder / "outputs").mkdir(parents=True)
    approvals = Approvals()
    link = TurnLink(THREAD, approvals)
    events: asyncio.Queue = asyncio.Queue()
    link.begin(
        Gate(
            folder=folder,
            skills=tmp_path / "skills",
            plugin_rules={"mcp__notion__create_page": "ask"},
        ),
        events,
        "claude-session",
    )
    return link, approvals, events


def _hook_input(tool: str, tool_input: dict) -> dict:
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": tool,
        "tool_input": tool_input,
    }


async def test_the_hook_answers_at_once_with_the_gates_verdict(tmp_path: Path) -> None:
    """Fast, so Claude Code's hook timeout never decides a call."""
    link, _, _ = _link(tmp_path)

    allowed = await link.pre_tool_use(
        _hook_input("Write", {"file_path": "outputs/a.md"}), "toolu_1", {}
    )
    refused = await link.pre_tool_use(
        _hook_input("Bash", {"command": "ls"}), "toolu_2", {}
    )
    asked = await link.pre_tool_use(
        _hook_input("mcp__notion__create_page", {}), "toolu_3", {}
    )

    assert allowed["hookSpecificOutput"]["permissionDecision"] == "allow"
    assert refused["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert refused["hookSpecificOutput"]["permissionDecisionReason"]
    assert asked["hookSpecificOutput"]["permissionDecision"] == "ask"


async def test_an_ask_waits_for_the_user_and_the_thread_sees_both_ends(
    tmp_path: Path,
) -> None:
    """The approval card names the step it holds back; Allow once runs the call."""
    link, approvals, events = _link(tmp_path)

    asking = asyncio.create_task(
        link.can_use_tool(
            "mcp__notion__create_page", {"title": "Q3"}, {"tool_use_id": "toolu_3"}
        )
    )
    asked = await asyncio.wait_for(events.get(), 1)
    assert asked.type == "permission.asked"
    assert asked.data["source"]["id"] == "toolu_3"
    assert asked.data["action"] == "notion_create_page"
    assert not asking.done()

    assert approvals.answer(THREAD, asked.data["id"], "once")

    assert isinstance(await asking, PermissionResultAllow)
    replied = await events.get()
    assert replied.type == "permission.replied"
    assert replied.data["reply"] == "once"


async def test_a_rejected_ask_never_runs(tmp_path: Path) -> None:
    """Reject reaches Claude Code as a refusal the model reads."""
    link, approvals, events = _link(tmp_path)

    asking = asyncio.create_task(
        link.can_use_tool("mcp__notion__create_page", {}, {"tool_use_id": "toolu_3"})
    )
    asked = await events.get()
    approvals.answer(THREAD, asked.data["id"], "reject")

    refused = await asking
    assert isinstance(refused, PermissionResultDeny)
    assert refused.message == "The user rejected this action."


async def test_the_second_gate_applies_the_same_rules(tmp_path: Path) -> None:
    """A call that reached it without the hook still meets the rules."""
    link, _, _ = _link(tmp_path)

    refused = await link.can_use_tool("Bash", {"command": "ls"}, {})
    allowed = await link.can_use_tool("Write", {"file_path": "outputs/a.md"}, {})

    assert isinstance(refused, PermissionResultDeny)
    assert isinstance(allowed, PermissionResultAllow)


async def test_an_answer_for_no_waiting_request_is_refused(tmp_path: Path) -> None:
    """The route then answers 404, as opencode's does."""
    _, approvals, _ = _link(tmp_path)

    assert approvals.answer(THREAD, "perm_unknown", "once") is False


async def test_stop_refuses_every_waiting_ask(tmp_path: Path) -> None:
    """A stopped turn leaves no call waiting on a card nobody can answer."""
    link, approvals, events = _link(tmp_path)
    asking = asyncio.create_task(
        link.can_use_tool("mcp__notion__create_page", {}, {"tool_use_id": "toolu_3"})
    )
    await events.get()

    approvals.drop(THREAD)

    assert isinstance(await asking, PermissionResultDeny)
