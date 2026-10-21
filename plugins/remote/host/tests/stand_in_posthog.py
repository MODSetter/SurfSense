"""PostHog's batch endpoint on loopback, keeping each body the host sent it."""

import json
from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route


class StandInPostHog:
    def __init__(self) -> None:
        self.bodies: list[bytes] = []
        # Answers 503, as PostHog down would.
        self.failing = False
        self.app = Starlette(routes=[Route("/batch/", self._batch, methods=["POST"])])

    @property
    def events(self) -> list[dict[str, Any]]:
        return [event for body in self.bodies for event in json.loads(body)["batch"]]

    async def _batch(self, request: Request) -> JSONResponse:
        self.bodies.append(await request.body())
        if self.failing:
            return JSONResponse({}, 503)
        return JSONResponse({"status": 1})
