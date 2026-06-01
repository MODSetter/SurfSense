"""Premium credit (USD micro-units) reserve / finalize / release lifecycle.

Both ``stream_new_chat`` and ``stream_resume_chat`` reserve premium credits up
front (so a single LLM call can't run away with the budget), then finalize the
actual provider cost reported by LiteLLM when the turn completes successfully,
or release the reservation on the cancellation / interrupted-without-finalize
paths.

State is held by the orchestrator as a simple ``PremiumReservation`` tuple
so reservation, fallback-on-denied, finalize, and release can all be reasoned
about from one place.
"""

from __future__ import annotations

import logging
import uuid as _uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from app.agents.new_chat.llm_config import AgentConfig
from app.db import shielded_async_session

if TYPE_CHECKING:
    from app.services.token_tracking_service import TokenAccumulator


@dataclass
class PremiumReservation:
    """Active premium-credit reservation for one turn.

    ``request_id`` is the per-reservation idempotency key (also passed to
    ``finalize``/``release`` so racing branches resolve to the same row).
    ``reserved_micros`` is the up-front estimate; ``finalize`` debits the
    actual cost, ``release`` returns it untouched.
    """

    request_id: str
    reserved_micros: int
    allowed: bool


def needs_premium_quota(agent_config: AgentConfig | None, user_id: str | None) -> bool:
    return bool(agent_config is not None and user_id and agent_config.is_premium)


async def reserve_premium(
    *,
    agent_config: AgentConfig,
    user_id: str,
) -> PremiumReservation:
    """Reserve estimated micros up front; returns the reservation handle."""
    from app.services.token_quota_service import (
        TokenQuotaService,
        estimate_call_reserve_micros,
    )

    request_id = _uuid.uuid4().hex[:16]
    litellm_params = agent_config.litellm_params or {}
    base_model = (
        (litellm_params.get("base_model") if isinstance(litellm_params, dict) else None)
        or agent_config.model_name
        or ""
    )
    reserve_amount_micros = estimate_call_reserve_micros(
        base_model=base_model,
        quota_reserve_tokens=agent_config.quota_reserve_tokens,
    )
    async with shielded_async_session() as quota_session:
        quota_result = await TokenQuotaService.premium_reserve(
            db_session=quota_session,
            user_id=UUID(user_id),
            request_id=request_id,
            reserve_micros=reserve_amount_micros,
        )
    return PremiumReservation(
        request_id=request_id,
        reserved_micros=reserve_amount_micros,
        allowed=quota_result.allowed,
    )


async def finalize_premium(
    *,
    reservation: PremiumReservation,
    user_id: str,
    accumulator: TokenAccumulator,
) -> None:
    """Finalize debit using the actual provider cost reported by LiteLLM.

    Best-effort: failures here must not bubble up to the SSE stream — the user
    has already received their tokens; we log and move on.
    """
    try:
        from app.services.token_quota_service import TokenQuotaService

        async with shielded_async_session() as quota_session:
            await TokenQuotaService.premium_finalize(
                db_session=quota_session,
                user_id=UUID(user_id),
                request_id=reservation.request_id,
                actual_micros=accumulator.total_cost_micros,
                reserved_micros=reservation.reserved_micros,
            )
    except Exception:
        logging.getLogger(__name__).warning(
            "Failed to finalize premium quota for user %s",
            user_id,
            exc_info=True,
        )


async def release_premium(
    *,
    reservation: PremiumReservation,
    user_id: str,
) -> None:
    """Release the reservation on cancellation paths; never raises."""
    try:
        from app.services.token_quota_service import TokenQuotaService

        async with shielded_async_session() as quota_session:
            await TokenQuotaService.premium_release(
                db_session=quota_session,
                user_id=UUID(user_id),
                reserved_micros=reservation.reserved_micros,
            )
    except Exception:
        logging.getLogger(__name__).warning(
            "Failed to release premium quota for user %s", user_id
        )
