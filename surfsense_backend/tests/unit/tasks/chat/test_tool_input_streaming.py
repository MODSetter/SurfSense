"""Unit tests for live tool-call argument streaming.

Pins the wire format that ``_stream_agent_events`` emits when
``SURFSENSE_ENABLE_STREAM_PARITY_V2=true``: ``tool-input-start`` →
``tool-input-delta``... → ``tool-input-available`` → ``tool-output-available``
all keyed by the same LangChain ``tool_call.id``.

Identity is tracked in ``index_to_meta`` (per-chunk ``index``) and
``ui_tool_call_id_by_run`` (LangGraph ``run_id``); both are private to
``_stream_agent_events`` so we exercise them via the public wire output.

These tests also lock in the legacy / parity_v2-OFF behaviour so the
synthetic ``call_<run_id>`` shape stays stable for older clients.
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any

import pytest

import app.tasks.chat.stream_new_chat as stream_module
from app.agents.new_chat.feature_flags import AgentFeatureFlags
from app.services.new_streaming_service import VercelStreamingService
from app.tasks.chat.stream_new_chat import (
    StreamResult,
    _legacy_match_lc_id,
    _stream_agent_events,
)

pytestmark = pytest.mark.unit


@dataclass
class _FakeChunk:
    """Minimal stand-in for ``AIMessageChunk``."""

    content: Any = ""
    additional_kwargs: dict[str, Any] = field(default_factory=dict)
    tool_call_chunks: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class _FakeToolMessage:
    """Stand-in for ``ToolMessage`` returned by ``on_tool_end``."""

    content: Any
    tool_call_id: str | None = None


@dataclass
class _FakeInterrupt:
    value: dict[str, Any]


@dataclass
class _FakeTask:
    interrupts: tuple[_FakeInterrupt, ...] = ()


class _FakeAgentState:
    """Stand-in for ``StateSnapshot`` returned by ``aget_state``."""

    def __init__(self, tasks: list[Any] | None = None) -> None:
        # Empty values keeps the cloud-fallback safety-net branch a no-op,
        # and empty ``tasks`` keep the post-stream interrupt check a no-op too.
        self.values: dict[str, Any] = {}
        self.tasks: list[Any] = tasks or []


class _FakeAgent:
    """Replays a list of ``astream_events`` events."""

    def __init__(
        self, events: list[dict[str, Any]], state: _FakeAgentState | None = None
    ) -> None:
        self._events = events
        self._state = state or _FakeAgentState()

    async def astream_events(  # type: ignore[no-untyped-def]
        self, _input_data: Any, *, config: dict[str, Any], version: str
    ) -> AsyncGenerator[dict[str, Any], None]:
        del config, version  # unused, contract-compatible
        for ev in self._events:
            yield ev

    async def aget_state(self, _config: dict[str, Any]) -> _FakeAgentState:
        # Called once after astream_events drains so the cloud-fallback
        # safety net can inspect staged filesystem work. The fake stays
        # empty so the safety net is a no-op.
        return self._state


def _model_stream(
    *,
    text: str = "",
    reasoning: str = "",
    tool_call_chunks: list[dict[str, Any]] | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    return (
        {
            "event": "on_chat_model_stream",
            "tags": tags or [],
            "data": {
                "chunk": _FakeChunk(
                    content=text,
                    tool_call_chunks=list(tool_call_chunks or []),
                )
            },
            # reasoning piggybacks via additional_kwargs path; if needed,
            # override content to a typed-block list. Most tests just check
            # tool_call_chunks routing so this is fine.
        }
        if not reasoning
        else {
            "event": "on_chat_model_stream",
            "tags": tags or [],
            "data": {
                "chunk": _FakeChunk(
                    content=text,
                    additional_kwargs={"reasoning_content": reasoning},
                    tool_call_chunks=list(tool_call_chunks or []),
                )
            },
        }
    )


def _tool_start(
    *,
    name: str,
    run_id: str,
    input_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "event": "on_tool_start",
        "name": name,
        "run_id": run_id,
        "data": {"input": input_payload or {}},
    }


def _tool_end(
    *,
    name: str,
    run_id: str,
    tool_call_id: str | None = None,
    output: Any = "ok",
) -> dict[str, Any]:
    return {
        "event": "on_tool_end",
        "name": name,
        "run_id": run_id,
        "data": {
            "output": _FakeToolMessage(
                content=json.dumps(output) if not isinstance(output, str) else output,
                tool_call_id=tool_call_id,
            )
        },
    }


@pytest.fixture
def parity_v2_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        stream_module,
        "get_flags",
        lambda: AgentFeatureFlags(enable_stream_parity_v2=True),
    )


@pytest.fixture
def parity_v2_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        stream_module,
        "get_flags",
        lambda: AgentFeatureFlags(enable_stream_parity_v2=False),
    )


async def _drain(
    events: list[dict[str, Any]], state: _FakeAgentState | None = None
) -> list[dict[str, Any]]:
    """Run ``_stream_agent_events`` against a fake agent and return the
    SSE payloads (parsed JSON) it yielded.
    """
    agent = _FakeAgent(events, state=state)
    service = VercelStreamingService()
    result = StreamResult()
    config = {"configurable": {"thread_id": "test-thread"}}
    sse_lines: list[str] = []
    async for sse in _stream_agent_events(
        agent, config, {}, service, result, step_prefix="thinking"
    ):
        sse_lines.append(sse)

    parsed: list[dict[str, Any]] = []
    for line in sse_lines:
        if not line.startswith("data: "):
            continue
        body = line[len("data: ") :].rstrip("\n")
        if not body or body == "[DONE]":
            continue
        try:
            parsed.append(json.loads(body))
        except json.JSONDecodeError:
            continue
    return parsed


def _types(payloads: list[dict[str, Any]]) -> list[str]:
    return [p.get("type", "?") for p in payloads]


def _of_type(payloads: list[dict[str, Any]], type_name: str) -> list[dict[str, Any]]:
    return [p for p in payloads if p.get("type") == type_name]


# ---------------------------------------------------------------------------
# Helper: ``_legacy_match_lc_id`` is a pure refactor; assert behaviour.
# ---------------------------------------------------------------------------


class TestLegacyMatch:
    def test_pops_first_id_bearing_chunk_with_matching_name(self) -> None:
        chunks: list[dict[str, Any]] = [
            {"id": "x1", "name": "ls"},
            {"id": "y1", "name": "write_file"},
        ]
        runs: dict[str, str] = {}
        result = _legacy_match_lc_id(chunks, "write_file", "run-1", runs)
        assert result == "y1"
        assert chunks == [{"id": "x1", "name": "ls"}]
        assert runs == {"run-1": "y1"}

    def test_falls_back_to_any_id_bearing_when_name_mismatches(self) -> None:
        chunks: list[dict[str, Any]] = [{"id": "anon", "name": None}]
        runs: dict[str, str] = {}
        out = _legacy_match_lc_id(chunks, "ls", "run-2", runs)
        assert out == "anon"
        assert chunks == []

    def test_returns_none_when_no_id_bearing_chunk(self) -> None:
        chunks: list[dict[str, Any]] = [{"id": None, "name": None}]
        runs: dict[str, str] = {}
        assert _legacy_match_lc_id(chunks, "ls", "run-3", runs) is None
        assert chunks == [{"id": None, "name": None}]
        assert runs == {}


# ---------------------------------------------------------------------------
# parity_v2 wire format tests.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_idless_chunk_merging_by_index(parity_v2_on: None) -> None:
    """First chunk carries id+name; later idless chunks at the same
    ``index`` merge into the SAME ``tool-input-start`` ui id and emit
    one ``tool-input-delta`` per chunk."""
    events = [
        _model_stream(
            tool_call_chunks=[
                {"id": "lc-1", "name": "write_file", "args": '{"file', "index": 0}
            ],
        ),
        _model_stream(
            tool_call_chunks=[
                {"id": None, "name": None, "args": '_path":"/x"}', "index": 0}
            ],
        ),
        _tool_start(
            name="write_file", run_id="run-A", input_payload={"file_path": "/x"}
        ),
        _tool_end(name="write_file", run_id="run-A", tool_call_id="lc-1"),
    ]

    payloads = await _drain(events)

    starts = _of_type(payloads, "tool-input-start")
    deltas = _of_type(payloads, "tool-input-delta")
    available = _of_type(payloads, "tool-input-available")
    output = _of_type(payloads, "tool-output-available")

    assert len(starts) == 1
    assert starts[0]["toolCallId"] == "lc-1"
    assert starts[0]["toolName"] == "write_file"
    assert starts[0]["langchainToolCallId"] == "lc-1"

    assert [d["inputTextDelta"] for d in deltas] == ['{"file', '_path":"/x"}']
    assert all(d["toolCallId"] == "lc-1" for d in deltas)

    assert len(available) == 1
    assert available[0]["toolCallId"] == "lc-1"

    assert len(output) == 1
    assert output[0]["toolCallId"] == "lc-1"


@pytest.mark.asyncio
async def test_two_interleaved_tool_calls_route_by_index(
    parity_v2_on: None,
) -> None:
    """Two same-name calls with distinct indices keep their deltas
    routed to the right card."""
    events = [
        _model_stream(
            tool_call_chunks=[
                {"id": "lc-A", "name": "write_file", "args": '{"a":1', "index": 0},
                {"id": "lc-B", "name": "write_file", "args": '{"b":2', "index": 1},
            ]
        ),
        _model_stream(
            tool_call_chunks=[
                {"id": None, "name": None, "args": "}", "index": 0},
                {"id": None, "name": None, "args": "}", "index": 1},
            ]
        ),
        _tool_start(name="write_file", run_id="run-A", input_payload={"a": 1}),
        _tool_end(name="write_file", run_id="run-A", tool_call_id="lc-A"),
        _tool_start(name="write_file", run_id="run-B", input_payload={"b": 2}),
        _tool_end(name="write_file", run_id="run-B", tool_call_id="lc-B"),
    ]

    payloads = await _drain(events)

    starts = _of_type(payloads, "tool-input-start")
    deltas = _of_type(payloads, "tool-input-delta")
    output = _of_type(payloads, "tool-output-available")

    assert {s["toolCallId"] for s in starts} == {"lc-A", "lc-B"}

    by_id: dict[str, list[str]] = {"lc-A": [], "lc-B": []}
    for d in deltas:
        by_id[d["toolCallId"]].append(d["inputTextDelta"])
    assert by_id["lc-A"] == ['{"a":1', "}"]
    assert by_id["lc-B"] == ['{"b":2', "}"]

    assert {o["toolCallId"] for o in output} == {"lc-A", "lc-B"}


@pytest.mark.asyncio
async def test_identity_stable_across_lifecycle(parity_v2_on: None) -> None:
    """Whatever id ``tool-input-start`` chose must be the SAME id used
    on ``tool-input-available`` AND ``tool-output-available``."""
    events = [
        _model_stream(
            tool_call_chunks=[
                {"id": "lc-9", "name": "ls", "args": '{"path":"/"}', "index": 0}
            ]
        ),
        _tool_start(name="ls", run_id="run-X", input_payload={"path": "/"}),
        _tool_end(name="ls", run_id="run-X", tool_call_id="lc-9"),
    ]
    payloads = await _drain(events)
    relevant = [
        p
        for p in payloads
        if p.get("type")
        in {"tool-input-start", "tool-input-available", "tool-output-available"}
    ]
    assert {p["toolCallId"] for p in relevant} == {"lc-9"}


@pytest.mark.asyncio
async def test_no_duplicate_tool_input_start(parity_v2_on: None) -> None:
    """When the chunk-emission loop already fired ``tool-input-start``
    for this run, ``on_tool_start`` MUST NOT emit a second one."""
    events = [
        _model_stream(
            tool_call_chunks=[
                {"id": "lc-1", "name": "write_file", "args": "{}", "index": 0}
            ]
        ),
        _tool_start(name="write_file", run_id="run-A", input_payload={}),
        _tool_end(name="write_file", run_id="run-A", tool_call_id="lc-1"),
    ]
    payloads = await _drain(events)
    starts = _of_type(payloads, "tool-input-start")
    assert len(starts) == 1
    assert starts[0]["toolCallId"] == "lc-1"


@pytest.mark.asyncio
async def test_active_text_closes_before_early_tool_input_start(
    parity_v2_on: None,
) -> None:
    """Streaming a text-delta then a tool-call chunk in subsequent
    chunks: the wire MUST contain ``text-end`` before the FIRST
    ``tool-input-start`` (clean part boundary on the frontend)."""
    events = [
        _model_stream(text="Working on it"),
        _model_stream(
            tool_call_chunks=[
                {"id": "lc-1", "name": "write_file", "args": "{}", "index": 0}
            ]
        ),
        _tool_start(name="write_file", run_id="run-A", input_payload={}),
        _tool_end(name="write_file", run_id="run-A", tool_call_id="lc-1"),
    ]
    types = _types(await _drain(events))
    text_end_idx = types.index("text-end")
    start_idx = types.index("tool-input-start")
    assert text_end_idx < start_idx


@pytest.mark.asyncio
async def test_mixed_text_and_tool_chunk_preserve_order(
    parity_v2_on: None,
) -> None:
    """One AIMessageChunk that carries BOTH ``text`` content AND
    ``tool_call_chunks`` should emit the text delta FIRST, then close
    text, then ``tool-input-start``+``tool-input-delta``."""
    events = [
        _model_stream(
            text="I'll update it",
            tool_call_chunks=[
                {
                    "id": "lc-1",
                    "name": "write_file",
                    "args": '{"file_path":"/x"}',
                    "index": 0,
                }
            ],
        ),
        _tool_start(
            name="write_file", run_id="run-A", input_payload={"file_path": "/x"}
        ),
        _tool_end(name="write_file", run_id="run-A", tool_call_id="lc-1"),
    ]
    types = _types(await _drain(events))
    # text-start … text-delta … text-end … tool-input-start … tool-input-delta
    assert types.index("text-start") < types.index("text-delta")
    assert types.index("text-delta") < types.index("text-end")
    assert types.index("text-end") < types.index("tool-input-start")
    assert types.index("tool-input-start") < types.index("tool-input-delta")


@pytest.mark.asyncio
async def test_parity_v2_off_preserves_legacy_shape(
    parity_v2_off: None,
) -> None:
    """When the flag is OFF, no deltas are emitted and the ``toolCallId``
    is ``call_<run_id>`` (NOT the lc id)."""
    events = [
        _model_stream(
            tool_call_chunks=[
                {"id": "lc-1", "name": "ls", "args": '{"path":"/"}', "index": 0}
            ]
        ),
        _tool_start(name="ls", run_id="run-A", input_payload={"path": "/"}),
        _tool_end(name="ls", run_id="run-A", tool_call_id="lc-1"),
    ]
    payloads = await _drain(events)

    assert _of_type(payloads, "tool-input-delta") == []
    starts = _of_type(payloads, "tool-input-start")
    assert len(starts) == 1
    assert starts[0]["toolCallId"].startswith("call_run-A")
    # No ``langchainToolCallId`` propagation on ``tool-input-start`` in
    # legacy mode (the start event fires before the ToolMessage is
    # available, so we can't extract the authoritative LangChain id yet).
    assert "langchainToolCallId" not in starts[0]
    output = _of_type(payloads, "tool-output-available")
    assert output[0]["toolCallId"].startswith("call_run-A")
    # ``tool-output-available`` MUST carry ``langchainToolCallId`` even
    # in legacy mode: the chat tool card uses it to backfill the
    # LangChain id and join against the ``data-action-log`` SSE event
    # (keyed by ``lc_tool_call_id``) so the inline Revert button can
    # light up. Sourced from the returned ``ToolMessage.tool_call_id``,
    # which is populated regardless of feature-flag state.
    assert output[0]["langchainToolCallId"] == "lc-1"


@pytest.mark.asyncio
async def test_skip_append_prevents_stale_id_reuse(
    parity_v2_on: None,
) -> None:
    """Two same-name tools: the SECOND tool's ``langchainToolCallId``
    must NOT come from the first tool's chunk (``pending_tool_call_chunks``
    must stay empty for indexed-registered chunks)."""
    events = [
        _model_stream(
            tool_call_chunks=[
                {"id": "lc-A", "name": "write_file", "args": "{}", "index": 0},
                {"id": "lc-B", "name": "write_file", "args": "{}", "index": 1},
            ]
        ),
        _tool_start(name="write_file", run_id="run-1", input_payload={}),
        _tool_end(name="write_file", run_id="run-1", tool_call_id="lc-A"),
        _tool_start(name="write_file", run_id="run-2", input_payload={}),
        _tool_end(name="write_file", run_id="run-2", tool_call_id="lc-B"),
    ]
    payloads = await _drain(events)

    starts = _of_type(payloads, "tool-input-start")
    # Two distinct lc ids, each its own card.
    assert {s["toolCallId"] for s in starts} == {"lc-A", "lc-B"}
    # Each tool-output-available landed on its respective card.
    output = _of_type(payloads, "tool-output-available")
    assert {o["toolCallId"] for o in output} == {"lc-A", "lc-B"}


@pytest.mark.asyncio
async def test_registration_waits_for_both_id_and_name(
    parity_v2_on: None,
) -> None:
    """An id-only chunk (no name yet) must NOT emit ``tool-input-start``."""
    events = [
        _model_stream(
            tool_call_chunks=[{"id": "lc-1", "name": None, "args": "", "index": 0}]
        ),
    ]
    payloads = await _drain(events)
    assert _of_type(payloads, "tool-input-start") == []


@pytest.mark.asyncio
async def test_unmatched_fallback_still_attaches_lc_id(
    parity_v2_on: None,
) -> None:
    """parity_v2 ON, but the provider didn't include an ``index``: the
    legacy fallback path must still emit ``tool-input-start`` with the
    matching ``langchainToolCallId``."""
    events = [
        # No index on the chunk → not registered into index_to_meta;
        # falls through to ``pending_tool_call_chunks`` so the legacy
        # match path can pop it at on_tool_start.
        _model_stream(tool_call_chunks=[{"id": "lc-orphan", "name": "ls", "args": ""}]),
        _tool_start(name="ls", run_id="run-1", input_payload={"path": "/"}),
        _tool_end(name="ls", run_id="run-1", tool_call_id="lc-orphan"),
    ]
    payloads = await _drain(events)
    starts = _of_type(payloads, "tool-input-start")
    assert len(starts) == 1
    assert starts[0]["toolCallId"].startswith("call_run-1")
    assert starts[0]["langchainToolCallId"] == "lc-orphan"


@pytest.mark.asyncio
async def test_interrupt_request_uses_task_that_contains_interrupt(
    parity_v2_on: None,
) -> None:
    interrupt_payload = {
        "type": "calendar_event_create",
        "action": {
            "tool": "create_calendar_event",
            "params": {"summary": "mom bday"},
        },
        "context": {},
    }
    state = _FakeAgentState(
        tasks=[
            _FakeTask(interrupts=()),
            _FakeTask(interrupts=(_FakeInterrupt(value=interrupt_payload),)),
        ]
    )

    payloads = await _drain([], state=state)

    interrupts = _of_type(payloads, "data-interrupt-request")
    assert len(interrupts) == 1
    assert (
        interrupts[0]["data"]["action_requests"][0]["name"] == "create_calendar_event"
    )
