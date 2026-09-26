"""Installs as jobs: start one, list them, follow them, cancel one.

A job outlives the request that started it, so a reload, a second window or
another settings page all read the same install.
"""

import asyncio
import contextlib
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse

from api.dependencies import SessionDep, transact
from modules.egress import service as egress
from modules.llm.catalog.local.dependencies import LocalCatalogDep
from modules.llm.catalog.local.install_jobs.describe import describe_install
from modules.llm.catalog.local.install_jobs.job import InstallJob
from modules.llm.catalog.local.install_jobs.schemas import (
    InstallJobRead,
    InstallJobsRead,
)
from modules.llm.catalog.local.install_jobs.steps import install_steps
from modules.llm.catalog.local.schemas import InstallRequest

router = APIRouter()

STALE_ID = "catalog id is stale or unknown; refresh the catalog"

# A frame this often even when nothing changed keeps the connection, and any
# proxy, alive, and resyncs a screen that missed one.
_HEARTBEAT_SECONDS = 15


def _read(job: InstallJob) -> InstallJobRead:
    return InstallJobRead(
        id=job.id,
        catalog_id=job.catalog_id,
        label=job.label,
        model_types=list(job.model_types),
        select=job.select,
        model_type=job.model_type,
        event=job.event,
    )


@router.post(
    "/installs",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=InstallJobRead,
    summary="Start downloading a model, queued behind any install ahead of it",
)
async def start_install(
    payload: InstallRequest,
    request: Request,
    service: LocalCatalogDep,
    session: SessionDep,
) -> InstallJobRead:
    plan = service.resolve_install(payload.catalog_id)
    if plan is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, STALE_ID)
    await transact(session, egress.require, egress.HUGGINGFACE)

    label, model_types = describe_install(service, payload.catalog_id, plan)
    session_factory = request.app.state.session_factory
    job = service.install_jobs().start(
        catalog_id=payload.catalog_id,
        label=label,
        model_types=model_types,
        select=payload.select,
        model_type=payload.model_type,
        steps=lambda: install_steps(
            service,
            plan,
            select=payload.select,
            model_type=payload.model_type,
            session_factory=session_factory,
        ),
    )
    return _read(job)


@router.get("/installs", response_model=InstallJobsRead, summary="Every install")
def list_installs(service: LocalCatalogDep) -> InstallJobsRead:
    return InstallJobsRead(jobs=[_read(j) for j in service.install_jobs().list()])


@router.get(
    "/installs/events",
    summary="Every install, as NDJSON: now, then again on each change",
)
async def follow_installs(service: LocalCatalogDep) -> StreamingResponse:
    jobs = service.install_jobs()

    async def frames() -> AsyncIterator[bytes]:
        changed = jobs.subscribe()
        try:
            while True:
                changed.clear()
                read = InstallJobsRead(jobs=[_read(j) for j in jobs.list()])
                yield (read.model_dump_json() + "\n").encode()
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(changed.wait(), _HEARTBEAT_SECONDS)
        finally:
            jobs.unsubscribe(changed)

    return StreamingResponse(
        frames(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/installs/{job_id}", response_model=InstallJobRead, summary="One install")
def read_install(job_id: str, service: LocalCatalogDep) -> InstallJobRead:
    job = service.install_jobs().get(job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"no install {job_id}")
    return _read(job)


@router.delete(
    "/installs/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel an install; a partial file resumes next time",
)
def cancel_install(job_id: str, service: LocalCatalogDep) -> Response:
    if not service.install_jobs().cancel(job_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"no running install {job_id}")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
