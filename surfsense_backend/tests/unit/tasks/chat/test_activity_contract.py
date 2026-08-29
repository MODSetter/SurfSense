from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.agents.chat.multi_agent_chat.shared.tools.mcp.tool import (
    _mcp_activity_descriptor,
)
from app.services.new_streaming_service import VercelStreamingService
from app.services.streaming.types import ActivityTimingData
from app.tasks.chat.content_builder import AssistantContentBuilder
from app.tasks.chat.streaming.activity_timing import ActivityTimer
from app.tasks.chat.streaming.agent.event_loop import stream_agent_events
from app.tasks.chat.streaming.flows.resume_chat.assistant_shell import (
    _resumable_journal_from_content,
)
from app.tasks.chat.streaming.flows.shared.assistant_finalize import (
    finalize_assistant_message,
)
from app.tasks.chat.streaming.flows.shared.first_frames import iter_initial_frames
from app.tasks.chat.streaming.handlers.custom_events import handle_activity_progress
from app.tasks.chat.streaming.handlers.tool_end import iter_tool_end_frames
from app.tasks.chat.streaming.handlers.tool_start import iter_tool_start_frames
from app.tasks.chat.streaming.handlers.tools.activity import resolve_tool_activity
from app.tasks.chat.streaming.relay.activity_sse import (
    emit_activity_timing_frame,
    emit_completed_activity_timing_frame,
    emit_completed_activity_timing_frame_if_running,
)
from app.tasks.chat.streaming.relay.state import AgentEventRelayState
from app.tasks.chat.streaming.shared.stream_result import StreamResult


def _payload(frame: str) -> dict:
    return json.loads(frame.removeprefix("data: ").strip())


def _streaming_source(relative_path: str) -> str:
    return (Path(__file__).parents[4] / relative_path).read_text()


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


@pytest.mark.parametrize(
    "relative_path",
    [
        "app/tasks/chat/streaming/flows/new_chat/orchestrator.py",
        "app/tasks/chat/streaming/flows/resume_chat/orchestrator.py",
    ],
)
def test_initial_timing_precedes_agent_stream(relative_path: str) -> None:
    source = _streaming_source(relative_path)
    assistant_id = source.index('"assistant-message-id"')
    initial_timing = source.index("yield emit_activity_timing_frame(", assistant_id)
    agent_stream = source.index("async for sse in run_stream_loop(", initial_timing)

    assert assistant_id < initial_timing < agent_stream


def test_hitl_pauses_timing_before_awaiting_activity_and_interrupt() -> None:
    source = _streaming_source("app/tasks/chat/streaming/agent/event_loop.py")
    pending_branch = source.index("if pending_values:")
    paused_timing = source.index("yield emit_activity_timing_frame(", pending_branch)
    awaiting_activity = source.index(
        "for snapshot in activity_state.journal.await_approval():", paused_timing
    )
    interrupt = source.index(
        "yield streaming_service.format_interrupt_request(", awaiting_activity
    )

    assert paused_timing < awaiting_activity < interrupt


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
        "iconKey": "square-terminal",
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
            {
                "name": "verify_artifact",
                "run_id": "verify-1",
                "metadata": {
                    "activity_descriptor": {
                        "active_title": "Checking the artifact",
                        "completed_title": "Checked the artifact",
                        "category": "artifact",
                        "icon_key": "badge-check",
                        "kind": "verify_artifact",
                    }
                },
                "data": {"input": {}},
            },
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


@pytest.mark.parametrize(
    ("content", "expected", "expected_status"),
    [
        (
            '{"status":"completed","value":1}',
            {"status": "completed", "value": 1},
            "completed",
        ),
        ('{"status":"cancelled"}', {"status": "cancelled"}, "cancelled"),
        ("[]", {"result": []}, "completed"),
        ('[{"id":1}]', {"result": [{"id": 1}]}, "completed"),
        ('"done"', {"result": "done"}, "completed"),
        ('"Error: failed"', {"result": "Error: failed"}, "error"),
        ("42", {"result": 42}, "completed"),
        ("true", {"result": True}, "completed"),
        ("null", {"result": None}, "completed"),
        ("not-json", {"result": "not-json"}, "completed"),
        ("Error: failed", {"result": "Error: failed"}, "error"),
    ],
)
def test_tool_end_handles_json_content_shapes(
    content: str,
    expected: dict,
    expected_status: str,
) -> None:
    service = VercelStreamingService()
    builder = AssistantContentBuilder()
    state = AgentEventRelayState()
    result = SimpleNamespace(write_attempted=False)

    list(
        iter_tool_start_frames(
            {
                "name": "create_calendar_event",
                "run_id": "tool-1",
                "data": {"input": {}},
            },
            state=state,
            streaming_service=service,
            content_builder=builder,
            result=result,
            step_prefix="turn",
        )
    )

    frames = [
        _payload(frame)
        for frame in iter_tool_end_frames(
            {
                "name": "create_calendar_event",
                "run_id": "tool-1",
                "data": {
                    "output": SimpleNamespace(
                        content=content,
                        tool_call_id="lc-tool-1",
                    )
                },
            },
            state=state,
            streaming_service=service,
            content_builder=builder,
            result=result,
            step_prefix="turn",
            config={},
        )
    ]

    output = next(frame for frame in frames if frame["type"] == "tool-output-available")
    assert output["output"] == expected
    activity_part = next(
        part for part in builder.snapshot() if part["type"] == "data-activities"
    )
    assert activity_part["data"]["activities"][0]["status"] == expected_status


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


def test_localized_native_descriptor_inventory_and_safe_fallbacks() -> None:
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
        "load_artifact_for_revision": "file-input",
        "read_sandbox_file": "file-text",
        "verify_artifact": "badge-check",
        "save_artifact": "file-output",
        "generate_image": "image",
        "generate_podcast": "microphone",
        "generate_video_presentation": "film",
        "search_knowledge_base": "library",
        "ask_knowledge_base": "library",
        "create_calendar_event": "calendar",
        "update_calendar_event": "calendar",
        "delete_calendar_event": "calendar",
        "search_calendar_events": "calendar",
        "create_automation": "workflow",
        "update_memory": "brain",
        "get_connected_accounts": "search",
    }

    for tool_name, icon_key in expected_icons.items():
        spec = resolve_tool_activity(
            tool_name,
            subagent_type=None,
            trusted_descriptor={
                "active_title": "Working",
                "completed_title": "Worked",
                "category": "action",
                "icon_key": icon_key,
                "kind": tool_name,
            },
        )
        assert spec.icon_key == icon_key

    unknown = resolve_tool_activity("dynamic_unknown_tool", subagent_type=None)
    assert unknown.icon_key == "tool"

    service = resolve_tool_activity(
        "youtube.scrape",
        subagent_type=None,
        trusted_descriptor={
            "active_title": "Reviewing video",
            "completed_title": "Reviewed video",
            "category": "research",
            "icon_key": "youtube",
            "kind": "youtube.scrape",
            "integration_key": "youtube",
        },
    )
    snapshot = service.snapshot(
        activity_id="act_youtube",
        sequence=1,
        status="running",
        started_at="2026-01-01T00:00:00+00:00",
    )
    assert snapshot["integration"] == {"source": "native", "key": "youtube"}


def test_visible_native_tools_declare_descriptors_at_their_definition() -> None:
    backend_root = Path(__file__).parents[4]
    inventory = {
        "app/agents/chat/multi_agent_chat/shared/middleware/filesystem/middleware/middleware.py": {
            "glob",
            "grep",
        },
        "app/agents/chat/multi_agent_chat/shared/middleware/todos.py": {"write_todos"},
        **{
            f"app/agents/chat/multi_agent_chat/shared/middleware/filesystem/tools/{name}/index.py": {
                name
            }
            for name in (
                "edit_file",
                "execute_code",
                "list_tree",
                "ls",
                "mkdir",
                "move_file",
                "read_file",
                "rm",
                "rmdir",
                "write_file",
            )
        },
        "app/agents/chat/multi_agent_chat/subagents/builtins/deliverables/tools/generate_image.py": {
            "generate_image"
        },
        "app/agents/chat/multi_agent_chat/subagents/builtins/deliverables/tools/enqueue_deliverable_job.py": {
            "enqueue_deliverable_job"
        },
        "app/agents/chat/multi_agent_chat/subagents/builtins/deliverables/tools/load_artifact_for_revision.py": {
            "load_artifact_for_revision"
        },
        "app/agents/chat/multi_agent_chat/subagents/builtins/deliverables/tools/podcast.py": {
            "generate_podcast"
        },
        "app/agents/chat/multi_agent_chat/subagents/builtins/deliverables/tools/sandbox.py": {
            "read_sandbox_file"
        },
        "app/agents/chat/multi_agent_chat/subagents/builtins/deliverables/tools/save_artifact.py": {
            "save_artifact"
        },
        "app/agents/chat/multi_agent_chat/subagents/builtins/deliverables/tools/synthesize_narration.py": {
            "synthesize_narration"
        },
        "app/agents/chat/multi_agent_chat/subagents/builtins/deliverables/tools/verify_artifact.py": {
            "verify_artifact"
        },
        "app/agents/chat/multi_agent_chat/subagents/builtins/deliverables/tools/video_presentation.py": {
            "generate_video_presentation"
        },
        "app/agents/chat/multi_agent_chat/subagents/builtins/knowledge_base/ask_knowledge_base_tool.py": {
            "ask_knowledge_base"
        },
        "app/agents/chat/multi_agent_chat/subagents/builtins/knowledge_base/tools/search_knowledge_base.py": {
            "search_knowledge_base"
        },
        "app/agents/chat/multi_agent_chat/subagents/builtins/mcp_discovery/tools/calendar/create_event.py": {
            "create_calendar_event"
        },
        "app/agents/chat/multi_agent_chat/subagents/builtins/mcp_discovery/tools/calendar/delete_event.py": {
            "delete_calendar_event"
        },
        "app/agents/chat/multi_agent_chat/subagents/builtins/mcp_discovery/tools/calendar/search_events.py": {
            "search_calendar_events"
        },
        "app/agents/chat/multi_agent_chat/subagents/builtins/mcp_discovery/tools/calendar/update_event.py": {
            "update_calendar_event"
        },
        "app/agents/chat/multi_agent_chat/subagents/builtins/mcp_discovery/tools/get_connected_accounts.py": {
            "get_connected_accounts"
        },
        "app/agents/chat/multi_agent_chat/main_agent/tools/automation/create.py": {
            "create_automation"
        },
        "app/agents/chat/multi_agent_chat/main_agent/tools/update_memory.py": {
            "memory.personal",
            "memory.team",
        },
        "app/agents/chat/multi_agent_chat/subagents/builtins/memory/tools/update_memory.py": {
            "memory.personal",
            "memory.team",
        },
    }

    for relative_path, tool_names in inventory.items():
        source = (backend_root / relative_path).read_text()
        assert source.count('"activity_descriptor"') >= len(tool_names), relative_path
        for tool_name in tool_names:
            assert f'kind="{tool_name}"' in source or (
                f'"{tool_name}"' in source
                and ("kind=TOOL_NAME" in source or "kind=tool_name" in source)
            ), (relative_path, tool_name)


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
    activity_id = state.journal.id_by_run["search-1"]

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
    state = AgentEventRelayState.for_invocation(
        initial_activities=[awaiting],
        resume_activity_id_by_tool_call={"lc-original-write": awaiting["id"]},
        resume_tool_call_ids=["lc-original-write"],
    )
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
    assert tool_part["langchainToolCallId"] == "lc-original-write"
    assert not state.resume_tool_call_ids
    assert not state.journal.resume_id_by_tool_call


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

    seed = _resumable_journal_from_content(
        [
            {
                "type": "data-activities",
                "data": {
                    "activities": [completed, awaiting],
                    "timing": {"status": "paused", "activeDurationMs": 2400},
                },
            },
            {
                "type": "tool-call",
                "toolCallId": "call-write",
                "toolName": "write_file",
                "metadata": {"activityId": awaiting["id"]},
            },
        ]
    )

    assert seed.activities == [awaiting]
    assert seed.timing == {"status": "paused", "activeDurationMs": 2400}
    assert seed.activity_id_by_tool_call == {"call-write": awaiting["id"]}
    assert seed.tool_call_ids == ["call-write"]


def test_activity_timer_excludes_hitl_wait_and_resumes_accumulation() -> None:
    timer = ActivityTimer.start(now_ns=1_000_000_000)
    assert timer.snapshot(now_ns=2_000_000_000) == {
        "status": "running",
        "activeDurationMs": 1000,
    }

    paused = timer.pause(now_ns=3_000_000_000)
    assert paused == {
        "status": "paused",
        "activeDurationMs": 2000,
    }
    assert timer.snapshot(now_ns=9_000_000_000) == paused

    timer = ActivityTimer.resume(paused, now_ns=10_000_000_000)
    completed = timer.complete(now_ns=13_000_000_000)
    assert completed == {
        "status": "completed",
        "activeDurationMs": 5000,
    }


def test_activity_timer_cleanup_completes_only_running_timers() -> None:
    running = ActivityTimer.start(now_ns=1_000_000_000)
    assert running.complete_if_running(now_ns=3_000_000_000) == {
        "status": "completed",
        "activeDurationMs": 2000,
    }
    assert running.complete_if_running(now_ns=9_000_000_000) is None

    paused = ActivityTimer.start(now_ns=1_000_000_000)
    paused.pause(now_ns=2_000_000_000)
    assert paused.complete_if_running(now_ns=9_000_000_000) is None
    assert paused.status == "paused"


async def test_disconnect_cleanup_uses_pending_hitl_checkpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.tasks.chat import persistence

    persisted: dict = {}

    async def capture_finalize(**kwargs) -> None:
        persisted.update(kwargs)

    monkeypatch.setattr(persistence, "finalize_assistant_turn", capture_finalize)

    pending_state = SimpleNamespace(
        tasks=[
            SimpleNamespace(
                interrupts=(
                    SimpleNamespace(
                        id="interrupt-1",
                        value={"type": "approval", "message": "Approve?"},
                    ),
                )
            )
        ],
        values={},
    )

    class Agent:
        def __init__(self) -> None:
            self.state_read_started = asyncio.Event()
            self.state_reads = 0

        async def astream_events(self, *_args, **_kwargs):
            return
            yield

        async def aget_state(self, _config):
            self.state_reads += 1
            if self.state_reads == 1:
                self.state_read_started.set()
                await asyncio.Event().wait()
            return pending_state

    builder = AssistantContentBuilder()
    builder.on_activity_timing({"status": "running", "activeDurationMs": 1200})
    result = StreamResult(
        turn_id="turn-hitl",
        assistant_message_id=42,
        content_builder=builder,
        activity_timer=ActivityTimer.resume(
            {"status": "paused", "activeDurationMs": 1200}
        ),
    )
    agent = Agent()

    async def consume_stream() -> None:
        async for _ in stream_agent_events(
            agent=agent,
            config={"configurable": {}},
            input_data={},
            streaming_service=VercelStreamingService(),
            result=result,
            content_builder=builder,
        ):
            pass

    consumer = asyncio.create_task(consume_stream())
    await agent.state_read_started.wait()
    consumer.cancel()
    with pytest.raises(asyncio.CancelledError):
        await consumer

    assert result.activity_timer.status == "running"

    await finalize_assistant_message(
        stream_result=result,
        chat_id=7,
        workspace_id=9,
        user_id="user-1",
        accumulator=SimpleNamespace(),
        log_prefix="test_disconnect",
    )

    journal = next(
        part for part in persisted["content"] if part["type"] == "data-activities"
    )
    assert result.is_interrupted is True
    assert result.activity_timer.status == "paused"
    assert journal["data"]["timing"]["status"] == "paused"


def test_activity_timer_excludes_multiple_hitl_waits_and_keeps_pause_strict() -> None:
    timer = ActivityTimer.start(now_ns=0)
    first_pause = timer.pause(now_ns=10_000_000_000)
    with pytest.raises(ValueError, match="Only a running activity timer can pause"):
        timer.pause(now_ns=20_000_000_000)

    timer = ActivityTimer.resume(first_pause, now_ns=310_000_000_000)
    second_pause = timer.pause(now_ns=325_000_000_000)
    timer = ActivityTimer.resume(second_pause, now_ns=925_000_000_000)

    assert timer.complete(now_ns=955_000_000_000) == {
        "status": "completed",
        "activeDurationMs": 55_000,
    }


def test_activity_builder_keeps_timing_and_rows_in_one_journal() -> None:
    builder = AssistantContentBuilder()
    builder.on_activity_timing(
        {
            "status": "paused",
            "activeDurationMs": 2000,
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
            "status": "running",
            "activeDurationMs": 1500,
        }
    )
    assert builder.snapshot()[0]["data"]["timing"] == {
        "status": "paused",
        "activeDurationMs": 2000,
    }
    builder.on_activity_timing(
        {
            "status": "completed",
            "activeDurationMs": 5000,
        }
    )
    builder.on_activity_timing(
        {
            "status": "running",
            "activeDurationMs": 6000,
        }
    )

    journal = builder.snapshot()[0]
    assert journal["type"] == "data-activities"
    assert journal["data"]["activities"][0]["id"] == "act_waiting"
    assert journal["data"]["timing"] == {
        "status": "completed",
        "activeDurationMs": 5000,
    }


def test_activity_timing_wire_and_persistence_use_the_same_snapshot() -> None:
    service = VercelStreamingService()
    builder = AssistantContentBuilder()
    snapshot: ActivityTimingData = {
        "status": "paused",
        "activeDurationMs": 2400,
    }

    frame = emit_activity_timing_frame(
        streaming_service=service,
        content_builder=builder,
        snapshot=snapshot,
    )

    assert _payload(frame) == {"type": "data-activity-timing", "data": snapshot}
    assert builder.snapshot()[0]["data"]["timing"] == snapshot


def test_completed_timing_frame_is_strict_and_cleanup_is_idempotent() -> None:
    service = VercelStreamingService()
    builder = AssistantContentBuilder()
    running = ActivityTimer.start(now_ns=1_000_000_000)

    frame = emit_completed_activity_timing_frame(
        streaming_service=service,
        content_builder=builder,
        timer=running,
        now_ns=3_000_000_000,
    )

    assert frame is not None
    assert _payload(frame)["data"] == {
        "status": "completed",
        "activeDurationMs": 2000,
    }
    assert (
        emit_completed_activity_timing_frame_if_running(
            streaming_service=service,
            content_builder=builder,
            timer=running,
            now_ns=9_000_000_000,
        )
        is None
    )

    paused = ActivityTimer.start(now_ns=1_000_000_000)
    paused.pause(now_ns=2_000_000_000)
    with pytest.raises(ValueError, match="Only a running activity timer can complete"):
        emit_completed_activity_timing_frame(
            streaming_service=service,
            content_builder=builder,
            timer=paused,
            now_ns=9_000_000_000,
        )
    assert (
        emit_completed_activity_timing_frame_if_running(
            streaming_service=service,
            content_builder=builder,
            timer=paused,
            now_ns=9_000_000_000,
        )
        is None
    )


def test_custom_progress_uses_allowlisted_title_not_raw_messages() -> None:
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
    state.journal.spec_by_id[snapshot["id"]] = spec
    state.journal.snapshot_by_id[snapshot["id"]] = snapshot

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
    assert data["progressTitle"] == "Reviewing sources (2/5)"
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
    state.journal.spec_by_id[running["id"]] = spec
    state.journal.snapshot_by_id[running["id"]] = running

    awaiting = state.journal.transition(running["id"], status="awaiting_approval")
    assert awaiting and awaiting["status"] == "awaiting_approval"
    assert "completedAt" not in awaiting

    interrupted = state.journal.transition(
        running["id"],
        status="interrupted",
        completed_at="2026-01-01T00:01:00+00:00",
    )
    assert interrupted and interrupted["status"] == "interrupted"
    assert interrupted["completedAt"]
    assert (
        state.journal.transition(running["id"], status="running")["status"]
        == "interrupted"
    )
