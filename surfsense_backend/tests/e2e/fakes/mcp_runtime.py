"""Shared strict MCP streamable-HTTP runtime fake for E2E tests."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

ListToolsFn = Callable[[], Any | Awaitable[Any]]
CallToolFn = Callable[[str, dict[str, Any]], Any | Awaitable[Any]]


@dataclass(frozen=True)
class _RuntimeHandler:
    expected_bearer: str
    list_tools: ListToolsFn
    call_tool: CallToolFn


_HANDLERS: dict[str, _RuntimeHandler] = {}


class _StrictFakeMixin:
    _component_name: str = "<unknown>"

    def __getattr__(self, name: str) -> Any:
        raise NotImplementedError(
            f"E2E MCP runtime fake missing surface: {self._component_name}.{name!r}. "
            "Add it to surfsense_backend/tests/e2e/fakes/mcp_runtime.py."
        )


class _FakeEndpoint(_StrictFakeMixin):
    _component_name = "streamablehttp_endpoint"

    def __init__(self, url: str, handler: _RuntimeHandler):
        self.url = url
        self.handler = handler


class _FakeStreamableHttpClient(_StrictFakeMixin):
    _component_name = "streamablehttp_client"

    def __init__(
        self, url: str, *, headers: dict[str, str] | None = None, **kwargs: Any
    ):
        del kwargs
        handler = _HANDLERS.get(url)
        if handler is None:
            raise NotImplementedError(f"Unexpected MCP streamable-http url={url!r}")

        auth = (headers or {}).get("Authorization")
        expected = f"Bearer {handler.expected_bearer}"
        if auth != expected:
            raise ValueError(
                f"Unexpected MCP Authorization header for {url!r}: {auth!r}"
            )

        self.url = url
        self.headers = headers or {}
        self.handler = handler

    async def __aenter__(self) -> tuple[_FakeEndpoint, _FakeEndpoint, None]:
        return (
            _FakeEndpoint(self.url, self.handler),
            _FakeEndpoint(self.url, self.handler),
            None,
        )

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        del exc_type, exc, tb


class _FakeClientSession(_StrictFakeMixin):
    _component_name = "ClientSession"

    def __init__(self, read: _FakeEndpoint, write: _FakeEndpoint):
        if read.handler is not write.handler:
            raise ValueError("MCP fake received mismatched read/write endpoints.")
        self.read = read
        self.write = write
        self.handler = read.handler

    async def __aenter__(self) -> _FakeClientSession:
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        del exc_type, exc, tb

    async def initialize(self) -> None:
        return None

    async def list_tools(self) -> SimpleNamespace:
        result = self.handler.list_tools()
        if inspect.isawaitable(result):
            result = await result
        return result

    async def call_tool(
        self, tool_name: str, *, arguments: dict[str, Any] | None = None
    ) -> SimpleNamespace:
        result = self.handler.call_tool(tool_name, arguments or {})
        if inspect.isawaitable(result):
            result = await result
        return result


def _fake_streamablehttp_client(
    url: str, *, headers: dict[str, str] | None = None, **kwargs: Any
) -> _FakeStreamableHttpClient:
    return _FakeStreamableHttpClient(url, headers=headers, **kwargs)


def register(
    *,
    url: str,
    expected_bearer: str,
    list_tools: ListToolsFn,
    call_tool: CallToolFn,
) -> None:
    """Register a fake streamable-HTTP MCP server by canonical MCP URL."""
    existing = _HANDLERS.get(url)
    handler = _RuntimeHandler(
        expected_bearer=expected_bearer,
        list_tools=list_tools,
        call_tool=call_tool,
    )
    if existing is not None and existing != handler:
        raise ValueError(f"MCP runtime fake handler already registered for {url!r}.")
    _HANDLERS[url] = handler


def install(active_patches: list[Any]) -> None:
    """Patch production MCP streamable-HTTP boundaries exactly once."""
    targets = [
        (
            "app.agents.multi_agent_chat.shared.tools.mcp.tool.streamablehttp_client",
            _fake_streamablehttp_client,
        ),
        ("app.agents.multi_agent_chat.shared.tools.mcp.tool.ClientSession", _FakeClientSession),
    ]
    for target, replacement in targets:
        p = patch(target, replacement)
        p.start()
        active_patches.append(p)
