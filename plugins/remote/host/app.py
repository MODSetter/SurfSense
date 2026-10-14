"""The plugin host: `/health`, `/cancel`, and each plugin's MCP server at `/<id>/mcp`."""

from collections.abc import AsyncIterator, Collection
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path

import anyio
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Mount, Route
from starlette.types import ASGIApp

from host.calls_in_flight import CallsInFlight
from host.cancel_broadcast import CancelBroadcast, LocalBroadcast
from host.cancel_route import cancel_route
from host.cancellable_calls import CancellableCalls
from host.mounted_plugins import MountedPlugin, mounted_plugins
from host.refused_unless_allowed import RefusedUnlessAllowed

# plugins/remote/, where the host's folder sits beside the plugins.
PLUGINS_ROOT = Path(__file__).resolve().parent.parent


def host_app(
    root: Path = PLUGINS_ROOT,
    plugins: Collection[str] | None = None,
    broadcast: CancelBroadcast | None = None,
) -> Starlette:
    """`plugins` limits the container to some; `broadcast` reaches the other copies."""
    mounted = mounted_plugins(root, plugins)
    calls = CallsInFlight()
    stops = broadcast or LocalBroadcast()

    @asynccontextmanager
    async def lifespan(_: Starlette) -> AsyncIterator[None]:
        async with AsyncExitStack() as stack:
            for plugin in mounted:
                await stack.enter_async_context(plugin.server.session_manager.run())
            listening = await stack.enter_async_context(anyio.create_task_group())
            await listening.start(stops.listen, calls.cancel)
            yield
            listening.cancel_scope.cancel()

    routes: list[Route | Mount] = [Route("/health", _health), cancel_route(stops)]
    routes += [Mount(f"/{plugin.id}", app=_served(plugin, calls)) for plugin in mounted]
    return Starlette(routes=routes, lifespan=lifespan)


def _served(plugin: MountedPlugin, calls: CallsInFlight) -> ASGIApp:
    # No session is kept, so any copy of the host answers any request. Reached by
    # its public hostname, not a user's loopback, so the SDK's DNS-rebinding guard
    # for local servers does not apply.
    app: ASGIApp = CancellableCalls(
        plugin.server.streamable_http_app(host="0.0.0.0", stateless_http=True), calls
    )
    # A plugin without `access` is open to anyone. SurfSense offers no free plugin
    # yet; one will be limited per IP address here, as the plugins proposal says.
    return app if plugin.access is None else RefusedUnlessAllowed(app, plugin.access)


async def _health(_: Request) -> PlainTextResponse:
    return PlainTextResponse("ok")
