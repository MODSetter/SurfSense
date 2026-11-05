"""SurfSense's license server's refresh route, answering as the real one does (contract 1, producer rule 7)."""

import asyncio
from dataclasses import dataclass, field

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response
from starlette.routing import Route


@dataclass(frozen=True)
class Asked:
    path: str
    query: str
    body: dict
    user_agent: str


@dataclass
class StandInLicenseServer:
    """`files` holds each key's current file; `refusal`, an answer given instead, as
    `(status, detail)`; `asked`, every request it received."""

    files: dict[str, str] = field(default_factory=dict)
    refusal: tuple[int, object] | None = None
    delay_seconds: float = 0.0
    asked: list[Asked] = field(default_factory=list)

    def app(self) -> Starlette:
        return Starlette(
            routes=[Route("/api/v1/license/refresh", self._refresh, methods=["POST"])]
        )

    async def _refresh(self, request: Request) -> Response:
        body = await request.json()
        self.asked.append(
            Asked(
                request.url.path,
                request.url.query,
                body,
                request.headers.get("user-agent", ""),
            )
        )
        await asyncio.sleep(self.delay_seconds)
        if self.refusal is not None:
            status, detail = self.refusal
            return JSONResponse({"detail": detail}, status)
        certificate = self.files.get(body.get("key", ""))
        if certificate is None:
            return JSONResponse({"detail": "No license has that key."}, 404)
        return PlainTextResponse(
            certificate,
            headers={
                "Content-Disposition": 'attachment; filename="surfsense.lic"',
                "Cache-Control": "no-store",
            },
        )
