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
from app.services.token_tracking_service import record_token_usage
from app.services.web_crawl_credit_service import WebCrawlCreditService

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
    service = WebCrawlCreditService(ctx.session)
    if not service.billing_enabled():
        return
    owner_user_id = await _resolve_workspace_owner(ctx.session, ctx.workspace_id)
    if owner_user_id is None:
        return
    await service.check_credits(owner_user_id, estimated_successes)


async def charge_capability(
    output: BillableOutput, unit: BillingUnit | None, ctx: CapabilityContext
) -> None:
    """Bill the workspace owner for this result's billable successes (03c). ``None`` = free."""
    if unit is None:
        return
    units = output.billable_units
    if units <= 0:
        return
    if unit is BillingUnit.WEB_CRAWL:
        await _charge_web_crawl(ctx, units)


async def _charge_web_crawl(ctx: CapabilityContext, successes: int) -> None:
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


async def _resolve_workspace_owner(
    session: AsyncSession, workspace_id: int
) -> UUID | None:
    """The ``user_id`` that owns ``workspace_id`` (the crawl payer, not the caller)."""
    from app.db import Workspace

    result = await session.execute(
        select(Workspace.user_id).where(Workspace.id == workspace_id)
    )
    return result.scalar_one_or_none()
