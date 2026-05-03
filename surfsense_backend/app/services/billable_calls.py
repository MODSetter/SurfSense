"""
Per-call billable wrapper for image generation, vision LLM extraction, and
any other short-lived premium operation that must charge against the user's
shared premium credit pool.

The ``billable_call`` async context manager encapsulates the standard
"reserve → execute → finalize / release → record audit row" lifecycle in a
single primitive so callers (the image-generation REST route and the
vision-LLM wrapper used during indexing) don't have to re-implement it.

KEY DESIGN POINTS (issue A, B):

1. **Session isolation.** ``billable_call`` takes no caller transaction.
   All ``TokenQuotaService.premium_*`` calls and the audit-row insert run
   inside their own session context. Route callers use
   ``shielded_async_session()`` by default; Celery callers can provide a
   worker-loop-safe session factory. This guarantees that quota
   commit/rollback can never accidentally flush or roll back rows the caller
   has staged in its main session (e.g. a freshly-created
   ``ImageGeneration`` row).

2. **ContextVar safety.** The accumulator is scoped via
   :func:`scoped_turn` (which uses ``ContextVar.reset(token)``), so a
   nested ``billable_call`` inside an outer chat turn cannot corrupt the
   chat turn's accumulator.

3. **Free configs are still audited.** Free calls bypass the reserve /
   finalize dance entirely but still record a ``TokenUsage`` audit row with
   the LiteLLM-reported ``cost_micros``. This keeps the cost-attribution
   pipeline complete for analytics even when nothing is debited.

4. **Quota denial raises ``QuotaInsufficientError``.** The route handler is
   responsible for translating that into HTTP 402. We *do not* catch the
   denial inside ``billable_call`` — letting it propagate also prevents
   the image-generation route from creating an ``ImageGeneration`` row
   for a request that never actually ran.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager, suppress
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import shielded_async_session
from app.services.token_quota_service import (
    TokenQuotaService,
    estimate_call_reserve_micros,
)
from app.services.token_tracking_service import (
    TurnTokenAccumulator,
    record_token_usage,
    scoped_turn,
)

logger = logging.getLogger(__name__)

AUDIT_TIMEOUT_SECONDS = 10.0
BACKGROUND_ARTIFACT_USAGE_TYPES = frozenset(
    {"video_presentation_generation", "podcast_generation"}
)
BillableSessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


class QuotaInsufficientError(Exception):
    """Raised when ``TokenQuotaService.premium_reserve`` denies a billable
    call because the user has exhausted their premium credit pool.

    The route handler should catch this and return HTTP 402 Payment
    Required (or the equivalent for the surface area). Outside of the HTTP
    layer (e.g. the ``QuotaCheckedVisionLLM`` wrapper used during indexing)
    callers may catch this and degrade gracefully — e.g. fall back to OCR
    when vision is unavailable.
    """

    def __init__(
        self,
        *,
        usage_type: str,
        used_micros: int,
        limit_micros: int,
        remaining_micros: int,
    ) -> None:
        self.usage_type = usage_type
        self.used_micros = used_micros
        self.limit_micros = limit_micros
        self.remaining_micros = remaining_micros
        super().__init__(
            f"Premium credit exhausted for {usage_type}: "
            f"used={used_micros} limit={limit_micros} remaining={remaining_micros} (micro-USD)"
        )


class BillingSettlementError(Exception):
    """Raised when a premium call completed but credit settlement failed."""

    def __init__(self, *, usage_type: str, user_id: UUID, cause: Exception) -> None:
        self.usage_type = usage_type
        self.user_id = user_id
        super().__init__(
            f"Failed to settle premium credit for {usage_type} user={user_id}: {cause}"
        )


async def _rollback_safely(session: AsyncSession) -> None:
    rollback = getattr(session, "rollback", None)
    if rollback is not None:
        with suppress(Exception):
            await rollback()


async def _record_audit_best_effort(
    *,
    session_factory: BillableSessionFactory,
    usage_type: str,
    search_space_id: int,
    user_id: UUID,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    cost_micros: int,
    model_breakdown: dict[str, Any],
    call_details: dict[str, Any] | None,
    thread_id: int | None,
    message_id: int | None,
    audit_label: str,
    timeout_seconds: float = AUDIT_TIMEOUT_SECONDS,
) -> None:
    """Persist a TokenUsage row without letting audit failure block callers.

    Premium settlement is mandatory, but TokenUsage is an audit trail. If the
    audit insert or commit hangs, user-facing artifacts such as videos and
    podcasts must still be able to transition to READY after settlement.
    """
    audit_thread_id = (
        None if usage_type in BACKGROUND_ARTIFACT_USAGE_TYPES else thread_id
    )

    async def _persist() -> None:
        logger.info(
            "[billable_call] audit start label=%s usage_type=%s user=%s thread=%s "
            "total_tokens=%d cost_micros=%d",
            audit_label,
            usage_type,
            user_id,
            audit_thread_id,
            total_tokens,
            cost_micros,
        )
        async with session_factory() as audit_session:
            try:
                await record_token_usage(
                    audit_session,
                    usage_type=usage_type,
                    search_space_id=search_space_id,
                    user_id=user_id,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    cost_micros=cost_micros,
                    model_breakdown=model_breakdown,
                    call_details=call_details,
                    thread_id=audit_thread_id,
                    message_id=message_id,
                )
                logger.info(
                    "[billable_call] audit row staged label=%s usage_type=%s user=%s thread=%s",
                    audit_label,
                    usage_type,
                    user_id,
                    audit_thread_id,
                )
                await audit_session.commit()
                logger.info(
                    "[billable_call] audit commit OK label=%s usage_type=%s user=%s thread=%s",
                    audit_label,
                    usage_type,
                    user_id,
                    audit_thread_id,
                )
            except BaseException:
                await _rollback_safely(audit_session)
                raise

    try:
        await asyncio.wait_for(_persist(), timeout=timeout_seconds)
    except TimeoutError:
        logger.warning(
            "[billable_call] audit timed out label=%s usage_type=%s user=%s thread=%s "
            "timeout=%.1fs total_tokens=%d cost_micros=%d",
            audit_label,
            usage_type,
            user_id,
            audit_thread_id,
            timeout_seconds,
            total_tokens,
            cost_micros,
        )
    except Exception:
        logger.exception(
            "[billable_call] audit failed label=%s usage_type=%s user=%s thread=%s "
            "total_tokens=%d cost_micros=%d",
            audit_label,
            usage_type,
            user_id,
            audit_thread_id,
            total_tokens,
            cost_micros,
        )


@asynccontextmanager
async def billable_call(
    *,
    user_id: UUID,
    search_space_id: int,
    billing_tier: str,
    base_model: str,
    quota_reserve_tokens: int | None = None,
    quota_reserve_micros_override: int | None = None,
    usage_type: str,
    thread_id: int | None = None,
    message_id: int | None = None,
    call_details: dict[str, Any] | None = None,
    billable_session_factory: BillableSessionFactory | None = None,
    audit_timeout_seconds: float = AUDIT_TIMEOUT_SECONDS,
) -> AsyncIterator[TurnTokenAccumulator]:
    """Wrap a single billable LLM/image call.

    Args:
        user_id: Owner of the credit pool to debit. For vision-LLM during
            indexing this is the *search-space owner* (issue M), not the
            triggering user.
        search_space_id: Required — recorded on the ``TokenUsage`` audit row.
        billing_tier: ``"premium"`` debits; anything else (``"free"``) skips
            the reserve/finalize dance but still records an audit row with
            the captured cost.
        base_model: Used by :func:`estimate_call_reserve_micros` to compute
            a worst-case reservation from LiteLLM's pricing table.
        quota_reserve_tokens: Optional per-config override for the chat-style
            reserve estimator (vision LLM uses this).
        quota_reserve_micros_override: Optional flat micro-USD reservation
            (image generation uses this — its cost shape is per-image, not
            per-token).
        usage_type: ``"image_generation"`` / ``"vision_extraction"`` / etc.
            Recorded on the ``TokenUsage`` row.
        thread_id, message_id: Optional FK columns on ``TokenUsage``.
        call_details: Optional per-call metadata (model name, parameters)
            forwarded to ``record_token_usage``.
        billable_session_factory: Optional async context factory used for
            reserve/finalize/release/audit sessions. Defaults to
            ``shielded_async_session`` for route callers; Celery callers pass
            a worker-loop-safe session factory.
        audit_timeout_seconds: Upper bound for TokenUsage audit persistence.
            Audit failure is best-effort and does not undo successful
            settlement.

    Yields:
        The ``TurnTokenAccumulator`` scoped to this call. The caller invokes
        the underlying LLM/image API while inside the ``async with``; the
        ``TokenTrackingCallback`` populates the accumulator automatically.

    Raises:
        QuotaInsufficientError: when premium and ``premium_reserve`` denies.
    """
    is_premium = billing_tier == "premium"
    session_factory = billable_session_factory or shielded_async_session

    async with scoped_turn() as acc:
        # ---------- Free path: just audit -------------------------------
        if not is_premium:
            try:
                yield acc
            finally:
                # Always audit, even on exception, so we capture cost when
                # provider returns successfully but the caller raises later.
                await _record_audit_best_effort(
                    session_factory=session_factory,
                    usage_type=usage_type,
                    search_space_id=search_space_id,
                    user_id=user_id,
                    prompt_tokens=acc.total_prompt_tokens,
                    completion_tokens=acc.total_completion_tokens,
                    total_tokens=acc.grand_total,
                    cost_micros=acc.total_cost_micros,
                    model_breakdown=acc.per_message_summary(),
                    call_details=call_details,
                    thread_id=thread_id,
                    message_id=message_id,
                    audit_label="free",
                    timeout_seconds=audit_timeout_seconds,
                )
            return

        # ---------- Premium path: reserve → execute → finalize ----------
        if quota_reserve_micros_override is not None:
            reserve_micros = max(1, int(quota_reserve_micros_override))
        else:
            reserve_micros = estimate_call_reserve_micros(
                base_model=base_model or "",
                quota_reserve_tokens=quota_reserve_tokens,
            )

        request_id = str(uuid4())

        async with session_factory() as quota_session:
            reserve_result = await TokenQuotaService.premium_reserve(
                db_session=quota_session,
                user_id=user_id,
                request_id=request_id,
                reserve_micros=reserve_micros,
            )

        if not reserve_result.allowed:
            logger.info(
                "[billable_call] reserve DENIED user=%s usage_type=%s "
                "reserve=%d used=%d limit=%d remaining=%d",
                user_id,
                usage_type,
                reserve_micros,
                reserve_result.used,
                reserve_result.limit,
                reserve_result.remaining,
            )
            raise QuotaInsufficientError(
                usage_type=usage_type,
                used_micros=reserve_result.used,
                limit_micros=reserve_result.limit,
                remaining_micros=reserve_result.remaining,
            )

        logger.info(
            "[billable_call] reserve OK user=%s usage_type=%s reserve_micros=%d "
            "(remaining=%d)",
            user_id,
            usage_type,
            reserve_micros,
            reserve_result.remaining,
        )

        try:
            yield acc
        except BaseException:
            # Release on any failure (including QuotaInsufficientError raised
            # from a downstream call, asyncio cancellation, etc.). We use
            # BaseException so cancellation also releases.
            try:
                async with session_factory() as quota_session:
                    await TokenQuotaService.premium_release(
                        db_session=quota_session,
                        user_id=user_id,
                        reserved_micros=reserve_micros,
                    )
            except Exception:
                logger.exception(
                    "[billable_call] premium_release failed for user=%s "
                    "reserve_micros=%d (reservation will be GC'd by quota "
                    "reconciliation if/when implemented)",
                    user_id,
                    reserve_micros,
                )
            raise

        # ---------- Success: finalize + audit ----------------------------
        actual_micros = acc.total_cost_micros
        try:
            logger.info(
                "[billable_call] finalize start user=%s usage_type=%s actual=%d "
                "reserved=%d thread=%s",
                user_id,
                usage_type,
                actual_micros,
                reserve_micros,
                thread_id,
            )
            async with session_factory() as quota_session:
                final_result = await TokenQuotaService.premium_finalize(
                    db_session=quota_session,
                    user_id=user_id,
                    request_id=request_id,
                    actual_micros=actual_micros,
                    reserved_micros=reserve_micros,
                )
            logger.info(
                "[billable_call] finalize user=%s usage_type=%s actual=%d "
                "reserved=%d → used=%d/%d (remaining=%d)",
                user_id,
                usage_type,
                actual_micros,
                reserve_micros,
                final_result.used,
                final_result.limit,
                final_result.remaining,
            )
        except Exception as finalize_exc:
            # Last-ditch: if finalize itself fails, we must at least release
            # so the reservation doesn't leak.
            logger.exception(
                "[billable_call] premium_finalize failed for user=%s; "
                "attempting release",
                user_id,
            )
            try:
                async with session_factory() as quota_session:
                    await TokenQuotaService.premium_release(
                        db_session=quota_session,
                        user_id=user_id,
                        reserved_micros=reserve_micros,
                    )
            except Exception:
                logger.exception(
                    "[billable_call] release after finalize failure ALSO failed "
                    "for user=%s",
                    user_id,
                )
            raise BillingSettlementError(
                usage_type=usage_type,
                user_id=user_id,
                cause=finalize_exc,
            ) from finalize_exc

        await _record_audit_best_effort(
            session_factory=session_factory,
            usage_type=usage_type,
            search_space_id=search_space_id,
            user_id=user_id,
            prompt_tokens=acc.total_prompt_tokens,
            completion_tokens=acc.total_completion_tokens,
            total_tokens=acc.grand_total,
            cost_micros=actual_micros,
            model_breakdown=acc.per_message_summary(),
            call_details=call_details,
            thread_id=thread_id,
            message_id=message_id,
            audit_label="premium",
            timeout_seconds=audit_timeout_seconds,
        )


async def _resolve_agent_billing_for_search_space(
    session: AsyncSession,
    search_space_id: int,
    *,
    thread_id: int | None = None,
) -> tuple[UUID, str, str]:
    """Resolve ``(owner_user_id, billing_tier, base_model)`` for the search-space
    agent LLM.

    Used by Celery tasks (podcast generation, video presentation) to bill the
    search-space owner's premium credit pool when the agent LLM is premium.

    Resolution rules mirror chat at ``stream_new_chat.py:2294-2351``:

    - Search space not found / no ``agent_llm_id``: raise ``ValueError``.
    - **Auto mode** (``id == AUTO_FASTEST_ID == 0``):
        * ``thread_id`` is set: delegate to
          ``resolve_or_get_pinned_llm_config_id`` (the same call chat uses) and
          recurse into the resolved id. Reuses chat's existing pin if present
          so the same model bills for chat + downstream podcast/video. If the
          user is not premium-eligible, the pin service auto-restricts to free
          deployments — denial only happens later in
          ``billable_call.premium_reserve`` if the pin really is premium and
          credit ran out mid-flow.
        * ``thread_id`` is None: fallback to ``("free", "auto")``. Forward-compat
          for any future direct-API path; today both Celery tasks always pass
          ``thread_id``.
    - **Negative id** (global YAML / OpenRouter): ``cfg["billing_tier"]``
      (defaults to ``"free"`` via ``app/config/__init__.py:52`` setdefault),
      ``base_model = litellm_params.get("base_model") or model_name`` —
      NOT provider-prefixed, matching chat's cost-map lookup convention.
    - **Positive id** (user BYOK ``NewLLMConfig``): always free (matches
      ``AgentConfig.from_new_llm_config`` which hard-codes ``billing_tier="free"``);
      ``base_model`` from ``litellm_params`` or ``model_name``.

    Note on imports: ``llm_service``, ``auto_model_pin_service``, and
    ``llm_router_service`` are imported lazily inside the function body to
    avoid hoisting litellm side-effects (``litellm.callbacks =
    [token_tracker]``, ``litellm.drop_params``, etc.) into
    ``billable_calls.py``'s module load path.
    """
    from sqlalchemy import select

    from app.db import NewLLMConfig, SearchSpace

    result = await session.execute(
        select(SearchSpace).where(SearchSpace.id == search_space_id)
    )
    search_space = result.scalars().first()
    if search_space is None:
        raise ValueError(f"Search space {search_space_id} not found")

    agent_llm_id = search_space.agent_llm_id
    if agent_llm_id is None:
        raise ValueError(
            f"Search space {search_space_id} has no agent_llm_id configured"
        )

    owner_user_id: UUID = search_space.user_id

    from app.services.auto_model_pin_service import (
        AUTO_FASTEST_ID,
        resolve_or_get_pinned_llm_config_id,
    )

    if agent_llm_id == AUTO_FASTEST_ID:
        if thread_id is None:
            return owner_user_id, "free", "auto"
        try:
            resolution = await resolve_or_get_pinned_llm_config_id(
                session,
                thread_id=thread_id,
                search_space_id=search_space_id,
                user_id=str(owner_user_id),
                selected_llm_config_id=AUTO_FASTEST_ID,
            )
        except ValueError:
            logger.warning(
                "[agent_billing] Auto-mode pin resolution failed for "
                "search_space=%s thread=%s; falling back to free",
                search_space_id,
                thread_id,
                exc_info=True,
            )
            return owner_user_id, "free", "auto"
        agent_llm_id = resolution.resolved_llm_config_id

    if agent_llm_id < 0:
        from app.services.llm_service import get_global_llm_config

        cfg = get_global_llm_config(agent_llm_id) or {}
        billing_tier = str(cfg.get("billing_tier", "free")).lower()
        litellm_params = cfg.get("litellm_params") or {}
        base_model = litellm_params.get("base_model") or cfg.get("model_name") or ""
        return owner_user_id, billing_tier, base_model

    nlc_result = await session.execute(
        select(NewLLMConfig).where(
            NewLLMConfig.id == agent_llm_id,
            NewLLMConfig.search_space_id == search_space_id,
        )
    )
    nlc = nlc_result.scalars().first()
    base_model = ""
    if nlc is not None:
        litellm_params = nlc.litellm_params or {}
        base_model = litellm_params.get("base_model") or nlc.model_name or ""
    return owner_user_id, "free", base_model


__all__ = [
    "BillingSettlementError",
    "QuotaInsufficientError",
    "_resolve_agent_billing_for_search_space",
    "billable_call",
]


# Re-export the config knob so callers don't have to import config just for
# the default image reserve.
DEFAULT_IMAGE_RESERVE_MICROS = config.QUOTA_DEFAULT_IMAGE_RESERVE_MICROS
