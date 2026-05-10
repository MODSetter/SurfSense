"""Pin the parent_ids walk + parallel sub-agent isolation that drives lane attribution."""

from __future__ import annotations

import pytest

from app.services.streaming.emitter import (
    Emitter,
    EmitterRegistry,
    main_emitter,
    subagent_emitter,
)

pytestmark = pytest.mark.unit


def _sub(run_id: str, kind: str = "deliverables") -> Emitter:
    return subagent_emitter(
        subagent_type=kind,
        subagent_run_id=f"sub_{run_id}",
        parent_tool_call_id=f"call_{run_id}",
    )


def test_unregistered_event_resolves_to_main_emitter() -> None:
    registry = EmitterRegistry()
    resolved = registry.resolve(run_id="run_1", parent_ids=["root"])
    assert resolved is main_emitter()


def test_event_owned_by_registered_run_id_returns_that_emitter() -> None:
    registry = EmitterRegistry()
    emitter = _sub("a")
    registry.register("run_task_a", emitter)
    assert registry.resolve(run_id="run_task_a", parent_ids=[]) is emitter


def test_descendant_resolves_via_parent_ids_chain() -> None:
    """A model-call event nested under the task tool inherits its sub-agent emitter."""
    registry = EmitterRegistry()
    emitter = _sub("a")
    registry.register("run_task_a", emitter)
    descendant = registry.resolve(
        run_id="run_chat_model",
        parent_ids=["root", "run_agent", "run_task_a"],
    )
    assert descendant is emitter


def test_nearest_registered_ancestor_wins_over_distant_ones() -> None:
    """Inner sub-agents owe their emitter to the nearest task tool, not the outer one."""
    registry = EmitterRegistry()
    outer = _sub("outer", kind="planner")
    inner = _sub("inner", kind="email")
    registry.register("run_outer", outer)
    registry.register("run_inner", inner)
    resolved = registry.resolve(
        run_id="run_inner_tool",
        parent_ids=["root", "run_outer", "run_inner"],
    )
    assert resolved is inner


def test_parallel_subagents_do_not_bleed_into_each_other() -> None:
    """Two concurrent task tools each own their own descendant events."""
    registry = EmitterRegistry()
    a = _sub("a", kind="search")
    b = _sub("b", kind="email")
    registry.register("run_task_a", a)
    registry.register("run_task_b", b)

    from_a = registry.resolve(run_id="x", parent_ids=["root", "run_task_a"])
    from_b = registry.resolve(run_id="y", parent_ids=["root", "run_task_b"])
    from_main = registry.resolve(run_id="z", parent_ids=["root"])

    assert from_a is a
    assert from_b is b
    assert from_main is main_emitter()


def test_unregister_releases_run_id_so_descendants_fall_back_to_main() -> None:
    registry = EmitterRegistry()
    emitter = _sub("a")
    registry.register("run_task_a", emitter)
    registry.unregister("run_task_a")
    assert registry.resolve(run_id="x", parent_ids=["run_task_a"]) is main_emitter()


def test_unregister_returns_the_previously_registered_emitter() -> None:
    """Lets callers emit ``data-subagent-finish`` carrying the same emitter they opened with."""
    registry = EmitterRegistry()
    emitter = _sub("a")
    registry.register("run_task_a", emitter)
    assert registry.unregister("run_task_a") is emitter


def test_has_active_subagents_tracks_open_lanes() -> None:
    registry = EmitterRegistry()
    assert not registry.has_active_subagents()
    registry.register("run_task_a", _sub("a"))
    assert registry.has_active_subagents()
    registry.unregister("run_task_a")
    assert not registry.has_active_subagents()


def test_empty_run_id_and_parent_ids_resolves_to_main() -> None:
    """Defensive: events without identifiers always belong to the main lane."""
    registry = EmitterRegistry()
    registry.register("run_task_a", _sub("a"))
    assert registry.resolve(run_id=None, parent_ids=None) is main_emitter()
    assert registry.resolve(run_id="", parent_ids=[]) is main_emitter()
