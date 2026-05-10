"""Pin Stage 1 extractions as faithful copies of the old helpers.

Extractions under ``app.tasks.chat.streaming`` are compared to
``app.tasks.chat.stream_new_chat`` helpers.
For each Stage 1 extraction we assert the new function returns the same
output as the old one for a representative input set. The moment the
two diverge - intentionally or otherwise - this file fails loudly so
the divergence is reviewed rather than shipped silently.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import pytest

from app.agents.new_chat.errors import BusyError
from app.agents.new_chat.middleware.busy_mutex import request_cancel, reset_cancel
from app.tasks.chat.stream_new_chat import (
    _classify_stream_exception as old_classify,
    _emit_stream_terminal_error as old_emit_terminal_error,
    _extract_chunk_parts as old_extract_chunk_parts,
    _extract_resolved_file_path as old_extract_resolved_file_path,
    _first_interrupt_value as old_first_interrupt_value,
    _tool_output_has_error as old_tool_output_has_error,
    _tool_output_to_text as old_tool_output_to_text,
)
from app.tasks.chat.streaming.errors.classifier import (
    classify_stream_exception as new_classify,
)
from app.tasks.chat.streaming.errors.emitter import (
    emit_stream_terminal_error as new_emit_terminal_error,
)
from app.tasks.chat.streaming.helpers.chunk_parts import (
    extract_chunk_parts as new_extract_chunk_parts,
)
from app.tasks.chat.streaming.helpers.interrupt_inspector import (
    first_interrupt_value as new_first_interrupt_value,
)
from app.tasks.chat.streaming.helpers.tool_output import (
    extract_resolved_file_path as new_extract_resolved_file_path,
    tool_output_has_error as new_tool_output_has_error,
    tool_output_to_text as new_tool_output_to_text,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------- chunk parts


@dataclass
class _Chunk:
    content: Any = ""
    additional_kwargs: dict[str, Any] = field(default_factory=dict)
    tool_call_chunks: list[dict[str, Any]] = field(default_factory=list)


_CHUNK_CASES: list[Any] = [
    None,
    _Chunk(content=""),
    _Chunk(content="hello"),
    _Chunk(content=42),  # invalid type, defensively coerced to empty
    _Chunk(
        content=[
            {"type": "text", "text": "Hello "},
            {"type": "text", "text": "world"},
        ]
    ),
    _Chunk(
        content=[
            {"type": "reasoning", "reasoning": "hmm "},
            {"type": "reasoning", "text": "still"},
            {"type": "text", "text": "answer"},
        ]
    ),
    _Chunk(
        content=[
            {"type": "tool_call_chunk", "id": "c1", "name": "x", "args": "{"},
            {"type": "tool_use", "id": "c2", "name": "y"},
            {"type": "image_url", "url": "ignored"},
        ]
    ),
    _Chunk(
        content="visible",
        additional_kwargs={"reasoning_content": "private"},
    ),
    _Chunk(
        tool_call_chunks=[
            {"id": None, "name": None, "args": '{"a":1}', "index": 0},
            {"id": "c", "name": "n", "args": "}", "index": 0},
        ]
    ),
    _Chunk(
        content=[{"type": "tool_call_chunk", "id": "from-block", "name": "x"}],
        tool_call_chunks=[{"id": "from-attr", "name": "y"}],
    ),
]


@pytest.mark.parametrize("chunk", _CHUNK_CASES)
def test_extract_chunk_parts_matches_old_implementation(chunk: Any) -> None:
    assert new_extract_chunk_parts(chunk) == old_extract_chunk_parts(chunk)


# ---------------------------------------------------------- interrupt inspector


@dataclass
class _Interrupt:
    value: dict[str, Any]


@dataclass
class _Task:
    interrupts: tuple[Any, ...] = ()


@dataclass
class _State:
    tasks: tuple[Any, ...] = ()
    interrupts: tuple[Any, ...] = ()


_INTERRUPT_CASES: list[Any] = [
    _State(),
    _State(tasks=(_Task(interrupts=(_Interrupt(value={"name": "send"}),)),)),
    # Multiple tasks: must return the FIRST one in iteration order.
    _State(
        tasks=(
            _Task(interrupts=(_Interrupt(value={"name": "first"}),)),
            _Task(interrupts=(_Interrupt(value={"name": "second"}),)),
        )
    ),
    # Empty task interrupts -> falls back to root state.interrupts.
    _State(
        tasks=(_Task(interrupts=()),),
        interrupts=(_Interrupt(value={"name": "root"}),),
    ),
    # Interrupts as plain dicts (not wrapper objects).
    _State(interrupts=({"value": {"name": "dict_root"}},)),
    # A defective task whose `.interrupts` raises - must be tolerated.
    _State(tasks=(object(),)),
]


@pytest.mark.parametrize("state", _INTERRUPT_CASES)
def test_first_interrupt_value_matches_old_implementation(state: Any) -> None:
    assert new_first_interrupt_value(state) == old_first_interrupt_value(state)


# ----------------------------------------------------------- error classifier


def _classify_cases() -> list[Exception]:
    """Inputs that the FE depends on being mapped to specific error codes."""
    return [
        Exception("totally generic error"),
        Exception('{"error":{"type":"rate_limit_error","message":"slow down"}}'),
        Exception(
            'OpenrouterException - {"error":{"message":"Provider returned error",'
            '"code":429}}'
        ),
        BusyError(request_id="thread-busy-parity"),
        Exception("Thread is busy with another request"),
    ]


@pytest.mark.parametrize("exc", _classify_cases())
def test_classify_stream_exception_matches_old_implementation(
    exc: Exception,
) -> None:
    new = new_classify(exc, flow_label="parity-test")
    old = old_classify(exc, flow_label="parity-test")
    # Strip the wall-clock retry timestamp before comparing — both
    # implementations call ``time.time()`` independently and the call
    # order is enough to differ by 1 ms in practice. Every other field
    # in the tuple must match exactly.
    new_extra = dict(new[5]) if isinstance(new[5], dict) else new[5]
    old_extra = dict(old[5]) if isinstance(old[5], dict) else old[5]
    if isinstance(new_extra, dict) and isinstance(old_extra, dict):
        new_extra.pop("retry_after_at", None)
        old_extra.pop("retry_after_at", None)
    assert new[:5] == old[:5]
    assert new_extra == old_extra


def test_classify_turn_cancelling_branch_parity() -> None:
    """The TURN_CANCELLING branch reads cancel state for the busy thread id;
    both implementations must agree on retry-window semantics, not just the
    plain THREAD_BUSY code."""
    thread_id = "parity-cancelling-thread"
    reset_cancel(thread_id)
    request_cancel(thread_id)
    exc = BusyError(request_id=thread_id)
    new = new_classify(exc, flow_label="parity-test")
    old = old_classify(exc, flow_label="parity-test")
    assert new[0] == old[0] == "thread_busy"
    assert new[1] == old[1] == "TURN_CANCELLING"
    assert isinstance(new[5], dict) and isinstance(old[5], dict)
    assert new[5]["retry_after_ms"] == old[5]["retry_after_ms"]


# ------------------------------------------------------------ terminal emitter


class _FakeStreamingService:
    """Duck-types ``format_error`` for both old and new emitters."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def format_error(
        self, message: str, *, error_code: str, extra: dict[str, Any] | None = None
    ) -> str:
        self.calls.append(
            {"message": message, "error_code": error_code, "extra": extra}
        )
        return f'data: {{"type":"error","errorText":"{message}"}}\n\n'


def test_emit_stream_terminal_error_matches_old_output_and_logs(caplog) -> None:
    """The new emitter must produce the same SSE frame and log the same
    structured payload as the old one for the same arguments."""
    args: dict[str, Any] = {
        "flow": "new",
        "request_id": "req-parity",
        "thread_id": 7,
        "search_space_id": 9,
        "user_id": "user-parity",
        "message": "boom",
        "error_kind": "server_error",
        "error_code": "SERVER_ERROR",
        "severity": "error",
        "is_expected": False,
        "extra": {"foo": "bar"},
    }

    new_svc = _FakeStreamingService()
    old_svc = _FakeStreamingService()

    with caplog.at_level(logging.ERROR):
        new_frame = new_emit_terminal_error(streaming_service=new_svc, **args)
        old_frame = old_emit_terminal_error(streaming_service=old_svc, **args)

    assert new_frame == old_frame
    assert new_svc.calls == old_svc.calls
    chat_error_records = [
        r for r in caplog.records if "[chat_stream_error]" in r.message
    ]
    # One log line per emit call (two emits -> two records).
    assert len(chat_error_records) == 2


# ---------------------------------------------------------------- tool output


def test_tool_output_helpers_match_old_implementation() -> None:
    samples: list[Any] = [
        {"result": "ok"},
        {"error": "bad"},
        {"result": "Error: x"},
        "Error: plain",
        "fine",
        {"nested": {"a": 1}},
    ]
    for s in samples:
        assert new_tool_output_to_text(s) == old_tool_output_to_text(s)
        assert new_tool_output_has_error(s) == old_tool_output_has_error(s)

    assert new_extract_resolved_file_path(
        tool_name="write_file",
        tool_output={"path": " /tmp/x "},
        tool_input=None,
    ) == old_extract_resolved_file_path(
        tool_name="write_file",
        tool_output={"path": " /tmp/x "},
        tool_input=None,
    )
    assert new_extract_resolved_file_path(
        tool_name="write_file",
        tool_output={},
        tool_input={"file_path": " /fallback "},
    ) == old_extract_resolved_file_path(
        tool_name="write_file",
        tool_output={},
        tool_input={"file_path": " /fallback "},
    )
