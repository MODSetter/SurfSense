"""The answer a route that would reach SurfSense's licence server gives while licensing is off."""

from fastapi import HTTPException, status

from modules.license.licensing import licensing_on

CODE = "licensing_off"


def refuse_while_licensing_off() -> None:
    """Raises 409 `licensing_off` before anything is sent: no server is there to answer."""
    if not licensing_on():
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "code": CODE,
                "message": "SurfSense is free, so there is no license to renew "
                "and no job pack to download: every job runs as it is.",
            },
        )
