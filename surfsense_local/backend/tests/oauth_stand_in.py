"""A stand-in OAuth authorization server, and an MCP server that only answers its tokens.

The authorization server auto-approves: `/authorize` redirects straight back with a code,
as a user who clicked Allow. It checks PKCE and the redirect URI as a real one would.
"""

import base64
import hashlib
import secrets
from dataclasses import dataclass, field
from urllib.parse import urlencode

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response
from starlette.routing import Route
from starlette.types import ASGIApp, Receive, Scope, Send


@dataclass
class _Code:
    client_id: str
    redirect_uri: str
    challenge: str
    scope: str | None


@dataclass
class StandInAuthorizationServer:
    """`issuer` is set once it is served; tokens it issued are what the protected server accepts."""

    issuer: str = ""
    expires_in: int = 3600
    supports_client_metadata_document: bool = False
    # `/authorize` answers `error=<this>` instead of a code.
    deny_with: str | None = None
    # Refreshing answers `400 invalid_grant`, as for a revoked grant.
    refuse_refresh: bool = False
    registered: list[dict] = field(default_factory=list)
    authorize_requests: list[dict[str, str]] = field(default_factory=list)
    token_requests: list[dict[str, str]] = field(default_factory=list)
    access_tokens: set[str] = field(default_factory=set)
    _codes: dict[str, _Code] = field(default_factory=dict)
    _refresh_tokens: dict[str, str] = field(default_factory=dict)
    _issued: int = 0

    def app(self) -> Starlette:
        return Starlette(
            routes=[
                Route("/.well-known/oauth-authorization-server", self._metadata),
                Route("/register", self._register, methods=["POST"]),
                Route("/authorize", self._authorize),
                Route("/token", self._token, methods=["POST"]),
            ]
        )

    def expire_access_tokens(self) -> None:
        """Every access token stops working; refresh tokens still do."""
        self.access_tokens.clear()

    async def _metadata(self, _: Request) -> Response:
        return JSONResponse(
            {
                "issuer": self.issuer,
                "authorization_endpoint": f"{self.issuer}/authorize",
                "token_endpoint": f"{self.issuer}/token",
                "registration_endpoint": f"{self.issuer}/register",
                "response_types_supported": ["code"],
                "code_challenge_methods_supported": ["S256"],
                "token_endpoint_auth_methods_supported": ["none"],
                "client_id_metadata_document_supported": self.supports_client_metadata_document,
            }
        )

    async def _register(self, request: Request) -> Response:
        metadata = await request.json()
        self.registered.append(metadata)
        return JSONResponse(
            {**metadata, "client_id": f"client-{len(self.registered)}"}, 201
        )

    async def _authorize(self, request: Request) -> Response:
        query = dict(request.query_params)
        self.authorize_requests.append(query)
        back = {"state": query.get("state", "")}
        if self.deny_with:
            back["error"] = self.deny_with
        else:
            code = secrets.token_urlsafe(16)
            self._codes[code] = _Code(
                query["client_id"],
                query["redirect_uri"],
                query["code_challenge"],
                query.get("scope"),
            )
            back["code"] = code
        return RedirectResponse(f"{query['redirect_uri']}?{urlencode(back)}", 302)

    async def _token(self, request: Request) -> Response:
        form = dict(await request.form())
        self.token_requests.append(form)
        if form.get("grant_type") == "authorization_code":
            code = self._codes.pop(form.get("code", ""), None)
            if (
                code is None
                or code.client_id != form.get("client_id")
                or code.redirect_uri != form.get("redirect_uri")
                or _challenge(form.get("code_verifier", "")) != code.challenge
            ):
                return JSONResponse({"error": "invalid_grant"}, 400)
            return self._issue(code.client_id, code.scope)
        if form.get("grant_type") == "refresh_token":
            client_id = self._refresh_tokens.pop(form.get("refresh_token", ""), None)
            if self.refuse_refresh or client_id != form.get("client_id"):
                return JSONResponse({"error": "invalid_grant"}, 400)
            return self._issue(client_id, None)
        return JSONResponse({"error": "unsupported_grant_type"}, 400)

    def _issue(self, client_id: str, scope: str | None) -> Response:
        self._issued += 1
        access, refresh = f"at-{self._issued}", f"rt-{self._issued}"
        self.access_tokens.add(access)
        self._refresh_tokens[refresh] = client_id
        body = {
            "access_token": access,
            "token_type": "Bearer",
            "expires_in": self.expires_in,
            "refresh_token": refresh,
        }
        if scope:
            body["scope"] = scope
        return JSONResponse(body)


def _challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


class ProtectedByStandIn:
    """An MCP app answering 401 with its resource metadata unless the request carries a live token.

    Its metadata sits at `<mcp url>/prm` and names `authorization_server`, so it works
    mounted under any path, as on the stand-in plugin host.
    """

    def __init__(
        self,
        app: ASGIApp,
        server: StandInAuthorizationServer,
        authorization_server: str = "",
    ) -> None:
        self.app = app
        self.server = server
        # Defaults to the stand-in's issuer; another names a host the app must ask about.
        self.authorization_server = authorization_server
        self.authorizations: list[str | None] = []

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request = Request(scope)
        url = str(request.url.replace(query=""))
        if url.endswith("/prm"):
            await JSONResponse(
                {
                    "resource": url.removesuffix("/prm"),
                    "authorization_servers": [
                        self.authorization_server or self.server.issuer
                    ],
                }
            )(scope, receive, send)
            return
        authorization = request.headers.get("authorization")
        self.authorizations.append(authorization)
        token = (authorization or "").removeprefix("Bearer ")
        if token not in self.server.access_tokens:
            await Response(
                status_code=401,
                headers={"www-authenticate": f'Bearer resource_metadata="{url}/prm"'},
            )(scope, receive, send)
            return
        await self.app(scope, receive, send)
