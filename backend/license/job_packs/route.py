"""`POST /license/job-pack`: the newest job pack a license may run, as its zip (contract 6).

Checked in the contract's order, answering at the first check that fails: the
request's rules, the rate limit, the job among those SurfSense sells, the
license's validation, its jobs, the store, its jobs against every job of the
packs, the runners. The key is in the body and is never logged or echoed; the
bytes come from memory, never a redirect, so the app reaches no other host.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request, Response, status

from license.job_packs.catalog import PackSourceUnavailableError, shared_catalog
from license.job_packs.schemas import JobPackRequest
from license.job_packs.selection import Refusal, choose, is_current
from license.job_packs.verdict import license_verdict
from license.jobs import JOBS
from license.rate_limit import enforce_job_pack_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/license", tags=["license"])

_UNAVAILABLE = "Jobs cannot be downloaded right now. Try again later."


@router.post("/job-pack")
async def job_pack(payload: JobPackRequest, request: Request) -> Response:
    """200 with the zip, 204 when the app's is current, else a refusal with a code."""
    await enforce_job_pack_rate_limit(request, key=payload.key)
    if payload.entitlement not in JOBS:
        raise _refused(422, "unknown_job", "SurfSense has no job with that code.")
    try:
        verdict = await license_verdict(payload.key)
    except Exception as error:
        logger.error(
            "Keygen could not validate a job pack's license (%s)", type(error).__name__
        )
        raise _refused(
            503,
            "job_packs_unavailable",
            "Could not check that license right now. Try again later.",
        ) from None
    if verdict.code == "NOT_FOUND":
        raise _refused(404, "license_not_found", "No license has that key.")
    if verdict.code != "VALID":
        # The key holder is the licensee, so naming the state leaks nothing.
        raise _refused(
            403,
            "license_not_valid",
            f"This license cannot download jobs ({verdict.code}).",
        )
    if payload.entitlement not in verdict.jobs:
        raise _refused(
            403,
            "job_not_included",
            "This license does not include that job. Jobs come with a Business "
            "license, or its 14-day trial.",
        )

    try:
        packs = await shared_catalog().packs()
    except PackSourceUnavailableError as error:
        logger.error("No job pack can be served: %s", error)
        raise _refused(503, "job_packs_unavailable", _UNAVAILABLE) from None
    except Exception:
        logger.exception("Reading the job packs failed")
        raise _refused(503, "job_packs_unavailable", _UNAVAILABLE) from None

    choice = choose(packs, payload.entitlement, payload.runners, verdict.jobs)
    if choice.pack is None:
        raise _not_chosen(choice.refusal, payload.entitlement)

    pack = choice.pack
    headers = {
        "X-Job-Pack-Id": pack.id,
        "X-Job-Pack-Version": pack.version,
        "Cache-Control": "no-store",
    }
    if is_current(payload.installed_version, pack):
        return Response(status_code=status.HTTP_204_NO_CONTENT, headers=headers)
    return Response(
        content=pack.data,
        media_type="application/zip",
        headers={
            **headers,
            "Content-Disposition": f'attachment; filename="{pack.filename}"',
        },
    )


def _not_chosen(refusal: Refusal | None, entitlement: str) -> HTTPException:
    if refusal == "not_covered":
        # Not job_not_included: the license does list the job, and the app says so.
        return _refused(
            403,
            "pack_not_covered",
            "Every pack of that job also holds a job this license does not include.",
        )
    if refusal == "needs_newer_app":
        return _refused(
            409,
            "needs_newer_app",
            "This job needs a newer version of SurfSense. Update the app, then try again.",
        )
    # Every license with the job is refused until a pack is published: worth an alarm.
    logger.error("No job pack with a job for %s is published", entitlement)
    return _refused(503, "job_packs_unavailable", _UNAVAILABLE)


def _refused(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code, detail={"code": code, "message": message}
    )
