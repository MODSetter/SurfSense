"""Resolve the auto-pin for the *initial* turn config.

Auto-pin (``selected_llm_config_id=0``) picks the best eligible LLM config for
this thread / search space / user, optionally filtered to vision-capable
configs when the turn carries images.

Errors classified here:

  * ``MODEL_DOES_NOT_SUPPORT_IMAGE_INPUT`` — the auto-pin pool has no
    vision-capable cfg for an image-bearing turn. The same gate fires later
    in ``llm_capability`` for explicit selections; mapping both to the same
    code keeps the FE error UI consistent.
  * ``SERVER_ERROR`` — any other ``ValueError`` from the resolver.

This module owns *initial* pin resolution; the rate-limit recovery loop has
its own narrower auto-pin call (with ``exclude_config_ids``) in
``flows/shared/rate_limit_recovery``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.observability import otel as ot
from app.services.auto_model_pin_service import resolve_or_get_pinned_llm_config_id


@dataclass
class AutoPinResult:
    """Outcome of ``resolve_initial_auto_pin``.

    ``llm_config_id`` is set when ``error`` is ``None``; ``error`` carries the
    classified user-facing message plus error code/kind so the orchestrator can
    emit one terminal-error SSE frame.
    """

    llm_config_id: int | None
    error: tuple[str, str, Literal["user_error", "server_error"]] | None


async def resolve_initial_auto_pin(
    session: AsyncSession,
    *,
    chat_id: int,
    search_space_id: int,
    user_id: str | None,
    selected_llm_config_id: int,
    requires_image_input: bool,
    requested_llm_config_id: int,
) -> AutoPinResult:
    """Run the resolver and classify any ``ValueError`` for the SSE error path."""
    try:
        pinned = await resolve_or_get_pinned_llm_config_id(
            session,
            thread_id=chat_id,
            search_space_id=search_space_id,
            user_id=user_id,
            selected_llm_config_id=selected_llm_config_id,
            requires_image_input=requires_image_input,
        )
        ot.add_event(
            "model.pin.resolved",
            {
                "pin.requested_id": requested_llm_config_id,
                "pin.resolved_id": pinned.resolved_llm_config_id,
                "pin.requires_image_input": requires_image_input,
            },
        )
        return AutoPinResult(llm_config_id=pinned.resolved_llm_config_id, error=None)
    except ValueError as pin_error:
        # The "no vision-capable cfg" path raises a ValueError whose message
        # we map to the friendly image-input SSE error so the user sees the
        # same message regardless of whether the gate fired in the resolver or
        # in ``llm_capability.assert_vision_capability_for_image_turn``.
        is_vision_failure = requires_image_input and "vision-capable" in str(pin_error)
        error_code = (
            "MODEL_DOES_NOT_SUPPORT_IMAGE_INPUT"
            if is_vision_failure
            else "SERVER_ERROR"
        )
        error_kind: Literal["user_error", "server_error"] = (
            "user_error" if is_vision_failure else "server_error"
        )
        if is_vision_failure:
            ot.add_event("quota.denied", {"quota.code": error_code})
        return AutoPinResult(
            llm_config_id=None, error=(str(pin_error), error_code, error_kind)
        )
