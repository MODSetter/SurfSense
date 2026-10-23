"""The one SurfSense backend: `/health`, and each module's routes beside it."""

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from host.app import ServedPlugins


def backend_app(plugins: ServedPlugins) -> Starlette:
    # The plugins' startup and shutdown are the process's: no other module holds any.
    return Starlette(
        routes=[Route("/health", _health), *plugins.routes], lifespan=plugins.lifespan
    )


async def _health(_: Request) -> PlainTextResponse:
    return PlainTextResponse("ok")
