"""`POST /license/refresh`: the license's current file, for the app to pick up a renewal.

A renewal extends the same key, so the app sends the key it already holds and
gets a fresh file carrying the new expiry. The key travels in the body, since a
URL ends up in logs. The app never contacts Keygen itself (ADR 0019).

Spec: ``docs/architecture/license/portal.md``.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request, Response, status

from license.fresh_file import fresh_file_for_key
from license.rate_limit import enforce_refresh_rate_limit
from license.schemas import LicenseRefreshRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/license", tags=["license"])


@router.post("/refresh")
async def refresh_license(payload: LicenseRefreshRequest, request: Request) -> Response:
    """200 with the file, 404 for a key no license has, 403 for one not in good standing."""
    await enforce_refresh_rate_limit(request, key=payload.key)
    try:
        keyed = await fresh_file_for_key(payload.key)
    except Exception:
        logger.exception("License refresh failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not check that license right now. Try again later.",
        ) from None

    if keyed.code == "NOT_FOUND":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No license has that key.",
        )
    if keyed.certificate is None:
        # The key holder is the licensee, so naming the state leaks nothing.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"This license cannot be refreshed ({keyed.code}). Contact support.",
        )
    return Response(
        content=keyed.certificate,
        media_type="text/plain",
        headers={
            "Content-Disposition": 'attachment; filename="surfsense.lic"',
            "Cache-Control": "no-store",
        },
    )
