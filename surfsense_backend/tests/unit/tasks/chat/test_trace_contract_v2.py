from __future__ import annotations

import json

from app.services.new_streaming_service import VercelStreamingService
from app.tasks.chat.content_builder import AssistantContentBuilder
from app.tasks.chat.streaming.flows.shared.first_frames import iter_initial_frames
from app.tasks.chat.streaming.handlers.tool_start import _artifact_skill_name


def _payload(frame: str) -> dict:
    return json.loads(frame.removeprefix("data: ").strip())


def test_reasoning_frames_and_persistence_carry_lifecycle() -> None:
    service = VercelStreamingService()
    builder = AssistantContentBuilder()

    start = _payload(service.format_reasoning_start("reasoning-1"))
    builder.on_reasoning_start("reasoning-1")
    builder.on_reasoning_delta("reasoning-1", "Visible provider reasoning")
    end = _payload(service.format_reasoning_end("reasoning-1"))
    builder.on_reasoning_end("reasoning-1")

    reasoning = next(part for part in builder.snapshot() if part["type"] == "reasoning")
    assert start["startedAt"]
    assert end["completedAt"]
    assert reasoning["id"] == "reasoning-1"
    assert reasoning["status"] == "completed"
    assert reasoning["startedAt"]
    assert reasoning["completedAt"]


def test_interrupted_reasoning_is_truthful() -> None:
    builder = AssistantContentBuilder()
    builder.on_reasoning_start("reasoning-1")
    builder.on_reasoning_delta("reasoning-1", "Partial")

    builder.mark_interrupted()

    reasoning = next(part for part in builder.snapshot() if part["type"] == "reasoning")
    assert reasoning["status"] == "interrupted"
    assert reasoning["completedAt"]


def test_initial_frames_carry_explicit_turn_start_without_synthetic_step() -> None:
    frames = [
        _payload(frame)
        for frame in iter_initial_frames(
            VercelStreamingService(), turn_id="12:legacy-clock", flow="resume"
        )
    ]

    assert [frame["type"] for frame in frames] == [
        "start",
        "start-step",
        "data-turn-info",
        "data-turn-status",
    ]
    turn_info = frames[2]["data"]
    assert turn_info["chat_turn_id"] == "12:legacy-clock"
    assert turn_info["started_at"]
    assert turn_info["flow"] == "resume"
    assert all(frame["type"] != "data-thinking-step" for frame in frames)


def test_artifact_skill_discovery_is_identified_without_exposing_command() -> None:
    assert (
        _artifact_skill_name(
            "execute",
            {
                "code_or_command": "cat /opt/skills/pdf/SKILL.md",
                "language": "bash",
            },
        )
        == "pdf"
    )
    assert _artifact_skill_name("execute", {"code_or_command": "python build.py"}) is None

