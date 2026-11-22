"""A thread that switched engines reads back from both, even while the one it left cannot answer."""

from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException, status

from modules.agent.engines.both_sessions import stored_step_of, thread_turns_of
from modules.chat.models import AgentEngineKind

pytestmark = pytest.mark.unit
# A thread now on Claude Code that ran on opencode before.
THREAD = SimpleNamespace(id=7, agent_engine=AgentEngineKind.CLAUDE_CODE)


class _Engine:
    """An engine holding a session of the thread, answering or refusing as told."""

    def __init__(
        self,
        kind: AgentEngineKind,
        turns: list[dict[str, Any]] | None = None,
        steps: dict[str, dict[str, Any]] | None = None,
        refusal: int | None = None,
    ) -> None:
        self.kind = kind
        self._turns = turns or []
        self._steps = steps or {}
        self._refusal = refusal

    def has_session(self, thread: object) -> bool:
        return True

    async def thread_messages(self, *_args: object) -> list[dict[str, Any]]:
        self._refuse()
        return self._turns

    async def stored_step(self, _session: object, _thread: object, part_id: str):
        self._refuse()
        if part_id not in self._steps:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "no such step")
        return self._steps[part_id]

    def _refuse(self) -> None:
        if self._refusal is not None:
            raise HTTPException(self._refusal, "not answering")


def _turn(role: str, text: str, at: str = "2026-10-17T09:00:00Z") -> dict[str, Any]:
    return {"role": role, "content": {"text": text}, "created_at": at}


async def test_the_engine_left_behind_not_answering_still_reads_the_thread() -> None:
    """opencode not running must not hide the turns the engine running the thread holds."""
    left = _Engine(AgentEngineKind.OPENCODE, refusal=503)
    current = _Engine(
        AgentEngineKind.CLAUDE_CODE,
        [_turn("user", "Second"), _turn("assistant", "Two.")],
    )

    turns = await thread_turns_of(None, THREAD, "key", False, [left, current])

    assert [t["content"]["text"] for t in turns] == ["Second", "Two."]


async def test_turns_in_the_same_second_read_back_in_the_order_they_were_sent() -> None:
    """A time on a whole second is spelled without its fraction, which must not sort it later."""
    current = _Engine(
        AgentEngineKind.CLAUDE_CODE,
        [
            _turn("user", "First", "2026-10-17T09:00:05Z"),
            _turn("assistant", "One.", "2026-10-17T09:00:05Z"),
            _turn("user", "Second", "2026-10-17T09:00:05.015000Z"),
            _turn("assistant", "Two.", "2026-10-17T09:00:05.015000Z"),
        ],
    )

    turns = await thread_turns_of(None, THREAD, "key", False, [current])

    assert [t["content"]["text"] for t in turns] == ["First", "One.", "Second", "Two."]


async def test_the_engine_running_the_thread_not_answering_is_said() -> None:
    """Its turns are the thread's latest: reading without them would show a stale thread."""
    left = _Engine(AgentEngineKind.OPENCODE, [_turn("user", "First")])
    current = _Engine(AgentEngineKind.CLAUDE_CODE, refusal=503)

    with pytest.raises(HTTPException) as refused:
        await thread_turns_of(None, THREAD, "key", False, [left, current])

    assert refused.value.status_code == 503


async def test_a_step_is_found_past_the_engine_left_behind_not_answering() -> None:
    """Save to Sources on a step of the engine running the thread, while the other cannot answer."""
    left = _Engine(AgentEngineKind.OPENCODE, refusal=502)
    current = _Engine(
        AgentEngineKind.CLAUDE_CODE, steps={"prt_1": {"id": "prt_1", "type": "tool"}}
    )

    step = await stored_step_of(None, THREAD, "prt_1", [left, current])

    assert step["id"] == "prt_1"
