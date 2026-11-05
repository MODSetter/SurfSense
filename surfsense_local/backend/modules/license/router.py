from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from api.dependencies import SessionDep
from modules.license.renewal.license_refresh import refresh_license
from modules.license.renewal.refresh_failed import RefreshFailedError
from modules.license.service import (
    LicenseStatus,
    import_certificate,
    remove_certificate,
)
from modules.license.service import status as license_status
from modules.license.verify import LicenseRejectedError

router = APIRouter(prefix="/license", tags=["license"])


class LicenseImport(BaseModel):
    certificate: str


@router.get("/status", response_model=LicenseStatus, summary="Read the license")
def read_status(session: SessionDep) -> LicenseStatus:
    return license_status(session)


@router.put("", response_model=LicenseStatus, summary="Import a license file")
def put_license(payload: LicenseImport, session: SessionDep) -> LicenseStatus:
    try:
        return import_certificate(session, payload.certificate)
    except LicenseRejectedError as rejected:
        raise _rejected(rejected) from rejected


@router.post(
    "/refresh", response_model=LicenseStatus, summary="Fetch the renewed license file"
)
async def refresh_file(session: SessionDep) -> LicenseStatus:
    """Settings' check for a renewal: the license server's current file for the stored key."""
    try:
        return await refresh_license(session)
    except RefreshFailedError as failed:
        raise _refresh_failed(failed) from failed
    except LicenseRejectedError as rejected:
        raise _rejected(rejected) from rejected


@router.delete("", status_code=status.HTTP_204_NO_CONTENT, summary="Remove the license")
def delete_license(session: SessionDep) -> None:
    remove_certificate(session)


def _rejected(rejected: LicenseRejectedError) -> HTTPException:
    return HTTPException(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        {"code": rejected.code, "message": REASONS[rejected.code]},
    )


def _refresh_failed(failed: RefreshFailedError) -> HTTPException:
    refusal = failed.refusal
    if refusal is None:
        status_code, message = REFRESH_FAILURES[failed.code]
        return HTTPException(status_code, {"code": failed.code, "message": message})
    # The host and destination too, so the UI can ask about them as for `egress_disabled`.
    return HTTPException(
        status.HTTP_403_FORBIDDEN,
        {
            "code": failed.code,
            "message": f"Checking for a renewal reaches {refusal.host}, "
            "which is off in Settings > Network.",
            "destination": refusal.destination,
            "host": refusal.host,
            "hosts": refusal.hosts,
            "purpose": refusal.purpose,
        },
    )


REASONS = {
    "not_a_license_file": "This is not a SurfSense license file.",
    "unsupported_algorithm": "This license file uses an algorithm this version cannot check.",
    "bad_signature": "This license file was not issued by SurfSense, or it was altered.",
    "clock_untrusted": "This computer's clock is behind the time the license was issued.",
    "file_expired": "This license file has expired; request a fresh copy at surfsense.com/license.",
}

REFRESH_FAILURES = {
    "license_none": (
        status.HTTP_409_CONFLICT,
        "No license is added, so there is none to renew.",
    ),
    "refresh_not_found": (
        status.HTTP_404_NOT_FOUND,
        "SurfSense's license server has no license with this key.",
    ),
    "refresh_refused": (
        status.HTTP_403_FORBIDDEN,
        "SurfSense's license server will not renew this license. Contact support.",
    ),
    "refresh_rate_limited": (
        status.HTTP_429_TOO_MANY_REQUESTS,
        "This license was checked too often; try again in an hour.",
    ),
    "refresh_unavailable": (
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "SurfSense's license server could not send a renewed file; try again later.",
    ),
}
