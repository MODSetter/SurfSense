"""Execute one plan step: when-predicate, params render, handler dispatch, retries."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from app.automations.registries import get_action
from app.automations.registries.actions.types import ActionContext
from app.automations.schemas.definition.plan_step import PlanStep
from app.automations.templating import evaluate_predicate, render_value

from .retries import with_retries


async def execute_step(
    *,
    step: PlanStep,
    template_context: Mapping[str, Any],
    action_context: ActionContext,
    default_max_retries: int,
    default_retry_backoff: str,
    default_timeout_seconds: int,
) -> dict[str, Any]:
    """Run one step and return its structured result entry."""
    started_at = datetime.now(UTC)

    if step.when is not None:
        try:
            should_run = evaluate_predicate(step.when, template_context)
        except Exception as exc:
            return _result(step, "failed", started_at, attempts=0, error=_error(exc, "when"))
        if not should_run:
            return _result(step, "skipped", started_at, attempts=0)

    try:
        resolved_params = render_value(step.params, template_context)
    except Exception as exc:
        return _result(step, "failed", started_at, attempts=0, error=_error(exc, "render"))

    action = get_action(step.action)
    if action is None:
        return _result(
            step,
            "failed",
            started_at,
            attempts=0,
            error={"message": f"action not registered: {step.action}", "type": "ActionNotFound"},
        )

    handler = action.build_handler(action_context)

    max_retries = step.max_retries if step.max_retries is not None else default_max_retries
    timeout = step.timeout_seconds or default_timeout_seconds

    try:
        result, attempts = await with_retries(
            lambda: handler(resolved_params),
            max_retries=max_retries,
            backoff=default_retry_backoff,
            timeout=timeout,
        )
    except Exception as exc:
        return _result(step, "failed", started_at, attempts=max_retries + 1, error=_error(exc))

    return _result(step, "succeeded", started_at, attempts=attempts, result=result)


def _result(
    step: PlanStep,
    status: str,
    started_at: datetime,
    *,
    attempts: int,
    result: Any = None,
    error: dict[str, Any] | None = None,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "step_id": step.step_id,
        "action": step.action,
        "status": status,
        "started_at": started_at.isoformat(),
        "finished_at": datetime.now(UTC).isoformat(),
        "attempts": attempts,
    }
    if result is not None:
        entry["result"] = result
    if error is not None:
        entry["error"] = error
    return entry


def _error(exc: Exception, phase: str | None = None) -> dict[str, Any]:
    msg = f"{phase}: {exc}" if phase else str(exc)
    return {"message": msg, "type": type(exc).__name__}
