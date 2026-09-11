from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from api.dependencies import SessionDep
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
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {"code": rejected.code, "message": REASONS[rejected.code]},
        ) from rejected


@router.delete("", status_code=status.HTTP_204_NO_CONTENT, summary="Remove the license")
def delete_license(session: SessionDep) -> None:
    remove_certificate(session)


REASONS = {
    "not_a_license_file": "This is not a SurfSense license file.",
    "unsupported_algorithm": "This license file uses an algorithm this version cannot check.",
    "bad_signature": "This license file was not issued by SurfSense, or it was altered.",
    "clock_untrusted": "This computer's clock is behind the time the license was issued.",
    "file_expired": "This license file has expired; download it again from your account.",
}
