"""Generate the REST door from the capability registry (05).

One typed ``POST`` per verb under ``/workspaces/{id}/scrapers/{platform}/{verb}``;
each runs the same thin adapter: authn -> workspace authz -> meter-gate -> executor
-> charge -> typed output. Every request is recorded to the ``runs`` table
(best-effort) and its id returned via the ``X-Run-Id`` header.

Runs can also be started in **async mode** (``?mode=async``): the POST inserts a
``running`` row, spawns the scrape as a background task, and returns ``202`` with
the run id. The client then tails ``GET .../runs/{run_id}/events`` (SSE) for live
progress and a terminal ``run.finished`` event, or cancels via
``POST .../runs/{run_id}/cancel``. Two ``GET`` routes expose the run history that
backs the Scraper-API logs UI.
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.capabilities.core.access.rate_limit import enforce_capability_rate_limit
from app.capabilities.core.billing import (
    charge_capability,
    gate_capability,
    pricing_meters,
)
from app.capabilities.core.events import run_event_bus
from app.capabilities.core.progress import progress_scope
from app.capabilities.core.runs import (
    create_pending_run,
    finalize_run,
    record_run,
    serialize_output,
)
from app.capabilities.core.store import all_capabilities
from app.capabilities.core.types import Capability, CapabilityContext
from app.db import Run, async_session_maker, get_async_session
from app.exceptions import ExternalServiceError, SurfSenseError
from app.services.web_crawl_credit_service import InsufficientCreditsError
from app.users import get_auth_context
from app.utils.rbac import check_workspace_access

logger = logging.getLogger(__name__)

_HEARTBEAT_SEC = 10
_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


class PricingMeter(BaseModel):
    """One live per-item rate a verb charges on, e.g. 3500 micro-USD per place."""

    unit: str
    micros_per_unit: int


class CapabilitySummary(BaseModel):
    """A verb's identity + input/output JSON schemas + pricing, for the playground UI."""

    name: str
    description: str
    input_schema: dict
    output_schema: dict
    # Empty list = free (billing disabled or an unmetered verb).
    pricing: list[PricingMeter] = []


class RunSummary(BaseModel):
    """Metadata row for the runs list (output body + progress log omitted)."""

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
    """Full run including input, stored output, and the coarse progress log."""

    thread_id: str | None
    input: dict | None
    output_text: str | None
    progress: list[dict] | None


def _origin_for(auth: AuthContext) -> str:
    """Session callers are the in-app UI; PAT/system callers are the public API."""
    return "ui" if getattr(auth, "method", None) == "session" else "api"


def _now_ms() -> int:
    return int(time.time() * 1000)


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, default=str)}\n\n"


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
    _register_capabilities_list(router, caps)
    _register_run_history(router)
    return router


def _register_capabilities_list(
    router: APIRouter, capabilities: list[Capability]
) -> None:
    """Register the ``GET`` that lists verbs + their input schemas for the UI."""

    # Schemas are static; pricing is attached per request because rates are
    # read live from config (env retune + restart, no rebuild).
    base_summaries = [
        (
            CapabilitySummary(
                name=capability.name,
                description=capability.description,
                input_schema=capability.input_schema.model_json_schema(),
                output_schema=capability.output_schema.model_json_schema(),
            ),
            capability.billing_unit,
        )
        for capability in capabilities
    ]

    async def list_capabilities(
        workspace_id: int,
        session: AsyncSession = Depends(get_async_session),
        auth: AuthContext = Depends(get_auth_context),
    ) -> list[CapabilitySummary]:
        await check_workspace_access(session, auth, workspace_id)
        return [
            summary.model_copy(
                update={"pricing": [PricingMeter(**m) for m in pricing_meters(unit)]}
            )
            for summary, unit in base_summaries
        ]

    router.add_api_route(
        "/workspaces/{workspace_id}/scrapers/capabilities",
        list_capabilities,
        methods=["GET"],
        response_model=list[CapabilitySummary],
        name="scraper:list_capabilities",
    )


async def _execute_async_run(
    *,
    run_id: str,
    workspace_id: int,
    capability: str,
    unit,
    executor,
    payload,
) -> None:
    """Run a scrape in the background: stream progress, charge, finalize the row.

    Owns its own DB sessions (the request session is long gone). Cancellation is
    finalized by the cancel endpoint, so here we simply let ``CancelledError``
    propagate. Every other failure finalizes the row as ``error`` and emits a
    terminal event so subscribers unblock.
    """
    prefixed = f"run_{run_id}"
    started = time.perf_counter()
    with progress_scope(run_id=run_id, bus=run_event_bus) as reporter:
        run_event_bus.publish(
            run_id,
            {
                "type": "run.started",
                "run_id": prefixed,
                "capability": capability,
                "ts": _now_ms(),
            },
        )
        try:
            output = await executor(payload)
        except asyncio.CancelledError:
            raise
        except (SurfSenseError, HTTPException) as exc:
            await _finalize_async(
                run_id, status="error", error=str(exc), started=started,
                progress=reporter.coarse,
            )
            _publish_finished(run_id, "error", error=str(exc))
            return
        except Exception:
            logger.exception("async run %s failed with an upstream error", run_id)
            await _finalize_async(
                run_id,
                status="error",
                error=f"The '{capability}' capability failed due to an upstream error.",
                started=started,
                progress=reporter.coarse,
            )
            _publish_finished(run_id, "error", error="upstream error")
            return

        duration_ms = int((time.perf_counter() - started) * 1000)
        cost_micros: int | None
        try:
            async with async_session_maker() as session:
                ctx = CapabilityContext(session=session, workspace_id=workspace_id)
                cost_micros = await charge_capability(output, unit, ctx)
        except Exception:
            logger.exception("charge failed for async run %s", run_id)
            cost_micros = None

        serialized = serialize_output(output)
        await _finalize_async(
            run_id,
            status="success",
            serialized=serialized,
            started=started,
            duration_ms=duration_ms,
            cost_micros=cost_micros,
            progress=reporter.coarse,
        )
        _publish_finished(run_id, "success", item_count=serialized.item_count)


async def _finalize_async(
    run_id: str,
    *,
    status: str,
    serialized=None,
    error: str | None = None,
    started: float | None = None,
    duration_ms: int | None = None,
    cost_micros: int | None = None,
    progress: list[dict] | None = None,
) -> None:
    if duration_ms is None and started is not None:
        duration_ms = int((time.perf_counter() - started) * 1000)
    async with async_session_maker() as session:
        await finalize_run(
            session,
            run_id=run_id,
            status=status,
            serialized=serialized,
            error=error,
            duration_ms=duration_ms,
            cost_micros=cost_micros,
            progress=progress,
        )


def _publish_finished(run_id: str, status: str, **extra) -> None:
    """Emit the terminal event to subscribers, then drop the run's bus state."""
    event = {
        "type": "run.finished",
        "run_id": f"run_{run_id}",
        "status": status,
        "ts": _now_ms(),
    }
    event.update(extra)
    run_event_bus.publish(run_id, event)
    run_event_bus.close(run_id)


def _log_task_result(run_id: str, task: asyncio.Task) -> None:
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.error("async run %s task crashed: %r", run_id, exc)


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
        mode: str = Query(default="sync", pattern="^(sync|async)$"),
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

        if mode == "async":
            run_id = await create_pending_run(
                session,
                workspace_id=workspace_id,
                capability=name,
                origin=origin,
                input=input_dump,
                user_id=user_id,
            )
            if run_id is None:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Could not start run.",
                )
            task = asyncio.create_task(
                _execute_async_run(
                    run_id=run_id,
                    workspace_id=workspace_id,
                    capability=name,
                    unit=unit,
                    executor=executor,
                    payload=payload,
                )
            )
            run_event_bus.register_task(run_id, task)
            task.add_done_callback(lambda t: _log_task_result(run_id, t))
            return JSONResponse(
                status_code=status.HTTP_202_ACCEPTED,
                content={"run_id": f"run_{run_id}", "status": "running"},
            )

        # Sync mode: block until done, persisting the coarse progress log.
        with progress_scope() as reporter:
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
                    progress=reporter.coarse,
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
                    progress=reporter.coarse,
                )
                raise ExternalServiceError(
                    f"The '{name}' capability failed due to an upstream error.",
                    code="CAPABILITY_UPSTREAM_ERROR",
                ) from exc

            duration_ms = int((time.perf_counter() - started) * 1000)
            cost_micros = await charge_capability(output, unit, ctx)

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
                cost_micros=cost_micros,
                progress=reporter.coarse,
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


def _parse_run_uuid(run_id: str) -> uuid.UUID:
    raw = run_id[len("run_") :] if run_id.startswith("run_") else run_id
    try:
        return uuid.UUID(raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Run not found."
        ) from exc


async def _load_run(
    session: AsyncSession, workspace_id: int, parsed_id: uuid.UUID
) -> Run:
    row = (
        await session.execute(
            select(Run).where(Run.id == parsed_id, Run.workspace_id == workspace_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Run not found."
        )
    return row


def _register_run_history(router: APIRouter) -> None:
    """Register the run list/detail + live-events + cancel routes."""

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
        parsed_id = _parse_run_uuid(run_id)
        row = await _load_run(session, workspace_id, parsed_id)
        return _to_detail(row)

    async def stream_run_events(
        workspace_id: int,
        run_id: str,
        session: AsyncSession = Depends(get_async_session),
        auth: AuthContext = Depends(get_auth_context),
    ):
        """SSE tail of a run's progress: replay buffered events, then live.

        Note: the request ``session`` must not be used inside the generator (it
        is torn down once the response starts streaming) — the generator opens
        its own session for the terminal snapshot.
        """
        await check_workspace_access(session, auth, workspace_id)
        parsed_id = _parse_run_uuid(run_id)
        await _load_run(session, workspace_id, parsed_id)  # authz + 404
        raw = str(parsed_id)

        async def gen():
            queue = run_event_bus.subscribe(raw)
            try:
                replayed = list(run_event_bus.replay(raw))
                for event in replayed:
                    yield _sse(event)
                if any(e.get("type") == "run.finished" for e in replayed):
                    return
                if run_event_bus.get_task(raw) is None:
                    # Not actively streaming (finished before we attached, or a
                    # sync/agent run) — snapshot the terminal state and close.
                    async with async_session_maker() as snap_session:
                        row = (
                            await snap_session.execute(
                                select(Run).where(
                                    Run.id == parsed_id,
                                    Run.workspace_id == workspace_id,
                                )
                            )
                        ).scalar_one_or_none()
                    yield _sse(
                        {
                            "type": "run.finished",
                            "run_id": f"run_{raw}",
                            "status": row.status if row else "error",
                            "item_count": row.item_count if row else 0,
                            "error": row.error if row else None,
                            "ts": _now_ms(),
                        }
                    )
                    return
                while True:
                    try:
                        event = await asyncio.wait_for(
                            queue.get(), timeout=_HEARTBEAT_SEC
                        )
                    except TimeoutError:
                        yield _sse({"type": "run.heartbeat", "ts": _now_ms()})
                        continue
                    yield _sse(event)
                    if event.get("type") == "run.finished":
                        return
            finally:
                run_event_bus.unsubscribe(raw, queue)

        return StreamingResponse(
            gen(), media_type="text/event-stream", headers=_SSE_HEADERS
        )

    async def cancel_run(
        workspace_id: int,
        run_id: str,
        session: AsyncSession = Depends(get_async_session),
        auth: AuthContext = Depends(get_auth_context),
    ):
        await check_workspace_access(session, auth, workspace_id)
        parsed_id = _parse_run_uuid(run_id)
        row = await _load_run(session, workspace_id, parsed_id)
        if row.status != "running":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Run is not in progress.",
            )
        raw = str(parsed_id)
        task = run_event_bus.get_task(raw)
        if task is not None and not task.done():
            task.cancel()
        # No output produced -> nothing charged. ponytail: any pre-cancel captcha
        # attempts go unbilled; upgrade path is charging from progress counters.
        async with async_session_maker() as cancel_session:
            await finalize_run(
                cancel_session,
                run_id=raw,
                status="cancelled",
                error="Cancelled by user",
            )
        _publish_finished(raw, "cancelled")
        return JSONResponse(content={"run_id": f"run_{raw}", "status": "cancelled"})

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
    router.add_api_route(
        "/workspaces/{workspace_id}/scrapers/runs/{run_id}/events",
        stream_run_events,
        methods=["GET"],
        name="scraper:stream_run_events",
    )
    router.add_api_route(
        "/workspaces/{workspace_id}/scrapers/runs/{run_id}/cancel",
        cancel_run,
        methods=["POST"],
        name="scraper:cancel_run",
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
        progress=row.progress,
    )
