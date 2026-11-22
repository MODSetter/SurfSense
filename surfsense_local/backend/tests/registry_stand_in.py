"""SurfSense's plugin host serving a signed registry, with one plugin's server beside it."""

import base64
import hashlib
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from mcp.server.mcpserver import MCPServer
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Mount, Route
from starlette.types import ASGIApp

SVG = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1"><rect width="1" height="1"/></svg>'


def entry(plugin_id: str = "notes", **changed: Any) -> dict[str, Any]:
    """A valid community entry on the plugin host, with `changed` fields replaced."""
    listed = {
        "id": plugin_id,
        "kind": "remote",
        "verification": "community",
        "name": plugin_id.title(),
        "description": f"Search the {plugin_id}.",
        "author": "Notes Project",
        "url": f"https://plugins.surfsense.com/{plugin_id}/mcp",
        "auth": {"type": "none"},
        "hosts": ["plugins.surfsense.com"],
        "access": "free",
        "privacy_policy": "https://example.com/privacy",
    }
    return {**listed, **changed}


class StandInRegistry:
    """What the host serves; `publish` replaces it, `serve_bytes` serves anything at all."""

    def __init__(self) -> None:
        self.key = Ed25519PrivateKey.generate()
        self.body = b""
        self.sig = b""
        self.icons: dict[str, bytes] = {}
        self.requests: list[str] = []
        self.publish([])

    @property
    def public_key_hex(self) -> str:
        return self.key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()

    def publish(
        self,
        plugins: list[dict[str, Any]],
        removed: list[dict[str, str]] | None = None,
        generated_at: str = "2026-10-10T12:00:00Z",
        schema_version: int = 1,
        icons: dict[str, bytes] | None = None,
    ) -> None:
        """Signed as CI signs it: each icon's hash added to the entry naming it."""
        self.icons = dict(icons or {})
        for listed in plugins:
            icon = self.icons.get(listed.get("icon", ""))
            if icon is not None and "icon_sha256" not in listed:
                listed["icon_sha256"] = hashlib.sha256(icon).hexdigest()
        document = {
            "schema_version": schema_version,
            "generated_at": generated_at,
            "plugins": plugins,
            "removed": removed or [],
        }
        self.serve_bytes(json.dumps(document).encode())

    def serve_bytes(
        self, body: bytes, sign_with: Ed25519PrivateKey | None = None
    ) -> None:
        self.body = body
        self.sig = base64.b64encode((sign_with or self.key).sign(body))

    def app(self, servers: dict[str, ASGIApp], mcp: list[MCPServer]) -> Starlette:
        async def listing(request: Request) -> Response:
            self.requests.append(request.url.path)
            return Response(self.body, media_type="application/json")

        async def signature(request: Request) -> Response:
            self.requests.append(request.url.path)
            return Response(self.sig, media_type="text/plain")

        async def icon(request: Request) -> Response:
            self.requests.append(request.url.path)
            found = self.icons.get(request.path_params["name"])
            return Response(status_code=404) if found is None else Response(found)

        @asynccontextmanager
        async def lifespan(_: Starlette) -> AsyncIterator[None]:
            managers = [server.session_manager.run() for server in mcp]
            for manager in managers:
                await manager.__aenter__()
            try:
                yield
            finally:
                for manager in reversed(managers):
                    await manager.__aexit__(None, None, None)

        return Starlette(
            routes=[
                Route("/plugins.json", listing),
                Route("/plugins.json.sig", signature),
                Route("/icons/{name}", icon),
                *(
                    Mount(f"/{plugin_id}", app=app)
                    for plugin_id, app in servers.items()
                ),
            ],
            lifespan=lifespan,
        )
