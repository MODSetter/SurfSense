"""Lock the ``execute_step`` orchestration contract.

Covers the pure step-execution logic: predicate gate, params rendering,
action lookup, retry budget, error shaping. The ``ActionContext.session``
is never touched by ``execute_step`` itself (it's only forwarded to the
handler), so unit tests pass ``None`` cast to the type.
"""

from __future__ import annotations

from typing import Any, cast

import pytest
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.automations.actions.store import register_action
from app.automations.actions.types import ActionContext, ActionDefinition
from app.automations.runtime.step import execute_step
from app.automations.schemas.definition.plan_step import PlanStep

pytestmark = pytest.mark.unit


class _AnyParams(BaseModel):
    """Open params model used by test actions — they never validate."""

    model_config = {"extra": "allow"}


def _action_context() -> ActionContext:
    """Minimal context: session is unused by ``execute_step``, only forwarded."""
    return ActionContext(
        session=cast(AsyncSession, None),
        run_id=1,
        step_id="s1",
        workspace_id=1,
        creator_user_id=None,
    )


async def test_execute_step_runs_registered_action_handler_and_wraps_result(
    isolated_action_registry: None,
) -> None:
    """A step pointing at a registered action runs its handler with the
    step's params and returns a ``succeeded`` entry carrying the handler's
    output plus ``attempts=1`` (one try, no retries triggered)."""
    invocations: list[dict[str, Any]] = []

    async def echo(params: dict[str, Any]) -> dict[str, Any]:
        invocations.append(params)
        return {"echoed": params["value"]}

    register_action(
        ActionDefinition(
            type="test_echo",
            name="Echo",
            description="Test action.",
            params_model=_AnyParams,
            build_handler=lambda _ctx: echo,
        )
    )

    step = PlanStep(step_id="s1", action="test_echo", params={"value": "hello"})

    result = await execute_step(
        step=step,
        template_context={},
        action_context=_action_context(),
        default_max_retries=0,
        default_retry_backoff="none",
        default_timeout_seconds=30,
    )

    assert result["status"] == "succeeded"
    assert result["step_id"] == "s1"
    assert result["action"] == "test_echo"
    assert result["attempts"] == 1
    assert result["result"] == {"echoed": "hello"}
    assert invocations == [{"value": "hello"}]


async def test_execute_step_skips_step_when_predicate_is_falsy(
    isolated_action_registry: None,
) -> None:
    """If ``step.when`` evaluates to falsy in the template context, the
    handler is **not** invoked, the result entry has ``status=skipped``
    and ``attempts=0``, and no ``result`` key is present."""
    invoked = False

    async def must_not_run(_params: dict[str, Any]) -> dict[str, Any]:
        nonlocal invoked
        invoked = True
        return {}

    register_action(
        ActionDefinition(
            type="test_guarded",
            name="Guarded",
            description="Test action that should not run.",
            params_model=_AnyParams,
            build_handler=lambda _ctx: must_not_run,
        )
    )

    step = PlanStep(
        step_id="s1",
        action="test_guarded",
        when="inputs.enabled",
        params={},
    )

    result = await execute_step(
        step=step,
        template_context={"inputs": {"enabled": False}},
        action_context=_action_context(),
        default_max_retries=0,
        default_retry_backoff="none",
        default_timeout_seconds=30,
    )

    assert result["status"] == "skipped"
    assert result["attempts"] == 0
    assert "result" not in result
    assert invoked is False


async def test_execute_step_fails_when_step_references_an_unknown_action(
    isolated_action_registry: None,
) -> None:
    """A step pointing at an action that isn't in the registry must fail
    with ``ActionNotFound`` rather than crashing. Catches typos in the
    plan and removed actions without the run going off the rails."""
    step = PlanStep(step_id="s1", action="no_such_action", params={})

    result = await execute_step(
        step=step,
        template_context={},
        action_context=_action_context(),
        default_max_retries=0,
        default_retry_backoff="none",
        default_timeout_seconds=30,
    )

    assert result["status"] == "failed"
    assert result["attempts"] == 0
    assert result["error"]["type"] == "ActionNotFound"
    assert "no_such_action" in result["error"]["message"]


async def test_execute_step_retries_failing_handler_up_to_default_budget(
    isolated_action_registry: None,
) -> None:
    """A handler that raises on every attempt consumes the retry budget
    (1 initial try + ``default_max_retries`` retries) and the step ends
    ``failed`` with the exception's type and message surfaced through
    the error envelope."""
    calls = 0

    async def always_fails(_params: dict[str, Any]) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        raise RuntimeError("boom")

    register_action(
        ActionDefinition(
            type="test_fails",
            name="Fails",
            description="Always raises.",
            params_model=_AnyParams,
            build_handler=lambda _ctx: always_fails,
        )
    )

    step = PlanStep(step_id="s1", action="test_fails", params={})

    result = await execute_step(
        step=step,
        template_context={},
        action_context=_action_context(),
        default_max_retries=2,
        default_retry_backoff="none",
        default_timeout_seconds=30,
    )

    assert result["status"] == "failed"
    assert result["attempts"] == 3
    assert calls == 3
    assert result["error"]["type"] == "RuntimeError"
    assert "boom" in result["error"]["message"]


async def test_execute_step_succeeds_when_handler_recovers_within_retry_budget(
    isolated_action_registry: None,
) -> None:
    """A handler that fails the first N times and then succeeds yields a
    ``succeeded`` entry with ``attempts == N + 1``. Locks that retries
    can actually recover (not just exhaust)."""
    calls = 0

    async def flaky(_params: dict[str, Any]) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise RuntimeError("transient")
        return {"ok": True}

    register_action(
        ActionDefinition(
            type="test_flaky",
            name="Flaky",
            description="Fails twice, succeeds third time.",
            params_model=_AnyParams,
            build_handler=lambda _ctx: flaky,
        )
    )

    step = PlanStep(step_id="s1", action="test_flaky", params={})

    result = await execute_step(
        step=step,
        template_context={},
        action_context=_action_context(),
        default_max_retries=2,
        default_retry_backoff="none",
        default_timeout_seconds=30,
    )

    assert result["status"] == "succeeded"
    assert result["attempts"] == 3
    assert result["result"] == {"ok": True}
    assert calls == 3


async def test_execute_step_renders_step_params_through_template_engine(
    isolated_action_registry: None,
) -> None:
    """Step params are rendered against the template context before the
    handler is invoked. String values containing Jinja expressions get
    substituted from ``inputs`` and ``steps`` in the run context."""
    received: list[dict[str, Any]] = []

    async def capture(params: dict[str, Any]) -> dict[str, Any]:
        received.append(params)
        return {}

    register_action(
        ActionDefinition(
            type="test_capture",
            name="Capture",
            description="Captures the params passed in.",
            params_model=_AnyParams,
            build_handler=lambda _ctx: capture,
        )
    )

    step = PlanStep(
        step_id="s1",
        action="test_capture",
        params={"message": "Hello {{ inputs.name }}"},
    )

    await execute_step(
        step=step,
        template_context={"inputs": {"name": "World"}, "steps": {}},
        action_context=_action_context(),
        default_max_retries=0,
        default_retry_backoff="none",
        default_timeout_seconds=30,
    )

    assert received == [{"message": "Hello World"}]
