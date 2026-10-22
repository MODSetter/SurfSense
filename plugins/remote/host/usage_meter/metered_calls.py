"""A plugin's MCP endpoint whose tools/call requests are counted, and no other request."""

import time

from mcp.server.mcpserver import MCPServer
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from host.post_only import route_path
from host.refused_unless_allowed import was_refused
from host.replayed_body import read_body_up_to
from host.usage_meter.call_counts import UNLICENSED, CallKey
from host.usage_meter.call_outcome import CallOutcome
from host.usage_meter.tool_call import ToolCall, tool_call
from host.usage_meter.usage_meter import UsageMeter
from mcp_server.access import checked_license

# Kept in place of a name the plugin has no tool for, since the caller chose that name.
UNKNOWN_TOOL = "unknown"
# The most of a body read before the license check: an agent's tool call is a few
# kilobytes, and a longer body goes to the server uncounted.
MAX_READ_BYTES = 1024 * 1024


class MeteredCalls:
    """Outside the license check, so a refused call is counted too.

    Only the tool's name is read from the request, and kept only when the plugin has
    that tool. The arguments, the key and the thread's token are never kept.
    """

    def __init__(
        self, app: ASGIApp, plugin_id: str, server: MCPServer, meter: UsageMeter
    ) -> None:
        self.app = app
        self.plugin_id = plugin_id
        self.server = server
        self.meter = meter
        self._tools: frozenset[str] | None = None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if not (
            scope["type"] == "http"
            and scope["method"] == "POST"
            and route_path(scope).rstrip("/") == "/mcp"
        ):
            await self.app(scope, receive, send)
            return
        body, replay = await read_body_up_to(receive, MAX_READ_BYTES)
        started = await self._started(body) if body is not None else None
        if started is None:
            await self.app(scope, replay, send)
            return
        call, day = started
        await self._counted(call, day, scope, replay, send)

    async def _started(self, body: bytes) -> tuple[ToolCall, str] | None:
        """The call and its UTC day, or None for a request that is not a tools/call."""
        try:
            call = tool_call(body)
            if call is None:
                return None
            if call.tool not in await self._tool_names():
                call = ToolCall(call.request_id, UNKNOWN_TOOL)
            return call, self.meter.today()
        except Exception:
            self.meter.failures.failed("reading a call")
            return None

    async def _counted(
        self, call: ToolCall, day: str, scope: Scope, receive: Receive, send: Send
    ) -> None:
        started = time.perf_counter()
        outcome = CallOutcome(call.request_id)
        checked_license.set(None)

        async def watched(message: Message) -> None:
            await send(message)
            try:
                outcome.saw(message)
            except Exception:
                self.meter.failures.failed("reading a response")

        raised: BaseException | None = None
        try:
            await self.app(scope, receive, watched)
        except BaseException as error:
            raised = error
            raise
        finally:
            try:
                ended = outcome.outcome(was_refused(scope), raised)
                license_id = checked_license.get() or UNLICENSED
                key = CallKey(day, license_id, self.plugin_id, call.tool, ended)
                self.meter.record(key, round((time.perf_counter() - started) * 1000))
            except Exception:
                self.meter.failures.failed("counting a call")

    async def _tool_names(self) -> frozenset[str]:
        if self._tools is None:
            self._tools = frozenset(
                tool.name for tool in await self.server.list_tools()
            )
        return self._tools
