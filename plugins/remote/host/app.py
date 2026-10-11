"""The plugin host: `/health`, and each plugin's MCP server at `/<id>/mcp`."""

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Mount, Route
from starlette.types import ASGIApp

from host.mounted_plugins import MountedPlugin, mounted_plugins
from host.refused_unless_allowed import RefusedUnlessAllowed

# plugins/remote/, where the host's folder sits beside the plugins.
PLUGINS_ROOT = Path(__file__).resolve().parent.parent


def host_app(root: Path = PLUGINS_ROOT) -> Starlette:
    plugins = mounted_plugins(root)

    @asynccontextmanager
    async def lifespan(_: Starlette) -> AsyncIterator[None]:
        async with AsyncExitStack() as stack:
            for plugin in plugins:
                await stack.enter_async_context(plugin.server.session_manager.run())
            yield

    routes: list[Route | Mount] = [Route("/health", _health)]
    routes += [Mount(f"/{plugin.id}", app=_served(plugin)) for plugin in plugins]
    return Starlette(routes=routes, lifespan=lifespan)


def _served(plugin: MountedPlugin) -> ASGIApp:
    # Reached by its public hostname, not on a user's loopback, so the SDK's
    # DNS-rebinding guard for local servers does not apply.
    app = plugin.server.streamable_http_app(host="0.0.0.0")
    return app if plugin.access is None else RefusedUnlessAllowed(app, plugin.access)


async def _health(_: Request) -> PlainTextResponse:
    return PlainTextResponse("ok")
