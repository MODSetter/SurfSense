"""The job pack route as the app reaches it: the backend's own app over a faked Keygen.

Built per request through `backend_app`, so the portal mounts the route and the
backend's 422 handler answers a malformed body, as they do in production.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

import httpx2
from starlette.applications import Starlette

from host.app import ServedPlugins
from license.portal import license_portal
from license.tests.test_license_routes import FakeKeygen
from server.app import backend_app

PACK_ROUTE = "/api/v1/license/job-pack"
REFRESH_ROUTE = "/api/v1/license/refresh"
RUNNERS = ("workbook-rows/1",)
# The socket's peer: the proxy in front, not the caller.
PEER = ("192.0.2.1", 50000)


@asynccontextmanager
async def _no_plugins(_: Starlette) -> AsyncIterator[None]:
    yield


@dataclass
class PackPortal:
    """The faked Keygen, and the folder `JOB_PACKS_DIR` names."""

    keygen: FakeKeygen
    packs: Path

    async def post(
        self,
        path: str,
        body: object = None,
        *,
        ip: str | None = "203.0.113.1",
        headers: dict[str, str] | None = None,
        content: bytes | None = None,
    ) -> httpx2.Response:
        """`ip` is what the proxy reports in X-Real-IP; None sends no such header."""
        portal = license_portal()
        assert portal is not None
        app = backend_app(ServedPlugins([], _no_plugins), portal)
        sent = {"X-Real-IP": ip} if ip is not None else {}
        sent.update(headers or {})
        transport = httpx2.ASGITransport(app=app, client=PEER)
        async with httpx2.AsyncClient(
            transport=transport, base_url="http://portal"
        ) as client:
            if content is not None:
                sent["Content-Type"] = "application/json"
                return await client.post(path, content=content, headers=sent)
            return await client.post(path, json=body, headers=sent)

    async def ask(
        self,
        key: str,
        entitlement: str = "JOB_QUESTIONNAIRE",
        *,
        installed_version: str | None = None,
        runners: Iterable[str] = RUNNERS,
        **kw,
    ) -> httpx2.Response:
        """What the app sends for one job of its license."""
        body: dict[str, object] = {
            "key": key,
            "entitlement": entitlement,
            "runners": list(runners),
        }
        if installed_version is not None:
            body["installed_version"] = installed_version
        return await self.post(PACK_ROUTE, body, **kw)

    async def refresh(self, key: str, **kw) -> httpx2.Response:
        return await self.post(REFRESH_ROUTE, {"key": key}, **kw)
