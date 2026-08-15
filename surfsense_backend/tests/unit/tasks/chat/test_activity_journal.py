from app.tasks.chat.streaming.handlers.tools.activity import resolve_tool_activity
from app.tasks.chat.streaming.relay.activity_journal import ActivityJournal


def _activity(tool_name: str, *, lifecycle: str = "invocation"):
    return resolve_tool_activity(
        tool_name,
        subagent_type=None,
        trusted_descriptor={
            "active_title": "Working",
            "completed_title": "Worked",
            "category": "action",
            "icon_key": "tool",
            "kind": tool_name,
            "lifecycle": lifecycle,
        },
    )


def _awaiting(activity_id: str, sequence: int):
    return _activity("write_file").snapshot(
        activity_id=activity_id,
        sequence=sequence,
        status="awaiting_approval",
        started_at=f"2026-01-01T00:00:0{sequence}+00:00",
    )


def test_resume_binding_distinguishes_same_kind_activities() -> None:
    first = _awaiting("act_first", 1)
    second = _awaiting("act_second", 2)
    journal = ActivityJournal.resume(
        activities=[first, second],
        activity_id_by_tool_call={
            "tool-call-first": first["id"],
            "tool-call-second": second["id"],
        },
    )
    spec = _activity("write_file")

    resumed_second = journal.begin_tool(
        spec=spec,
        run_id="run-second",
        step_prefix="resume",
        scope="root",
        started_at="2026-01-01T00:01:00+00:00",
        tool_call_id="tool-call-second",
        langchain_tool_call_id=None,
        integration=None,
    )
    resumed_first = journal.begin_tool(
        spec=spec,
        run_id="run-first",
        step_prefix="resume",
        scope="root",
        started_at="2026-01-01T00:01:01+00:00",
        tool_call_id="tool-call-first",
        langchain_tool_call_id=None,
        integration=None,
    )

    assert resumed_second.activity_id == second["id"]
    assert resumed_second.snapshots[-1]["startedAt"] == second["startedAt"]
    assert resumed_first.activity_id == first["id"]
    assert resumed_first.snapshots[-1]["startedAt"] == first["startedAt"]


def test_resume_prefers_authoritative_langchain_tool_call_id() -> None:
    first = _awaiting("act_ui", 1)
    second = _awaiting("act_lc", 2)
    journal = ActivityJournal.resume(
        activities=[first, second],
        activity_id_by_tool_call={
            "ui-call": first["id"],
            "lc-call": second["id"],
        },
    )

    resumed = journal.begin_tool(
        spec=_activity("write_file"),
        run_id="run",
        step_prefix="resume",
        scope="root",
        started_at="2026-01-01T00:01:00+00:00",
        tool_call_id="ui-call",
        langchain_tool_call_id="lc-call",
        integration=None,
    )

    assert resumed.activity_id == second["id"]
    assert "lc-call" not in journal.resume_id_by_tool_call


def test_phase_reuses_identity_until_a_different_phase_starts() -> None:
    journal = ActivityJournal()
    planning = _activity("write_todos", lifecycle="phase")
    research = _activity("web.crawl", lifecycle="phase")

    first = journal.begin_tool(
        spec=planning,
        run_id="plan-1",
        step_prefix="turn",
        scope="root",
        started_at="2026-01-01T00:00:00+00:00",
        tool_call_id="call-plan-1",
        langchain_tool_call_id=None,
        integration=None,
    )
    repeated = journal.begin_tool(
        spec=planning,
        run_id="plan-2",
        step_prefix="turn",
        scope="root",
        started_at="2026-01-01T00:00:01+00:00",
        tool_call_id="call-plan-2",
        langchain_tool_call_id=None,
        integration=None,
    )
    assert journal.finish_tool(
        run_id="plan-1",
        status="completed",
        completed_at="2026-01-01T00:00:01+00:00",
    ).snapshot is None
    assert journal.finish_tool(
        run_id="plan-2",
        status="completed",
        completed_at="2026-01-01T00:00:01+00:00",
    ).snapshot is None
    next_phase = journal.begin_tool(
        spec=research,
        run_id="research",
        step_prefix="turn",
        scope="root",
        started_at="2026-01-01T00:00:02+00:00",
        tool_call_id="call-research",
        langchain_tool_call_id=None,
        integration=None,
    )

    assert repeated.activity_id == first.activity_id
    assert next_phase.snapshots[0]["id"] == first.activity_id
    assert next_phase.snapshots[0]["status"] == "completed"
    assert next_phase.activity_id != first.activity_id


def test_phase_close_waits_for_all_runs_and_preserves_late_error() -> None:
    journal = ActivityJournal()
    planning = _activity("write_todos", lifecycle="phase")
    research = _activity("web.crawl", lifecycle="phase")

    first = journal.begin_tool(
        spec=planning,
        run_id="plan-1",
        step_prefix="turn",
        scope="root",
        started_at="2026-01-01T00:00:00+00:00",
        tool_call_id="call-plan-1",
        langchain_tool_call_id=None,
        integration=None,
    )
    journal.begin_tool(
        spec=planning,
        run_id="plan-2",
        step_prefix="turn",
        scope="root",
        started_at="2026-01-01T00:00:01+00:00",
        tool_call_id="call-plan-2",
        langchain_tool_call_id=None,
        integration=None,
    )
    next_phase = journal.begin_tool(
        spec=research,
        run_id="research",
        step_prefix="turn",
        scope="root",
        started_at="2026-01-01T00:00:02+00:00",
        tool_call_id="call-research",
        langchain_tool_call_id=None,
        integration=None,
    )

    assert [snapshot["id"] for snapshot in next_phase.snapshots] == [
        next_phase.activity_id
    ]
    assert journal.finish_tool(
        run_id="plan-2",
        status="completed",
        completed_at="2026-01-01T00:00:03+00:00",
    ).snapshot is None
    failed = journal.finish_tool(
        run_id="plan-1",
        status="error",
        completed_at="2026-01-01T00:00:04+00:00",
    ).snapshot

    assert failed is not None
    assert failed["id"] == first.activity_id
    assert failed["status"] == "error"
    assert failed["completedAt"] == "2026-01-01T00:00:04+00:00"


def test_phase_outcomes_use_deterministic_severity() -> None:
    journal = ActivityJournal()
    phase = _activity("write_todos", lifecycle="phase")
    for run_id in ("one", "two", "three"):
        journal.begin_tool(
            spec=phase,
            run_id=run_id,
            step_prefix="turn",
            scope="root",
            started_at="2026-01-01T00:00:00+00:00",
            tool_call_id=f"call-{run_id}",
            langchain_tool_call_id=None,
            integration=None,
        )

    assert journal.finish_tool(
        run_id="one",
        status="interrupted",
        completed_at="2026-01-01T00:00:01+00:00",
    ).snapshot is None
    assert journal.finish_tool(
        run_id="two",
        status="cancelled",
        completed_at="2026-01-01T00:00:02+00:00",
    ).snapshot is None
    final = journal.finish_tool(
        run_id="three",
        status="error",
        completed_at="2026-01-01T00:00:03+00:00",
    ).snapshot

    assert final is not None
    assert final["status"] == "error"


def test_successful_phase_closes_after_its_final_active_run() -> None:
    journal = ActivityJournal()
    phase = _activity("write_todos", lifecycle="phase")
    started = journal.begin_tool(
        spec=phase,
        run_id="one",
        step_prefix="turn",
        scope="root",
        started_at="2026-01-01T00:00:00+00:00",
        tool_call_id="call-one",
        langchain_tool_call_id=None,
        integration=None,
    )
    journal.begin_tool(
        spec=phase,
        run_id="two",
        step_prefix="turn",
        scope="root",
        started_at="2026-01-01T00:00:01+00:00",
        tool_call_id="call-two",
        langchain_tool_call_id=None,
        integration=None,
    )

    assert (
        journal.complete_open_phases(completed_at="2026-01-01T00:00:02+00:00")
        == []
    )
    assert journal.finish_tool(
        run_id="one",
        status="completed",
        completed_at="2026-01-01T00:00:03+00:00",
    ).snapshot is None
    closed = journal.finish_tool(
        run_id="two",
        status="completed",
        completed_at="2026-01-01T00:00:04+00:00",
    ).snapshot

    assert closed is not None
    assert closed["id"] == started.activity_id
    assert closed["status"] == "completed"
    assert closed["completedAt"] == "2026-01-01T00:00:02+00:00"


def test_interrupt_running_force_closes_active_phase_runs() -> None:
    journal = ActivityJournal()
    started = journal.begin_tool(
        spec=_activity("write_todos", lifecycle="phase"),
        run_id="plan",
        step_prefix="turn",
        scope="root",
        started_at="2026-01-01T00:00:00+00:00",
        tool_call_id="call-plan",
        langchain_tool_call_id=None,
        integration=None,
    )

    interrupted = journal.interrupt_running(
        completed_at="2026-01-01T00:00:01+00:00"
    )

    assert interrupted[0]["id"] == started.activity_id
    assert interrupted[0]["status"] == "interrupted"
    assert "plan" not in journal.id_by_run
    assert started.activity_id not in journal.active_runs_by_activity


def test_terminal_activity_never_regresses() -> None:
    journal = ActivityJournal()
    started = journal.begin_tool(
        spec=_activity("write_file"),
        run_id="write",
        step_prefix="turn",
        scope="root",
        started_at="2026-01-01T00:00:00+00:00",
        tool_call_id="call-write",
        langchain_tool_call_id=None,
        integration=None,
    )
    assert started.activity_id

    completed = journal.transition(
        started.activity_id,
        status="completed",
        completed_at="2026-01-01T00:00:01+00:00",
    )
    stale = journal.transition(started.activity_id, status="running")

    assert completed and completed["status"] == "completed"
    assert stale == completed


def test_progress_updates_details_without_unpausing_activity() -> None:
    awaiting = _awaiting("act_waiting", 1)
    journal = ActivityJournal.resume(activities=[awaiting])
    spec = _activity("write_file")
    journal.spec_by_id[awaiting["id"]] = spec

    updated = journal.update_current_progress("Reviewing sources (1/2)")

    assert updated is not None
    assert updated["status"] == "awaiting_approval"
    assert updated["details"] == ["Reviewing sources (1/2)"]
