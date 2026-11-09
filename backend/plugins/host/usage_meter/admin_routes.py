"""`/admin/usage/*`: the meter's records for SurfSense's own reports, behind a bearer token.

The host serves them only when `USAGE_ADMIN_TOKEN` is set; otherwise they are 404.
"""

import hmac
from dataclasses import asdict

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from host.usage_meter.usage_meter import UsageMeter
from host.usage_meter.utc_days import is_day


def usage_admin_routes(meter: UsageMeter, token: str) -> list[Route]:
    def allowed(request: Request) -> bool:
        scheme, _, given = request.headers.get("authorization", "").partition(" ")
        return scheme.lower() == "bearer" and hmac.compare_digest(
            given.strip().encode(), token.encode()
        )

    async def first_seen(request: Request) -> JSONResponse:
        """Each license id's first day with a call, for the license cohort report."""
        if not allowed(request):
            return _unauthorized()
        return JSONResponse({"licences": await meter.first_seen()})

    async def daily(request: Request) -> JSONResponse:
        """One day's totals per plugin, tool and outcome, with no license id."""
        if not allowed(request):
            return _unauthorized()
        day = request.query_params.get("day", "")
        if not is_day(day):
            return JSONResponse({"reason": "invalid_day"}, 400)
        return JSONResponse(asdict(await meter.daily_usage(day)))

    return [
        Route("/admin/usage/first-seen", first_seen, methods=["GET"]),
        Route("/admin/usage/daily", daily, methods=["GET"]),
    ]


def _unauthorized() -> JSONResponse:
    return JSONResponse(
        {"reason": "unauthorized"}, 401, headers={"WWW-Authenticate": "Bearer"}
    )
