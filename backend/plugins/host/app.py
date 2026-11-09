"""The plugin host: `/cancel`, `/license`, `/admin/usage`, and each plugin's MCP server at `/<id>/mcp`."""

import logging
from collections.abc import AsyncIterator, Callable, Collection
from contextlib import AbstractAsyncContextManager, AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

import anyio
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import BaseRoute, Mount, Route
from starlette.types import ASGIApp

from host.calls_in_flight import CallsInFlight
from host.cancel_broadcast import CancelBroadcast, LocalBroadcast
from host.cancel_route import cancel_route
from host.cancellable_calls import CancellableCalls
from host.license_route import license_route
from host.mounted_plugins import MountedPlugin, mounted_plugins
from host.post_only import PostOnly
from host.refused_unless_allowed import RefusedUnlessAllowed
from host.usage_meter.admin_routes import usage_admin_routes
from host.usage_meter.metered_calls import MeteredCalls
from host.usage_meter.usage_meter import UsageMeter

logger = logging.getLogger(__name__)

# backend/plugins/, where the host's folder sits beside the plugins.
PLUGINS_ROOT = Path(__file__).resolve().parent.parent
# How long one plugin's lifespan may take to close its pools at shutdown.
CLOSE_SECONDS = 10.0


@dataclass(frozen=True)
class ServedPlugins:
    """The plugins' routes, and the startup and shutdown they share, for an app to mount."""

    routes: list[BaseRoute]
    lifespan: Callable[[Starlette], AbstractAsyncContextManager[None]]


def host_app(
    root: Path = PLUGINS_ROOT,
    plugins: Collection[str] | None = None,
    broadcast: CancelBroadcast | None = None,
    lifespans: bool = True,
    meter: UsageMeter | None = None,
    usage_admin_token: str | None = None,
) -> Starlette:
    """The plugins served alone, with `/health`; the backend mounts them beside its other modules."""
    served = served_plugins(
        root, plugins, broadcast, lifespans, meter, usage_admin_token
    )
    return Starlette(
        routes=[Route("/health", _health), *served.routes], lifespan=served.lifespan
    )


def served_plugins(
    root: Path = PLUGINS_ROOT,
    plugins: Collection[str] | None = None,
    broadcast: CancelBroadcast | None = None,
    lifespans: bool = True,
    meter: UsageMeter | None = None,
    usage_admin_token: str | None = None,
) -> ServedPlugins:
    """`plugins` limits the container to some; `broadcast` reaches the other copies.

    `lifespans=False` holds no plugin's `lifespan`: nothing is warmed at startup, and
    no shared pool is closed at shutdown. `meter` counts each plugin's tool calls;
    `usage_admin_token` serves its records at `/admin/usage`.
    """
    mounted = mounted_plugins(root, plugins)
    calls = CallsInFlight()
    stops = broadcast or LocalBroadcast()

    @asynccontextmanager
    async def lifespan(_: Starlette) -> AsyncIterator[None]:
        async with AsyncExitStack() as stack:
            # Entered first to close last, once the calls using their pools have ended.
            held = await stack.enter_async_context(anyio.create_task_group())
            kept = [
                _Kept(plugin) for plugin in mounted if plugin.lifespan and lifespans
            ]
            for plugin in kept:
                held.start_soon(plugin.run)
            stack.push_async_callback(_close, kept)
            if meter is not None:
                # Entered before the servers, so it writes once more after their calls end.
                await stack.enter_async_context(meter.running())
            for plugin in mounted:
                await stack.enter_async_context(plugin.server.session_manager.run())
            listening = await stack.enter_async_context(anyio.create_task_group())
            await listening.start(stops.listen, calls.cancel)
            yield
            listening.cancel_scope.cancel()

    routes: list[BaseRoute] = [cancel_route(stops)]
    # One license unlocks every paid plugin, so any one's check answers for all.
    paid = next((plugin.access for plugin in mounted if plugin.access), None)
    if paid is not None:
        routes.append(license_route(paid))
    if meter is not None and usage_admin_token:
        routes += usage_admin_routes(meter, usage_admin_token)
    routes += [
        Mount(f"/{plugin.id}", app=_served(plugin, calls, meter)) for plugin in mounted
    ]
    return ServedPlugins(routes, lifespan)


def _served(
    plugin: MountedPlugin, calls: CallsInFlight, meter: UsageMeter | None
) -> ASGIApp:
    # No session is kept, so any copy of the host answers any request. Reached by
    # its public hostname, not a user's loopback, so the SDK's DNS-rebinding guard
    # for local servers does not apply.
    app: ASGIApp = CancellableCalls(
        plugin.server.streamable_http_app(host="0.0.0.0", stateless_http=True), calls
    )
    # A plugin without `access` is open to anyone. SurfSense offers no free plugin
    # yet; one will be limited per IP address here, as the plugins proposal says.
    if plugin.access is not None:
        app = RefusedUnlessAllowed(app, plugin.access)
    # Outside the license check, so refused calls are counted too.
    if meter is not None:
        app = MeteredCalls(app, plugin.id, plugin.server, meter)
    # Outermost, so a refused GET costs no license check.
    return PostOnly(app)


class _Kept:
    """One plugin's lifespan, held open by a task of its own.

    Startup waits for none of them, so a slow warm-up never delays `/health`, and
    one that fails is logged while the plugin is still served.
    """

    def __init__(self, plugin: MountedPlugin) -> None:
        self.plugin = plugin
        self.scope = anyio.CancelScope()
        self.entered = False
        self.leave = anyio.Event()
        self.left = anyio.Event()

    async def run(self) -> None:
        assert self.plugin.lifespan is not None
        try:
            with self.scope:
                async with self.plugin.lifespan():
                    self.entered = True
                    await self.leave.wait()
        except Exception:
            logger.exception("[host] %s: its lifespan failed", self.plugin.id)
        finally:
            self.left.set()

    async def close(self) -> None:
        if not self.entered:
            # Still starting: nothing to close yet.
            self.scope.cancel()
        self.leave.set()
        with anyio.move_on_after(CLOSE_SECONDS) as waited:
            await self.left.wait()
        if waited.cancelled_caught:
            logger.warning(
                "[host] %s: its lifespan took over %ss to close",
                self.plugin.id,
                CLOSE_SECONDS,
            )
            self.scope.cancel()


async def _close(kept: list[_Kept]) -> None:
    """Last mounted first, one at a time, as an exit stack would."""
    for plugin in reversed(kept):
        await plugin.close()


async def _health(_: Request) -> PlainTextResponse:
    return PlainTextResponse("ok")
