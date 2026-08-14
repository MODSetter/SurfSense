from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.agents.chat.multi_agent_chat.shared.tools.mcp.tool import (
    _mcp_activity_descriptor,
)
from app.services.new_streaming_service import VercelStreamingService
from app.services.streaming.types import ActivityTimingData
from app.tasks.chat.content_builder import AssistantContentBuilder
from app.tasks.chat.streaming.activity_timing import ActivityTimer
from app.tasks.chat.streaming.flows.resume_chat.assistant_shell import (
    _resumable_journal_from_messages,
)
from app.tasks.chat.streaming.flows.shared.first_frames import iter_initial_frames
from app.tasks.chat.streaming.handlers.custom_events import handle_activity_progress
from app.tasks.chat.streaming.handlers.tool_end import iter_tool_end_frames
from app.tasks.chat.streaming.handlers.tool_start import (
    _artifact_instruction_type,
    iter_tool_start_frames,
)
from app.tasks.chat.streaming.handlers.tools.activity import resolve_tool_activity
from app.tasks.chat.streaming.relay.activity_sse import emit_activity_timing_frame
from app.tasks.chat.streaming.relay.state import AgentEventRelayState


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


def test_initial_frames_carry_turn_identity_without_timing_copy() -> None:
    frames = [
        _payload(frame)
        for frame in iter_initial_frames(
            VercelStreamingService(), turn_id="12:activity-clock"
        )
    ]

    assert [frame["type"] for frame in frames] == [
        "start",
        "start-step",
        "data-turn-info",
        "data-turn-status",
    ]
    turn_info = frames[2]["data"]
    assert turn_info == {"chat_turn_id": "12:activity-clock"}
    assert all(frame["type"] != "data-thinking-step" for frame in frames)


def test_artifact_instruction_type_comes_from_the_structured_tool() -> None:
    assert (
        _artifact_instruction_type(
            "load_artifact_instructions",
            {"artifact_type": "pdf"},
        )
        == "pdf"
    )
    assert _artifact_instruction_type("execute", {"artifact_type": "pdf"}) is None


def test_backend_owns_activity_copy_and_phase_lifecycle() -> None:
    service = VercelStreamingService()
    builder = AssistantContentBuilder()
    state = AgentEventRelayState(active_subagent_type="deliverables")
    result = SimpleNamespace(
        write_attempted=False,
        write_succeeded=False,
        verification_succeeded=False,
        sandbox_files=[],
    )
    tool_input = {
        "code_or_command": "python render.py",
        "language": "python",
        "description": "Untrusted model label",
    }

    start_frames = [
        _payload(frame)
        for frame in iter_tool_start_frames(
            {"name": "execute", "run_id": "render-1", "data": {"input": tool_input}},
            state=state,
            streaming_service=service,
            content_builder=builder,
            result=result,
            step_prefix="turn",
        )
    ]
    started = next(frame for frame in start_frames if frame["type"] == "data-activity")
    assert started["data"]["title"] == "Creating the artifact"
    assert started["data"] == {
        "id": "act_turn_1",
        "sequence": 1,
        "kind": "artifact.create",
        "status": "running",
        "title": "Creating the artifact",
        "category": "artifact",
        "iconKey": "terminal",
        "startedAt": started["data"]["startedAt"],
    }
    assert "Untrusted model label" not in json.dumps(started)

    end_frames = [
        _payload(frame)
        for frame in iter_tool_end_frames(
            {
                "name": "execute",
                "run_id": "render-1",
                "data": {"output": {"result": "Exit code: 0\nOutput:\nrendered"}},
            },
            state=state,
            streaming_service=service,
            content_builder=builder,
            result=result,
            step_prefix="turn",
            config={},
        )
    ]
    assert all(frame["type"] != "data-activity" for frame in end_frames)

    repeated_frames = [
        _payload(frame)
        for frame in iter_tool_start_frames(
            {
                "name": "execute",
                "run_id": "render-2",
                "data": {"input": {"code_or_command": "python polish.py"}},
            },
            state=state,
            streaming_service=service,
            content_builder=builder,
            result=result,
            step_prefix="turn",
        )
    ]
    repeated = next(
        frame for frame in repeated_frames if frame["type"] == "data-activity"
    )
    assert repeated["data"]["id"] == "act_turn_1"
    assert repeated["data"]["sequence"] == 1
    list(
        iter_tool_end_frames(
            {
                "name": "execute",
                "run_id": "render-2",
                "data": {"output": {"result": "Exit code: 0"}},
            },
            state=state,
            streaming_service=service,
            content_builder=builder,
            result=result,
            step_prefix="turn",
            config={},
        )
    )

    verify_frames = [
        _payload(frame)
        for frame in iter_tool_start_frames(
            {"name": "verify_artifact", "run_id": "verify-1", "data": {"input": {}}},
            state=state,
            streaming_service=service,
            content_builder=builder,
            result=result,
            step_prefix="turn",
        )
    ]
    thinking_frames = [
        frame for frame in verify_frames if frame["type"] == "data-activity"
    ]
    assert [
        (frame["data"]["title"], frame["data"]["status"]) for frame in thinking_frames
    ] == [
        ("Created the artifact", "completed"),
        ("Checking the artifact", "running"),
    ]
    list(
        iter_tool_end_frames(
            {
                "name": "verify_artifact",
                "run_id": "verify-1",
                "data": {"output": {"error": "preview failed"}},
            },
            state=state,
            streaming_service=service,
            content_builder=builder,
            result=result,
            step_prefix="turn",
            config={},
        )
    )
    repair_frames = [
        _payload(frame)
        for frame in iter_tool_start_frames(
            {
                "name": "execute",
                "run_id": "repair-1",
                "data": {"input": {"code_or_command": "python repair.py"}},
            },
            state=state,
            streaming_service=service,
            content_builder=builder,
            result=result,
            step_prefix="turn",
        )
    ]
    repair = next(frame for frame in repair_frames if frame["type"] == "data-activity")
    assert repair["data"]["id"] == "act_turn_3"
    assert repair["data"]["title"] == "Repairing the artifact"

    parts = builder.snapshot()
    activity_part = next(part for part in parts if part["type"] == "data-activities")
    persisted = activity_part["data"]["activities"][0]
    assert persisted["title"] == "Created the artifact"
    assert persisted["id"] == "act_turn_1"
    tool_part = next(part for part in parts if part["type"] == "tool-call")
    assert tool_part["metadata"]["activityId"] == "act_turn_1"


def test_unknown_tools_are_generic_and_internal_tools_are_hidden() -> None:
    service = VercelStreamingService()
    result = SimpleNamespace(write_attempted=False)

    unknown = [
        _payload(frame)
        for frame in iter_tool_start_frames(
            {
                "name": "send_secret_command",
                "run_id": "unknown-1",
                "data": {"input": {"description": "Leak this", "command": "rm -rf /"}},
            },
            state=AgentEventRelayState(),
            streaming_service=service,
            content_builder=AssistantContentBuilder(),
            result=result,
            step_prefix="turn",
        )
    ]
    activity = next(frame for frame in unknown if frame["type"] == "data-activity")
    assert activity["data"]["kind"] == "tool.action"
    assert activity["data"]["title"] == "Using a tool"
    assert "secret" not in json.dumps(activity).lower()
    assert "rm -rf" not in json.dumps(activity)

    for hidden_name in ("noop", "load_artifact_instructions"):
        hidden = [
            _payload(frame)
            for frame in iter_tool_start_frames(
                {
                    "name": hidden_name,
                    "run_id": f"hidden-{hidden_name}",
                    "data": {"input": {"artifact_type": "pdf"}},
                },
                state=AgentEventRelayState(),
                streaming_service=service,
                content_builder=AssistantContentBuilder(),
                result=result,
                step_prefix="turn",
            )
        ]
        assert all(frame["type"] != "data-activity" for frame in hidden)


def test_backend_assigns_specific_icons_and_safe_fallbacks() -> None:
    expected_icons = {
        "read_file": "file-text",
        "write_file": "file-plus",
        "edit_file": "file-pen",
        "move_file": "files",
        "rm": "file-x",
        "mkdir": "folder-plus",
        "rmdir": "folder-x",
        "ls": "folder-open",
        "list_tree": "folder-tree",
        "glob": "folder-search",
        "grep": "search-code",
        "execute": "terminal",
        "execute_code": "square-code",
        "write_todos": "list-todo",
        "load_artifact_source": "file-input",
        "read_sandbox_file": "file-text",
        "verify_artifact": "badge-check",
        "save_artifact": "file-output",
        "save_document": "file-output",
        "generate_image": "image",
        "display_image": "image",
        "generate_podcast": "microphone",
        "generate_video_presentation": "film",
        "search_knowledge_base": "library",
        "ask_knowledge_base": "library",
        "scrape_webpage": "scan-text",
        "google_search.scrape": "search",
        "web.crawl": "scan-text",
        "link_preview": "external-link",
        "multi_link_preview": "external-link",
        "create_calendar_event": "calendar",
        "update_calendar_event": "calendar",
        "delete_calendar_event": "calendar",
        "search_calendar_events": "calendar",
        "create_automation": "workflow",
        "update_memory": "brain",
    }

    for tool_name, icon_key in expected_icons.items():
        spec = resolve_tool_activity(tool_name, subagent_type=None)
        assert spec.icon_key == icon_key

    unknown = resolve_tool_activity("dynamic_unknown_tool", subagent_type=None)
    assert unknown.icon_key == "tool"

    service = resolve_tool_activity("youtube.scrape", subagent_type=None)
    snapshot = service.snapshot(
        activity_id="act_youtube",
        sequence=1,
        status="running",
        started_at="2026-01-01T00:00:00+00:00",
    )
    assert snapshot["integration"] == {"source": "native", "key": "youtube"}


def test_unknown_mcp_tool_uses_generic_activity_and_mcp_integration() -> None:
    frames = [
        _payload(frame)
        for frame in iter_tool_start_frames(
            {
                "name": "dynamic_mcp_action",
                "run_id": "mcp-1",
                "metadata": {"mcp_is_generic": True},
                "data": {"input": {}},
            },
            state=AgentEventRelayState(),
            streaming_service=VercelStreamingService(),
            content_builder=AssistantContentBuilder(),
            result=SimpleNamespace(write_attempted=False),
            step_prefix="turn",
        )
    ]
    activity = next(
        frame["data"] for frame in frames if frame["type"] == "data-activity"
    )

    assert activity["iconKey"] == "tool"
    assert activity["integration"] == {"source": "mcp"}


def test_mcp_descriptor_is_safe_for_known_connectors_and_generic_otherwise() -> None:
    assert _mcp_activity_descriptor(connector_name="Linear", is_generic_mcp=False) == {
        "active_title": "Using connected app",
        "completed_title": "Used connected app",
        "category": "connector",
        "icon_key": "plug",
        "kind": "connector.action",
    }
    assert (
        _mcp_activity_descriptor(
            connector_name="User named <script>", is_generic_mcp=True
        )
        is None
    )


def test_trusted_descriptor_wins_for_generated_native_tool_name() -> None:
    descriptor = {
        "active_title": "Searching the web",
        "completed_title": "Searched the web",
        "category": "research",
        "icon_key": "search",
        "integration_key": "google_search",
    }

    spec = resolve_tool_activity(
        "google_search_scrape",
        subagent_type=None,
        trusted_descriptor=descriptor,
    )
    snapshot = spec.snapshot(
        activity_id="act_search",
        sequence=1,
        status="running",
        started_at="2026-01-01T00:00:00+00:00",
    )

    assert snapshot["title"] == "Searching the web"
    assert snapshot["integration"] == {
        "source": "native",
        "key": "google_search",
    }


def test_trusted_descriptor_precedes_colliding_legacy_tool_name() -> None:
    spec = resolve_tool_activity(
        "read_file",
        subagent_type=None,
        trusted_descriptor={
            "active_title": "Using connected app",
            "completed_title": "Used connected app",
            "category": "connector",
            "icon_key": "plug",
            "kind": "connector.action",
        },
    )

    assert spec.kind == "connector.action"
    assert spec.active_title == "Using connected app"


def test_generated_native_tool_keeps_activity_id_through_result_lifecycle() -> None:
    descriptor = {
        "active_title": "Searching the web",
        "completed_title": "Searched the web",
        "category": "research",
        "icon_key": "search",
        "kind": "google_search.scrape",
        "integration_key": "google_search",
    }
    state = AgentEventRelayState()
    builder = AssistantContentBuilder()
    service = VercelStreamingService()
    result = SimpleNamespace(write_attempted=False)

    list(
        iter_tool_start_frames(
            {
                "name": "google_search_scrape",
                "run_id": "search-1",
                "metadata": {"activity_descriptor": descriptor},
                "data": {"input": {"search_queries": ["activity trace"]}},
            },
            state=state,
            streaming_service=service,
            content_builder=builder,
            result=result,
            step_prefix="turn",
        )
    )
    activity_id = state.activity_id_by_run["search-1"]

    list(
        iter_tool_end_frames(
            {
                "name": "google_search_scrape",
                "run_id": "search-1",
                "data": {"output": {"results": []}},
            },
            state=state,
            streaming_service=service,
            content_builder=builder,
            result=result,
            step_prefix="turn",
            config={},
        )
    )

    tool_part = next(part for part in builder.snapshot() if part["type"] == "tool-call")
    assert tool_part["metadata"]["activityId"] == activity_id
    assert tool_part["result"]["status"] == "completed"
    activity = builder.snapshot()[0]["data"]["activities"][0]
    assert activity["id"] == activity_id
    assert activity["status"] == "completed"
    assert activity["title"] == "Searched the web"


def test_incomplete_or_unbounded_descriptor_uses_generic_fallback() -> None:
    for descriptor in (
        {"active_title": "Searching"},
        {
            "active_title": "x" * 121,
            "completed_title": "Done",
            "category": "research",
            "icon_key": "search",
        },
        {
            "active_title": "Searching",
            "completed_title": "Done",
            "category": "not-a-category",
            "icon_key": "search",
        },
    ):
        spec = resolve_tool_activity(
            "untrusted_dynamic_tool",
            subagent_type=None,
            trusted_descriptor=descriptor,
        )
        assert spec.kind == "tool.action"
        assert spec.active_title == "Using a tool"


def test_resume_reuses_persisted_awaiting_activity_identity() -> None:
    awaiting = resolve_tool_activity("write_file", subagent_type=None).snapshot(
        activity_id="act_original_7",
        sequence=7,
        status="awaiting_approval",
        started_at="2026-01-01T00:00:00+00:00",
    )
    state = AgentEventRelayState.for_invocation(initial_activities=[awaiting])
    builder = AssistantContentBuilder()
    result = SimpleNamespace(write_attempted=False)

    start_frames = [
        _payload(frame)
        for frame in iter_tool_start_frames(
            {
                "name": "write_file",
                "run_id": "resumed-write",
                "data": {"input": {"file_path": "report.md", "content": "done"}},
            },
            state=state,
            streaming_service=VercelStreamingService(),
            content_builder=builder,
            result=result,
            step_prefix="resume-new-turn",
        )
    ]

    resumed = next(frame for frame in start_frames if frame["type"] == "data-activity")
    assert resumed["data"]["id"] == "act_original_7"
    assert resumed["data"]["sequence"] == 7
    assert resumed["data"]["status"] == "running"
    assert resumed["data"]["startedAt"] == "2026-01-01T00:00:00+00:00"
    tool_part = next(part for part in builder.snapshot() if part["type"] == "tool-call")
    assert tool_part["metadata"]["activityId"] == "act_original_7"


def test_resume_seed_loader_returns_paused_journal() -> None:
    running_spec = resolve_tool_activity("write_file", subagent_type=None)
    awaiting = running_spec.snapshot(
        activity_id="act_waiting",
        sequence=2,
        status="awaiting_approval",
        started_at="2026-01-01T00:00:00+00:00",
    )
    completed = running_spec.snapshot(
        activity_id="act_done",
        sequence=1,
        status="completed",
        started_at="2026-01-01T00:00:00+00:00",
        completed_at="2026-01-01T00:00:01+00:00",
    )

    seed = _resumable_journal_from_messages(
        [
            [
                {"type": "data-thinking-steps", "data": {"steps": []}},
                {
                    "type": "data-activities",
                    "data": {
                        "activities": [completed, awaiting],
                        "timing": {"status": "paused", "activeDurationMs": 2400},
                    },
                },
            ]
        ]
    )

    assert seed.activities == [awaiting]
    assert seed.timing == {"status": "paused", "activeDurationMs": 2400}


def test_resume_seed_loader_uses_latest_snapshot_across_resume_messages() -> None:
    spec = resolve_tool_activity("write_file", subagent_type=None)
    awaiting = spec.snapshot(
        activity_id="act_shared",
        sequence=1,
        status="awaiting_approval",
        started_at="2026-01-01T00:00:00+00:00",
    )
    completed = spec.snapshot(
        activity_id="act_shared",
        sequence=1,
        status="completed",
        started_at="2026-01-01T00:00:00+00:00",
        completed_at="2026-01-01T00:00:01+00:00",
    )

    seed = _resumable_journal_from_messages(
        [
            [
                {
                    "type": "data-activities",
                    "data": {
                        "activities": [completed],
                        "timing": {"status": "completed", "activeDurationMs": 3100},
                    },
                }
            ],
            [
                {
                    "type": "data-activities",
                    "data": {
                        "activities": [awaiting],
                        "timing": {"status": "paused", "activeDurationMs": 2000},
                    },
                }
            ],
        ]
    )

    assert seed.activities == []
    assert seed.timing is None


def test_activity_timer_excludes_hitl_wait_and_resumes_accumulation() -> None:
    started = datetime(2026, 1, 1, tzinfo=UTC)
    timer = ActivityTimer.start(now=started)
    assert timer.snapshot(now=started + timedelta(seconds=1)) == {
        "status": "running",
        "activeDurationMs": 1000,
        "sampledAt": "2026-01-01T00:00:01+00:00",
    }

    paused = timer.pause(now=started + timedelta(seconds=2))
    assert paused == {
        "status": "paused",
        "activeDurationMs": 2000,
        "sampledAt": "2026-01-01T00:00:02+00:00",
    }
    assert timer.snapshot(now=started + timedelta(hours=1)) == paused

    timer = ActivityTimer.resume(paused, now=started + timedelta(hours=1))
    completed = timer.complete(now=started + timedelta(hours=1, seconds=3))
    assert completed == {
        "status": "completed",
        "activeDurationMs": 5000,
        "sampledAt": "2026-01-01T01:00:03+00:00",
    }


def test_activity_builder_keeps_timing_and_rows_in_one_journal() -> None:
    builder = AssistantContentBuilder()
    builder.on_activity_timing(
        {
            "status": "paused",
            "activeDurationMs": 2000,
            "sampledAt": "2026-01-01T00:00:02+00:00",
        }
    )
    builder.on_activity(
        resolve_tool_activity("write_file", subagent_type=None).snapshot(
            activity_id="act_waiting",
            sequence=1,
            status="awaiting_approval",
            started_at="2026-01-01T00:00:00+00:00",
        )
    )
    builder.on_activity_timing(
        {
            "status": "completed",
            "activeDurationMs": 5000,
            "sampledAt": "2026-01-01T00:00:05+00:00",
        }
    )

    journal = builder.snapshot()[0]
    assert journal["type"] == "data-activities"
    assert journal["data"]["activities"][0]["id"] == "act_waiting"
    assert journal["data"]["timing"] == {
        "status": "completed",
        "activeDurationMs": 5000,
        "sampledAt": "2026-01-01T00:00:05+00:00",
    }


def test_activity_timing_wire_and_persistence_use_the_same_snapshot() -> None:
    service = VercelStreamingService()
    builder = AssistantContentBuilder()
    snapshot: ActivityTimingData = {
        "status": "paused",
        "activeDurationMs": 2400,
        "sampledAt": "2026-01-01T00:00:02.400000+00:00",
    }

    frame = emit_activity_timing_frame(
        streaming_service=service,
        content_builder=builder,
        snapshot=snapshot,
    )

    assert _payload(frame) == {"type": "data-activity-timing", "data": snapshot}
    assert builder.snapshot()[0]["data"]["timing"] == snapshot


def test_custom_progress_uses_allowlisted_details_not_raw_messages() -> None:
    service = VercelStreamingService()
    builder = AssistantContentBuilder()
    state = AgentEventRelayState()
    spec = resolve_tool_activity("scrape_webpage", subagent_type=None)
    snapshot = spec.snapshot(
        activity_id="act_turn_1",
        sequence=1,
        status="running",
        started_at="2026-01-01T00:00:00+00:00",
    )
    state.activity_spec_by_id[snapshot["id"]] = spec
    state.activity_snapshot_by_id[snapshot["id"]] = snapshot

    frame = handle_activity_progress(
        {
            "phase": "scraping",
            "current": 2,
            "total": 5,
            "message": "Untrusted connector output",
        },
        state=state,
        streaming_service=service,
        content_builder=builder,
    )

    assert frame is not None
    data = _payload(frame)["data"]
    assert data["details"] == ["Reviewing sources (2/5)"]
    assert "Untrusted connector output" not in json.dumps(data)


def test_activity_state_preserves_terminal_monotonicity() -> None:
    state = AgentEventRelayState()
    spec = resolve_tool_activity("write_file", subagent_type=None)
    running = spec.snapshot(
        activity_id="act_turn_1",
        sequence=1,
        status="running",
        started_at="2026-01-01T00:00:00+00:00",
    )
    state.activity_spec_by_id[running["id"]] = spec
    state.activity_snapshot_by_id[running["id"]] = running

    awaiting = state.transition_activity(running["id"], status="awaiting_approval")
    assert awaiting and awaiting["status"] == "awaiting_approval"
    assert "completedAt" not in awaiting

    interrupted = state.transition_activity(
        running["id"],
        status="interrupted",
        completed_at="2026-01-01T00:01:00+00:00",
    )
    assert interrupted and interrupted["status"] == "interrupted"
    assert interrupted["completedAt"]
    assert (
        state.transition_activity(running["id"], status="running")["status"]
        == "interrupted"
    )
