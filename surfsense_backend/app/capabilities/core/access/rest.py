"""Generate the REST door from the capability registry (05).

One typed ``POST`` per verb under ``/workspaces/{id}/scrapers/{platform}/{verb}``;
each runs the same thin adapter: authn -> workspace authz -> meter-gate -> executor
-> charge -> typed output. Every request is recorded to the ``runs`` table
(best-effort) and its id returned via the ``X-Run-Id`` header. Two ``GET`` routes
expose the run history that backs the Scraper-API logs UI.
"""

import time
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.capabilities.core.access.rate_limit import enforce_capability_rate_limit
from app.capabilities.core.billing import charge_capability, gate_capability
from app.capabilities.core.runs import record_run, serialize_output
from app.capabilities.core.store import all_capabilities
from app.capabilities.core.types import Capability, CapabilityContext
from app.db import Run, async_session_maker, get_async_session
from app.exceptions import ExternalServiceError, SurfSenseError
from app.services.web_crawl_credit_service import InsufficientCreditsError
from app.users import get_auth_context
from app.utils.rbac import check_workspace_access


class RunSummary(BaseModel):
    """Metadata row for the runs list (output body omitted)."""

    id: str
    capability: str
    origin: str
    status: str
    item_count: int
    char_count: int
    duration_ms: int | None
    cost_micros: int | None
    error: str | None
    created_at: datetime


class RunDetail(RunSummary):
    """Full run including input and stored output."""

    thread_id: str | None
    input: dict | None
    output_text: str | None


def _origin_for(auth: AuthContext) -> str:
    """Session callers are the in-app UI; PAT/system callers are the public API."""
    return "ui" if getattr(auth, "method", None) == "session" else "api"


async def _record_rest_run(**kwargs) -> str | None:
    """Record a run on a dedicated session so it survives a failed request txn."""
    async with async_session_maker() as session:
        return await record_run(session, **kwargs)


def build_capabilities_router(
    capabilities: list[Capability] | None = None,
) -> APIRouter:
    """Emit one typed route per verb (defaults to the whole registry) + run history."""
    router = APIRouter(tags=["scrapers"])
    caps = capabilities if capabilities is not None else all_capabilities()
    for capability in caps:
        _register_verb(router, capability)
    _register_run_history(router)
    return router


def _register_verb(router: APIRouter, capability: Capability) -> None:
    input_model = capability.input_schema
    output_model = capability.output_schema
    unit = capability.billing_unit
    executor = capability.executor
    name = capability.name
    platform, _, verb = name.partition(".")

    async def endpoint(
        workspace_id: int,
        payload: input_model,
        response: Response,
        session: AsyncSession = Depends(get_async_session),
        auth: AuthContext = Depends(get_auth_context),
    ):
        await check_workspace_access(session, auth, workspace_id)
        ctx = CapabilityContext(session=session, workspace_id=workspace_id)
        try:
            await gate_capability(payload, unit, ctx)
        except InsufficientCreditsError as exc:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={
                    "error_code": "insufficient_credits",
                    "message": str(exc),
                    "balance_micros": exc.balance_micros,
                    "required_micros": exc.required_micros,
                },
            ) from exc

        input_dump = payload.model_dump(exclude_none=True)
        user_id = getattr(auth.user, "id", None)
        origin = _origin_for(auth)
        started = time.perf_counter()
        try:
            output = await executor(payload)
        except (SurfSenseError, HTTPException) as exc:
            await _record_rest_run(
                workspace_id=workspace_id,
                capability=name,
                origin=origin,
                status="error",
                input=input_dump,
                user_id=user_id,
                error=str(exc),
                duration_ms=int((time.perf_counter() - started) * 1000),
            )
            raise
        except Exception as exc:
            await _record_rest_run(
                workspace_id=workspace_id,
                capability=name,
                origin=origin,
                status="error",
                input=input_dump,
                user_id=user_id,
                error=str(exc),
                duration_ms=int((time.perf_counter() - started) * 1000),
            )
            raise ExternalServiceError(
                f"The '{name}' capability failed due to an upstream error.",
                code="CAPABILITY_UPSTREAM_ERROR",
            ) from exc

        duration_ms = int((time.perf_counter() - started) * 1000)
        await charge_capability(output, unit, ctx)

        serialized = serialize_output(output)
        run_id = await _record_rest_run(
            workspace_id=workspace_id,
            capability=name,
            origin=origin,
            status="success",
            serialized=serialized,
            input=input_dump,
            user_id=user_id,
            duration_ms=duration_ms,
        )
        if run_id is not None:
            response.headers["X-Run-Id"] = f"run_{run_id}"
        return output

    router.add_api_route(
        f"/workspaces/{{workspace_id}}/scrapers/{platform}/{verb}",
        endpoint,
        methods=["POST"],
        response_model=output_model,
        name=f"scraper:{name}",
        dependencies=[Depends(enforce_capability_rate_limit)],
    )


def _register_run_history(router: APIRouter) -> None:
    """Register the ``GET`` list + detail routes that back the logs UI."""

    async def list_runs(
        workspace_id: int,
        session: AsyncSession = Depends(get_async_session),
        auth: AuthContext = Depends(get_auth_context),
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        capability: str | None = Query(default=None),
        run_status: str | None = Query(default=None, alias="status"),
    ) -> list[RunSummary]:
        await check_workspace_access(session, auth, workspace_id)
        stmt = select(Run).where(Run.workspace_id == workspace_id)
        if capability:
            stmt = stmt.where(Run.capability == capability)
        if run_status:
            stmt = stmt.where(Run.status == run_status)
        stmt = stmt.order_by(Run.created_at.desc()).limit(limit).offset(offset)
        rows = (await session.execute(stmt)).scalars().all()
        return [_to_summary(row) for row in rows]

    async def get_run(
        workspace_id: int,
        run_id: str,
        session: AsyncSession = Depends(get_async_session),
        auth: AuthContext = Depends(get_auth_context),
    ) -> RunDetail:
        await check_workspace_access(session, auth, workspace_id)
        raw_id = run_id[len("run_") :] if run_id.startswith("run_") else run_id
        try:
            parsed_id = uuid.UUID(raw_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Run not found."
            ) from exc
        row = (
            await session.execute(
                select(Run).where(
                    Run.id == parsed_id, Run.workspace_id == workspace_id
                )
            )
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Run not found."
            )
        return _to_detail(row)

    router.add_api_route(
        "/workspaces/{workspace_id}/scrapers/runs",
        list_runs,
        methods=["GET"],
        response_model=list[RunSummary],
        name="scraper:list_runs",
    )
    router.add_api_route(
        "/workspaces/{workspace_id}/scrapers/runs/{run_id}",
        get_run,
        methods=["GET"],
        response_model=RunDetail,
        name="scraper:get_run",
    )


def _to_summary(row: Run) -> RunSummary:
    return RunSummary(
        id=f"run_{row.id}",
        capability=row.capability,
        origin=row.origin,
        status=row.status,
        item_count=row.item_count,
        char_count=row.char_count,
        duration_ms=row.duration_ms,
        cost_micros=row.cost_micros,
        error=row.error,
        created_at=row.created_at,
    )


def _to_detail(row: Run) -> RunDetail:
    return RunDetail(
        **_to_summary(row).model_dump(),
        thread_id=row.thread_id,
        input=row.input,
        output_text=row.output_text,
    )
