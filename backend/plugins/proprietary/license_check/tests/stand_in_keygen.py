"""Keygen's validate-key action on loopback, answering each key with the code a test gives it."""

import uuid

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

ACCOUNT = "stand-in-account"


def license_id_of(key: str) -> str:
    """The id Keygen gives the license with `key`: a UUID that does not hold the key."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"stand-in-license:{key}"))


def accounts_url(base: str) -> str:
    """`KEYGEN_API_URL` for a stand-in served at `base`: its accounts endpoint, as the backend's."""
    return f"{base}/v1/accounts"


class StandInKeygen:
    def __init__(self, codes: dict[str, str]) -> None:
        self.codes = codes
        self.validated: list[str] = []
        # Each request's Host and X-Forwarded-Proto, as a self-hosted Keygen reads them.
        self.seen_headers: list[tuple[str | None, str | None]] = []
        self.down = False
        self.garbled = False
        self.app = Starlette(
            routes=[
                Route(
                    f"/v1/accounts/{ACCOUNT}/licenses/actions/validate-key",
                    self._validate,
                    methods=["POST"],
                )
            ]
        )

    async def _validate(self, request: Request) -> Response:
        self.seen_headers.append(
            (request.headers.get("host"), request.headers.get("x-forwarded-proto"))
        )
        if self.down:
            return JSONResponse({}, status_code=503)
        if self.garbled:
            return Response("<html>not Keygen</html>", media_type="text/html")
        key = (await request.json())["meta"]["key"]
        self.validated.append(key)
        code = self.codes.get(key, "NOT_FOUND")
        # Keygen answers a key it does not know with `data: null`.
        data = (
            {"id": license_id_of(key), "type": "licenses"}
            if key in self.codes
            else None
        )
        return JSONResponse(
            {"meta": {"valid": code == "VALID", "code": code}, "data": data}
        )
