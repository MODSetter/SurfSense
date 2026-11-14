"""The one SurfSense backend: `/health`, the license portal and every plugin, in one FastAPI app."""

from fastapi import APIRouter, FastAPI
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response
from starlette.routing import Route

from host.app import ServedPlugins
from license.portal import LOCAL_ORIGINS, site_origins

# The license portal's prefix: every body under it may carry a license key.
_PORTAL = "/api/v1/"


def backend_app(
    plugins: ServedPlugins, license_portal: APIRouter | None = None
) -> FastAPI:
    # No /docs or /openapi.json: nothing here is a public API to browse.
    # The plugins' startup and shutdown are the process's; the license portal's router
    # brings its own, its rate limits' sweep, which including it runs inside them.
    app = FastAPI(
        routes=[Route("/health", _health), *plugins.routes],
        lifespan=plugins.lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    if license_portal is not None:
        app.include_router(license_portal)
    app.add_exception_handler(RequestValidationError, _validation_failed)
    # The success page reads the file's name from Content-Disposition.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=site_origins(),
        allow_origin_regex=LOCAL_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
        max_age=86400,
    )
    return app


async def _health(_: Request) -> PlainTextResponse:
    return PlainTextResponse("ok")


async def _validation_failed(request: Request, exc: RequestValidationError) -> Response:
    """The portal's bodies carry a license key, so a refused one is described, never echoed.

    FastAPI's own answer repeats the input, which for a missing field is the whole
    body; this covers the refresh route as well as the job packs'.
    """
    if not request.url.path.startswith(_PORTAL):
        return await request_validation_exception_handler(request, exc)
    return JSONResponse(
        status_code=422,
        content={
            "detail": [
                {"type": error["type"], "loc": list(error["loc"]), "msg": error["msg"]}
                for error in exc.errors()
            ]
        },
    )
