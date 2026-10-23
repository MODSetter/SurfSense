"""The one SurfSense backend: `/health`, the license portal and every plugin, in one FastAPI app."""

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from host.app import ServedPlugins
from license.portal import LOCAL_ORIGINS, site_origins


def backend_app(
    plugins: ServedPlugins, license_portal: APIRouter | None = None
) -> FastAPI:
    # No /docs or /openapi.json: nothing here is a public API to browse.
    # The plugins' startup and shutdown are the process's: no other module holds any.
    app = FastAPI(
        routes=[Route("/health", _health), *plugins.routes],
        lifespan=plugins.lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    if license_portal is not None:
        app.include_router(license_portal)
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
