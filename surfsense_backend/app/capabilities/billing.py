"""Charge the workspace owner per billable success at the capability executor (03c)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from app.capabilities.types import (
    BillableInput,
    BillableOutput,
    BillingUnit,
    CapabilityContext,
)
from app.config import config
from app.services.token_tracking_service import record_token_usage
from app.services.web_crawl_credit_service import WebCrawlCreditService
from app.utils.captcha import captcha_enabled

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession


async def gate_capability(
    payload: BillableInput, unit: BillingUnit | None, ctx: CapabilityContext
) -> None:
    """Pre-flight: block an over-budget owner before the executor runs (03c).

    Raises ``InsufficientCreditsError`` when the wallet can't cover the input's
    worst-case ``estimated_units``. ``None`` unit = free = no gate.
    """
    if unit is None:
        return
    if unit is BillingUnit.WEB_CRAWL:
        await _gate_web_crawl(ctx, payload.estimated_units)


async def _gate_web_crawl(ctx: CapabilityContext, estimated_successes: int) -> None:
    """Reserve the worst-case cost: crawl successes + worst-case captcha attempts.

    Captcha budget is only reserved when solving is actually enabled — with
    solving off, attempts can never happen, so reserving would wrongly block a
    run for captcha that will never be attempted. Mirrors the indexer path (3d).
    """
    service = WebCrawlCreditService(ctx.session)
    crawl_on = service.billing_enabled()
    captcha_on = service.captcha_billing_enabled() and captcha_enabled()
    if not crawl_on and not captcha_on:
        return
    owner_user_id = await _resolve_workspace_owner(ctx.session, ctx.workspace_id)
    if owner_user_id is None:
        return

    required_micros = 0
    if crawl_on:
        required_micros += service.successes_to_micros(estimated_successes)
    if captcha_on:
        worst_case_attempts = estimated_successes * config.CAPTCHA_MAX_ATTEMPTS_PER_URL
        required_micros += service.captcha_solves_to_micros(worst_case_attempts)
    await service.check_balance(owner_user_id, required_micros)


async def charge_capability(
    output: BillableOutput, unit: BillingUnit | None, ctx: CapabilityContext
) -> None:
    """Bill the workspace owner for this result's billable successes (03c). ``None`` = free.

    For crawl-backed verbs this also bills any captcha *attempts* (Phase 3d) as a
    separate per-attempt unit — the solver charges per attempt even when the crawl
    ultimately failed, so it can't ride the per-success crawl meter.
    """
    if unit is None:
        return
    if unit is BillingUnit.WEB_CRAWL:
        await _charge_web_crawl(ctx, output.billable_units)
        await _charge_captcha(ctx, getattr(output, "captcha_attempts", 0))


async def _charge_web_crawl(ctx: CapabilityContext, successes: int) -> None:
    if successes <= 0:
        return
    service = WebCrawlCreditService(ctx.session)
    if not service.billing_enabled():
        return
    owner_user_id = await _resolve_workspace_owner(ctx.session, ctx.workspace_id)
    if owner_user_id is None:
        return
    # Stage the audit row before charge_credits' commit flushes both.
    await record_token_usage(
        ctx.session,
        usage_type="web_crawl",
        workspace_id=ctx.workspace_id,
        user_id=owner_user_id,
        cost_micros=service.successes_to_micros(successes),
        call_details={"successes": successes},
    )
    await service.charge_credits(owner_user_id, successes)


async def _charge_captcha(ctx: CapabilityContext, attempts: int) -> None:
    if attempts <= 0:
        return
    service = WebCrawlCreditService(ctx.session)
    if not service.captcha_billing_enabled():
        return
    owner_user_id = await _resolve_workspace_owner(ctx.session, ctx.workspace_id)
    if owner_user_id is None:
        return
    # Stage the audit row before charge_captcha's commit flushes both.
    await record_token_usage(
        ctx.session,
        usage_type="web_crawl_captcha",
        workspace_id=ctx.workspace_id,
        user_id=owner_user_id,
        cost_micros=service.captcha_solves_to_micros(attempts),
        call_details={"attempts": attempts},
    )
    await service.charge_captcha(owner_user_id, attempts)


async def _resolve_workspace_owner(
    session: AsyncSession, workspace_id: int
) -> UUID | None:
    """The ``user_id`` that owns ``workspace_id`` (the crawl payer, not the caller)."""
    from app.db import Workspace

    result = await session.execute(
        select(Workspace.user_id).where(Workspace.id == workspace_id)
    )
    return result.scalar_one_or_none()
