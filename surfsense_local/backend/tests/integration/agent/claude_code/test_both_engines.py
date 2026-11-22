"""The same scenarios through opencode and Claude Code stream the same frames and read back alike.

The frontend has one renderer for both engines, so any drift between them is a
bug. Ids, step titles (never shown) and tool outputs (the Claude stand-in runs
no tool) are left out of the comparison; everything else must match.
"""

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from tests.claude_agent_stand_in import Call, Hang, Say, Step
from tests.integration.agent.claude_code.conftest import ClaudeAgent
from tests.integration.agent.claude_code.test_handover import _choose_claude
from tests.integration.agent.conftest import AgentAPI
from tests.integration.agent.test_agent_threads import open_thread, send, thread_folder
from tests.integration.agent.test_plugin_tools import connect_notes
from tests.mcp_test_server import notes_server, serving

pytestmark = pytest.mark.integration

OnFrame = Callable[[AgentAPI, int, dict], Awaitable[None]]


@dataclass(frozen=True)
class Scenario:
    """One user message, scripted for each engine's model to answer the same way."""

    text: str
    opencode: Callable[[Path], list[tuple[str, str]]]
    claude: Callable[[Path], list[Step]]
    on_frame: OnFrame | None = None


def _call(name: str, **arguments: object) -> tuple[str, str]:
    return ("call", json.dumps({"name": name, "arguments": arguments}))


async def _approve(api: AgentAPI, thread_id: int, frame: dict) -> None:
    if frame["type"] == "permission-request":
        await api.http.post(
            f"/chat/threads/{thread_id}/permissions/{frame['id']}",
            json={"reply": "once"},
        )


async def _stop(api: AgentAPI, thread_id: int, frame: dict) -> None:
    if frame["type"] == "delta":
        await api.http.post(f"/chat/threads/{thread_id}/run/stop")


async def _run(
    api: AgentAPI, thread_id: int, scenario: Scenario
) -> tuple[list[tuple], list[dict]]:
    async def on_frame(frame: dict) -> None:
        if scenario.on_frame is not None:
            await scenario.on_frame(api, thread_id, frame)

    folder = thread_folder(api.workspace_id, thread_id)
    frames = await send(api, thread_id, scenario.text, on_frame)
    listed = (await api.http.get(f"/chat/threads/{thread_id}/messages")).json()
    return _seen(frames, folder), _read_back(listed, folder)


async def _on_both(
    api: AgentAPI,
    claude_on_this_machine: Any,
    claude_agent: ClaudeAgent,
    scenario: Scenario,
) -> tuple[tuple, tuple]:
    on_opencode = await open_thread(api, mode="agentic")
    folder = thread_folder(api.workspace_id, on_opencode["id"])
    api.model.replies = scenario.opencode(folder)
    opencode = await _run(api, on_opencode["id"], scenario)
    api.model.release.set()

    await _choose_claude(api, claude_on_this_machine)
    on_claude = await open_thread(api, mode="agentic")
    folder = thread_folder(api.workspace_id, on_claude["id"])
    claude_agent.turns = [scenario.claude(folder)]
    claude = await _run(api, on_claude["id"], scenario)
    return opencode, claude


def _seen(frames: list[dict], folder: Path) -> list[tuple]:
    """What the chat shows from a turn's frames, in order.

    The chat matches an approval to its step by call id, so opencode asking a
    moment before its step moves is shown as Claude Code's step-then-ask is.
    The run's state follows the approvals in code both engines share.
    """
    seen: list[tuple] = []
    steps: set[str] = set()
    early: dict[str, tuple] = {}
    for frame in frames:
        kind = frame["type"]
        if kind == "run-state":
            continue
        if kind == "agent-step":
            # opencode announces a call before its input has streamed; nothing shows it.
            if frame["status"] != "pending":
                seen.append(_step(frame, folder))
                steps.add(frame["call_id"])
                if frame["call_id"] in early:
                    seen.append(early.pop(frame["call_id"]))
        elif kind == "permission-request" and frame["call_id"] not in steps:
            early[frame["call_id"]] = (kind, frame["permission"])
        elif kind == "delta":
            if seen and seen[-1][0] == "text":
                seen[-1] = ("text", seen[-1][1] + frame["text"])
            else:
                seen.append(("text", frame["text"]))
        elif kind == "permission-request":
            seen.append((kind, frame["permission"]))
        elif kind == "completed":
            seen.append((kind, frame["text"]))
        elif kind == "error":
            seen.append((kind, frame["kind"]))
        else:
            seen.append((kind,))
    return seen


def _read_back(listed: list[dict], folder: Path) -> list[dict]:
    return [
        {
            "role": turn["role"],
            "text": turn["content"]["text"],
            "steps": [_step(s, folder) for s in turn["content"].get("steps", [])],
            "ending": turn["content"].get("ending"),
        }
        for turn in listed
    ]


def _step(step: dict, folder: Path) -> tuple:
    given = {
        key: value.replace(str(folder), "<thread>") if isinstance(value, str) else value
        for key, value in step["input"].items()
    }
    return ("step", step["tool"], step["status"], json.dumps(given, sort_keys=True))


async def test_an_answer(
    agent_api: AgentAPI, claude_on_this_machine, claude_agent: ClaudeAgent
) -> None:
    """Streamed text and the stated reply."""
    scenario = Scenario(
        "What grew?",
        opencode=lambda _: [("text", "Q3 grew 12%.")],
        claude=lambda _: [Say("Q3 grew 12%.")],
    )

    opencode, claude = await _on_both(
        agent_api, claude_on_this_machine, claude_agent, scenario
    )

    assert claude == opencode


async def test_a_write_in_outputs_and_one_refused_outside(
    agent_api: AgentAPI, claude_on_this_machine, claude_agent: ClaudeAgent
) -> None:
    """The thread's write rules refuse the second, and the turn goes on."""
    scenario = Scenario(
        "Write it down",
        opencode=lambda folder: [
            _call("write", path=str(folder / "outputs/a.md"), content="A"),
            _call("write", path=str(folder / "notes.md"), content="B"),
            ("text", "Wrote it."),
        ],
        claude=lambda folder: [
            Call("Write", {"file_path": str(folder / "outputs/a.md"), "content": "A"}),
            Call("Write", {"file_path": str(folder / "notes.md"), "content": "B"}),
            Say("Wrote it."),
        ],
    )

    opencode, claude = await _on_both(
        agent_api, claude_on_this_machine, claude_agent, scenario
    )

    assert claude == opencode


async def test_a_plugin_call_the_user_allows(
    agent_api: AgentAPI, claude_on_this_machine, claude_agent: ClaudeAgent
) -> None:
    """A tool that says nothing of itself may destroy, so both engines ask first."""
    scenario = Scenario(
        "Count",
        opencode=lambda _: [_call("notes_count", text="a b c"), ("text", "Three.")],
        claude=lambda _: [
            Call("mcp__notes__count", {"text": "a b c"}, '{"words": 3}'),
            Say("Three."),
        ],
        on_frame=_approve,
    )
    with serving(notes_server().streamable_http_app()) as base:
        await connect_notes(agent_api, f"{base}/mcp")

        opencode, claude = await _on_both(
            agent_api, claude_on_this_machine, claude_agent, scenario
        )

    assert claude == opencode


async def test_stop_mid_reply(
    agent_api: AgentAPI, claude_on_this_machine, claude_agent: ClaudeAgent
) -> None:
    """The reply keeps what streamed and reads back stopped."""
    scenario = Scenario(
        "Think it over",
        opencode=lambda _: [("stall", "Thinking about")],
        claude=lambda _: [Hang("Thinking about")],
        on_frame=_stop,
    )

    opencode, claude = await _on_both(
        agent_api, claude_on_this_machine, claude_agent, scenario
    )

    assert claude == opencode
