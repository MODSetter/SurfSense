"""Pin that sub-agent emitter reaches every wire event the relay emits."""

from __future__ import annotations

import json

import pytest

from app.services.streaming.emitter import subagent_emitter
from app.services.streaming.service import StreamingService

pytestmark = pytest.mark.unit


def _decode(frame: str) -> dict:
    body = frame.removeprefix("data: ").removesuffix("\n\n")
    return json.loads(body)


@pytest.fixture
def service() -> StreamingService:
    return StreamingService()


@pytest.fixture
def sub_emitter():
    return subagent_emitter(
        subagent_type="deliverables",
        subagent_run_id="sub_xyz",
        parent_tool_call_id="call_parent",
    )


def test_text_delta_carries_subagent_emitter_on_the_wire(service, sub_emitter) -> None:
    payload = _decode(service.format_text_delta("text_1", "hi", emitter=sub_emitter))
    assert payload["emitted_by"]["subagent_run_id"] == "sub_xyz"
    assert payload["delta"] == "hi"


def test_reasoning_delta_carries_subagent_emitter_on_the_wire(
    service, sub_emitter
) -> None:
    payload = _decode(
        service.format_reasoning_delta("r_1", "thinking", emitter=sub_emitter)
    )
    assert payload["emitted_by"]["subagent_run_id"] == "sub_xyz"


def test_tool_input_start_carries_subagent_emitter_and_lc_id(
    service, sub_emitter
) -> None:
    payload = _decode(
        service.format_tool_input_start(
            "call_1",
            "send_email",
            langchain_tool_call_id="lc_1",
            emitter=sub_emitter,
        )
    )
    assert payload["emitted_by"]["subagent_type"] == "deliverables"
    assert payload["langchainToolCallId"] == "lc_1"
    assert payload["toolName"] == "send_email"


def test_tool_output_available_carries_subagent_emitter(service, sub_emitter) -> None:
    payload = _decode(
        service.format_tool_output_available(
            "call_1", {"ok": True}, emitter=sub_emitter
        )
    )
    assert payload["emitted_by"]["subagent_run_id"] == "sub_xyz"
    assert payload["output"] == {"ok": True}


def test_thinking_step_carries_subagent_emitter(service, sub_emitter) -> None:
    payload = _decode(
        service.format_thinking_step(
            step_id="s1",
            title="Sending email",
            status="in_progress",
            emitter=sub_emitter,
        )
    )
    assert payload["type"] == "data-thinking-step"
    assert payload["emitted_by"]["subagent_run_id"] == "sub_xyz"


def test_action_log_carries_subagent_emitter(service, sub_emitter) -> None:
    payload = _decode(
        service.format_action_log(
            {"id": 1, "tool_name": "send_email", "reversible": False},
            emitter=sub_emitter,
        )
    )
    assert payload["emitted_by"]["subagent_run_id"] == "sub_xyz"
    assert payload["data"]["tool_name"] == "send_email"


def test_subagent_lifecycle_events_share_run_id_for_pairing(
    service, sub_emitter
) -> None:
    start = _decode(
        service.format_subagent_start(
            subagent_run_id="sub_xyz",
            subagent_type="deliverables",
            parent_tool_call_id="call_parent",
            emitter=sub_emitter,
        )
    )
    finish = _decode(
        service.format_subagent_finish(
            subagent_run_id="sub_xyz",
            subagent_type="deliverables",
            parent_tool_call_id="call_parent",
            emitter=sub_emitter,
        )
    )
    assert start["data"]["subagent_run_id"] == finish["data"]["subagent_run_id"]
    assert start["type"] == "data-subagent-start"
    assert finish["type"] == "data-subagent-finish"


def test_main_emitter_events_omit_emitted_by_field(service) -> None:
    payload = _decode(service.format_text_delta("text_1", "hi"))
    assert "emitted_by" not in payload


def test_resolve_emitter_through_service_uses_registry(service, sub_emitter) -> None:
    service.emitter_registry.register("run_task_1", sub_emitter)
    resolved = service.resolve_emitter(
        run_id="run_chat_model",
        parent_ids=["root", "run_task_1"],
    )
    assert resolved is sub_emitter


def test_message_id_is_assigned_on_message_start_and_reused(service) -> None:
    frame = service.format_message_start()
    payload = _decode(frame)
    assigned = payload["messageId"]
    assert assigned.startswith("msg_")
    assert service.message_id == assigned
