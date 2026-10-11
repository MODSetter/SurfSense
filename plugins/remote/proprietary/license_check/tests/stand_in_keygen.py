"""Keygen's validate-key action on loopback, answering each key with the code a test gives it."""

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

ACCOUNT = "stand-in-account"


class StandInKeygen:
    def __init__(self, codes: dict[str, str]) -> None:
        self.codes = codes
        self.validated: list[str] = []
        self.down = False
        self.app = Starlette(
            routes=[
                Route(
                    f"/v1/accounts/{ACCOUNT}/licenses/actions/validate-key",
                    self._validate,
                    methods=["POST"],
                )
            ]
        )

    async def _validate(self, request: Request) -> JSONResponse:
        if self.down:
            return JSONResponse({}, status_code=503)
        key = (await request.json())["meta"]["key"]
        self.validated.append(key)
        code = self.codes.get(key, "NOT_FOUND")
        return JSONResponse({"meta": {"valid": code == "VALID", "code": code}})
